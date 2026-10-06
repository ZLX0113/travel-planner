"""行程模板构建器 — 将搜索结果编排为结构化 DayPlan

在线数据源可用时（配置了高德 Key），交通时长/费用、天气、三餐都取实时数据；
取不到则回退到本地估算，保证离线也能出完整行程。
"""

from datetime import datetime, timedelta
from app.agents.state import (
    DayPlan,
    FlightInfo,
    HotelInfo,
    AttractionInfo,
)
from app.tools.data_source import get_data_source
from app.tools.search_tools import search_food

# 三餐参考价（在线 POI 没有人均数据时使用）
MEAL_DEFAULT_PRICE = {"早餐": 40, "午餐": 80, "晚餐": 150}


# ============ 在线数据辅助 ============

def _online_source():
    """在线数据源，不可用时返回 None"""
    try:
        source = get_data_source()
        return source if source.is_online else None
    except Exception:
        return None


def meals_for_strategy(city: str, strategy: str | None = None) -> dict | None:
    """用在线餐饮 POI 生成三餐建议，按价格档位切分以支持多版本差异化

    strategy: budget（最便宜一档）/ comfort（中间档）/ trendy（最贵一档）/ None（全部混合）
    """
    try:
        foods = search_food(city)
    except Exception:
        return None
    if not foods:
        return None

    priced = sorted(foods, key=lambda f: f.get("price") or 0)
    if strategy == "budget":
        picked = priced[: max(3, len(priced) // 3)]
    elif strategy == "trendy":
        picked = priced[-max(3, len(priced) // 3):]
    elif strategy == "comfort":
        third = max(3, len(priced) // 3)
        picked = priced[third: third * 2] or priced
    else:
        picked = priced

    meal_names = ["早餐", "午餐", "晚餐"]
    buckets: dict[str, list] = {name: [] for name in meal_names}
    used_brands: set[str] = set()
    for idx, food in enumerate(picked):
        meal = meal_names[idx % 3]
        if len(buckets[meal]) >= 3:
            continue
        # 同一家店（同名不同分店）只取一次，避免三餐推荐重复
        brand = str(food.get("name", "")).split("(")[0].strip()
        if brand and brand in used_brands:
            continue
        used_brands.add(brand)
        price = float(food.get("price") or 0) or MEAL_DEFAULT_PRICE[meal]
        buckets[meal].append({
            "suggestion": food.get("name", ""),
            "price": price,
            "address": food.get("address", ""),
            "rating": food.get("rating", 0),
            "lat": food.get("lat", 0),
            "lon": food.get("lon", 0),
            "source": food.get("source", "amap"),
            "fields": [
                {"label": "人均", "value": f"¥{price:g}"},
                {"label": "地址", "value": food.get("address", "")},
                {"label": "评分", "value": str(food.get("rating") or "")},
            ],
        })

    if not any(buckets.values()):
        return None
    return buckets


_ROUTE_CACHE: dict[tuple[str, str, str], dict | None] = {}


def online_transit(
    origin: tuple[float, float] | None,
    destination: tuple[float, float] | None,
    mode: str = "driving",
) -> dict | None:
    """通过在线数据源获取两点间真实路线（距离/耗时/费用），带进程内缓存"""
    source = _online_source()
    if source is None or not origin or not destination:
        return None
    if not origin[0] or not origin[1] or not destination[0] or not destination[1]:
        return None

    origin_str = f"{origin[0]},{origin[1]}"
    dest_str = f"{destination[0]},{destination[1]}"
    cache_key = (origin_str, dest_str, mode)
    if cache_key in _ROUTE_CACHE:
        return _ROUTE_CACHE[cache_key]

    try:
        result = source.get_route(origin_str, dest_str, mode)
    except Exception:
        result = None
    _ROUTE_CACHE[cache_key] = result
    return result


def build_transit_detail(
    origin: dict,
    destination: dict,
    fallback_mode: str,
    fallback_route: str,
    fallback_duration: str,
    fallback_price: float,
) -> dict:
    """交通详情：优先用在线实时路线，取不到时用本地估算"""
    detail: dict = {
        "mode": fallback_mode,
        "route": fallback_route,
        "duration": fallback_duration,
        "price": fallback_price,
        "source": "estimate",
        "fields": [],
    }

    route = online_transit(
        (origin.get("lon", 0), origin.get("lat", 0)),
        (destination.get("lon", 0), destination.get("lat", 0)),
        "driving",
    )
    if not route:
        return detail

    distance_km = (route.get("distance_m") or 0) / 1000
    duration_min = int(round((route.get("duration_s") or 0) / 60))
    # 打车费按里程估算（起步价 + 每公里单价），在线接口只返回里程与耗时
    est_price = max(route.get("cost") or 0, round(distance_km * 2.5 + 10))

    detail.update({
        "mode": "🚕 打车",
        "route": "实时路线规划",
        "duration": f"{duration_min}分钟" if duration_min else fallback_duration,
        "price": est_price,
        "source": "amap",
        "distanceKm": round(distance_km, 1),
        "fields": [
            {"label": "距离", "value": f"{distance_km:.1f} 公里"},
            {"label": "预计耗时", "value": f"{duration_min} 分钟" if duration_min else "待查"},
            {"label": "打车预估", "value": f"¥{est_price:g}"},
            {"label": "数据来源", "value": "高德实时路线规划"},
        ],
    })
    return detail


def attraction_detail(attr: dict) -> dict:
    """景点节点详情：核心字段 + 数据源自适应字段（fields 供前端动态渲染）"""
    return {
        "name": attr["name"],
        "images": attr.get("images", []),
        "ticketPrice": attr.get("ticket_price", 0),
        "free": attr.get("ticket_price", 0) == 0,
        "ticketKnown": attr.get("ticket_known", True),
        "openingHours": attr.get("opening_hours", ""),
        "closingDay": attr.get("closing_day", ""),
        "needBooking": attr.get("need_booking", False),
        "rating": attr.get("rating", 0),
        "reviewCount": attr.get("review_count", 0),
        "suggestedDuration": attr.get("suggested_duration", attr.get("estimated_duration", "2小时")),
        "howToGet": attr.get("how_to_get", []),
        "tips": attr.get("tips", ""),
        "tags": attr.get("tags", []),
        "address": attr.get("description", ""),
        "lat": attr.get("lat", 0),
        "lon": attr.get("lon", 0),
        "source": attr.get("source", "local"),
        "fields": attr.get("fields", []),
    }


def meal_detail(meal: dict, note: str) -> dict:
    """餐饮节点详情：价格 + 备注 + 数据源自适应字段"""
    detail: dict = {
        "price": meal.get("price", 0),
        "notes": note,
        "lat": meal.get("lat", 0),
        "lon": meal.get("lon", 0),
    }
    if meal.get("fields"):
        detail["fields"] = meal["fields"]
    if meal.get("address"):
        detail["address"] = meal["address"]
    if meal.get("source"):
        detail["source"] = meal["source"]
    return detail


def online_weather(city: str) -> dict | None:
    """通过在线数据源获取实时天气"""
    source = _online_source()
    if source is None or not city:
        return None
    try:
        return source.get_weather(city)
    except Exception:
        return None


# 三餐建议（按城市，每日不重样）
MEAL_SUGGESTIONS = {
    "北京": {
        "早餐": [
            {"suggestion": "老北京豆汁配焦圈+烧饼", "price": 25},
            {"suggestion": "包子铺猪肉大葱包+豆浆", "price": 18},
            {"suggestion": "煎饼果子+豆腐脑", "price": 15},
        ],
        "午餐": [
            {"suggestion": "老北京炸酱面+小菜", "price": 45},
            {"suggestion": "卤煮火烧/炒肝+包子", "price": 40},
            {"suggestion": "烤鸭店午餐套餐", "price": 120},
        ],
        "晚餐": [
            {"suggestion": "铜锅涮肉+麻酱烧饼", "price": 150},
            {"suggestion": "北京烤鸭（整只+配菜）", "price": 220},
            {"suggestion": "京味家常菜馆", "price": 110},
        ],
    },
    "上海": {
        "早餐": [
            {"suggestion": "生煎包+咸豆浆", "price": 20},
            {"suggestion": "南翔小笼+小馄饨", "price": 35},
            {"suggestion": "四大金刚（大饼油条粢饭豆浆）", "price": 16},
        ],
        "午餐": [
            {"suggestion": "本帮面馆（辣肉面/大排面）", "price": 35},
            {"suggestion": "小笼+蟹壳黄+汤", "price": 55},
            {"suggestion": "商场餐厅工作日套餐", "price": 60},
        ],
        "晚餐": [
            {"suggestion": "本帮菜（红烧肉/油爆虾）", "price": 160},
            {"suggestion": "蟹粉小笼+蟹宴", "price": 220},
            {"suggestion": "夜市小海鲜+啤酒", "price": 130},
        ],
    },
    "成都": {
        "早餐": [
            {"suggestion": "担担面+蛋烘糕", "price": 18},
            {"suggestion": "肥肠粉+锅盔", "price": 20},
            {"suggestion": "红油抄手+豆浆", "price": 15},
        ],
        "午餐": [
            {"suggestion": "川菜小炒（回锅肉/麻婆豆腐）", "price": 50},
            {"suggestion": "龙抄手套餐+钟水饺", "price": 45},
            {"suggestion": "冒菜+米饭", "price": 35},
        ],
        "晚餐": [
            {"suggestion": "成都火锅（鸳鸯锅+毛肚）", "price": 130},
            {"suggestion": "串串香+冰粉", "price": 80},
            {"suggestion": "川味江湖菜馆", "price": 110},
        ],
    },
    "西安": {
        "早餐": [
            {"suggestion": "肉夹馍+胡辣汤", "price": 20},
            {"suggestion": "牛羊肉泡馍（自己掰馍）", "price": 45},
            {"suggestion": "甑糕+油茶麻花", "price": 15},
        ],
        "午餐": [
            {"suggestion": "油泼面+凉皮", "price": 30},
            {"suggestion": "biangbiang面+肉夹馍", "price": 40},
            {"suggestion": "葫芦头泡馍", "price": 38},
        ],
        "晚餐": [
            {"suggestion": "回民街小吃巡礼（烤肉/柿子饼）", "price": 90},
            {"suggestion": "陕菜馆（葫芦鸡/金线油塔）", "price": 120},
            {"suggestion": "烤肉+冰峰+烤馍", "price": 70},
        ],
    },
    "广州": {
        "早餐": [
            {"suggestion": "肠粉+艇仔粥", "price": 22},
            {"suggestion": "早茶（虾饺/烧卖/凤爪）", "price": 80},
            {"suggestion": "生滚粥+油条", "price": 20},
        ],
        "午餐": [
            {"suggestion": "烧腊饭（叉烧/烧鹅）", "price": 40},
            {"suggestion": "云吞面+牛杂", "price": 35},
            {"suggestion": "煲仔饭+例汤", "price": 45},
        ],
        "晚餐": [
            {"suggestion": "粤菜小炒+老火靓汤", "price": 140},
            {"suggestion": "砂锅粥+炒牛河", "price": 110},
            {"suggestion": "宵夜大排档（炒螺/烤生蚝）", "price": 100},
        ],
    },
    "杭州": {
        "早餐": [
            {"suggestion": "片儿川+小笼包", "price": 25},
            {"suggestion": "生煎+豆浆+粢饭团", "price": 18},
            {"suggestion": "知味观小笼+猫耳朵", "price": 35},
        ],
        "午餐": [
            {"suggestion": "杭帮面（虾爆鳝面/腰花面）", "price": 40},
            {"suggestion": "楼外楼简餐（东坡肉+龙井虾仁）", "price": 110},
            {"suggestion": "景区附近家常菜", "price": 60},
        ],
        "晚餐": [
            {"suggestion": "杭帮菜馆（西湖醋鱼/宋嫂鱼羹）", "price": 150},
            {"suggestion": "东坡肉+叫花鸡+龙井茶", "price": 130},
            {"suggestion": "河坊街小吃街巡礼", "price": 80},
        ],
    },
}

DEFAULT_MEALS = {
    "早餐": [
        {"suggestion": "本地早市特色早餐（包子/面食+豆浆）", "price": 20},
        {"suggestion": "酒店自助早餐", "price": 45},
        {"suggestion": "街头老字号早点", "price": 25},
    ],
    "午餐": [
        {"suggestion": "当地特色面食或快餐", "price": 40},
        {"suggestion": "景区附近本地菜简餐", "price": 60},
        {"suggestion": "当地招牌小吃套餐", "price": 50},
    ],
    "晚餐": [
        {"suggestion": "当地特色菜馆（2-3 道招牌菜）", "price": 120},
        {"suggestion": "夜市小吃+本地啤酒", "price": 80},
        {"suggestion": "老字号餐厅正餐", "price": 150},
    ],
}

# 特殊人群关怀规则：key 与前端 PlanForm 的 specialNeeds 取值保持一致
# max_attractions 控制每天最多安排几个景点，rest 表示需要插入午休节点
SPECIAL_NEED_RULES: dict[str, dict] = {
    "infant": {
        "label": "婴幼儿（0-3岁）",
        "max_attractions": 2,
        "rest": True,
        "tips": [
            "景点之间预留哺乳、换尿布的时间，优先选有母婴室的场馆",
            "建议带轻便推车，避开台阶多、需要长时间抱娃的景区",
        ],
    },
    "child": {
        "label": "儿童（4-12岁）",
        "max_attractions": 3,
        "rest": False,
        "tips": [
            "穿插亲子互动项目，控制单段步行距离，避免孩子体力透支",
            "避开需要长时间排队的项目，热门场馆提前网上预约",
        ],
    },
    "senior": {
        "label": "老人（60+）",
        "max_attractions": 2,
        "rest": True,
        "tips": [
            "每天留出午休时间，景点间尽量打车，减少换乘和长距离步行",
            "优先走电梯、无障碍入口，避免登山和连续上下台阶",
        ],
    },
    "pregnant": {
        "label": "孕妇",
        "max_attractions": 2,
        "rest": True,
        "tips": [
            "避免颠簸路段与剧烈活动，行程随时可就近休息",
            "随身带水和小食，避开人流高峰时段，注意防晒防滑",
        ],
    },
    "accessible": {
        "label": "无障碍需求",
        "max_attractions": 3,
        "rest": True,
        "tips": [
            "优先选择有无障碍通道的景点与酒店，出发前确认电梯位置",
            "提前电话确认景区轮椅租借与无障碍卫生间情况",
        ],
    },
}


def build_itinerary(
    flights: list[FlightInfo],
    hotels: list[HotelInfo],
    attractions: list[AttractionInfo],
    days: int,
    destination: str,
    selected_flight_index: int = 0,
    selected_hotel_index: int = 0,
    start_date: str | None = None,
    meals_input: dict | None = None,
    special_needs: list[str] | None = None,
) -> list[DayPlan]:
    """根据搜索结果构建每日行程 — 每天3-4个景点，含三餐和交通，每天主题不同

    special_needs 命中时（有小孩 / 老人 / 孕妇 / 无障碍需求）会相应放缓节奏、
    减少每日景点、插入午休节点，并在每天给出针对性提醒。
    """
    if start_date is None:
        start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # 特殊人群关怀：取各项里最严格的每日景点上限，任一项需要休息就插入午休
    needs = [n for n in (special_needs or []) if n in SPECIAL_NEED_RULES]
    care_labels = [SPECIAL_NEED_RULES[n]["label"] for n in needs]
    care_tips = [tip for n in needs for tip in SPECIAL_NEED_RULES[n]["tips"]]
    max_per_day = min([4] + [SPECIAL_NEED_RULES[n]["max_attractions"] for n in needs])
    min_per_day = min(3, max_per_day)
    need_break = any(SPECIAL_NEED_RULES[n]["rest"] for n in needs)

    base_date = datetime.strptime(start_date, "%Y-%m-%d")
    # 餐饮优先级：版本策略指定的餐表 → 在线实时餐饮 POI → 本地餐表 → 通用兜底
    meals = meals_input or meals_for_strategy(destination) or MEAL_SUGGESTIONS.get(destination, DEFAULT_MEALS)
    # 兼容旧格式：如果是列表则转为新格式
    if isinstance(meals, list):
        meals = {
            "早餐": [{"suggestion": meals[0]["suggestion"], "price": meals[0]["price"]}],
            "午餐": [{"suggestion": meals[1]["suggestion"], "price": meals[1]["price"]}],
            "晚餐": [{"suggestion": meals[2]["suggestion"], "price": meals[2]["price"]}],
        }

    # 每天不同主题 + 对应的景点类别偏好
    day_themes = ["经典探索", "深度体验", "隐藏乐趣", "文化巡礼", "休闲放松", "购物狂欢", "美食之旅"]
    # 每个主题优先选择的景点类别（按优先级排列，确保每天风格不同）
    theme_category_prefs = {
        "经典探索": ["文化", "自然", "美食", "购物", "娱乐"],
        "深度体验": ["文化", "美食", "自然", "娱乐", "购物"],
        "隐藏乐趣": ["自然", "娱乐", "美食", "文化", "购物"],
        "文化巡礼": ["文化", "购物", "自然", "美食", "娱乐"],
        "休闲放松": ["自然", "美食", "文化", "娱乐", "购物"],
        "购物狂欢": ["购物", "美食", "娱乐", "文化", "自然"],
        "美食之旅": ["美食", "购物", "娱乐", "自然", "文化"],
    }
    day_notes = [
        "首日适应节奏，安排经典地标景点，轻松开启旅程",
        "精力充沛的一天，深入探索当地文化精髓",
        "行程过半，放慢节奏，发现城市隐藏的惊喜角落",
        "沉浸式文化体验，感受城市的历史底蕴与艺术气息",
        "放松身心的一天，享受自然风光与悠闲时光",
        "购物和美食的狂欢日，尽情享受消费乐趣",
        "最后一天，用美食为旅程画上完美句号",
    ]

    # === 按主题分配景点：每天从不同类别优先选取 ===
    all_attrs = list(attractions)
    # 按类别分组
    by_category: dict[str, list] = {}
    for attr in all_attrs:
        cat = attr.get("category", "文化")
        by_category.setdefault(cat, []).append(attr)

    daily_attractions: list[list[AttractionInfo]] = [[] for _ in range(days)]
    used_attrs: set[str] = set()  # 已分配的景点名称，确保不重复

    for day in range(days):
        theme = day_themes[day % len(day_themes)]
        prefs = theme_category_prefs.get(theme, ["文化", "自然", "美食", "购物", "娱乐"])
        day_attrs = daily_attractions[day]

        # 按主题偏好顺序，从各类别中取景点
        for cat in prefs:
            if len(day_attrs) >= max_per_day:
                break
            candidates = [a for a in by_category.get(cat, []) if a["name"] not in used_attrs]
            # 每天每类最多取2个，保证多样性
            taken = 0
            for a in candidates:
                if len(day_attrs) >= max_per_day or taken >= 2:
                    break
                day_attrs.append(a)
                used_attrs.add(a["name"])
                taken += 1

        # 兜底：保证每天至少 min_per_day 个景点，不足时从未分配的景点里补齐
        if len(day_attrs) < min_per_day:
            remaining = [a for a in all_attrs if a["name"] not in used_attrs]
            for a in remaining:
                if len(day_attrs) >= max_per_day:
                    break
                day_attrs.append(a)
                used_attrs.add(a["name"])

    # 天气：在线数据源可用时取实时天气，否则用占位值
    weather = online_weather(destination) or {"condition": "晴", "temp": "25°C"}

    itinerary: list[DayPlan] = []

    for day in range(days):
        date = base_date + timedelta(days=day)
        date_str = date.strftime("%m月%d日")
        day_label = f"Day {day + 1}"
        theme = day_themes[day % len(day_themes)]
        note = day_notes[day % len(day_notes)]

        # 每日不同餐饮索引
        meal_idx = day % 3

        nodes = []
        activities = []

        # === 早餐 ===
        breakfast_list = meals.get("早餐", [{"suggestion": "当地早餐", "price": 50}])
        breakfast = breakfast_list[meal_idx % len(breakfast_list)]
        nodes.append({
            "time": "08:00",
            "type": "meal",
            "title": breakfast["suggestion"],
            "category": "早餐",
            "detail": meal_detail(breakfast, "享用当地特色早餐，为一天的行程补充能量"),
        })

        # === 上午景点 ===
        morning_attrs = daily_attractions[day][:2]
        for i, attr in enumerate(morning_attrs):
            hour = 9 + i * 2
            hour_str = f"{hour:02d}:00"

            nodes.append({
                "time": hour_str,
                "type": "attraction",
                "title": attr["name"],
                "category": attr.get("category", ""),
                "detail": attraction_detail(attr),
            })

            activities.append({
                "name": attr["name"],
                "time": "上午",
                "duration": attr["estimated_duration"],
                "notes": attr["description"],
                "category": attr["category"],
                "ticket_price": attr["ticket_price"],
            })

            # 景点间通勤
            if i < len(morning_attrs) - 1:
                next_attr = morning_attrs[i + 1]
                transit_hour = hour + 2
                nodes.append({
                    "time": f"{transit_hour:02d}:00",
                    "type": "transit",
                    "title": f"{attr['name']} → {next_attr['name']}",
                    "category": "交通",
                    "detail": build_transit_detail(
                        attr, next_attr,
                        fallback_mode="🚇 地铁",
                        fallback_route="乘坐地铁约3站",
                        fallback_duration="15分钟",
                        fallback_price=180,
                    ),
                })

        # === 午餐 ===
        lunch_list = meals.get("午餐", [{"suggestion": "当地午餐", "price": 80}])
        lunch = lunch_list[meal_idx % len(lunch_list)]
        nodes.append({
            "time": "12:30",
            "type": "meal",
            "title": lunch["suggestion"],
            "category": "午餐",
            "detail": meal_detail(lunch, "上午游览结束，就近品尝当地美食"),
        })

        # === 午休：有老人 / 婴幼儿 / 孕妇 / 无障碍需求时插入 ===
        if need_break:
            nodes.append({
                "time": "13:30",
                "type": "break",
                "title": "午休 & 休整",
                "category": "关怀安排",
                "detail": {
                    "duration": "1小时",
                    "tips": "回酒店或就近找咖啡厅休息，恢复体力后再开始下午行程",
                    "fields": [
                        {"label": "关怀对象", "value": "、".join(care_labels)},
                        {"label": "建议", "value": "避免连续赶路，下午行程按体力灵活增减"},
                    ],
                },
            })

        # === 下午景点 ===
        afternoon_attrs = daily_attractions[day][2:]
        for i, attr in enumerate(afternoon_attrs):
            hour = 14 + i * 2
            hour_str = f"{hour:02d}:00"

            nodes.append({
                "time": hour_str,
                "type": "attraction",
                "title": attr["name"],
                "category": attr.get("category", ""),
                "detail": attraction_detail(attr),
            })

            activities.append({
                "name": attr["name"],
                "time": "下午" if i == 0 else "傍晚",
                "duration": attr["estimated_duration"],
                "notes": attr["description"],
                "category": attr["category"],
                "ticket_price": attr["ticket_price"],
            })

            # 景点间通勤
            if i < len(afternoon_attrs) - 1:
                next_attr = afternoon_attrs[i + 1]
                transit_hour = hour + 2
                nodes.append({
                    "time": f"{transit_hour:02d}:00",
                    "type": "transit",
                    "title": f"{attr['name']} → {next_attr['name']}",
                    "category": "交通",
                    "detail": build_transit_detail(
                        attr, next_attr,
                        fallback_mode="🚇 地铁",
                        fallback_route="乘坐地铁约3站",
                        fallback_duration="15分钟",
                        fallback_price=180,
                    ),
                })

        # 最后景点到酒店的通勤
        last_attr = daily_attractions[day][-1] if daily_attractions[day] else None
        if last_attr and hotels and selected_hotel_index < len(hotels):
            h = hotels[selected_hotel_index]
            nodes.append({
                "time": "17:00",
                "type": "transit",
                "title": f"{last_attr['name']} → {h['name']}",
                "category": "交通",
                "detail": build_transit_detail(
                    last_attr, h,
                    fallback_mode="🚇 地铁",
                    fallback_route="返回酒店",
                    fallback_duration="20分钟",
                    fallback_price=200,
                ),
            })

        # === 晚餐 ===
        dinner_list = meals.get("晚餐", [{"suggestion": "当地晚餐", "price": 150}])
        dinner = dinner_list[meal_idx % len(dinner_list)]
        nodes.append({
            "time": "18:30",
            "type": "meal",
            "title": dinner["suggestion"],
            "category": "晚餐",
            "detail": meal_detail(dinner, "一天游览结束，尽情享受当地美食"),
        })

        # === 酒店入住 ===
        hotel_detail = {}
        if hotels and selected_hotel_index < len(hotels):
            h = hotels[selected_hotel_index]
            hotel_detail = {
                "name": h["name"],
                "images": h.get("images", []),
                "star": h.get("rating", 0),
                "address": h.get("address", ""),
                "pricePerNight": h.get("price_per_night", 0),
                "distanceToStation": h.get("distance_to_station", h.get("highlights", ["近地铁"])[0] if isinstance(h.get("highlights"), list) and h.get("highlights") else "近地铁"),
                "tags": h.get("tags", []) or h.get("highlights", [])[:3],
                "matchReason": h.get("match_reason", "紧邻今日最后一个景点，减少往返绕行"),
                "lat": h.get("lat", 0),
                "lon": h.get("lon", 0),
                "source": h.get("source", "local"),
                "fields": h.get("fields", []),
            }

        nodes.append({
            "time": "20:00",
            "type": "rest",
            "title": f"入住 {hotel_detail.get('name', '酒店')}",
            "category": "住宿",
            "detail": hotel_detail,
        })

        notes = ""
        if day == 0 and flights and selected_flight_index < len(flights):
            f = flights[selected_flight_index]
            notes = f"✈️ 推荐航班 {f['airline']} {f['flight_no']}，{f['departure_time']}-{f['arrival_time']}，¥{f['price']}"

        # 有特殊人群时，在当天主题说明里点出来，前端也会单独展示关怀提示
        if care_labels:
            note = f"{note}（{'、'.join(care_labels)}同行，今日节奏已放缓、景点数已精简）"

        itinerary.append(DayPlan(
            day=day + 1,
            date=f"Day {day + 1} ({date_str})",
            theme=theme,
            activities=activities,
            nodes=nodes,
            meals=[
                {"type": "早餐", "suggestion": breakfast["suggestion"]},
                {"type": "午餐", "suggestion": lunch["suggestion"]},
                {"type": "晚餐", "suggestion": dinner["suggestion"]},
            ],
            hotel=hotel_detail,
            notes=note,
            careTips=care_tips,
            weather=weather,
        ))

    return itinerary


def itinerary_to_markdown(
    itinerary: list[DayPlan],
    destination: str,
    flight_info: dict | None = None,
    hotel_info: dict | None = None,
) -> str:
    """将行程转换为 Markdown 格式输出"""
    lines = [f"# 🗺️ {destination} {len(itinerary)}天旅行行程\n"]

    if flight_info:
        lines.append("## ✈️ 推荐航班\n")
        lines.append(f"- **{flight_info['airline']} {flight_info['flight_no']}**")
        lines.append(f"- {flight_info['departure']} → {flight_info['arrival']}")
        lines.append(f"- {flight_info['departure_time']} - {flight_info['arrival_time']}")
        lines.append(f"- 票价: ¥{flight_info['price']}/人\n")

    if hotel_info:
        lines.append("## 🏨 推荐酒店\n")
        lines.append(f"- **{hotel_info['name']}** ⭐{hotel_info['rating']}")
        lines.append(f"- 地址: {hotel_info['address']}")
        lines.append(f"- 价格: ¥{hotel_info['price_per_night']}/晚")
        if 'highlights' in hotel_info:
            lines.append(f"- 亮点: {' | '.join(hotel_info['highlights'])}\n")

    lines.append("## 📅 每日行程\n")

    for plan in itinerary:
        lines.append(f"### {plan['date']}")
        if plan.get("theme"):
            lines.append(f"🎯 主题: {plan['theme']}")
        hotel_name = plan['hotel'].get('name', '待定') if isinstance(plan['hotel'], dict) else (plan['hotel'] or '待定')
        lines.append(f"🏨 住宿: {hotel_name}")
        if plan.get("weather"):
            lines.append(f"🌤️ 天气: {plan['weather']['condition']} {plan['weather']['temp']}")
        lines.append("")
        lines.append("| 时间 | 类型 | 内容 |")
        lines.append("|------|------|------|")

        if plan["activities"]:
            lines.append("\n| 时段 | 景点 | 类别 | 时长 | 门票 | 说明 |")
            lines.append("|------|------|------|------|------|------|")
            for act in plan["activities"]:
                notes_short = act['notes'][:30] + "..." if len(act['notes']) > 30 else act['notes']
                lines.append(
                    f"| {act['time']} | {act['name']} | {act['category']} | {act['duration']} | ¥{act['ticket_price']} | {notes_short} |"
                )
        else:
            lines.append("（自由安排）")

        lines.append(f"\n🍽️ 餐饮建议:")
        for meal in plan["meals"]:
            lines.append(f"- {meal['type']}: {meal['suggestion']}")

        if plan["notes"]:
            lines.append(f"\n💡 {plan['notes']}")

        lines.append("\n---\n")

    return "\n".join(lines)


def modify_itinerary(
    itinerary: list[DayPlan],
    attractions: list[AttractionInfo],
    modify_request: str,
) -> tuple[list[DayPlan], str]:
    """根据用户修改指令，局部调整行程
    
    Args:
        itinerary: 当前行程
        attractions: 可选景点池
        modify_request: 用户修改指令，如 "第三天换成海边景点"
    
    Returns:
        (修改后的行程, 修改说明)
    """
    import re
    
    # 解析修改指令：提取目标天数
    cn_num_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    day_match = re.search(r'第\s*(\d+|[一二三四五六七八九十]+)\s*天', modify_request)
    if not day_match:
        return itinerary, "未能识别修改的目标天数，请用'第X天'的格式描述。"
    
    day_str = day_match.group(1)
    if day_str.isdigit():
        target_day = int(day_str)
    else:
        target_day = cn_num_map.get(day_str, 0)
        if target_day == 0:
            return itinerary, f"无法识别天数 '{day_str}'，请用数字或中文数字表示。"
    if target_day < 1 or target_day > len(itinerary):
        return itinerary, f"只有 {len(itinerary)} 天行程，第{target_day}天不存在。"
    
    # 提取目标类别
    category_map = {
        "海边": "自然", "自然": "自然", "寺庙": "文化", "文化": "文化",
        "美食": "美食", "吃": "美食", "购物": "购物", "买": "购物",
        "娱乐": "娱乐", "玩": "娱乐", "乐园": "娱乐",
        "网红": "购物", "打卡": "文化",
    }
    
    target_category = None
    for keyword, cat in category_map.items():
        if keyword in modify_request:
            target_category = cat
            break
    
    if not target_category:
        existing_cats = {a["category"] for a in itinerary[target_day - 1]["activities"]}
        for cat in ["文化", "美食", "购物", "自然", "娱乐"]:
            if cat not in existing_cats:
                target_category = cat
                break
        if not target_category:
            target_category = "文化"
    
    # 从景点池中找匹配的替换景点
    day_plan = itinerary[target_day - 1]
    current_attraction_names = {a["name"] for a in day_plan["activities"]}
    
    candidates = [a for a in attractions if a["category"] == target_category and a["name"] not in current_attraction_names]
    
    if not candidates:
        return itinerary, f"没有找到新的{target_category}类景点可替换。"
    
    # 替换第一个活动
    replacement = candidates[0]
    old_activity = day_plan["activities"][0] if day_plan["activities"] else {"name": "无"}
    
    day_plan["activities"][0] = {
        "name": replacement["name"],
        "time": "上午",
        "duration": replacement["estimated_duration"],
        "notes": replacement["description"],
        "category": replacement["category"],
        "ticket_price": replacement["ticket_price"],
    }
    
    day_plan["notes"] = f"🔄 已替换: {old_activity['name']} → {replacement['name']}"
    
    return itinerary, f"已将第{target_day}天的 {old_activity['name']} 替换为 {replacement['name']}（{replacement['category']}类）"


# 版本策略定义
VERSION_STRATEGIES = {
    "budget": {
        "label": "💰 省钱版",
        "description": "精打细算，高性价比，优先免费景点和公共交通",
        "hotel_budget_ratio": 0.15,
        "flight_budget_ratio": 0.25,
        "attraction_budget_ratio": 0.05,
        "preference_weights": {"美食": 3, "自然": 2, "文化": 1, "购物": 0, "娱乐": 0},
        "hotel_index": 0,  # 选最便宜的酒店
        "flight_index": 0,  # 选最便宜的航班
        "meals": {
            "早餐": [
                {"suggestion": "包子豆浆/煎饼果子", "price": 12},
                {"suggestion": "便利店早餐+现磨豆浆", "price": 10},
                {"suggestion": "社区面馆小碗面", "price": 15},
            ],
            "午餐": [
                {"suggestion": "快餐盖饭/兰州拉面", "price": 25},
                {"suggestion": "沙县小吃套餐", "price": 20},
                {"suggestion": "街边面馆+小菜", "price": 22},
            ],
            "晚餐": [
                {"suggestion": "社区小炒/麻辣烫", "price": 45},
                {"suggestion": "快餐套餐+饮品", "price": 35},
                {"suggestion": "夜市小吃（烤串/煎饼）", "price": 40},
            ],
        },
    },
    "comfort": {
        "label": "⭐ 舒适版",
        "description": "品质出行，舒适体验，兼顾经典景点与美食",
        "hotel_budget_ratio": 0.30,
        "flight_budget_ratio": 0.30,
        "attraction_budget_ratio": 0.15,
        "preference_weights": {"文化": 3, "美食": 2, "购物": 1, "自然": 1, "娱乐": 0},
        "hotel_index": 1,  # 选中档酒店
        "flight_index": 1,  # 选中间航班
        "meals": {
            "早餐": [
                {"suggestion": "酒店自助早餐", "price": 50},
                {"suggestion": "老字号早餐店（本地特色）", "price": 35},
                {"suggestion": "咖啡馆+现烤面包", "price": 45},
            ],
            "午餐": [
                {"suggestion": "本地特色餐厅（招牌菜2道）", "price": 80},
                {"suggestion": "商场餐厅套餐", "price": 70},
                {"suggestion": "特色面馆/小吃组合", "price": 60},
            ],
            "晚餐": [
                {"suggestion": "本地菜馆（4菜1汤）", "price": 150},
                {"suggestion": "火锅/烤肉双人餐", "price": 130},
                {"suggestion": "江河海鲜餐厅", "price": 140},
            ],
        },
    },
    "trendy": {
        "label": "📸 网红打卡版",
        "description": "出片第一，潮流体验，打卡最火景点和餐厅",
        "hotel_budget_ratio": 0.35,
        "flight_budget_ratio": 0.30,
        "attraction_budget_ratio": 0.20,
        "preference_weights": {"娱乐": 3, "购物": 3, "美食": 2, "文化": 1, "自然": 0},
        "hotel_index": 2,  # 选最贵的酒店（如果够）
        "flight_index": 2,  # 选最好的航班
        "meals": {
            "早餐": [
                {"suggestion": "网红 Brunch 店（出片早餐）", "price": 90},
                {"suggestion": "精品咖啡+手工欧包", "price": 70},
                {"suggestion": "网红早茶/甜品店", "price": 85},
            ],
            "午餐": [
                {"suggestion": "网红餐厅/米其林推荐", "price": 200},
                {"suggestion": "景观餐厅（窗边位）", "price": 180},
                {"suggestion": "创意融合料理", "price": 160},
            ],
            "晚餐": [
                {"suggestion": "高端餐厅/星级酒店晚餐", "price": 350},
                {"suggestion": "城市观景餐厅晚餐", "price": 300},
                {"suggestion": "网红火锅/烧烤打卡", "price": 280},
            ],
        },
    },
}


def generate_version_plan(
    flights: list[FlightInfo],
    hotels: list[HotelInfo],
    attractions: list[AttractionInfo],
    days: int,
    destination: str,
    budget: float | None,
    strategy: str,
    travelers: int = 1,
    start_date: str | None = None,
    special_needs: list[str] | None = None,
) -> dict:
    """根据策略生成单版本方案 — 真正差异化三个版本"""
    from app.tools.budget_calculator import calculate_budget

    strat = VERSION_STRATEGIES.get(strategy, VERSION_STRATEGIES["comfort"])

    # ===== 1. 按策略差异化选酒店 =====
    sorted_hotels = sorted(hotels, key=lambda h: h["price_per_night"])
    hotel_idx = min(strat["hotel_index"], len(sorted_hotels) - 1) if sorted_hotels else 0
    selected_hotels = [sorted_hotels[hotel_idx]] if sorted_hotels else hotels

    # ===== 2. 按策略差异化选航班 =====
    sorted_flights = sorted(flights, key=lambda f: f["price"])
    flight_idx = min(strat["flight_index"], len(sorted_flights) - 1) if sorted_flights else 0
    selected_flights = [sorted_flights[flight_idx]] if sorted_flights else flights

    # ===== 3. 按策略差异化选景点 =====
    weights = strat["preference_weights"]
    scored_attractions = []
    for a in attractions:
        # 按策略权重打分，免费景点有加分
        score = weights.get(a["category"], 0) * 10 + (5 if a["ticket_price"] == 0 else 0)
        scored_attractions.append((score, a))
    scored_attractions.sort(key=lambda x: x[0], reverse=True)

    # 每个版本从不同偏移量开始取景点，确保三个版本景点差异明显
    face_offsets = {"budget": 0, "comfort": 3, "trendy": 6}
    face_offset = face_offsets.get(strategy, 0)
    needs = days * 4  # 每天最多4个景点
    selected_attractions = [a for _, a in scored_attractions[face_offset:face_offset + needs]]

    # 如果选出的景点不够，从剩余景点中补充
    if len(selected_attractions) < needs:
        all_selected_names = {a["name"] for a in selected_attractions}
        remaining = [a for _, a in scored_attractions if a["name"] not in all_selected_names]
        selected_attractions += remaining[:needs - len(selected_attractions)]

    # 如果还不够，从头循环补充（确保每天至少2个景点）
    if len(selected_attractions) < days * 2:
        remaining = [a for _, a in scored_attractions if a["name"] not in {s["name"] for s in selected_attractions}]
        selected_attractions += remaining
        # 去重
        seen = set()
        unique = []
        for a in selected_attractions:
            if a["name"] not in seen:
                seen.add(a["name"])
                unique.append(a)
        selected_attractions = unique

    # ===== 4. 按策略差异化餐饮 =====
    # 有在线餐饮数据时按价格档位取真实的店，否则用本地版本餐表
    version_meals = (
        meals_for_strategy(destination, strategy)
        or strat.get("meals", MEAL_SUGGESTIONS.get(destination, DEFAULT_MEALS))
    )

    # ===== 5. 构建行程 =====
    itinerary = build_itinerary(
        flights=selected_flights,
        hotels=selected_hotels,
        attractions=selected_attractions,
        days=days,
        destination=destination,
        selected_flight_index=0,
        selected_hotel_index=0,
        meals_input=version_meals,
        start_date=start_date,
        special_needs=special_needs,
    )

    # ===== 6. 计算预算 =====
    # 计算一天三餐总价（取每种餐的第1个选项）
    daily_meal_cost = 0
    for meal_type in ["早餐", "午餐", "晚餐"]:
        meal_opts = version_meals.get(meal_type, [{"price": 0}])
        daily_meal_cost += meal_opts[0]["price"] if isinstance(meal_opts, list) else meal_opts.get("price", 0)
    budget_breakdown = calculate_budget(
        flights=selected_flights,
        hotels=selected_hotels,
        attractions=selected_attractions,
        days=days,
        meals_per_day=daily_meal_cost,
        travelers=travelers,
    )

    return {
        "id": strategy,
        "label": strat["label"],
        "description": strat["description"],
        "itinerary": itinerary,
        "budget": budget_breakdown.to_dict(),
        # 该版本选中的机票与酒店，供前端在“版本详情”里单独展示
        "flight": selected_flights[0] if selected_flights else None,
        "hotel": selected_hotels[0] if selected_hotels else None,
    }


def generate_versions(
    flights: list[FlightInfo],
    hotels: list[HotelInfo],
    attractions: list[AttractionInfo],
    days: int,
    destination: str,
    budget: float | None = None,
    travelers: int = 1,
    start_date: str | None = None,
    special_needs: list[str] | None = None,
) -> list[dict]:
    """生成多版本方案对比（省钱版/舒适版/网红版）"""
    versions = []
    for strategy in ["budget", "comfort", "trendy"]:
        version = generate_version_plan(
            flights=flights,
            hotels=hotels,
            attractions=attractions,
            days=days,
            destination=destination,
            budget=budget,
            strategy=strategy,
            travelers=travelers,
            start_date=start_date,
            special_needs=special_needs,
        )
        versions.append(version)
    return versions