"""请求/响应数据模型"""

from pydantic import BaseModel, Field
from typing import Optional


class ChatMessage(BaseModel):
    """单条消息"""
    role: str = Field(..., description="角色: user / assistant / system")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """聊天请求"""
    messages: list[ChatMessage] = Field(..., description="历史对话消息列表")
    stream: bool = Field(default=True, description="是否流式返回")


class ChatResponse(BaseModel):
    """聊天响应（非流式）"""
    content: str
    role: str = "assistant"


class TripPlanRequest(BaseModel):
    """旅行规划请求"""
    destination: str = Field(..., description="目的地")
    days: int = Field(..., ge=1, le=30, description="行程天数")
    budget: Optional[float] = Field(default=None, description="预算（元）")
    preferences: Optional[list[str]] = Field(default=None, description="偏好标签，如 美食/购物/自然/文化")
    departure: Optional[str] = Field(default=None, description="出发城市")
    travelers: Optional[int] = Field(default=1, ge=1, description="出行人数")
    special_needs: Optional[list[str]] = Field(
        default=None,
        description="特殊人群关怀：infant/child/senior/pregnant/accessible",
    )
    start_date: Optional[str] = Field(default=None, description="出发日期 YYYY-MM-DD，用于行程日期起算")


class ModifyRequest(BaseModel):
    """行程修改请求"""
    itinerary: list[dict] = []
    attractions: list[dict] = []
    modify_request: str = ""
    destination: str = ""


class VersionPlanRequest(BaseModel):
    """多版本方案请求"""
    destination: str
    days: int
    budget: Optional[float] = None
    preferences: Optional[list[str]] = None
    departure: Optional[str] = "北京"
    travelers: Optional[int] = 1
    special_needs: Optional[list[str]] = Field(
        default=None,
        description="特殊人群关怀：infant/child/senior/pregnant/accessible",
    )
    start_date: Optional[str] = Field(default=None, description="出发日期 YYYY-MM-DD，用于行程日期起算")


# --- 旅行请求完整模型 ---

class TravelRequest(BaseModel):
    """完整旅行请求"""
    origin: str = "北京"
    destination: str
    departure_date: str = ""
    return_date: str = ""
    adults: int = 1
    children: int = 0
    seniors: int = 0
    special_needs: list[str] = []
    budget: str = "¥5,000-8,000"
    styles: list[str] = []
    transport_pref: str = "public"
    hotel_pref: list[str] = []
    pace: str = "moderate"


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str
    type: str = "all"


# --- 行程数据模型 ---

class TransitOption(BaseModel):
    mode: str = ""
    route: str = ""
    duration: str = ""
    price: float = 0


class FlightDetail(BaseModel):
    flight_no: str = ""
    airline: str = ""
    departure_time: str = ""
    arrival_time: str = ""
    duration: str = ""
    price: float = 0
    departure_airport: str = ""
    arrival_airport: str = ""
    baggage: str = ""
    seats_left: int = 0


class TransitDetail(BaseModel):
    mode: str = ""
    route: str = ""
    duration: str = ""
    price: float = 0
    alternatives: list[TransitOption] = []


class AttractionDetail(BaseModel):
    name: str = ""
    images: list[str] = []
    ticket_price: float = 0
    free: bool = True
    opening_hours: str = ""
    closing_day: str = ""
    need_booking: bool = False
    rating: float = 0
    review_count: int = 0
    suggested_duration: str = ""
    how_to_get: list[TransitOption] = []
    tips: str = ""
    tags: list[str] = []


class HotelInfo(BaseModel):
    name: str = ""
    images: list[str] = []
    star: float = 0
    address: str = ""
    price_per_night: float = 0
    distance_to_station: str = ""
    tags: list[str] = []
    match_reason: str = ""


class TimeNode(BaseModel):
    time: str = ""
    type: str = ""
    title: str = ""
    category: str = ""
    detail: Optional[dict] = None


class DayPlan(BaseModel):
    day: int = 0
    date: str = ""
    weather: dict = {}
    nodes: list[TimeNode] = []
    hotel: Optional[HotelInfo] = None


class BudgetBreakdown(BaseModel):
    flight: float = 0
    hotel: float = 0
    tickets: float = 0
    dining: float = 0
    transit: float = 0
    insurance: float = 0
    misc: float = 0
    total: float = 0


class ItineraryResponse(BaseModel):
    id: str = ""
    version: str = ""
    destination: str = ""
    days: list[DayPlan] = []
    total_budget: BudgetBreakdown = BudgetBreakdown()
    created_at: str = ""


# --- 用户与鉴权 ---

class UserInfo(BaseModel):
    """用户公开信息"""
    id: int
    username: str
    nickname: str = ""


class RegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(..., min_length=3, max_length=32, description="用户名")
    password: str = Field(..., min_length=6, max_length=64, description="密码")
    nickname: str = Field(default="", max_length=32, description="昵称，可留空")
    invite_code: str = Field(
        default="",
        max_length=64,
        description="注册邀请码，服务端配置了 REGISTER_CODE 时必填",
    )


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
    """登录/注册成功响应"""
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


# --- 用户记忆（偏好 / 历史行程） ---

class PreferenceForm(BaseModel):
    """偏好设置表单的原始选择 — 用户下次进入偏好页时原样回显

    与 preferences（后端标签）分开存：标签是给景点筛选用的，
    这里要的是用户当时勾了什么，才能还原成勾选状态。
    """

    styles: list[str] = Field(default=[], description="旅行风格选项值")
    transport_pref: str = Field(default="", description="交通偏好，空表示未选择")
    hotel_pref: list[str] = Field(default=[], description="住宿偏好选项值")
    pace: str = Field(default="", description="行程节奏，空表示未选择")


class PreferenceRequest(BaseModel):
    """用户偏好（长期记忆）"""
    departure_city: str = Field(default="", description="常用出发城市")
    destination: str = Field(default="", description="上次目的地")
    days: int = Field(default=5, ge=1, le=30)
    budget: Optional[float] = Field(default=None)
    travelers: int = Field(default=1, ge=1)
    preferences: list[str] = Field(default=[], description="偏好标签")
    form_state: PreferenceForm = Field(default_factory=PreferenceForm)


class PreferenceResponse(PreferenceRequest):
    """偏好响应"""
    updated_at: str = ""


class TripRecordRequest(BaseModel):
    """保存历史行程请求"""
    destination: str
    departure_city: str = ""
    days: int = Field(default=3, ge=1, le=30)
    budget: Optional[float] = None
    travelers: int = Field(default=1, ge=1)
    preferences: list[str] = []
    summary: str = Field(default="", max_length=500)
    content: str = Field(default="", description="方案内容 JSON 字符串")


class TripRecordSummary(BaseModel):
    """历史行程列表项（不含大段内容）"""
    id: int
    destination: str
    departure_city: str = ""
    days: int = 3
    budget: Optional[float] = None
    travelers: int = 1
    preferences: list[str] = []
    summary: str = ""
    created_at: str = ""


class TripRecordDetail(TripRecordSummary):
    """历史行程详情（含方案内容）"""
    content: str = ""