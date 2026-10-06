"""国内目的地解析 —— 白名单 + 高德在线校验

系统只支持国内旅行目的地，且不局限于大城市：区县、乡镇、知名景区都能规划
（例如 稻城、婺源、乌镇、喀纳斯）。境外一律拒绝。

判定顺序（结果带缓存，避免重复请求高德）：
1. 境外黑名单命中直接拒绝：「东京」「新加坡」这类名字在国内有大量同名地点，
   不靠名单挡的话会被当成国内城市；
2. 本地白名单（含别名）命中即通过，离线可用，同时作为前端推荐的候选；
3. 高德行政区划接口：查到「市 / 区县」级即通过；查到省级时只有直辖市算通过；
4. 高德输入提示接口：首条与输入强匹配且带 adcode 的，视为国内地点
   （覆盖景区、岛屿、乡镇这类不是标准行政区划的地名）；
5. 以上都不满足则拒绝。

解析结果同时给出「检索键」：高德 POI / 天气接口对乡镇级地名（如「乌镇」）
会退化成默认城市，所以统一优先用 adcode 检索，展示仍然用用户看到的地名。
"""

from __future__ import annotations

import re

from fastapi import HTTPException, status

# 支持的目的地城市（按区域分组，供前端下拉推荐）
DOMESTIC_CITY_GROUPS: dict[str, list[str]] = {
    "华北": [
        "北京", "天津", "石家庄", "保定", "秦皇岛", "承德", "唐山", "张家口",
        "太原", "大同", "平遥", "呼和浩特", "包头", "鄂尔多斯",
    ],
    "东北": [
        "哈尔滨", "长春", "吉林", "延吉", "沈阳", "大连", "丹东", "长白山", "漠河",
    ],
    "华东": [
        "上海", "南京", "苏州", "无锡", "常州", "扬州", "镇江", "徐州", "南通", "连云港",
        "杭州", "宁波", "温州", "绍兴", "嘉兴", "湖州", "舟山", "台州", "义乌",
        "黄山", "合肥", "芜湖",
        "福州", "厦门", "泉州",
        "青岛", "济南", "烟台", "威海", "泰安", "曲阜", "日照",
    ],
    "华中": [
        "武汉", "宜昌", "恩施", "神农架", "长沙", "张家界", "凤凰", "郑州", "洛阳",
        "开封", "安阳", "南昌", "景德镇", "九江", "婺源",
    ],
    "华南": [
        "广州", "深圳", "珠海", "佛山", "东莞", "惠州", "汕头", "湛江", "肇庆",
        "桂林", "阳朔", "北海", "柳州",
        "三亚", "海口", "万宁", "陵水", "香港", "澳门",
    ],
    "西南": [
        "成都", "都江堰", "乐山", "峨眉山", "绵阳", "西昌", "稻城", "九寨沟", "重庆",
        "昆明", "大理", "丽江", "香格里拉", "西双版纳", "腾冲",
        "贵阳", "安顺", "遵义", "黔东南", "拉萨", "林芝", "日喀则",
    ],
    "西北": [
        "西安", "咸阳", "延安", "榆林", "汉中", "宝鸡", "华山",
        "敦煌", "兰州", "嘉峪关", "张掖", "天水",
        "西宁", "格尔木", "银川", "中卫", "乌鲁木齐", "吐鲁番", "喀什", "伊犁",
    ],
}

# 扁平化的城市列表（保持分组顺序）
DOMESTIC_CITIES: list[str] = [city for cities in DOMESTIC_CITY_GROUPS.values() for city in cities]

# 常见别名 / 简称 / 全称 → 标准城市名
CITY_ALIASES: dict[str, str] = {
    "京": "北京", "沪": "上海", "穗": "广州", "鹏城": "深圳", "渝": "重庆",
    "蓉城": "成都", "春城": "昆明", "冰城": "哈尔滨", "星城": "长沙", "鹭岛": "厦门",
    "鹿城": "三亚", "长安": "西安", "金陵": "南京", "姑苏": "苏州", "临安": "杭州",
    "岛城": "青岛", "武陵源": "张家界", "莫高窟": "敦煌", "乌市": "乌鲁木齐",
    "大理古城": "大理", "洱海": "大理", "玉龙雪山": "丽江", "阳朔县": "阳朔",
    "西江千户苗寨": "黔东南", "九寨沟县": "九寨沟", "中国香港": "香港",
}

