"""数据库会话管理 — SQLModel + SQLite（可通过 DATABASE_URL 切换其它数据库）"""

import os
from collections.abc import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import app_config

# SQLite 在多线程场景下需要关闭同线程检查（FastAPI 依赖注入会跨线程）
_connect_args = (
    {"check_same_thread": False}
    if app_config.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(app_config.database_url, echo=False, connect_args=_connect_args)

# 建表之后需要补齐的列：{表名: {列名: 建列语句片段}}
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "user_preferences": {
        # 偏好设置表单的原始选择，用于下次进入偏好页时回显
        "form_state": "VARCHAR DEFAULT ''",
    },
}


def _sync_columns() -> None:
    """给已存在的表补上后加的列（create_all 不会改已有表结构）"""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            if table not in existing_tables:
                continue
            present = {col["name"] for col in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    """初始化数据库：确保目录存在、建表、补齐后加的列（幂等）"""
    url = app_config.database_url
    if url.startswith("sqlite:///"):
        db_path = url.replace("sqlite:///", "", 1)
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    # 导入模型以完成表注册
    from app.models import db_models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _sync_columns()


def get_session() -> Generator[Session, None, None]:
    """FastAPI 依赖：提供数据库会话"""
    with Session(engine) as session:
        yield session
