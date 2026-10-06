# AI 旅行规划师 — 单镜像部署（前端构建产物由 FastAPI 一起托管）
# 构建：docker build -t travel-planner .
# 运行：docker run -p 8000:8000 --env-file backend/.env travel-planner

# ---------- 阶段 1：构建前端 ----------
FROM node:20-alpine AS frontend-build

WORKDIR /build/frontend

# 先只拷贝依赖清单，利用 Docker 层缓存
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# 构建命令是 tsc --noEmit && vite build，需要 devDependencies 里的 typescript
ENV NODE_ENV=development
RUN npm run build


# ---------- 阶段 2：运行时 ----------
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/

# 带上构建好的前端静态资源，FastAPI 启动时会自动托管
COPY --from=frontend-build /build/frontend/dist ./frontend/dist

# 在 backend 目录下启动，app 包才能被正确导入
WORKDIR /app/backend

# 数据库默认落在容器内；生产建议挂载持久卷并把 DATABASE_URL 指过去，
# 例如：DATABASE_URL=sqlite:////data/app.db 且卷挂载到 /data
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen(f\"http://127.0.0.1:{os.getenv('PORT','8000')}/api/health\", timeout=4).status==200 else 1)"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
