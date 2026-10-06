"""鉴权模块 — bcrypt 密码哈希 + JWT 令牌 + 当前用户依赖"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.core.config import app_config
from app.core.db import get_session
from app.models.db_models import User

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """bcrypt 加盐哈希（慢哈希，抗彩虹表与暴力破解）"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """校验明文密码与哈希是否匹配"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int) -> str:
    """签发访问令牌，payload 里带用户 ID 与过期时间"""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=app_config.auth.expire_minutes
    )
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(
        payload,
        app_config.auth.secret_key,
        algorithm=app_config.auth.algorithm,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> User:
    """依赖：解析 Bearer 令牌并返回当前用户，未登录或令牌失效返回 401"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录，请先登录",
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            app_config.auth.secret_key,
            algorithms=[app_config.auth.algorithm],
        )
        user_id = int(payload.get("sub", 0))
    except (jwt.PyJWTError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录状态已失效，请重新登录",
        )

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在，请重新登录",
        )
    return user
