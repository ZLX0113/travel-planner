"""目的地搜索路由 — 仅支持国内城市

预置了国内热门城市的概览数据，未预置的城市用 LLM 动态生成；
海外城市会在入口处被拒绝。
"""

import json
from fastapi import APIRouter, Query
from app.core.cities import ensure_domestic_city, normalize_city
from app.tools.search_tools import search_attractions, search_hotels, search_flights
from app.tools.data_source import get_data_source
from app.core.llm import get_llm_client

router = APIRouter(prefix="/api/search", tags=["search"])

# 搜索结果缓存
_search_cache: dict[str, dict] = {}

# 国内城市概览数据
CITY_OVERVIEWS = {
    "北京": {
        "name": "北京", "country": "中国",
        "description": "北京是中国的首都，拥有三千多年建城史和八百多年建都史。故宫、天安门、长城、天坛、颐和园构成最经典的历史轴线，胡同、四合院与国子监街保留着老北京的生活气息，同时也有 798、国贸这样现代的一面。",
        "best_season": "9-10月秋高气爽最佳，4-5月花开宜人",
        "currency": "人民币 (CNY)", "language": "汉语", "timezone": "UTC+8", "visa": "国内旅行，无需签证",
        "images": ["https://picsum.photos/seed/beijing-forbidden-city/800/400", "https://picsum.photos/seed/beijing-great-wall/800/400"],
        "hot_tags": ["历史古都", "长城", "故宫", "胡同", "烤鸭"],
        "daily_budget": "¥500-1500/天（不含机票）",
    },
    "上海": {
        "name": "上海", "country": "中国",
        "description": "上海是中国最大的经济中心城市，外滩万国建筑群与陆家嘴摩天楼隔江相望，梧桐树下的法租界、老弄堂与豫园古园林并存。这座城市适合步行探索，也适合安静地喝一杯咖啡看城市流动。",
        "best_season": "3-5月、9-11月最舒适",
        "currency": "人民币 (CNY)", "language": "汉语", "timezone": "UTC+8", "visa": "国内旅行，无需签证",
        "images": ["https://picsum.photos/seed/shanghai-bund/800/400", "https://picsum.photos/seed/shanghai-skyline/800/400"],
        "hot_tags": ["外滩夜景", "城市漫步", "咖啡馆", "博物馆", "小笼包"],
        "daily_budget": "¥600-1800/天（不含机票）",
    },
    "成都": {
        "name": "成都", "country": "中国",
        "description": "成都是天府之国的中心，以悠闲的生活节奏和麻辣美食闻名。大熊猫繁育研究基地、武侯祠、宽窄巷子、锦里是必去之地，周边还有青城山、都江堰与西岭雪山，是美食与自然兼得的目的地。",
        "best_season": "3-6月、9-11月最佳",
        "currency": "人民币 (CNY)", "language": "汉语", "timezone": "UTC+8", "visa": "国内旅行，无需签证",
        "images": ["https://picsum.photos/seed/chengdu-panda/800/400", "https://picsum.photos/seed/chengdu-teahouse/800/400"],
        "hot_tags": ["大熊猫", "火锅", "慢生活", "川菜", "茶馆"],
        "daily_budget": "¥400-1200/天（不含机票）",
    },
    "西安": {
        "name": "西安", "country": "中国",
        "description": "西安是十三朝古都，丝绸之路的起点。兵马俑、大雁塔、明城墙、陕西历史博物馆串起秦汉唐的厚重历史，回民街的羊肉泡馍、肉夹馍、biangbiang 面让历史变得有滋有味。",
        "best_season": "3-5月、9-11月最佳",
        "currency": "人民币 (CNY)", "language": "汉语", "timezone": "UTC+8", "visa": "国内旅行，无需签证",
        "images": ["https://picsum.photos/seed/xian-warriors/800/400", "https://picsum.photos/seed/xian-wall/800/400"],
        "hot_tags": ["兵马俑", "古城墙", "历史", "面食", "回民街"],
        "daily_budget": "¥400-1200/天（不含机票）",
    },
    "三亚": {
        "name": "三亚", "country": "中国",
        "description": "三亚是中国最南端的热带海滨城市，亚龙湾、海棠湾、大东海拥有细腻沙滩与清澈海水，蜈支洲岛适合浮潜，天涯海角、南山文化旅游区、热带天堂森林公园各有特色，是冬天避寒的首选。",
        "best_season": "10月至次年4月（避寒最佳）",
        "currency": "人民币 (CNY)", "language": "汉语", "timezone": "UTC+8", "visa": "国内旅行，无需签证",
        "images": ["https://picsum.photos/seed/sanya-beach/800/400", "https://picsum.photos/seed/sanya-bay/800/400"],
        "hot_tags": ["海岛", "沙滩", "潜水", "海鲜", "度假"],
        "daily_budget": "¥800-2500/天（不含机票）",
    },
    "杭州": {
        "name": "杭州", "country": "中国",
        "description": "杭州以西湖闻名天下，苏堤春晓、断桥残雪、三潭印月四季各有景致。灵隐寺、龙井茶园、宋城、西溪湿地与京杭大运河让这座城市兼具自然与人文，也是江南美食的代表地。",
        "best_season": "3-5月、9-11月最佳",
        "currency": "人民币 (CNY)", "language": "汉语", "timezone": "UTC+8", "visa": "国内旅行，无需签证",
        "images": ["https://picsum.photos/seed/hangzhou-westlake/800/400", "https://picsum.photos/seed/hangzhou-tea/800/400"],
        "hot_tags": ["西湖", "龙井茶", "江南园林", "宋韵", "杭帮菜"],
        "daily_budget": "¥500-1500/天（不含机票）",
    },
    "厦门": {
        "name": "厦门", "country": "中国",
        "description": "厦门是座悠闲的海滨城市，鼓浪屿的万国建筑与钢琴声、环岛路的椰林海岸、南普陀寺与厦门大学的红砖绿瓦构成独特气质，沙茶面、海蛎煎、土笋冻是地道味道。",
        "best_season": "3-5月、9-11月最佳",
        "currency": "人民币 (CNY)", "language": "汉语", "timezone": "UTC+8", "visa": "国内旅行，无需签证",
        "images": ["https://picsum.photos/seed/xiamen-gulangyu/800/400", "https://picsum.photos/seed/xiamen-coast/800/400"],
        "hot_tags": ["鼓浪屿", "海岛", "文艺", "海鲜", "环岛路"],
        "daily_budget": "¥500-1500/天（不含机票）",
    },
    "重庆": {
        "name": "重庆", "country": "中国",
        "description": "重庆是山城与江城，立体交通、轻轨穿楼、洪崖洞夜景让这里成为网红之城。火锅、小面、烤鱼代表地道江湖味，磁器口古镇、长江索道、武隆喀斯特与大足石刻丰富了行程选择。",
        "best_season": "3-5月、9-11月较舒适",
        "currency": "人民币 (CNY)", "language": "汉语", "timezone": "UTC+8", "visa": "国内旅行，无需签证",
        "images": ["https://picsum.photos/seed/chongqing-night/800/400", "https://picsum.photos/seed/chongqing-river/800/400"],
        "hot_tags": ["洪崖洞", "火锅", "轻轨穿楼", "夜景", "山城"],
        "daily_budget": "¥400-1200/天（不含机票）",
    },
    "桂林": {
        "name": "桂林", "country": "中国",
        "description": "桂林山水甲天下，漓江两岸喀斯特峰林倒影如画。象鼻山、两江四湖、龙脊梯田、阳朔西街与遇龙河竹筏漂流都是经典体验，慢下来才能感受到山水之间的宁静。",
        "best_season": "4-10月（雨水充足，山水最绿）",
        "currency": "人民币 (CNY)", "language": "汉语", "timezone": "UTC+8", "visa": "国内旅行，无需签证",
        "images": ["https://picsum.photos/seed/guilin-lijiang/800/400", "https://picsum.photos/seed/guilin-karst/800/400"],
        "hot_tags": ["漓江", "山水", "阳朔", "梯田", "竹筏"],
        "daily_budget": "¥400-1200/天（不含机票）",
    },
    "张家界": {
        "name": "张家界", "country": "中国",
        "description": "张家界以石英砂岩峰林地貌闻名，是《阿凡达》悬浮山的取景灵感来源。天门山玻璃栈道、袁家界、金鞭溪、十里画廊与天子山构成核心游览线路，适合喜欢徒步与自然奇观的旅行者。",
        "best_season": "4-6月、9-11月最佳",
        "currency": "人民币 (CNY)", "language": "汉语", "timezone": "UTC+8", "visa": "国内旅行，无需签证",
        "images": ["https://picsum.photos/seed/zhangjiajie-peaks/800/400", "https://picsum.photos/seed/zhangjiajie-glass/800/400"],
        "hot_tags": ["峰林", "天门山", "玻璃栈道", "徒步", "自然奇观"],
        "daily_budget": "¥400-1200/天（不含机票）",
    },
    "丽江": {
        "name": "丽江", "country": "中国",
        "description": "丽江是纳西族聚居的高原古城，丽江古城的青石板路、四方街的流水与东巴文化，加上玉龙雪山、束河古镇、拉市海，构成慢节奏的高原旅行体验，也是前往香格里拉与泸沽湖的门户。",
        "best_season": "4-6月、9-11月（天气晴朗）",
        "currency": "人民币 (CNY)", "language": "汉语", "timezone": "UTC+8", "visa": "国内旅行，无需签证",
        "images": ["https://picsum.photos/seed/lijiang-oldtown/800/400", "https://picsum.photos/seed/lijiang-snowmountain/800/400"],
        "hot_tags": ["古城", "玉龙雪山", "纳西文化", "高原", "慢生活"],
        "daily_budget": "¥400-1300/天（不含机票）",
    },
    "青岛": {
        "name": "青岛", "country": "中国",
        "description": "青岛是红瓦绿树、碧海蓝天的海滨城市，八大关的欧式建筑、栈桥、崂山、奥帆中心与金沙滩各有风情。啤酒博物馆与海鲜大排档是夏夜标配，整体节奏轻松舒适。",
        "best_season": "5-10月（夏季适合海滨）",
        "currency": "人民币 (CNY)", "language": "汉语", "timezone": "UTC+8", "visa": "国内旅行，无需签证",
        "images": ["https://picsum.photos/seed/qingdao-coast/800/400", "https://picsum.photos/seed/qingdao-beer/800/400"],
        "hot_tags": ["海滨", "啤酒", "八大关", "崂山", "海鲜"],
        "daily_budget": "¥500-1500/天（不含机票）",
    },
    "广州": {
        "name": "广州", "country": "中国",
        "description": "广州是岭南文化中心，既有陈家祠、沙面、永庆坊这样的历史街区，也有广州塔、珠江夜游的现代景观。早茶、烧腊、糖水构成全天候的美食日常，长隆度假区适合亲子出行。",
        "best_season": "10月至次年3月（避开湿热）",
        "currency": "人民币 (CNY)", "language": "汉语", "timezone": "UTC+8", "visa": "国内旅行，无需签证",
        "images": ["https://picsum.photos/seed/guangzhou-tower/800/400", "https://picsum.photos/seed/guangzhou-dish/800/400"],
        "hot_tags": ["早茶", "珠江夜景", "岭南文化", "长隆", "美食"],
        "daily_budget": "¥500-1500/天（不含机票）",
    },
    "哈尔滨": {
        "name": "哈尔滨", "country": "中国",
        "description": "哈尔滨被称为冰城，冬季的冰雪大世界、雪博会、中央大街与索菲亚教堂构成浓郁的欧陆风情。夏季凉爽宜人，太阳岛与松花江畔适合避暑，俄式西餐与红肠是特色味道。",
        "best_season": "12月至次年2月看冰雪，6-8月避暑",
        "currency": "人民币 (CNY)", "language": "汉语", "timezone": "UTC+8", "visa": "国内旅行，无需签证",
        "images": ["https://picsum.photos/seed/harbin-ice/800/400", "https://picsum.photos/seed/harbin-church/800/400"],
        "hot_tags": ["冰雪大世界", "中央大街", "欧式建筑", "滑雪", "俄式西餐"],
        "daily_budget": "¥400-1300/天（不含机票）",
    },
    "敦煌": {
        "name": "敦煌", "country": "中国",
        "description": "敦煌是丝绸之路上的重镇，莫高窟的壁画彩塑是世界文化遗产，鸣沙山月牙泉的沙泉共生奇观、雅丹魔鬼城的戈壁地貌与玉门关遗址共同构成大漠风情，夜晚星空极佳。",
        "best_season": "5-10月（9-10月最佳）",
        "currency": "人民币 (CNY)", "language": "汉语", "timezone": "UTC+8", "visa": "国内旅行，无需签证",
        "images": ["https://picsum.photos/seed/dunhuang-mogao/800/400", "https://picsum.photos/seed/dunhuang-dune/800/400"],
        "hot_tags": ["莫高窟", "鸣沙山", "月牙泉", "戈壁", "丝路"],
        "daily_budget": "¥400-1200/天（不含机票）",
    },
}


