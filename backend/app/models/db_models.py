"""数据库模型 — 用户、用户偏好（长期记忆）、历史行程记录"""

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    """当前时间（带时区，SQLModel 要求时区感知的 datetime）"""
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    """用户表"""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, max_length=32, description="登录用户名")
    hashed_password: str = Field(description="bcrypt 哈希后的密码")
    nickname: str = Field(default="", max_length=32, description="昵称")
    created_at: datetime = Field(default_factory=_now)


class UserPreference(SQLModel, table=True):
    """用户偏好（长期记忆）— 每个用户一条，下次规划时自动回填"""

    __tablename__ = "user_preferences"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, unique=True, foreign_key="users.id")
    departure_city: str = Field(default="", max_length=32, description="常用出发城市")
    destination: str = Field(default="", max_length=32, description="上次目的地")
    days: int = Field(default=5, description="常用天数")
    budget: float | None = Field(default=None, description="常用预算")
    travelers: int = Field(default=1, description="常用出行人数")
    preferences: str = Field(default="", description="偏好标签，逗号分隔")
    form_state: str = Field(default="", description="偏好设置表单的原始选择（JSON）")
    updated_at: datetime = Field(default_factory=_now)


class TripRecord(SQLModel, table=True):
    """历史行程记录 — 保存生成过的方案，支持回看"""

    __tablename__ = "trip_records"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="users.id")
    destination: str = Field(max_length=32)
    departure_city: str = Field(default="", max_length=32)
    days: int = Field(default=3)
    budget: float | None = Field(default=None)
    travelers: int = Field(default=1)
    preferences: str = Field(default="", description="偏好标签，逗号分隔")
    summary: str = Field(default="", max_length=500, description="方案摘要")
    content: str = Field(default="", description="方案内容（JSON 字符串）")
    created_at: datetime = Field(default_factory=_now)
