"""AI 旅行规划师 — FastAPI 入口"""

import sys, os

# On Vercel, packages are installed via pip (not bundled lib/)
if not os.environ.get('VERCEL'):
    lib_path = os.path.join(os.path.dirname(__file__), '..', 'lib')
    if os.path.isdir(lib_path):
        sys.path.insert(0, lib_path)

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import app_config
from app.core.cities import suggest_places, supported_cities_payload
from app.core.db import init_db
from app.routers import chat
from app.routers import trip
from app.routers import search
from app.routers import auth
from app.routers import user

app = FastAPI(
    title="AI 旅行规划师",
    description="基于 LLM 的智能旅行规划助手",
    version="0.1.0",
)


@app.on_event("startup")
def on_startup() -> None:
    """启动时初始化数据库（建表）"""
    init_db()


# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(chat.router)
app.include_router(trip.router)
app.include_router(search.router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "AI 旅行规划师"}


@app.get("/api/cities")
async def supported_cities():
    """支持的目的地城市（仅国内），前端下拉与提示统一用这份数据"""
    return supported_cities_payload()


@app.get("/api/cities/suggest")
def suggest_cities(q: str = ""):
    """地名联想（仅国内）：本地热门城市 + 高德输入提示

    同步函数，FastAPI 会放到线程池执行，避免阻塞事件循环。
    """
    return {"items": suggest_places(q)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=app_config.host,
        port=app_config.port,
        reload=True,
    )