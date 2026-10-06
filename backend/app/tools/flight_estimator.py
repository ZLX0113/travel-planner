"""参考航班生成 — 没有免费的实时航班接口时，用大模型生成参考航班

生成结果会带上 source=llm-reference 与 note 标注，前端可以明确提示用户
"参考航班，非实时数据，请以航司/预订平台为准"，避免把参考价当成实付价。
"""

from __future__ import annotations

import json
import logging
import re

from openai import OpenAI

from app.core.config import app_config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是航空出行数据助手。根据出发城市与目的城市，给出 3 个该航线常见的直飞航班信息。
只输出 JSON 数组，不要输出任何解释文字、不要使用 Markdown 代码块。
数组每个元素包含以下字段：
airline（航司中文名）、flight_no（航班号）、departure_time（HH:MM）、arrival_time（HH:MM）、
duration（如 3h30m）、price（经济舱常见价格，人民币整数）、baggage（行李额，如 23kg×2）、
seats_left（1-20 的整数）、departure_airport（出发机场）、arrival_airport（到达机场）。
请使用真实存在的航司名称与合理的航班号格式。"""

_JSON_BLOCK = re.compile(r"\[[\s\S]*\]")


def _extract_json(text: str) -> list[dict] | None:
    """从模型输出里提取 JSON 数组"""
    match = _JSON_BLOCK.search(text or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if isinstance(data, list) and data:
        return [item for item in data if isinstance(item, dict)]
    return None


def estimate_flights(departure: str, destination: str) -> list[dict]:
    """用大模型生成参考航班，失败返回空列表"""
    if not app_config.llm.api_key:
        return []

    try:
        client = OpenAI(
            api_key=app_config.llm.api_key,
            base_url=app_config.llm.base_url,
        )
        response = client.chat.completions.create(
            model=app_config.llm.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"出发城市：{departure}；目的城市：{destination}。请给出 3 个参考航班。",
                },
            ],
            temperature=0.3,
            max_tokens=900,
        )
        content = response.choices[0].message.content or ""
    except Exception as exc:
        logger.warning("参考航班生成失败: %s", exc)
        return []

    flights = _extract_json(content)
    if not flights:
        return []

    result: list[dict] = []
    for item in flights[:3]:
        result.append(
            {
                "airline": str(item.get("airline", "参考航司")),
                "flight_no": str(item.get("flight_no", "")),
                "departure_time": str(item.get("departure_time", "")),
                "arrival_time": str(item.get("arrival_time", "")),
                "price": float(item.get("price") or 0),
                "duration": str(item.get("duration", "")),
                "baggage": str(item.get("baggage", "")),
                "seats_left": int(item.get("seats_left") or 0),
                "departure_airport": str(item.get("departure_airport", f"{departure}机场")),
                "arrival_airport": str(item.get("arrival_airport", f"{destination}机场")),
                "source": "llm-reference",
                "is_reference": True,
                "note": "参考航班，非实时数据，请以航司或预订平台为准",
            }
        )
    return result
