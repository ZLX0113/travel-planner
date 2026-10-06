"""可插拔数据源 — 工具层只依赖接口，数据来源可替换

默认使用本地 JSON 文件（app/data/*.json），新增数据源时：
1. 实现 TravelDataSource 子类；
2. 在 _SOURCES 中注册；
3. 通过环境变量 DATA_SOURCE 切换即可，Agent 与工具函数无需改动。
"""

import json
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import lru_cache

from app.core.config import AppConfig, app_config


class TravelDataSource(ABC):
    """旅行数据源接口"""

    @abstractmethod
    def get_flights(self, departure: str, destination: str) -> list[dict]:
        """按出发地/目的地返回航班原始数据"""

    @abstractmethod
    def get_hotels(self, city: str) -> list[dict]:
        """按城市返回酒店原始数据"""

    @abstractmethod
    def get_attractions(self, city: str) -> list[dict]:
        """按城市返回景点原始数据"""

    def available_cities(self) -> list[str]:
        """当前数据源覆盖的城市（用于判断是否有预置数据）"""
        return []

    # ---- 以下为在线数据源的可选能力，离线数据源可不实现 ----

    def get_food(self, city: str) -> list[dict]:
        """按城市返回餐饮原始数据"""
        return []

    def get_route(self, origin: str, destination: str, mode: str = "driving") -> dict | None:
        """两点间路线（经度,纬度），返回距离与耗时；离线数据源返回 None"""
        return None

    def get_weather(self, city: str) -> dict | None:
        """实时天气；离线数据源返回 None"""
        return None

    @property
    def is_online(self) -> bool:
        """是否为在线实时数据源"""
        return False


class LocalJsonDataSource(TravelDataSource):
    """本地 JSON 文件数据源，首次访问时加载并建立索引"""

    def __init__(self, data_dir: str) -> None:
        self._data_dir = data_dir
        self._flights: dict[tuple[str, str], list[dict]] | None = None
        self._hotels: dict[str, list[dict]] | None = None
        self._attractions: dict[str, list[dict]] | None = None

    def _load(self, filename: str) -> dict:
        path = os.path.join(self._data_dir, filename)
        if not os.path.exists(path):
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _flight_index(self) -> dict[tuple[str, str], list[dict]]:
        if self._flights is None:
            routes = self._load("flights.json").get("routes", [])
            self._flights = {
                (r["departure"], r["destination"]): r["flights"] for r in routes
            }
        return self._flights

    def _hotel_index(self) -> dict[str, list[dict]]:
        if self._hotels is None:
            cities = self._load("hotels.json").get("cities", [])
            self._hotels = {c["city"]: c["hotels"] for c in cities}
        return self._hotels

    def _attraction_index(self) -> dict[str, list[dict]]:
        if self._attractions is None:
            cities = self._load("attractions.json").get("cities", [])
            self._attractions = {c["city"]: c["attractions"] for c in cities}
        return self._attractions

    def get_flights(self, departure: str, destination: str) -> list[dict]:
        return list(self._flight_index().get((departure, destination), []))

    def get_hotels(self, city: str) -> list[dict]:
        return list(self._hotel_index().get(city, []))

    def get_attractions(self, city: str) -> list[dict]:
        return list(self._attraction_index().get(city, []))

    def available_cities(self) -> list[str]:
        return sorted(set(self._hotel_index()) | set(self._attraction_index()))


def _build_amap_source(_cfg: AppConfig) -> TravelDataSource:
    """延迟导入高德数据源，避免模块循环依赖"""
    from app.tools.amap_source import AmapDataSource

    return AmapDataSource()


# 数据源注册表：新增 sqlite / api 等实现时在此登记
_SOURCES: dict[str, Callable[[AppConfig], TravelDataSource]] = {
    "local_json": lambda cfg: LocalJsonDataSource(cfg.data_dir),
    "amap": _build_amap_source,
}


def resolve_data_source_name() -> str:
    """解析实际使用的数据源：auto 表示有高德 Key 就走在线，否则回退本地 JSON"""
    name = app_config.data_source.strip().lower()
    if name != "auto":
        return name
    return "amap" if app_config.amap.enabled else "local_json"


@lru_cache(maxsize=None)
def get_data_source() -> TravelDataSource:
    """按配置返回数据源实例（进程内单例）"""
    name = resolve_data_source_name()
    builder = _SOURCES.get(name)
    if builder is None:
        raise ValueError(f"未知的数据源类型: {name}，可选: {list(_SOURCES)}")
    return builder(app_config)


@lru_cache(maxsize=None)
def get_fallback_data_source() -> TravelDataSource:
    """离线兜底数据源：在线数据源取不到数据时使用"""
    return LocalJsonDataSource(app_config.data_dir)
