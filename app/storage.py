import logging
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from app.errors import APIError

logger = logging.getLogger("uvicorn.error")
MAX_FILE_SIZE = 50 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac"}


def remove_file(root: Path, relative_path: str) -> None:
    """只删除上传目录内一个明确文件；不遍历目录、不递归删除。"""
    target = root / relative_path
    if target.parent.resolve() != root.resolve() or target.is_symlink():
        raise ValueError("Unsafe upload path")
    target.unlink(missing_ok=True)


def save_file(stream: BinaryIO, filename: str, root: Path) -> tuple[str, int]:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise APIError(400, "INVALID_FILE_TYPE", "仅支持 wav/mp3/m4a/aac 文件")
    relative_path = f"{uuid4()}{extension}"
    size = 0
    created = False
    try:
        root.mkdir(parents=True, exist_ok=True)
        # 排他创建，原始文件名从不参与磁盘路径，避免覆盖及路径穿越。
        with (root / relative_path).open("xb") as output:
            created = True
            while chunk := stream.read(CHUNK_SIZE):
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    raise APIError(413, "FILE_TOO_LARGE", "文件不能超过 50MB")
                output.write(chunk)
        if size == 0:
            raise APIError(400, "EMPTY_FILE", "文件不能为空")
    except BaseException:
        if created:
            try:
                remove_file(root, relative_path)
            except OSError as exc:
                logger.error("upload_cleanup_failed file=%s error=%s", relative_path, type(exc).__name__)
        raise
    return relative_path, size
