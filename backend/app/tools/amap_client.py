"""高德地图 Web 服务客户端 — POI 搜索 / 路径规划 / 天气

只做网络请求与字段归一化，不掺业务逻辑。未配置 Key 或请求失败时返回空结果，
由上层决定回退策略，保证任何情况下都不会因为外部接口不可用而中断主流程。
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import app_config

logger = logging.getLogger(__name__)

# 高德 POI 类型编码
TYPE_SCENIC = "110000"      # 风景名胜
TYPE_CULTURE = "140000"     # 科教文化服务（博物馆、美术馆等）
TYPE_LEISURE = "080000"     # 体育休闲服务（公园、游乐场等）
TYPE_HOTEL = "100000"       # 住宿服务
TYPE_FOOD = "050000"        # 餐饮服务


class AmapClient:
    """高德 Web 服务封装（同步客户端，内部统一异常处理）"""

    def __init__(self) -> None:
        cfg = app_config.amap
        self._key = cfg.key.strip()
        self._timeout = cfg.timeout
        self._base = cfg.base_url.rstrip("/")

    @property
    def enabled(self) -> bool:
        return bool(self._key)

    def _get(self, path: str, params: dict) -> dict | None:
        """发起 GET 请求，失败返回 None"""
        if not self.enabled:
            return None

        params = {**params, "key": self._key, "output": "json"}
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{self._base}{path}", params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # 网络异常、超时、非 JSON 响应等
            logger.warning("高德接口调用失败 %s: %s", path, exc)
            return None

        if str(data.get("status")) != "1":
            logger.warning("高德接口返回异常 %s: %s", path, data.get("info"))
            return None
        return data

    # ---------- POI 搜索 ----------

    def search_poi(
        self,
        keywords: str,
        city: str,
        types: str | None = None,
        offset: int = 20,
        page: int = 1,
    ) -> list[dict]:
        """关键字 + 城市搜索 POI，返回归一化后的地点列表"""
        params: dict = {
            "keywords": keywords,
            "city": city,
            "citylimit": "true",
            "offset": min(offset, 25),
            "page": page,
            "extensions": "all",
        }
        if types:
            params["types"] = types

        data = self._get("/place/text", params)
        if not data:
            return []
        return [self._normalize_poi(poi, city) for poi in data.get("pois", [])]

    def search_poi_by_types(self, city: str, types: str, offset: int = 20) -> list[dict]:
        """按类型编码搜索 POI（不带关键字，适合整类获取）"""
        params = {
            "city": city,
            "citylimit": "true",
            "types": types,
            "offset": min(offset, 25),
            "page": 1,
            "extensions": "all",
        }
        data = self._get("/place/text", params)
        if not data:
            return []
        return [self._normalize_poi(poi, city) for poi in data.get("pois", [])]

    @staticmethod
    def _to_float(value, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _normalize_poi(self, poi: dict, city: str) -> dict:
        """把高德 POI 转成统一结构：核心字段 + 自适应字段列表 + 原始数据"""
        biz = poi.get("biz_ext") or {}
        if not isinstance(biz, dict):
            biz = {}

        lng, lat = 0.0, 0.0
        location = poi.get("location") or ""
        if "," in location:
            lng_s, lat_s = location.split(",", 1)
            lng, lat = self._to_float(lng_s), self._to_float(lat_s)

        photos = [p.get("url") for p in (poi.get("photos") or []) if p.get("url")]
        amap_type = poi.get("type") or ""

        rating = self._to_float(biz.get("rating"))
        cost = self._to_float(biz.get("cost"))
        tel = poi.get("tel") or ""
        if isinstance(tel, list):
            tel = " / ".join(str(t) for t in tel if t)

        # 自适应字段：外部接口有什么就展示什么
        fields: list[dict] = []
        for label, value in (
            ("地址", poi.get("address")),
            ("所在区域", f"{poi.get('cityname') or ''}{poi.get('adname') or ''}"),
            ("类型", amap_type),
            ("评分", rating if rating else None),
            ("人均/门票", f"¥{cost:g}" if cost else None),
            ("电话", tel or None),
            ("营业时间", poi.get("opentime2") or poi.get("opentime")),
            ("标签", poi.get("tag") if isinstance(poi.get("tag"), str) else None),
        ):
            if value not in (None, "", 0):
                fields.append({"label": label, "value": str(value)})

        return {
            "id": poi.get("id") or "",
            "name": poi.get("name") or "",
            "city": city,
            "address": poi.get("address") or "",
            "location": location,
            "lat": lat,
            "lon": lng,
            "amap_type": amap_type,
            "rating": rating,
            "cost": cost,
            "photos": photos,
            "tel": tel,
            "source": "amap",
            "fields": fields,
            "raw": poi,
        }

    # ---------- 路径规划 ----------

    def route(self, origin: str, destination: str, mode: str = "driving") -> dict | None:
        """两点间路线：origin/destination 为 "经度,纬度" 字符串

        返回 {"mode", "distance_m", "duration_s", "cost", "line"}，失败返回 None
        """
        if not origin or not destination:
            return None

        if mode == "driving":
            data = self._get(
                "/direction/driving",
                {"origin": origin, "destination": destination, "extensions": "base"},
            )
            if not data:
                return None
            paths = ((data.get("route") or {}).get("paths") or [])
            if not paths:
                return None
            path = paths[0]
            return {
                "mode": "driving",
                "distance_m": self._to_float(path.get("distance")),
                "duration_s": self._to_float(path.get("duration")),
                "cost": self._to_float(path.get("tolls")),
                "line": "驾车",
            }

        if mode == "walking":
            data = self._get(
                "/direction/walking",
                {"origin": origin, "destination": destination},
            )
            if not data:
                return None
            paths = ((data.get("route") or {}).get("paths") or [])
            if not paths:
                return None
            path = paths[0]
            return {
                "mode": "walking",
                "distance_m": self._to_float(path.get("distance")),
                "duration_s": self._to_float(path.get("duration")),
                "cost": 0.0,
                "line": "步行",
            }

        if mode == "transit":
            data = self._get(
                "/direction/transit/integrated",
                {"origin": origin, "destination": destination, "strategy": 0},
            )
            if not data:
                return None
            transits = ((data.get("route") or {}).get("transits") or [])
            if not transits:
                return None
            transit = transits[0]
            line_names = []
            for segment in transit.get("segments") or []:
                bus = segment.get("bus") or {}
                for busline in bus.get("buslines") or []:
                    name = busline.get("name")
                    if name:
                        line_names.append(name.split("(")[0])
            return {
                "mode": "transit",
                "distance_m": self._to_float(transit.get("distance")),
                "duration_s": self._to_float(transit.get("duration")),
                "cost": self._to_float(transit.get("cost")),
                "line": " / ".join(line_names[:2]) or "公共交通",
            }

        return None

    # ---------- 行政区划（用于判断是不是国内城市） ----------

    def district_search(self, keywords: str) -> list[dict]:
        """查询行政区划，返回 [{name, level, adcode, center}]；查不到返回空列表

        level 取值：country / province / city / district / street
        """
        data = self._get(
            "/config/district",
            {"keywords": keywords, "subdistrict": 0, "extensions": "base"},
        )
        if not data:
            return []
        return [
            {
                "name": d.get("name") or "",
                "level": d.get("level") or "",
                "adcode": d.get("adcode") or "",
                "center": d.get("center") or "",
            }
            for d in (data.get("districts") or [])
        ]

    # ---------- 输入提示（地名联想） ----------

    @staticmethod
    def _first(value) -> str:
        """输入提示接口的字段可能是字符串，也可能是空数组"""
        if isinstance(value, list):
            return str(value[0]) if value else ""
        return str(value) if value else ""

    def input_tips(self, keywords: str, types: str | None = None) -> list[dict]:
        """输入提示，返回 [{name, district, adcode, location}]；查不到返回空列表

        types 传高德 POI 类型编码可限定结果范围（如只要地名/景区），不传则返回全部类型。
        用于把用户输入的任意地名（含景点、乡镇）解析成带 adcode 的行政区划。
        """
        if not keywords:
            return []

        params: dict = {"keywords": keywords}
        if types:
            params["type"] = types

        data = self._get("/assistant/inputtips", params)
        if not data:
            return []
        return [
            {
                "name": t.get("name") or "",
                "district": self._first(t.get("district")),
                "adcode": self._first(t.get("adcode")),
                "location": self._first(t.get("location")),
            }
            for t in (data.get("tips") or [])
        ]

    # ---------- 天气 ----------

    def weather(self, city: str) -> dict | None:
        """实时天气，返回 {"condition", "temp", "wind", "humidity", "report_time"}"""
        data = self._get("/weather/weatherInfo", {"city": city, "extensions": "base"})
        if not data:
            return None
        lives = data.get("lives") or []
        if not lives:
            return None
        live = lives[0]
        return {
            "condition": live.get("weather") or "",
            "temp": f"{live.get('temperature', '')}°C" if live.get("temperature") else "",
            "wind": f"{live.get('winddirection', '')}风 {live.get('windpower', '')}级".strip(),
            "humidity": f"{live.get('humidity', '')}%" if live.get("humidity") else "",
            "report_time": live.get("reporttime") or "",
        }


_client: AmapClient | None = None


def get_amap_client() -> AmapClient:
    """获取高德客户端单例"""
    global _client
    if _client is None:
        _client = AmapClient()
    return _client
