"""旅行搜索工具函数 — 在线数据源优先，失败自动回退本地数据

工具函数保持无状态：每次调用向数据源取原始数据，再做过滤与排序。
数据源由配置决定（默认 auto：配了高德 Key 走在线实时数据，否则用本地 JSON），
返回结果里带上 source / fields / raw，前端可自适应渲染字段。
"""

import logging
import random

from app.agents.state import AttractionInfo, FlightInfo, FoodInfo, HotelInfo
from app.core.config import app_config
from app.tools.data_source import get_data_source, get_fallback_data_source
from app.tools.flight_estimator import estimate_flights

logger = logging.getLogger(__name__)


def _raw_attraction(a: dict, city: str) -> AttractionInfo:
    return AttractionInfo(
        name=a["name"],
        city=city,
        category=a["category"],
        estimated_duration=a["estimated_duration"],
        ticket_price=a["ticket_price"],
        ticket_known=a.get("ticket_known", True),
        description=a["description"],
        images=a.get("images", []),
        opening_hours=a.get("opening_hours", ""),
        closing_day=a.get("closing_day", ""),
        need_booking=a.get("need_booking", False),
        rating=a.get("rating", 0),
        review_count=a.get("review_count", 0),
        suggested_duration=a.get("suggested_duration", a.get("estimated_duration", "2小时")),
        how_to_get=a.get("how_to_get", []),
        tips=a.get("tips", ""),
        tags=a.get("tags", []),
        lat=a.get("lat", 0),
        lon=a.get("lon", 0),
        source=a.get("source", "local"),
        fields=a.get("fields", []),
        raw=a.get("raw", {}),
    )


# ============ 工具函数 ============

def search_flights(
    departure: str,
    destination: str,
    budget: float | None = None
) -> list[FlightInfo]:
    """搜索航班：在线数据源优先，无数据时用大模型生成参考航班，最后回退本地数据"""
    flights = get_data_source().get_flights(departure, destination)

    if not flights and app_config.flight_source in ("auto", "llm"):
        flights = estimate_flights(departure, destination)

    if not flights:
        flights = get_fallback_data_source().get_flights(departure, destination)

    if not flights:
        flights = [{
            "airline": "通用航空",
            "flight_no": f"GA{random.randint(1000,9999)}",
            "departure_time": "10:00",
            "arrival_time": "14:00",
            "price": 3000,
            "duration": "4h",
            "baggage": "23kg×1",
            "seats_left": random.randint(1, 20),
            "departure_airport": f"{departure}国际机场",
            "arrival_airport": f"{destination}国际机场",
            "source": "estimate",
            "is_reference": True,
            "note": "参考航班，非实时数据",
        }]

    result = []
    for f in flights:
        if budget is None or f["price"] <= budget:
            result.append(FlightInfo(
                airline=f["airline"],
                flight_no=f["flight_no"],
                departure=departure,
                arrival=destination,
                departure_time=f["departure_time"],
                arrival_time=f["arrival_time"],
                price=f["price"],
                duration=f.get("duration", ""),
                baggage=f.get("baggage", ""),
                seats_left=f.get("seats_left", 0),
                departure_airport=f.get("departure_airport", ""),
                arrival_airport=f.get("arrival_airport", ""),
                source=f.get("source", "local"),
                is_reference=f.get("is_reference", False),
                note=f.get("note", ""),
            ))

    return sorted(result, key=lambda x: x["price"])


def search_hotels(
    city: str,
    budget_per_night: float | None = None,
    min_rating: float = 3.5
) -> list[HotelInfo]:
    """搜索酒店：在线数据源优先，取不到时回退本地数据"""
    hotels = get_data_source().get_hotels(city)
    if not hotels:
        hotels = get_fallback_data_source().get_hotels(city)

    if not hotels:
        hotels = [{
            "name": f"{city}中心酒店",
            "rating": 4.0,
            "price_per_night": 500,
            "address": f"{city}市中心",
            "highlights": ["位置便利"],
            "images": [],
            "tags": ["经济型"],
            "distance_to_station": "步行5分钟",
            "match_reason": "便利的地理位置",
            "source": "fallback",
        }]

    result = []
    for h in hotels:
        if h["rating"] >= min_rating:
            if budget_per_night is None or h["price_per_night"] <= budget_per_night:
                result.append(HotelInfo(
                    name=h["name"],
                    city=city,
                    rating=h["rating"],
                    price_per_night=h["price_per_night"],
                    address=h["address"],
                    highlights=h["highlights"],
                    images=h.get("images", []),
                    tags=h.get("tags", []),
                    distance_to_station=h.get("distance_to_station", ""),
                    match_reason=h.get("match_reason", ""),
                    lat=h.get("lat", 0),
                    lon=h.get("lon", 0),
                    source=h.get("source", "local"),
                    fields=h.get("fields", []),
                    raw=h.get("raw", {}),
                ))

    return sorted(result, key=lambda x: x["rating"], reverse=True)


def search_attractions(
    city: str,
    preferences: list[str] | None = None
) -> list[AttractionInfo]:
    """搜索景点：在线数据源优先，取不到时回退本地数据"""
    attractions = get_data_source().get_attractions(city)
    if not attractions:
        attractions = get_fallback_data_source().get_attractions(city)

    if not attractions:
        attractions = [{
            "name": f"{city}城市观光",
            "category": "文化",
            "estimated_duration": "3小时",
            "ticket_price": 50,
            "description": f"探索{city}的魅力",
            "images": [],
            "opening_hours": "9:00-17:00",
            "closing_day": "无",
            "need_booking": False,
            "rating": 4.0,
            "review_count": 1000,
            "suggested_duration": "3小时",
            "how_to_get": [],
            "tips": "",
            "tags": ["文化"],
            "lat": 0, "lon": 0,
            "source": "fallback",
        }]

    result = []
    for a in attractions:
        if not preferences or a["category"] in preferences:
            result.append(_raw_attraction(a, city))

    # 偏好没有命中任何景点时，返回全部，避免出现空行程
    if not result:
        result = [_raw_attraction(a, city) for a in attractions]

    return result


def search_food(city: str, preferences: list[str] | None = None) -> list[FoodInfo]:
    """搜索餐饮：在线数据源返回实时 POI，离线数据源返回空（由本地餐表兜底）"""
    foods = get_data_source().get_food(city)
    if not foods:
        return []

    result = []
    for f in foods:
        result.append(FoodInfo(
            name=f["name"],
            city=city,
            category=f.get("category", "美食"),
            price=f.get("price", 0),
            address=f.get("address", ""),
            rating=f.get("rating", 0),
            images=f.get("images", []),
            lat=f.get("lat", 0),
            lon=f.get("lon", 0),
            source=f.get("source", "amap"),
            fields=f.get("fields", []),
            raw=f.get("raw", {}),
        ))
    return result
