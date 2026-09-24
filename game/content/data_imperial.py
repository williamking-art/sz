# -*- coding: utf-8 -*-
"""宋祚 · 游戏内容数据 —— 帝行矩阵 / 年号 / 个人行动

从 content/data.py 拆出（零行为变更，只搬代码）。
"""
# cspell:words MEIPASS ZHONGZHI KOUYU MULT JIAOZI COEFF CHANGPING prereq steampump elecbasis elecsteel metaltype hotspot mult

# 史实年号序列
ERA_NAMES_HISTORY = {
    1101: "建中靖国",
    1102: "崇宁",
    1107: "大观",
    1111: "政和",
    1118: "重和",
    1119: "宣和",
}

# ============================================================
# 个人行动效果
# ============================================================
PERSONAL_ACTIONS = {
    "勤政": {
        "bandwidth_bonus": 2,
        "prestige_gain": 3,
        "health_cost": 2,
        "desc": "批阅奏章、召对大臣，增加圣旨带宽与皇威"
    },
    "书画翰墨": {
        "art_gain": 3,
        "prestige_gain": 1,
        "desc": "挥毫泼墨、吟诗作画，提升艺术造诣"
    },
    "崇道修醮": {
        "taoism_gain": 4,
        "treasury_cost": 50000,
        "clergy_satisfaction": 5,
        "desc": "设醮祈福、召见方士，提升道门好感，但耗费国帑"
    },
    "享乐宴游": {
        "health_cost": 5,
        "pleasure_gain": 4,
        "treasury_cost": 80000,
        "desc": "大宴群臣、游幸园林，损健康耗国帑"
    },
}

# ============================================================
# 皇帝个人行动矩阵（言枢密契约 v2 + A15 史实素材，单一权威源）
# 结构：location -> mode -> action -> 行动定义
#   label     三标签：史实 / 合理推演 / 玩法抽象（防捏造史实）
#   desc      行动说明（UI 与叙事用）
#   base_cost 程序基础开销（贯；AI 不写数值，守恒走此通道）
#   fund      资源通道：treasury=公开大驾（国库）/ imperial_treasury=微服便服（内帑）
#   risk      默认风险档（低/中/高；AI 契约可覆盖）
#   era_gate  时代门槛（年份，None=不限；艮岳1117/延福宫1113/上清宝箓宫1117/东幸镇江1126）
#   prep      公开出京准备期月数（与 prepared 联动：实际 = prep - (1 if prepared else 0)，即 1~2 月）
#   distance  微服他地距离核算（True 时按目标路距离档定装备月数）
#   micro_once 微服京城每月 1 次（程序按回合计数限）
#   base_effects 程序兜底效果（数值；AI 契约失败时以此落地，不伪造 AI 文本）
# 注：effects 落地白名单 = prestige / population_satisfaction / emperor_health /
#     art_mastery / taoism_leaning / pleasure_leaning / factions.*.satisfaction /
#     decree_bandwidth（bandwidth_bonus），与 state_applier 白名单对齐。
# ============================================================
IMPERIAL_LOCATIONS = ("宫里", "京城", "出京")
IMPERIAL_MODES = ("公开", "微服")
IMPERIAL_RISK_LEVELS = ("低", "中", "高")
# 风险概率（程序掷定）：低 2% / 中 8% / 高 20%
IMPERIAL_RISK_PROB = {"低": 0.02, "中": 0.08, "高": 0.20}