async def _llm_generate_city_data(city: str, departure: str = "北京") -> dict:
    """使用 LLM 生成国内城市搜索数据（仅用于未预置概览的城市）"""
    llm = get_llm_client()
    client = llm.get_client()

    prompt = f"""你是一个专业的国内旅行数据专家。请为中国的"{city}"生成真实的旅行搜索数据，以 JSON 格式返回。

要求：
1. 只要国内城市的数据，所有景点、酒店都必须是"{city}"当地真实存在的地方
2. 景点名称、描述、开放时间、门票价格、交通方式都要真实
3. 酒店名称、地址、价格要符合实际市场行情
4. 航班信息要合理（从{departure}出发的国内航线）

请严格按照以下 JSON 格式返回，不要添加任何额外说明：

```json
{{
  "overview": {{
    "name": "城市名",
    "country": "中国",
    "description": "150字以内的城市介绍，突出特色",
    "best_season": "最佳旅行季节和原因",
    "currency": "人民币 (CNY)",
    "language": "汉语",
    "timezone": "UTC+8",
    "visa": "国内旅行，无需签证",
    "hot_tags": ["标签1", "标签2", "标签3", "标签4", "标签5"],
    "daily_budget": "人均每日预算范围（人民币）"
  }},
  "attractions": [
    {{
      "name": "景点名称",
      "category": "文化/自然/美食/购物/娱乐",
      "estimated_duration": "建议游玩时长",
      "ticket_price": 门票价格(人民币),
      "description": "50字以内景点描述",
      "opening_hours": "开放时间",
      "closing_day": "闭馆日",
      "need_booking": true/false,
      "rating": 4.0-5.0,
      "review_count": 评论数,
      "suggested_duration": "建议游玩时长",
      "tips": "实用贴士",
      "tags": ["标签1", "标签2"],
      "how_to_get": [{{"mode": "交通方式", "route": "路线", "duration": "耗时", "price": 费用(人民币)}}]
    }}
  ],
  "hotels": [
    {{
      "name": "酒店名称",
      "rating": 评分,
      "price_per_night": 每晚价格(人民币),
      "address": "具体地址",
      "tags": ["标签1", "标签2"],
      "distance_to_station": "距最近交通站距离",
      "match_reason": "推荐理由（50字以内）"
    }}
  ],
  "flights": [
    {{
      "airline": "航司名称",
      "flight_no": "航班号",
      "departure_time": "出发时间",
      "arrival_time": "到达时间",
      "price": 价格(人民币),
      "duration": "飞行时长",
      "baggage": "行李额度",
      "seats_left": 剩余座位数,
      "departure_airport": "出发机场",
      "arrival_airport": "到达机场"
    }}
  ]
}}
```

重要：
- attractions 提供 5-6 个真实景点
- hotels 提供 3-4 个真实酒店，覆盖经济型到豪华型
- flights 提供 2-3 个真实航班
- 所有价格单位为人民币
- 只返回 JSON，不要任何额外文字"""

    try:
        response = await client.chat.completions.create(
            model=llm.get_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4096,
        )
        content = response.choices[0].message.content or ""

        # 提取 JSON
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            data = json.loads(content[json_start:json_end])
            return data
    except Exception as e:
        print(f"LLM 生成 {city} 数据失败: {e}")

    return None