# 直辖市：高德把它们的 level 标为 province
_MUNICIPALITIES = {"北京", "上海", "天津", "重庆"}

# 允许作为出发地的城市（国内主要枢纽）
DEPARTURE_CITIES: list[str] = [
    "北京", "上海", "广州", "深圳", "成都", "杭州", "西安", "重庆",
    "南京", "武汉", "长沙", "厦门", "青岛", "天津", "郑州", "昆明",
    "哈尔滨", "沈阳", "大连", "济南", "合肥", "福州", "南昌", "贵阳",
    "南宁", "海口", "三亚", "兰州", "银川", "西宁", "乌鲁木齐", "太原",
    "石家庄", "宁波", "温州", "珠海", "桂林", "呼和浩特",
]

DEFAULT_DEPARTURE = "北京"

# 行政区划后缀 / 民族名后缀（用于把「稻城县」「恩施土家族苗族自治州」压成「稻城」「恩施」）
_ADMIN_SUFFIX = re.compile(
    r"(特别行政区|自治区|自治州|自治县|地区|林区|市|省|县|区|盟|旗|都|国)$"
)
_ETHNIC_SUFFIX = re.compile(
    r"(蒙古|藏|回|维吾尔|苗|彝|壮|布依|朝鲜|满|侗|瑶|白|土家|哈尼|哈萨克|傣|黎|"
    r"傈僳|佤|畲|高山|拉祜|水|东乡|纳西|景颇|柯尔克孜|土|达斡尔|仫佬|羌|布朗|"
    r"撒拉|毛南|仡佬|锡伯|阿昌|普米|塔吉克|怒|乌孜别克|俄罗斯|鄂温克|德昂|保安|"
    r"裕固|京|塔塔尔|独龙|鄂伦春|赫哲|门巴|珞巴|基诺)+族$"
)

