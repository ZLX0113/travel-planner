"""高德在线数据源 — 景点 / 酒店 / 餐饮 POI、路线、天气

数据全部来自高德 Web 服务实时查询，字段随接口返回自适应（放在 fields 里传给前端渲染），
保留 raw 原始返回，方便后续接口升级时不用改代码结构。
"""

from __future__ import annotations

import logging

from app.core.cities import resolve_search_key
from app.tools.amap_client import (
    TYPE_FOOD,
    TYPE_HOTEL,
    AmapClient,
    get_amap_client,
)
from app.tools.data_source import TravelDataSource

logger = logging.getLogger(__name__)

# 高德类型 → 项目内部景点类别（供主题编排与偏好筛选使用）
# 注意：高德把绝大多数景区都归为「风景名胜」，所以判定顺序上文化类要优先于自然类
_CATEGORY_RULES: list[tuple[tuple[str, ...], str]] = [
    (("餐饮", "美食", "小吃", "咖啡", "茶艺", "糕饼", "甜品"), "美食"),
    (("购物", "商场", "超市", "市场", "专卖店", "商业街"), "购物"),
    (("博物馆", "宫殿", "古迹", "文物", "世界遗产", "文化", "寺", "庙", "教堂", "纪念馆", "美术馆", "展览", "图书馆", "故居", "广场", "遗址"), "文化"),
    (("公园", "自然", "山", "湖", "海", "温泉", "度假", "动物园", "植物园", "风景"), "自然"),
    (("娱乐", "休闲", "游乐", "影剧院", "酒吧", "KTV", "剧院", "运动", "健身"), "娱乐"),
]

# 酒店参考价区间（高德 POI 一般不含实时房价，这里按类型给出的参考估价）
_HOTEL_PRICE_HINTS: list[tuple[tuple[str, ...], float]] = [
    (("五星", "豪华", "奢华", "度假"), 1500.0),
    (("四星", "高档", "精品"), 900.0),
    (("三星", "舒适", "快捷", "连锁"), 450.0),
    (("民宿", "客栈", "青年旅舍", "旅馆"), 260.0),
]
_DEFAULT_HOTEL_PRICE = 600.0

# 关键字检索：比纯类型检索命中率高很多（类型检索会返回大量冷门 POI）
_ATTRACTION_KEYWORDS = ("著名景点", "景区", "博物馆", "公园", "古迹")
_FOOD_KEYWORDS = ("美食", "餐厅", "特色小吃")
_HOTEL_KEYWORDS = ("酒店", "宾馆", "民宿")


# 名称里带这些词的优先判为自然类（高德类型串里常混着「世界遗产」，只看类型会全归到文化）
_NATURE_NAME_HINTS = (
    "公园", "植物园", "动物园", "温泉", "森林", "湿地", "峡谷", "草原",
    "山", "湖", "海", "岛", "湾", "沙滩", "瀑布",
)


def _guess_category(amap_type: str, name: str) -> str:
    """根据名称与高德类型推断内部类别"""
    if any(hint in name for hint in _NATURE_NAME_HINTS):
        return "自然"

    haystack = f"{amap_type}{name}"
    for keywords, category in _CATEGORY_RULES:
        if any(k in haystack for k in keywords):
            return category
    return "文化"


def _estimate_hotel_price(poi: dict) -> float:
    """酒店参考价：优先用接口返回的人均/起价，否则按类型给参考区间"""
    cost = float(poi.get("cost") or 0)
    if cost > 0:
        return cost

    haystack = f"{poi.get('amap_type', '')}{poi.get('name', '')}"
    for keywords, price in _HOTEL_PRICE_HINTS:
        if any(k in haystack for k in keywords):
            return price
    return _DEFAULT_HOTEL_PRICE


