import os
from pathlib import Path

import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import engine
from . import models
from .routers import (
    collections,
    dashboard,
    environment,
    exhibitions,
    loans,
    locations,
    restorations,
)


def _migrate_missing_columns() -> None:
    """为已存在的数据库补齐新增字段(零配置演示库平滑升级,生产建议改用 Alembic)。"""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    missing = {
        "exhibitions": {
            "frozen": sa.Boolean(),
            "frozen_at": sa.DateTime(),
            "frozen_by": sa.String(length=50),
        },
        "exhibition_items": {
            "install_plan_note": sa.String(length=300),
            "planned_mount_date": sa.Date(),
            "mount_acceptor": sa.String(length=50),
            "mount_photo_note": sa.String(length=500),
            "mount_anomaly": sa.Text(),
            "mount_anomaly_resolved": sa.Boolean(),
            "mount_anomaly_resolved_at": sa.DateTime(),
            "mount_anomaly_resolved_by": sa.String(length=50),
            "dismount_acceptor": sa.String(length=50),
            "dismount_photo_note": sa.String(length=500),
            "dismount_anomaly": sa.Text(),
            "dismount_anomaly_resolved": sa.Boolean(),
            "dismount_anomaly_resolved_at": sa.DateTime(),
            "dismount_anomaly_resolved_by": sa.String(length=50),
            "change_order_id": sa.Integer(),
        },
        "change_orders": {
            "remove_item_label": sa.String(length=200),
        },
    }
    with engine.begin() as conn:
        for table, columns in missing.items():
            if table not in existing_tables:
                continue
            present = {col["name"] for col in inspector.get_columns(table)}
            for name, column_type in columns.items():
                if name not in present:
                    conn.execute(
                        sa.text(
                            f"ALTER TABLE {table} ADD COLUMN {name} "
                            + _column_ddl(engine.dialect.name, name, column_type)
                        )
                    )


def _column_ddl(dialect: str, name: str, col: "sa.Column") -> str:
    if isinstance(col, sa.Boolean):
        return "BOOLEAN DEFAULT 0" if dialect == "sqlite" else "BOOLEAN DEFAULT FALSE"
    if isinstance(col, sa.Integer):
        return "INTEGER"
    if isinstance(col, sa.DateTime):
        return "DATETIME"
    if isinstance(col, sa.Date):
        return "DATE"
    if isinstance(col, sa.Text):
        return "TEXT"
    length = getattr(col, "length", 100) or 100
    return f"VARCHAR({length})"


# 自动建表(SQLite / PostgreSQL 均可;如需迁移可在此基础上引入 Alembic)
_migrate_missing_columns()
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="博物馆藏品管理系统 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    dashboard.router,
    collections.router,
    locations.router,
    exhibitions.router,
    exhibitions.anomaly_router,
    restorations.router,
    loans.router,
    environment.router,
):
    app.include_router(router)


@app.get("/api/health")
def health():
    return {"status": "ok", "db": engine.dialect.name}


# 生产模式:若已构建前端(dist 目录存在),由 FastAPI 一并托管
DIST_DIR = Path(__file__).resolve().parent.parent / "frontend_dist"
if DIST_DIR.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=DIST_DIR / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return {"detail": "Not Found"}
        index = DIST_DIR / "index.html"
        if full_path:
            candidate = DIST_DIR / full_path
            if candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(index)