# 境外地名黑名单：国家 / 地区名 + 主要城市 + 热门旅游地。
# 存在的意义是「东京」「新加坡」「巴厘岛」这类名字在国内都有同名地点（甚至名字完全一致），
# 只靠高德接口无法区分，必须靠这份名单先把境外挡掉。
_OVERSEAS_NAMES = frozenset({
    # —— 国家 / 地区 ——
    "日本", "韩国", "朝鲜", "蒙古", "越南", "老挝", "柬埔寨", "缅甸", "泰国", "马来西亚",
    "新加坡", "印度尼西亚", "菲律宾", "文莱", "东帝汶", "印度", "巴基斯坦", "孟加拉",
    "尼泊尔", "不丹", "斯里兰卡", "马尔代夫", "阿富汗", "伊朗", "伊拉克", "叙利亚",
    "黎巴嫩", "约旦", "以色列", "巴勒斯坦", "沙特", "阿联酋", "卡塔尔", "科威特",
    "巴林", "阿曼", "也门", "土耳其", "格鲁吉亚", "亚美尼亚", "阿塞拜疆", "哈萨克斯坦",
    "乌兹别克斯坦", "土库曼斯坦", "塔吉克斯坦", "吉尔吉斯斯坦",
    "俄罗斯", "乌克兰", "白俄罗斯", "波兰", "捷克", "斯洛伐克", "匈牙利", "罗马尼亚",
    "保加利亚", "塞尔维亚", "克罗地亚", "斯洛文尼亚", "波黑", "黑山", "北马其顿",
    "阿尔巴尼亚", "希腊", "意大利", "西班牙", "葡萄牙", "法国", "德国", "奥地利",
    "瑞士", "荷兰", "比利时", "卢森堡", "英国", "爱尔兰", "丹麦", "挪威", "瑞典",
    "芬兰", "冰岛", "爱沙尼亚", "拉脱维亚", "立陶宛", "摩尔多瓦", "马耳他", "塞浦路斯",
    "摩纳哥", "梵蒂冈", "圣马力诺", "安道尔", "列支敦士登",
    "埃及", "摩洛哥", "阿尔及利亚", "突尼斯", "利比亚", "苏丹", "埃塞俄比亚", "肯尼亚",
    "坦桑尼亚", "乌干达", "卢旺达", "尼日利亚", "加纳", "塞内加尔", "马里", "科特迪瓦",
    "喀麦隆", "刚果", "安哥拉", "赞比亚", "津巴布韦", "博茨瓦纳", "纳米比亚", "南非",
    "马达加斯加", "毛里求斯", "塞舌尔", "索马里", "吉布提", "厄立特里亚", "乍得",
    "尼日尔", "布基纳法索", "贝宁", "多哥", "几内亚", "塞拉利昂", "利比里亚", "冈比亚",
    "佛得角", "莫桑比克", "马拉维", "莱索托", "斯威士兰",
    "美国", "加拿大", "墨西哥", "危地马拉", "伯利兹", "洪都拉斯", "萨尔瓦多",
    "尼加拉瓜", "哥斯达黎加", "巴拿马", "古巴", "牙买加", "海地", "多米尼加", "巴哈马",
    "巴巴多斯", "哥伦比亚", "委内瑞拉", "厄瓜多尔", "秘鲁", "玻利维亚", "巴西", "智利",
    "阿根廷", "乌拉圭", "巴拉圭", "圭亚那", "苏里南",
    "澳大利亚", "新西兰", "斐济", "巴布亚新几内亚", "萨摩亚", "汤加", "瓦努阿图",
    "帕劳", "密克罗尼西亚", "马绍尔群岛", "瑙鲁", "图瓦卢", "基里巴斯", "所罗门群岛",
    "南极", "北极",
    # —— 日韩 ——
    "东京", "大阪", "京都", "名古屋", "横滨", "神户", "札幌", "福冈", "广岛", "冲绳",
    "那霸", "奈良", "箱根", "镰仓", "静冈", "仙台", "长崎", "熊本", "鹿儿岛", "冈山",
    "金泽", "富山", "日光", "富士", "北海道", "本州", "九州", "四国", "热海", "轻井泽",
    "白川乡", "别府", "高松", "姬路", "宇治", "首尔", "釜山", "仁川", "大邱",
    "济州", "济州岛", "水原", "庆州", "春川", "浦项",
    # —— 东南亚 ——
    "曼谷", "清迈", "清莱", "普吉", "普吉岛", "芭提雅", "甲米", "苏梅岛", "皮皮岛",
    "华欣", "拜县", "万象", "琅勃拉邦", "金边", "暹粒", "西哈努克", "仰光", "曼德勒",
    "蒲甘", "河内", "胡志明", "岘港", "芽庄", "会安", "下龙湾", "富国岛", "沙巴",
    "吉隆坡", "槟城", "马六甲", "兰卡威", "沙捞越", "巴厘岛", "雅加达",
    "日惹", "龙目岛", "美娜多", "马尼拉", "宿务", "长滩岛", "巴拉望", "薄荷岛", "达沃",
    # —— 南亚 / 中东 / 中亚 ——
    "新德里", "孟买", "班加罗尔", "加德满都", "科伦坡", "马累", "达卡", "卡拉奇",
    "拉合尔", "迪拜", "阿布扎比", "多哈", "利雅得", "吉达", "麦加", "特拉维夫",
    "耶路撒冷", "伊斯坦布尔", "安卡拉", "德黑兰", "巴格达", "贝鲁特", "安曼",
    "马斯喀特", "科威特城", "麦纳麦", "第比利斯", "埃里温", "巴库", "阿拉木图",
    "塔什干", "比什凯克", "杜尚别", "阿什哈巴德", "乌兰巴托",
    # —— 欧洲 ——
    "伦敦", "巴黎", "罗马", "米兰", "威尼斯", "佛罗伦萨", "那不勒斯", "都灵", "热那亚",
    "博洛尼亚", "比萨", "阿姆斯特丹", "鹿特丹", "海牙", "布鲁塞尔", "安特卫普", "柏林",
    "慕尼黑", "汉堡", "法兰克福", "科隆", "斯图加特", "杜塞尔多夫", "德累斯顿", "纽伦堡",
    "海德堡", "维也纳", "萨尔茨堡", "因斯布鲁克", "苏黎世", "日内瓦", "伯尔尼",
    "卢塞恩", "巴塞尔", "洛桑", "马德里", "巴塞罗那", "瓦伦西亚", "塞维利亚",
    "格拉纳达", "里斯本", "波尔图", "雅典", "圣托里尼", "米科诺斯", "布拉格",
    "布达佩斯", "华沙", "克拉科夫", "布加勒斯特", "索非亚", "贝尔格莱德", "萨格勒布",
    "卢布尔雅那", "萨拉热窝", "地拉那", "斯科普里", "哥本哈根", "斯德哥尔摩", "奥斯陆",
    "赫尔辛基", "雷克雅未克", "塔林", "里加", "维尔纽斯", "莫斯科", "圣彼得堡",
    "叶卡捷琳堡", "新西伯利亚", "喀山", "索契", "基辅", "明斯克", "敖德萨", "都柏林",
    "爱丁堡", "曼彻斯特", "利物浦", "格拉斯哥", "剑桥", "牛津", "约克", "巨石阵",
    "尼斯", "戛纳", "马赛", "里昂", "波尔多", "图卢兹", "斯特拉斯堡", "阿尔卑斯",
    "地中海", "爱琴海",
    # —— 北美 ——
    "纽约", "洛杉矶", "旧金山", "芝加哥", "波士顿", "华盛顿", "西雅图", "拉斯维加斯",
    "迈阿密", "奥兰多", "休斯顿", "达拉斯", "费城", "亚特兰大", "丹佛", "凤凰城",
    "圣地亚哥", "波特兰", "檀香山", "夏威夷", "阿拉斯加", "温哥华", "多伦多",
    "蒙特利尔", "渥太华", "卡尔加里", "魁北克", "班夫", "惠斯勒",
    # —— 拉美 ——
    "墨西哥城", "坎昆", "哈瓦那", "巴拿马城", "圣何塞", "波哥大", "基多", "利马",
    "库斯科", "马丘比丘", "布宜诺斯艾利斯", "里约热内卢", "里约", "圣保罗", "巴西利亚",
    "蒙得维的亚", "亚松森", "拉巴斯", "乌尤尼",
    # —— 大洋洲 / 非洲 ——
    "悉尼", "墨尔本", "布里斯班", "珀斯", "阿德莱德", "堪培拉", "黄金海岸", "凯恩斯",
    "塔斯马尼亚", "奥克兰", "惠灵顿", "基督城", "皇后镇", "苏瓦", "楠迪", "大溪地",
    "关岛", "塞班", "开罗", "亚历山大", "卢克索", "阿斯旺", "卡萨布兰卡", "马拉喀什",
    "拉巴特", "阿尔及尔", "内罗毕", "蒙巴萨", "达累斯萨拉姆", "桑给巴尔",
    "亚的斯亚贝巴", "拉各斯", "阿克拉", "开普敦", "约翰内斯堡", "比勒陀利亚", "德班",
    "维多利亚瀑布", "加勒比", "撒哈拉", "佩特拉", "金字塔",
})


