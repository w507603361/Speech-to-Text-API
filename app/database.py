from sqlalchemy.ext.asyncio import create_async_engine

from app.config import database_url


def create_database_engine():
    return create_async_engine(
        database_url(),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3, "init_command": "SET time_zone = '+00:00'"},
    )
