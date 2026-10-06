"""Agent 状态定义"""

from typing import TypedDict, Optional, Annotated
from langgraph.graph.message import add_messages


class FlightInfo(TypedDict, total=False):
    airline: str
    flight_no: str
    departure: str
    arrival: str
    departure_time: str
    arrival_time: str
    price: float
    duration: str
    baggage: str
    seats_left: int
    departure_airport: str
    arrival_airport: str
    source: str
    is_reference: bool
    note: str


class HotelInfo(TypedDict, total=False):
    name: str
    city: str
    rating: float
    price_per_night: float
    address: str
    highlights: list[str]
    images: list[str]
    tags: list[str]
    distance_to_station: str
    match_reason: str
    lat: float
    lon: float
    source: str
    fields: list[dict]
    raw: dict


class FoodInfo(TypedDict, total=False):
    name: str
    city: str
    category: str
    price: float
    address: str
    rating: float
    images: list[str]
    lat: float
    lon: float
    source: str
    fields: list[dict]
    raw: dict


class AttractionInfo(TypedDict, total=False):
    name: str
    city: str
    category: str
    estimated_duration: str
    ticket_price: float
    ticket_known: bool
    description: str
    images: list[str]
    opening_hours: str
    closing_day: str
    need_booking: bool
    rating: float
    review_count: int
    suggested_duration: str
    how_to_get: list[dict]
    tips: str
    tags: list[str]
    lat: float
    lon: float
    source: str
    fields: list[dict]
    raw: dict


class DayPlan(TypedDict, total=False):
    day: int
    date: str
    theme: str
    activities: list[dict]
    nodes: list[dict]
    meals: list[dict]
    hotel: dict  # HotelInfo 对象
    notes: str
    # 命名与前端保持一致（前端按 careTips 读取）
    careTips: list[str]
    weather: dict


class PlannerState(TypedDict):
    """Planner Agent 的全局状态"""
    messages: Annotated[list, add_messages]
    destination: Optional[str]
    days: Optional[int]
    budget: Optional[float]
    preferences: Optional[list[str]]
    departure_city: Optional[str]
    travelers: Optional[int]
    special_needs: Optional[list[str]]
    start_date: Optional[str]

    flights: Optional[list[FlightInfo]]
    hotels: Optional[list[HotelInfo]]
    attractions: Optional[list[AttractionInfo]]

    itinerary: Optional[list[DayPlan]]
    total_budget_estimate: Optional[float]

    next_step: Optional[str]
    error: Optional[str]