def _short_name(name: str) -> str:
    """「稻城县」→「稻城」；「恩施土家族苗族自治州」→「恩施」"""
    text = _ADMIN_SUFFIX.sub("", (name or "").strip())
    text = _ETHNIC_SUFFIX.sub("", text)
    return text or (name or "").strip()


def looks_overseas(name: str | None) -> bool:
    """是否命中境外地名黑名单"""
    raw = str(name).strip() if name else ""
    if not raw:
        return False
    if raw in _OVERSEAS_NAMES:
        return True
    return _ADMIN_SUFFIX.sub("", raw) in _OVERSEAS_NAMES


def _mentions_overseas(text: str) -> bool:
    """文本里是否带境外地名（用于过滤提示词里的同名地点，如「东京北华府」）"""
    if not text:
        return False
    if looks_overseas(text):
        return True
    return any(word in text for word in _OVERSEAS_NAMES)


def normalize_city(name: str | None) -> str | None:
    """本地白名单归一化：命中返回标准城市名，否则返回 None"""
    if not name:
        return None

    raw = str(name).strip()
    if not raw:
        return None

    if raw in CITY_ALIASES:
        raw = CITY_ALIASES[raw]

    if raw in DOMESTIC_CITIES:
        return raw

    # 兼容「宁波市」「北京市」这类带后缀的写法
    stripped = _ADMIN_SUFFIX.sub("", raw)
    if stripped in DOMESTIC_CITIES:
        return stripped

    return None