class AmapDataSource(TravelDataSource):
    """基于高德 Web 服务的在线数据源"""

    def __init__(self, client: AmapClient | None = None) -> None:
        self._client = client or get_amap_client()

    @property
    def is_online(self) -> bool:
        return True

    def enabled(self) -> bool:
        return self._client.enabled

    def _search_key(self, city: str) -> str:
        """把地名转成高德检索参数

        高德 POI / 天气接口对乡镇级地名（如「乌镇」「喀纳斯」）会退化成默认城市，
        传 adcode 才能正确定位；解析不出来时退回原名。
        """
        return resolve_search_key(city) or city

    def _search_by_keywords(
        self, city: str, keywords: tuple[str, ...], offset: int = 10, types: str | None = None
    ) -> list[dict]:
        """按多个关键字分别检索并去重（关键字检索比纯类型检索命中率高）"""
        pois: list[dict] = []
        seen: set[str] = set()
        for keyword in keywords:
            for poi in self._client.search_poi(keyword, city, types=types, offset=offset):
                key = poi.get("id") or poi.get("name", "")
                if key and key not in seen:
                    seen.add(key)
                    pois.append(poi)
        return pois

    # ---------- 景点 ----------

    def get_attractions(self, city: str) -> list[dict]:
        pois = self._search_by_keywords(self._search_key(city), _ATTRACTION_KEYWORDS, offset=10)
        pois = self._drop_sub_spots(pois)
        # 按评分从高到低，保证优先选到热门景点
        pois.sort(key=lambda p: p.get("rating") or 0, reverse=True)
        return [self._to_attraction(p, city) for p in pois if p.get("name")]

    @staticmethod
    def _drop_sub_spots(pois: list[dict]) -> list[dict]:
        """过滤景区内部的子景点（如「颐和园长廊」），只保留主景点"""
        names = {p.get("name", "") for p in pois if p.get("name")}
        return [
            p
            for p in pois
            if not any(
                other != p.get("name") and other and other in p.get("name", "")
                for other in names
            )
        ]

    def _to_attraction(self, poi: dict, city: str) -> dict:
        category = _guess_category(poi.get("amap_type", ""), poi.get("name", ""))
        photos = poi.get("photos") or []
        cost = float(poi.get("cost") or 0)
        rating = float(poi.get("rating") or 0)

        fields = list(poi.get("fields") or [])
        if cost <= 0:
            # 高德 POI 多数没有门票数据，明确标注待查，避免前端误显示为"免费"
            fields.append({"label": "门票", "value": "实时票价待查（以景区官方为准）"})

        return {
            "name": poi.get("name", ""),
            "city": city,
            "category": category,
            "estimated_duration": "2小时",
            "ticket_price": cost,
            "ticket_known": cost > 0,
            "description": poi.get("address") or f"{city}{poi.get('amap_type', '')}",
            "images": photos[:3],
            "opening_hours": poi.get("raw", {}).get("opentime2", "") or "",
            "closing_day": "",
            "need_booking": False,
            "rating": rating,
            "review_count": 0,
            "suggested_duration": "2-3小时",
            "how_to_get": [],
            "tips": "",
            "tags": [t for t in (poi.get("amap_type", "").split(";") if poi.get("amap_type") else []) if t][:3],
            "lat": poi.get("lat", 0),
            "lon": poi.get("lon", 0),
            "source": "amap",
            "fields": fields,
            "raw": poi.get("raw", {}),
        }

    # ---------- 酒店 ----------

    def get_hotels(self, city: str) -> list[dict]:
        pois = self._search_by_keywords(
            self._search_key(city), _HOTEL_KEYWORDS, offset=10, types=TYPE_HOTEL
        )
        pois.sort(key=lambda p: p.get("rating") or 0, reverse=True)
        return [self._to_hotel(p, city) for p in pois if p.get("name")]

    def _to_hotel(self, poi: dict, city: str) -> dict:
        price = _estimate_hotel_price(poi)
        rating = float(poi.get("rating") or 0)
        photos = poi.get("photos") or []

        fields = list(poi.get("fields") or [])
        fields.append({"label": "价格说明", "value": "参考估价，实时房价请以预订平台为准"})

        return {
            "name": poi.get("name", ""),
            "city": city,
            "rating": rating or 4.0,
            "price_per_night": price,
            "address": poi.get("address", ""),
            "highlights": [poi.get("amap_type", "")] if poi.get("amap_type") else [],
            "images": photos[:2],
            "tags": [t for t in (poi.get("amap_type", "").split(";") if poi.get("amap_type") else []) if t][:3],
            "distance_to_station": "",
            "match_reason": "来自高德地图实时检索结果",
            "lat": poi.get("lat", 0),
            "lon": poi.get("lon", 0),
            "source": "amap",
            "fields": fields,
            "raw": poi.get("raw", {}),
        }

    # ---------- 餐饮 ----------

    def get_food(self, city: str) -> list[dict]:
        pois = self._search_by_keywords(
            self._search_key(city), _FOOD_KEYWORDS, offset=10, types=TYPE_FOOD
        )
        pois.sort(key=lambda p: p.get("rating") or 0, reverse=True)
        return [self._to_food(p, city) for p in pois if p.get("name")]

    def _to_food(self, poi: dict, city: str) -> dict:
        cost = float(poi.get("cost") or 0)
        photos = poi.get("photos") or []
        return {
            "name": poi.get("name", ""),
            "city": city,
            "category": "美食",
            "price": cost,
            "address": poi.get("address", ""),
            "rating": float(poi.get("rating") or 0),
            "images": photos[:2],
            "lat": poi.get("lat", 0),
            "lon": poi.get("lon", 0),
            "source": "amap",
            "fields": list(poi.get("fields") or []),
            "raw": poi.get("raw", {}),
        }

    # ---------- 路线与天气 ----------

    def get_route(self, origin: str, destination: str, mode: str = "driving") -> dict | None:
        return self._client.route(origin, destination, mode)

    def get_weather(self, city: str) -> dict | None:
        return self._client.weather(self._search_key(city))

    # ---------- 航班 ----------

    def get_flights(self, departure: str, destination: str) -> list[dict]:
        """高德无航班数据，返回空由上层用大模型生成参考航班"""
        return []
