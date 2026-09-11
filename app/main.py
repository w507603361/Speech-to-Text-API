import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import create_database_engine
from app.errors import APIError
from app.routes import router
from app.tasks import mark_interrupted
from app.deepseek import DeepSeek

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = create_database_engine()
    app.state.tasks = set()
    app.state.deepseek = DeepSeek()
    try:
        await mark_interrupted(app.state.db)
        logger.info("Application started (step 4: DeepSeek summaries)")
        yield
    finally:
        tasks = list(app.state.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await app.state.deepseek.close()
        await app.state.db.dispose()
        logger.info("Database connections closed")


app = FastAPI(title="Speech-to-Text API", version="0.4.0", lifespan=lifespan)
app.include_router(router)


@app.exception_handler(HTTPException)
async def handle_http_error(request, exc):
    return JSONResponse(status_code=exc.status_code, headers=exc.headers,
                        content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail)}})


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request, exc):
    return JSONResponse(status_code=400, content={"error": {"code": "INVALID_REQUEST", "message": "请求参数不合法"}})


@app.exception_handler(SQLAlchemyError)
async def handle_database_error(request, exc):
    logger.error("database_error error=%s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"error": {"code": "DATABASE_ERROR", "message": "数据库操作失败"}})


@app.exception_handler(APIError)
async def handle_api_error(request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.get("/health")
async def health():
    try:
        async with asyncio.timeout(5):
            async with app.state.db.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, TimeoutError, OSError) as exc:
        # Only log the exception type: connection details may contain credentials.
        logger.warning("Database health check failed: %s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "DATABASE_UNAVAILABLE", "message": "数据库暂不可用"}},
        )
    return {"status": "ok", "database": "ok"}
