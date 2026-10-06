"""用户鉴权路由 — 注册 / 登录 / 当前用户"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.models.db_models import User
from app.models.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserInfo,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _to_token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id or 0),
        user=UserInfo(id=user.id or 0, username=user.username, nickname=user.nickname),
    )


@router.post("/register", response_model=TokenResponse)
def register(request: RegisterRequest, session: Session = Depends(get_session)):
    """注册新用户，成功后直接返回登录令牌"""
    exists = session.exec(
        select(User).where(User.username == request.username)
    ).first()
    if exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户名已被注册",
        )

    user = User(
        username=request.username,
        hashed_password=hash_password(request.password),
        nickname=request.nickname or request.username,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return _to_token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, session: Session = Depends(get_session)):
    """登录，校验密码后签发令牌"""
    user = session.exec(
        select(User).where(User.username == request.username)
    ).first()
    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    return _to_token_response(user)


@router.get("/me", response_model=UserInfo)
def me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息（用于前端校验登录状态）"""
    return UserInfo(
        id=current_user.id or 0,
        username=current_user.username,
        nickname=current_user.nickname,
    )
