import logging
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.concurrency import run_in_threadpool

from app.errors import APIError
from app.storage import remove_file, save_file

logger = logging.getLogger("uvicorn.error")


async def create_recording(
    upload: UploadFile | None, engine: AsyncEngine, upload_dir: Path
) -> dict[str, str]:
    """保存文件，再原子创建录音与任务；由下一阶段的接口负责调用。"""
    recording_id, task_id = str(uuid4()), str(uuid4())
    context = f"recording_id={recording_id} task_id={task_id} attempt=1"
    if upload is None or not upload.filename:
        logger.info("upload_rejected %s code=FILE_REQUIRED", context)
        raise APIError(400, "FILE_REQUIRED", "请提供 file 文件")
    # 文件名仅作展示；兼容 Windows 路径，且避免超出表字段长度。
    filename = upload.filename.replace("\\", "/").rsplit("/", 1)[-1]
    if not filename or len(filename) > 255:
        logger.info("upload_rejected %s code=INVALID_FILENAME", context)
        raise APIError(400, "INVALID_FILENAME", "文件名长度应为 1～255 个字符")

    relative_path = None
    try:
        logger.info("upload_started %s", context)
        # 同步磁盘 IO 在线程中完成，避免后续 HTTP 接口阻塞事件循环。
        relative_path, size = await run_in_threadpool(save_file, upload.file, filename, upload_dir)
        logger.info("upload_saved %s bytes=%s", context, size)
        async with engine.begin() as connection:
            await connection.execute(
                text("INSERT INTO recordings (id, original_filename, storage_path, size_bytes) "
                     "VALUES (:id, :filename, :path, :size)"),
                {"id": recording_id, "filename": filename, "path": relative_path, "size": size},
            )
            await connection.execute(
                text("INSERT INTO tasks (id, recording_id) VALUES (:id, :recording_id)"),
                {"id": task_id, "recording_id": recording_id},
            )
    except BaseException as exc:
        # engine.begin 自动回滚；补偿清理只针对本次新建文件。
        if relative_path is not None:
            try:
                await run_in_threadpool(remove_file, upload_dir, relative_path)
                logger.info("upload_cleaned %s", context)
            except OSError as cleanup_error:
                logger.error("upload_cleanup_failed %s file=%s error=%s", context, relative_path, type(cleanup_error).__name__)
        logger.warning("upload_failed %s code=%s error=%s", context,
                       exc.code if isinstance(exc, APIError) else "UPLOAD_FAILED", type(exc).__name__)
        if isinstance(exc, APIError) or not isinstance(exc, Exception):
            raise
        raise APIError(500, "UPLOAD_FAILED", "录音保存失败，请稍后重试") from exc

    logger.info("task_created %s status=pending", context)
    return {"recording_id": recording_id, "task_id": task_id, "status": "pending"}
