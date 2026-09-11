import os
from pathlib import Path

from sqlalchemy import URL

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/app/uploads"))


def database_url() -> URL:
    return URL.create(
        "mysql+asyncmy",
        username=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        host=os.getenv("MYSQL_HOST", "db"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        database=os.environ["MYSQL_DATABASE"],
        query={"charset": "utf8mb4"},
    )