def _get_amap_client():
    """取高德客户端（未配置 Key 时返回 None）"""
    try:
        from app.tools.amap_client import get_amap_client

        client = get_amap_client()
    except Exception:
        return None
    return client if client.enabled else None


# 输入提示只保留「地名地址信息」与「风景名胜」两类
# （190000 含国家/省/市/区县/乡镇/村庄/街道，110000 是景区）：
# 不限定类型的话，「哈哈哈」会命中「哈哈哈蟹田营地」这种同名店铺，被当成地名放行。
_PLACE_POI_TYPES = "190000|110000"


def _best_tip(client, keyword: str) -> dict | None:
    """在输入提示里找与关键词强匹配、且带 adcode 的国内地点

    强匹配指「完全相同 / 一方是另一方的前缀」，「澳门巴黎人」这种夹在中间的同名地点不算。
    """
    for tip in client.input_tips(keyword, types=_PLACE_POI_TYPES):
        name = tip.get("name") or ""
        adcode = tip.get("adcode") or ""
        if not adcode or not name or _mentions_overseas(name):
            continue
        if name == keyword or name.startswith(keyword) or keyword.startswith(name):
            return tip
    return None


# 地名解析缓存（手动维护，只存确定性结论，见 _resolve）
_RESOLVE_CACHE_SIZE = 4096
_resolve_cache: dict[str, tuple[str, str, str]] = {}


def _resolve(name: str) -> tuple[str, str, str]:
    """解析地名 → (展示名, 检索键, 判定)，结果带缓存

    只缓存确定性结论。接口限流 / 网络抖动会导致地名解析不出结果，
    这种「unknown」不缓存，否则一次偶发失败会把某个城市永久锁死。
    """
    key = (name or "").strip()
    cached = _resolve_cache.get(key)
    if cached is not None:
        return cached

    result = _resolve_uncached(key)
    if result[2] != "unknown":
        if len(_resolve_cache) >= _RESOLVE_CACHE_SIZE:
            _resolve_cache.clear()
        _resolve_cache[key] = result
    return result


def _resolve_uncached(raw: str) -> tuple[str, str, str]:
    """解析地名 → (展示名, 检索键, 判定)

    判定取值：domestic（国内可规划）/ province（省级，需要更具体）/ overseas / unknown / empty
    """
    if not raw:
        return ("", "", "empty")

    local = normalize_city(raw)
    # 境外黑名单优先：白名单之外的词一旦命中，直接判境外
    if local is None and looks_overseas(raw):
        return ("", "", "overseas")

    display = local or raw

    client = _get_amap_client()
    if client is not None:
        districts = client.district_search(raw)

        province = next(
            (d for d in districts if d.get("level") == "province" and d.get("adcode")),
            None,
        )
        province_short = _short_name(province["name"]) if province else ""

        # 直辖市：高德给的 city 级结果是「市辖区」（adcode 如 110100），
        # 这个编码不能用作 POI 检索参数（会退化成默认城市），直接用省级编码
        if province and province_short in _MUNICIPALITIES:
            return (display, province["adcode"], "domestic")

        # 市 级：直接认定是国内目的地
        for district in districts:
            if district.get("level") == "city" and district.get("adcode"):
                return (display, district["adcode"], "domestic")

        # 省级：白名单里的（如香港、澳门）放行，其余提示要更具体的地名
        if province:
            if local:
                return (display, province["adcode"], "domestic")
            return (province_short or raw, province["adcode"], "province")

        # 区县 级：同样算国内目的地（如 稻城、婺源、义乌）
        for district in districts:
            if district.get("level") == "district" and district.get("adcode"):
                return (display, district["adcode"], "domestic")

        # 景区 / 岛屿 / 乡镇这类非标准行政区划地名，靠输入提示补上 adcode
        tip = _best_tip(client, raw)
        if tip:
            return (display, tip["adcode"], "domestic")

    # 没网或接口异常：白名单仍可用，其它一律不敢放行
    if local:
        return (local, local, "domestic")
    return ("", "", "unknown")


