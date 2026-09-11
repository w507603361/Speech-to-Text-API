import os

from sqlalchemy import URL


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