IMPERIAL_ACTION_MATRIX = {
    "宫里": {
        "公开": {
            "临朝": {
                "label": "史实", "desc": "临朝视事、批阅奏章、召对大臣",
                "base_cost": 0, "fund": "treasury", "risk": "低", "era_gate": None,
                "base_effects": {"bandwidth_bonus": 2, "prestige": 3, "emperor_health": -2},
            },
            "书画翰墨": {
                "label": "史实", "desc": "挥毫泼墨、吟诗作画，提升艺术造诣",
                "base_cost": 0, "fund": "treasury", "risk": "低", "era_gate": None,
                "base_effects": {"art_mastery": 3, "prestige": 1},
            },
            "崇道修醮": {
                "label": "史实", "desc": "设醮祈福、召见方士，提升道门好感与皇威",
                "base_cost": 50000, "fund": "treasury", "risk": "低", "era_gate": None,
                "base_effects": {"taoism_leaning": 4, "faction_change": {"新党": 3}},
            },
            "宴游享乐": {
                "label": "史实", "desc": "大宴群臣、游幸园林，损健康耗国帑",
                "base_cost": 80000, "fund": "treasury", "risk": "低", "era_gate": None,
                "base_effects": {"emperor_health": -5, "pleasure_leaning": 4},
            },
        },
        "微服": {},   # 宫里无微服（跨格子非法）
    },
    "京城": {
        "公开": {
            "幸艮岳": {
                "label": "史实", "desc": "游幸艮岳万岁山，御制《艮岳记》（政和七年始筑）",
                "base_cost": 300000, "fund": "treasury", "risk": "低", "era_gate": 1117,
                "base_effects": {"pleasure_leaning": 3, "population_satisfaction": -2},
            },
            "延福宫宴游": {
                "label": "史实", "desc": "延福宫宴游，与近臣赋诗观花（政和三年建）",
                "base_cost": 150000, "fund": "treasury", "risk": "低", "era_gate": 1113,
                "base_effects": {"pleasure_leaning": 2, "art_mastery": 1},
            },
            "上清宝箓宫": {
                "label": "史实", "desc": "驾临上清宝箓宫，会道士二千余人（政和七年）",
                "base_cost": 100000, "fund": "treasury", "risk": "低", "era_gate": 1117,
                "base_effects": {"taoism_leaning": 3, "prestige": 1},
            },
        },
        "微服": {
            "微行市井": {
                "label": "史实(方向)+合理推演", "desc": "微服夜行汴京街市酒肆（传闻细节为推演）",
                "base_cost": 20000, "fund": "imperial_treasury", "risk": "高", "era_gate": None,
                "micro_once": True, "base_effects": {"prestige": -1},
            },
            "微行大臣府第": {
                "label": "史实", "desc": "微服造访近臣宅第（《宋史·王黼传》载微行过其家）",
                "base_cost": 10000, "fund": "imperial_treasury", "risk": "中", "era_gate": None,
                "micro_once": True, "base_effects": {"prestige": 1},
            },
        },
    },
    "出京": {
        "公开": {
            "巡幸东南": {
                "label": "合理推演", "desc": "大驾巡幸东南（正史无成行，标推演）",
                "base_cost": 500000, "fund": "treasury", "risk": "中", "era_gate": None,
                "prep": 2, "bandwidth_cost": 1,
                "base_effects": {"prestige": 2, "population_satisfaction": -1},
            },
            "东幸镇江": {
                "label": "史实(避难)", "desc": "金军南下时东幸镇江避兵（靖康元年起）",
                "base_cost": 300000, "fund": "treasury", "risk": "高", "era_gate": 1126,
                "prep": 1, "bandwidth_cost": 1,
                "base_effects": {"prestige": -5, "population_satisfaction": -3},
            },
        },
        "微服": {
            "微服他地": {
                "label": "合理推演", "desc": "微服往他州路察访民情（近当月来回/中备1月/远备2月）",
                "base_cost": 50000, "fund": "imperial_treasury", "risk": "中", "era_gate": None,
                "distance": True, "base_effects": {"population_satisfaction": 2},
            },
        },
    },
}

# 微服他地距离档 → 装备月数（近=当月来回 / 中=装备1月 / 远=装备2月）
IMPERIAL_DISTANCE_MONTHS = {"近": 0, "中": 1, "远": 2}
# 目标路名 → 距离档（关键词前缀匹配；未命中默认「中」）
IMPERIAL_ROUTE_DISTANCE = {
    "近": ("开封", "京畿", "京西", "京东"),
    "中": ("河北", "河东", "淮南", "京西南", "京西北", "京东南", "京东北"),
    "远": ("陕西", "江南", "两浙", "荆湖", "四川", "广南", "福建", "燕云", "永兴", "秦凤"),
}


def imperial_distance(target: str) -> str:
    """目标州路名 → 距离档（近/中/远）；未识别默认「中」。"""
    t = str(target or "")
    for dist, kws in IMPERIAL_ROUTE_DISTANCE.items():
        if any(k in t for k in kws):
            return dist
    return "中"


def imperial_prep_months(location: str, mode: str, action: str,
                         prepared: bool = False, target: str = "") -> int:
    """行动准备期（月）：
    - 公开出京：prep 基础月数 - (1 if prepared) → 1~2 月（pending_imperial_trip 月度推进）；
    - 微服他地：按目标路距离档定装备月数（近0/中1/远2）；
    - 其余（宫里/京城）：0（当月生效）。
    """
    cell = IMPERIAL_ACTION_MATRIX.get(location, {}).get(mode, {}).get(action) or {}
    if cell.get("distance"):
        return IMPERIAL_DISTANCE_MONTHS.get(imperial_distance(target), 1)
    if location == "出京" and mode == "公开":
        return max(1, int(cell.get("prep", 2)) - (1 if prepared else 0))
    return 0


# 皇帝个人行动 AI 契约 v2 effects 键 → 落地维度（与 state_applier 白名单 path 对齐）
IMPERIAL_EFFECT_DIM = {
    "威望": "prestige",
    "民心": "population_satisfaction",
    "健康": "emperor_health",
    "心情": "pleasure_leaning",   # 心情 → 享乐/心情倾向（0~100）
}
# 0~100 刻度维度的档位基准（prestige/民心 走 ai.client_utils._TIER_BASE 同源换算）
IMPERIAL_EFFECT_BASE = {"emperor_health": 3.0, "pleasure_leaning": 3.0}

# 旧单值 personal_action → 宫里·公开 矩阵行动（旧档/旧 UI 通道迁移）
# 旧键以 PERSONAL_ACTIONS 为准（享乐宴游）；矩阵行动名为「宴游享乐」。
LEGACY_PERSONAL_ACTION_MAP = {
    "勤政": "临朝",
    "书画翰墨": "书画翰墨",
    "崇道修醮": "崇道修醮",
    "享乐宴游": "宴游享乐",
}