# 重名目的地的检索区域覆盖：同名地点太多，高德的相关性排序会选错
_SEARCH_KEY_OVERRIDES: dict[str, str] = {
    "华山": "610582",  # 陕西渭南华阴市（而不是济南历城区的华山街道）
}


def resolve_search_key(name: str | None) -> str:
    """高德检索用的城市参数：优先 adcode

    高德 POI / 天气接口对乡镇级地名（如「乌镇」）会退化成默认城市返回北京数据，
    传 adcode 才能正确定位到目标区域；展示仍然用用户看到的地名。
    """
    raw = (name or "").strip()
    if not raw:
        return ""
    display, key, verdict = _resolve(raw)
    override = _SEARCH_KEY_OVERRIDES.get(display) or _SEARCH_KEY_OVERRIDES.get(raw)
    return override or key or display or raw


def normalize_departure(name: str | None) -> str:
    """出发地归一化：白名单或在线校验通过就用它，否则回退到默认出发城市"""
    raw = (name or "").strip()

    local = normalize_city(raw)
    if local:
        return local

    display, _key, verdict = _resolve(raw)
    if verdict == "domestic" and display:
        return display

    return DEFAULT_DEPARTURE


def supported_cities_payload() -> dict:
    """给前端用的城市数据（分组 + 出发城市列表）"""
    return {
        "groups": DOMESTIC_CITY_GROUPS,
        "cities": DOMESTIC_CITIES,
        "departure_cities": DEPARTURE_CITIES,
        "default_departure": DEFAULT_DEPARTURE,
        "scope": "domestic",
    }


def ensure_domestic_city(name: str | None) -> str:
    """校验目的地必须是国内地点，否则抛出 400；返回展示用的地名"""
    raw = (name or "").strip()
    display, _key, verdict = _resolve(raw)

    if verdict == "domestic":
        return display

    shown = display or raw

    if verdict == "empty":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请输入国内目的地，例如：北京、成都、乌镇、喀纳斯",
        )

    if verdict == "province":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"「{shown}」是省级行政区，请输入具体的城市、区县或景区，例如：省会城市或热门旅游目的地",
        )

    if verdict == "overseas":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"目前仅支持国内目的地，「{shown}」属于境外，暂无法规划",
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"没有找到国内目的地「{shown}」，请检查地名是否有误，例如：北京、成都、乌镇、喀纳斯",
    )


def suggest_places(keyword: str, limit: int = 8) -> list[dict]:
    """目的地联想：本地白名单 + 高德输入提示（只要地名与景区），结果已过滤境外"""
    raw = (keyword or "").strip()
    if not raw:
        return []

    items: list[dict] = []
    seen: set[str] = set()

    def push(name: str, district: str, adcode: str) -> None:
        name = name.strip()
        if not name or name in seen:
            return
        seen.add(name)
        items.append({"name": name, "district": district.strip(), "adcode": adcode})

    for city in DOMESTIC_CITIES:
        if raw in city:
            push(city, "国内热门目的地" if city in DEPARTURE_CITIES else "", "")

    client = _get_amap_client()
    if client is not None:
        for tip in client.input_tips(raw, types=_PLACE_POI_TYPES):
            name = tip.get("name") or ""
            adcode = tip.get("adcode") or ""
            if not name or not adcode or _mentions_overseas(name):
                continue
            push(name, tip.get("district") or "", adcode)

    return items[:limit]
