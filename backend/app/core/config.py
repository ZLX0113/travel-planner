"""应用配置管理"""

import os
from dataclasses import dataclass, field
from pathlib import Path

# 默认数据目录：backend/app/data
_DEFAULT_DATA_DIR = str(Path(__file__).resolve().parent.parent / "data")
# 默认数据库文件：backend/data/app.db
_DEFAULT_DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "data" / "app.db")


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str = os.getenv("LLM_PROVIDER", "openai")  # openai / azure / local
    model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    api_key: str = os.getenv("OPENAI_API_KEY", "")
    base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class AuthConfig:
    """鉴权配置"""
    secret_key: str = os.getenv("JWT_SECRET", "dev-secret-key-change-in-production")
    algorithm: str = "HS256"
    expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24 * 7)))


@dataclass
class AmapConfig:
    """高德地图 Web 服务配置（在线景点/餐饮/酒店/路线/天气数据源）"""

    key: str = os.getenv("AMAP_KEY", "")
    base_url: str = os.getenv("AMAP_BASE_URL", "https://restapi.amap.com/v3")
    timeout: float = float(os.getenv("AMAP_TIMEOUT", "8"))

    @property
    def enabled(self) -> bool:
        """只有配置了 Key 才会走在线数据源"""
        return bool(self.key.strip())


@dataclass
class AppConfig:
    """应用全局配置"""
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    cors_origins: list[str] = field(default_factory=lambda: [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://ai-travel-planner-nbyx.vercel.app",
        "https://ai-travel-planner.vercel.app",
    ])
    llm: LLMConfig = field(default_factory=LLMConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    amap: AmapConfig = field(default_factory=AmapConfig)
    # 数据源：auto（有高德 Key 就走在线，否则本地 JSON）/ amap / local_json
    data_source: str = os.getenv("DATA_SOURCE", "auto")
    data_dir: str = os.getenv("DATA_DIR", _DEFAULT_DATA_DIR)
    # 航班数据来源：auto（优先在线，无则大模型生成参考航班）/ llm / local
    flight_source: str = os.getenv("FLIGHT_SOURCE", "auto")
    # 用户数据库（SQLite，可通过 DATABASE_URL 切换 MySQL 等）
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{_DEFAULT_DB_PATH}")
    # 注册邀请码：填了才校验，留空则开放注册。
    # 公开演示时填上，避免陌生人注册后消耗自己的大模型额度。
    register_code: str = os.getenv("REGISTER_CODE", "")


app_config = AppConfig()