def _build_fallback(city: str) -> dict:
    """构建兜底数据（国内城市通用）"""
    return {
        "overview": {
            "name": city, "country": "中国",
            "description": f"{city}是国内值得一去的旅行目的地，有丰富的自然与人文景观，适合安排 3-5 天的深度旅行。",
            "best_season": "春季（3-5月）与秋季（9-11月）较为舒适",
            "currency": "人民币 (CNY)", "language": "汉语", "timezone": "UTC+8",
            "visa": "国内旅行，无需签证",
            "images": [f"https://picsum.photos/seed/{city}1/800/400", f"https://picsum.photos/seed/{city}2/800/400"],
            "hot_tags": ["国内旅行", "自然风光", "人文历史"],
            "daily_budget": "¥400-1500/天（不含机票）",
        },
        "attractions": search_attractions(city),
        "hotels": search_hotels(city),
        "flights": search_flights("北京", city),
    }


@router.get("")
async def search_destination(q: str = Query(..., description="搜索关键词（国内城市名）")):
    """搜索国内目的地：优先使用预置数据，否则用 LLM 动态生成

    海外城市会返回 400，与规划接口保持一致的口径。
    """
    # 校验并归一化城市名（海外城市在这里被拒绝）
    city = ensure_domestic_city(q)
    # 命中预置概览的城市用标准名
    if city not in CITY_OVERVIEWS:
        matched = normalize_city(city)
        city = matched or city

    # 检查缓存
    cache_key = city.lower()
    if cache_key in _search_cache:
        return _search_cache[cache_key]

    # 检查数据源中是否有充足的预置数据（>1 个景点说明有真实数据）
    has_mock = city in CITY_OVERVIEWS and len(get_data_source().get_attractions(city)) > 1

    if has_mock:
        # 使用预置数据
        result = {
            "overview": CITY_OVERVIEWS[city],
            "attractions": search_attractions(city),
            "hotels": search_hotels(city),
            "flights": search_flights("北京", city),
        }
        _search_cache[cache_key] = result
        return result

    # LLM 动态生成
    llm_data = await _llm_generate_city_data(city)

    if llm_data and llm_data.get("attractions") and len(llm_data["attractions"]) > 1:
        overview = llm_data["overview"]
        overview["country"] = "中国"
        overview["visa"] = "国内旅行，无需签证"
        overview["images"] = [
            f"https://picsum.photos/seed/{city}1/800/400",
            f"https://picsum.photos/seed/{city}2/800/400",
        ]

        result = {
            "overview": overview,
            "attractions": llm_data["attractions"],
            "hotels": llm_data["hotels"],
            "flights": llm_data["flights"],
        }
        _search_cache[cache_key] = result
        return result

    # 兜底
    return _build_fallback(city)
