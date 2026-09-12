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
    """保存文件，再原子创建录音与任务；路由随后注册后台处理。"""
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


async def retry_task(engine: AsyncEngine, task_id: str) -> dict[str, str]:
    async with engine.begin() as conn:
        # 与删除统一先锁任务行，重复请求只有一个能从 failed 进入 pending。
        row = (await conn.execute(text('SELECT * FROM tasks WHERE id=:id FOR UPDATE'),
                                  {'id': task_id})).mappings().first()
        if row is None:
            raise APIError(404, 'TASK_NOT_FOUND', '任务不存在')
        if row['status'] != 'failed':
            logger.info('retry_rejected task_id=%s status=%s', task_id, row['status'])
            raise APIError(409, 'TASK_NOT_FAILED', '仅失败任务可以重试')
        await conn.execute(text(
            "UPDATE tasks SET status='pending', attempt=attempt+1, error_code=NULL, "
            "error_message=NULL, started_at=NULL, finished_at=NULL WHERE id=:id"
        ), {'id': task_id})
        # 保留成功转写，只清除上一轮摘要，后续执行可直接进入 summarizing。
        await conn.execute(text('UPDATE recordings SET summary_result=NULL WHERE id=:id'),
                           {'id': row['recording_id']})
    logger.info('task_retried task_id=%s recording_id=%s attempt=%s status=pending',
                task_id, row['recording_id'], row['attempt']+1)
    return {'recording_id': row['recording_id'], 'task_id': task_id, 'status': 'pending'}


async def delete_recording(engine: AsyncEngine, recording_id: str, upload_dir: Path):
    async with engine.begin() as conn:
        row = (await conn.execute(text(
            'SELECT id, status, attempt FROM tasks WHERE recording_id=:id FOR UPDATE'
        ), {'id': recording_id})).mappings().first()
        if row is None:
            raise APIError(404, 'RECORDING_NOT_FOUND', '录音不存在')
        if row['status'] not in ('done', 'failed'):
            logger.info('delete_rejected recording_id=%s status=%s', recording_id, row['status'])
            raise APIError(409, 'RECORDING_ACTIVE', '任务尚未结束，不能删除录音')
        path = (await conn.execute(text('SELECT storage_path FROM recordings WHERE id=:id'),
                                   {'id': recording_id})).scalar_one()
        try:
            # 锁内删除一个明确文件，禁止重试同时启动；文件已缺失可继续清理数据库。
            await run_in_threadpool(remove_file, upload_dir, path)
        except (OSError, ValueError) as exc:
            logger.error('delete_file_failed recording_id=%s error=%s', recording_id, type(exc).__name__)
            raise APIError(500, 'FILE_DELETE_FAILED', '录音文件删除失败') from exc
        await conn.execute(text('DELETE FROM recordings WHERE id=:id'), {'id': recording_id})
    logger.info('recording_deleted recording_id=%s task_id=%s attempt=%s',
                recording_id, row['id'], row['attempt'])
