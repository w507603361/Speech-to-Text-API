import asyncio
import logging
import random

from sqlalchemy import text

logger = logging.getLogger("uvicorn.error")


async def mark_interrupted(engine):
    """重启只标记失败，不重新执行遗留任务。单实例启动时调用。"""
    async with engine.begin() as conn:
        rows = (await conn.execute(text(
            "SELECT id, recording_id, attempt FROM tasks "
            "WHERE status IN ('pending','transcribing','summarizing') FOR UPDATE"
        ))).mappings().all()
        await conn.execute(text(
            "UPDATE tasks SET status='failed', error_code='SERVICE_RESTARTED', "
            "error_message='服务重启导致任务中断', finished_at=UTC_TIMESTAMP(6) "
            "WHERE status IN ('pending','transcribing','summarizing')"
        ))
    for row in rows:
        logger.info("task_interrupted task_id=%s recording_id=%s attempt=%s", row['id'], row['recording_id'], row['attempt'])


async def transcribe(engine, task_id):
    """Mock 模拟耗时与失败率；摘要接入前保留 summarizing 中间态。"""
    try:
        async with engine.begin() as conn:
            claimed = await conn.execute(text(
                "UPDATE tasks SET status='transcribing', started_at=UTC_TIMESTAMP(6) "
                "WHERE id=:id AND status='pending'"
            ), {'id': task_id})
            if not claimed.rowcount:
                return
            row = (await conn.execute(text(
                "SELECT recording_id, attempt FROM tasks WHERE id=:id"
            ), {'id': task_id})).mappings().one()
        context = f"task_id={task_id} recording_id={row['recording_id']} attempt={row['attempt']}"
        delay = random.uniform(5, 15)
        logger.info("task_transcribing %s delay_seconds=%.2f", context, delay)
        await asyncio.sleep(delay)
        if random.random() < 0.2:
            async with engine.begin() as conn:
                await conn.execute(text(
                    "UPDATE tasks SET status='failed', error_code='ASR_FAILED', "
                    "error_message='模拟转写失败', finished_at=UTC_TIMESTAMP(6) WHERE id=:id"
                ), {'id': task_id})
            logger.info("task_failed %s code=ASR_FAILED", context)
            return
        async with engine.begin() as conn:
            await conn.execute(text(
                "UPDATE recordings SET transcript=:transcript WHERE id=:id"
            ), {'id': row['recording_id'], 'transcript': '今天讨论了录音服务的开发计划。先完成上传和转写，再接入智能摘要。小王负责接口联调，小李在周五前整理部署文档。'})
            await conn.execute(text("UPDATE tasks SET status='summarizing' WHERE id=:id"), {'id': task_id})
        logger.info("task_summarizing %s summary_not_implemented=true", context)
    except asyncio.CancelledError:
        logger.info("task_cancelled task_id=%s; next startup marks failed", task_id)
        raise
    except Exception as exc:
        logger.error("task_error task_id=%s error=%s", task_id, type(exc).__name__)
        try:
            async with engine.begin() as conn:
                await conn.execute(text(
                    "UPDATE tasks SET status='failed', error_code='PROCESSING_FAILED', "
                    "error_message='任务处理异常', finished_at=UTC_TIMESTAMP(6) WHERE id=:id"
                ), {'id': task_id})
        except Exception as persistence_error:
            logger.error("task_failure_not_saved task_id=%s error=%s", task_id, type(persistence_error).__name__)


def schedule(app, task_id):
    task = asyncio.create_task(transcribe(app.state.db, task_id))
    app.state.tasks.add(task)
    task.add_done_callback(app.state.tasks.discard)
