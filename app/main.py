import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import create_database_engine
from app.errors import APIError

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = create_database_engine()
    logger.info("Application started (step 2: recording persistence)")
    try:
        yield
    finally:
        await app.state.db.dispose()
        logger.info("Database connections closed")


app = FastAPI(title="Speech-to-Text API", version="0.2.0", lifespan=lifespan)


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
