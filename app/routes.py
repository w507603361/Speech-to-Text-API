import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, File, Query, Request, UploadFile
from sqlalchemy import text

from app.config import UPLOAD_DIR
from app.errors import APIError
from app.recordings import create_recording
from app.tasks import schedule

router = APIRouter(prefix='/v1')


def serialize(row):
    result = dict(row)
    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = value.replace(tzinfo=timezone.utc).isoformat()
    if isinstance(result.get('summary_result'), str):
        result['summary_result'] = json.loads(result['summary_result'])
    return result


@router.post('/recordings', status_code=202)
async def upload_recording(request: Request, file: UploadFile | None = File(default=None)):
    try:
        result = await create_recording(file, request.app.state.db, UPLOAD_DIR)
        # 仅注册后台协程，HTTP 请求不等待模拟转写。
        schedule(request.app, result['task_id'])
        return result
    finally:
        if file is not None:
            await file.close()


@router.get('/tasks/{task_id}')
async def get_task(task_id: UUID, request: Request):
    async with request.app.state.db.connect() as conn:
        row = (await conn.execute(text('SELECT * FROM tasks WHERE id=:id'), {'id': str(task_id)})).mappings().first()
    if row is None:
        raise APIError(404, 'TASK_NOT_FOUND', '任务不存在')
    return serialize(row)


@router.get('/recordings')
async def list_recordings(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    # 同一事务读取总数和列表，使用 MySQL 默认可重复读快照。
    async with request.app.state.db.begin() as conn:
        total = (await conn.execute(text('SELECT COUNT(*) FROM recordings'))).scalar_one()
        rows = (await conn.execute(text(
            'SELECT r.id, r.original_filename, r.size_bytes, r.created_at, r.updated_at, '
            't.id AS task_id, t.status FROM recordings r JOIN tasks t ON t.recording_id=r.id '
            'ORDER BY r.created_at DESC, r.id DESC LIMIT :limit OFFSET :offset'
        ), {'limit': page_size, 'offset': (page-1)*page_size})).mappings().all()
    return {'items': [serialize(row) for row in rows], 'total': total, 'page': page, 'page_size': page_size}


@router.get('/recordings/{recording_id}')
async def get_recording(recording_id: UUID, request: Request):
    async with request.app.state.db.connect() as conn:
        row = (await conn.execute(text(
            'SELECT r.id, r.original_filename, r.size_bytes, r.transcript, r.summary_result, '
            'r.created_at, r.updated_at, t.id AS task_id, t.status '
            'FROM recordings r JOIN tasks t ON t.recording_id=r.id WHERE r.id=:id'
        ), {'id': str(recording_id)})).mappings().first()
    if row is None:
        raise APIError(404, 'RECORDING_NOT_FOUND', '录音不存在')
    return serialize(row)
