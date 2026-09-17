import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

# 默认 SQLite 文件固定在 backend 目录下,避免随启动目录漂移
_DEFAULT_SQLITE_URL = f"sqlite:///{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/museum.db"

connect_args = (
    {"check_same_thread": False}
    if (settings.database_url or "").startswith("sqlite") or not settings.database_url
    else {}
)
engine = create_engine(
    settings.sqlalchemy_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_sqlite() -> bool:
    return engine.dialect.name == "sqlite"


def reset_sqlite_sequence():
    """SQLite 下清空自增序列,便于重新播种样例数据。"""
    if engine.dialect.name != "sqlite":
        return
    import sqlalchemy as sa

    with engine.begin() as conn:
        tables = [
            "alerts",
            "env_readings",
            "restorations",
            "loan_records",
            "exhibition_exceptions",
            "exhibition_change_orders",
            "exhibition_items",
            "exhibitions",
            "movements",
            "collections",
            "locations",
        ]
        for t in tables:
            conn.execute(sa.text(f"DELETE FROM {t}"))
            conn.execute(sa.text("DELETE FROM sqlite_sequence WHERE name = :n"), {"n": t})


if "CREATE_ALL_ON_IMPORT" in os.environ:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
