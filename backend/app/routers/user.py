"""用户记忆路由 — 偏好记忆（长期）+ 历史行程记录"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.core.db import get_session
from app.core.security import get_current_user
from app.models.db_models import TripRecord, User, UserPreference
from app.models.schemas import (
    PreferenceForm,
    PreferenceRequest,
    PreferenceResponse,
    TripRecordDetail,
    TripRecordRequest,
    TripRecordSummary,
)

router = APIRouter(prefix="/api/user", tags=["user"])


def _split_tags(value: str) -> list[str]:
    return [t for t in value.split(",") if t]


def _join_tags(tags: list[str]) -> str:
    return ",".join(tags)


def _load_form_state(value: str) -> PreferenceForm:
    """解析存下来的表单状态；历史数据为空或损坏时返回空表单"""
    if not value:
        return PreferenceForm()
    try:
        return PreferenceForm(**json.loads(value))
    except (ValueError, TypeError):
        return PreferenceForm()


def _to_preference_response(pref: UserPreference) -> PreferenceResponse:
    return PreferenceResponse(
        departure_city=pref.departure_city,
        destination=pref.destination,
        days=pref.days,
        budget=pref.budget,
        travelers=pref.travelers,
        preferences=_split_tags(pref.preferences),
        form_state=_load_form_state(pref.form_state),
        updated_at=pref.updated_at.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
    )


def _to_summary(record: TripRecord) -> TripRecordSummary:
    return TripRecordSummary(
        id=record.id or 0,
        destination=record.destination,
        departure_city=record.departure_city,
        days=record.days,
        budget=record.budget,
        travelers=record.travelers,
        preferences=_split_tags(record.preferences),
        summary=record.summary,
        created_at=record.created_at.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
    )


# ============ 偏好记忆 ============

@router.get("/preferences", response_model=PreferenceResponse | None)
def get_preferences(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """读取当前用户的偏好（用于表单自动回填），没有则返回 null"""
    pref = session.exec(
        select(UserPreference).where(UserPreference.user_id == current_user.id)
    ).first()
    if pref is None:
        return None
    return _to_preference_response(pref)


@router.put("/preferences", response_model=PreferenceResponse)
def save_preferences(
    request: PreferenceRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """保存/更新当前用户的偏好"""
    pref = session.exec(
        select(UserPreference).where(UserPreference.user_id == current_user.id)
    ).first()
    if pref is None:
        pref = UserPreference(user_id=current_user.id or 0)

    pref.departure_city = request.departure_city
    pref.destination = request.destination
    pref.days = request.days
    pref.budget = request.budget
    pref.travelers = request.travelers
    pref.preferences = _join_tags(request.preferences)
    pref.form_state = request.form_state.model_dump_json()
    pref.updated_at = datetime.now(timezone.utc)

    session.add(pref)
    session.commit()
    session.refresh(pref)
    return _to_preference_response(pref)


# ============ 历史行程 ============

@router.get("/trips", response_model=list[TripRecordSummary])
def list_trips(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """按时间倒序返回当前用户的历史行程"""
    records = session.exec(
        select(TripRecord)
        .where(TripRecord.user_id == current_user.id)
        .order_by(TripRecord.created_at.desc())
    ).all()
    return [_to_summary(r) for r in records]


@router.post("/trips", response_model=TripRecordSummary)
def create_trip(
    request: TripRecordRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """保存一次行程方案到历史记录"""
    record = TripRecord(
        user_id=current_user.id or 0,
        destination=request.destination,
        departure_city=request.departure_city,
        days=request.days,
        budget=request.budget,
        travelers=request.travelers,
        preferences=_join_tags(request.preferences),
        summary=request.summary,
        content=request.content,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return _to_summary(record)


@router.get("/trips/{trip_id}", response_model=TripRecordDetail)
def get_trip(
    trip_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """获取历史行程详情（仅限本人）"""
    record = session.get(TripRecord, trip_id)
    if record is None or record.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="行程记录不存在",
        )
    summary = _to_summary(record)
    return TripRecordDetail(**summary.model_dump(), content=record.content)


@router.delete("/trips/{trip_id}")
def delete_trip(
    trip_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """删除历史行程（仅限本人）"""
    record = session.get(TripRecord, trip_id)
    if record is None or record.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="行程记录不存在",
        )
    session.delete(record)
    session.commit()
    return {"status": "ok"}
