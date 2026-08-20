# -*- coding: utf-8 -*-
"""宋祚 · AI 客户端工具函数（拆分自 ai/client.py）"""
import os, sys, json, re
import urllib.request
import urllib.error
from difflib import SequenceMatcher
from typing import Any

def _app_root() -> str:
    """可写资源根（配置/存档）：frozen 时用 exe 同级目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _prompt_dir() -> str:
    """只读资源根（提示词）：frozen 时打包在 _MEIPASS，否则源码目录。"""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "ai", "prompts")
    return os.path.join(_app_root(), "ai", "prompts")

_BASE = _app_root()
_PROMPT_DIR = _prompt_dir()


def _http_post_json(url: str, headers: dict, payload: dict, timeout: int = 30):
    """用标准库 urllib 发送 JSON POST，返回 (status_code, json_or_None, text)。

    替代 requests.post，避免打包进 requests 及其重型依赖（urllib3/certifi/
    cryptography），显著减小分发体积。
    """
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", "ignore")
            try:
                return resp.status, json.loads(text), text
            except Exception:
                return resp.status, None, text
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "ignore") if e.fp else ""
        try:
            return e.code, json.loads(text), text
        except Exception:
            return e.code, None, text
    except Exception:
        raise


def _load_prompt(name: str, **kwargs) -> str:
    """载入 ai/prompts/<name>.md 并把 {key} 替换为 kwargs 值。"""
    path = os.path.join(_PROMPT_DIR, f"{name}.md")
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        text = f"[提示词文件缺失: {name}]"
    for k, v in kwargs.items():
        text = text.replace("{" + k + "}", str(v))
    return text


# ============================================================
# 档位换算表（AI 只给 tier，数字由程序掷定并封顶）
# 单一权威源已迁至 content/data.py（TIER_RANGE/TIER_ORDER），此处只做导入转发
# ============================================================
from content.data import TIER_RANGE, TIER_ORDER
TIER_KEYS = list(TIER_RANGE.keys())

# 各维度档位 → 基准数值（再乘皇威乘数等）
_TIER_BASE = {
    "prestige": 4,                     # 皇威 ±
    "treasury": 800_000,               # 国帑 ±（贯）
    "population_satisfaction": 3,      # 民心 ±
    "external_jin": 4,                 # 金态度 ±
    "external_liao": 4,                # 辽态度 ±
    "external_xixia": 4,               # 西夏态度 ±
    "defense_bonus": 3,                # 城防 ±
    "commerce_tax": 0.15,              # 工商征率（设定值：tier 档位→税率，非增量）
    "curtail_waste": 100_000,          # 省浮费：月省贯（设定值）
    "reduce_office": 100_000,          # 裁汰冗员：月省贯（设定值）
    "land_survey": 0.05,               # 方田均税：清丈隐田，降隐漏率（微/小/中/大 → 0.0125/0.025/0.05/0.09）
    "hoard": 0.05,                     # 士绅囤粮：囤/抛「中」档 = 月产(囤)或屯粮(抛)的 5%（AI 推演档位）
    "finance": 800_000,                # 金融（交子/市舶收益）±
    "talent": 3,                       # 科举得才 ±
    "tech": 3,                         # 科技积累 ±
    "army": 3,                         # 军力 ±
    "reform": 3,                       # 改革推进 ±
}
# 单项封顶（防止一诏/一举过大）
_TIER_CAP = {
    "prestige": 12, "treasury": 3_000_000, "population_satisfaction": 10,
    "external_jin": 12, "external_liao": 12, "external_xixia": 12,
    "defense_bonus": 10, "finance": 3_000_000, "talent": 10, "tech": 10,
    "army": 10, "reform": 10, "land_survey": 0.10,
}


def tier_to_value(dim: str, tier: str, authority: float = 1.0) -> float:
    """档位 → 数值。dim 不在表内返回 0。tier 经 normalize_tier 归一（丰富表达→标准档）。"""
    from content.data import normalize_tier
    tier = normalize_tier(tier)
    if dim == "commerce_tax":
        # 工商征率是"设定值"而非增量：tier 档位直接映射税率（玩家诏"征几成"由 AI 归档）。
        _COMMERCE_TAX_TIER = {"无": 0.05, "微": 0.10, "小": 0.15, "中": 0.20, "大": 0.25, "巨": 0.30, "极": 0.35}
        return _COMMERCE_TAX_TIER.get(tier, 0.15)
    base = _TIER_BASE.get(dim, 0)
    mult = TIER_RANGE.get(tier, 0.0)
    cap = _TIER_CAP.get(dim, 0)
    val = base * mult * authority
    if cap > 0:
        val = max(-cap, min(cap, val))
    return round(val)


# ============================================================
# AI 输出安全过滤（对玩家隐藏不当输出）
# 与 desensitize.py 职责分离：desensitize 是「对 AI 隐藏真值」，
# 本模块是「对玩家隐藏不当输出」。
# ============================================================


def _safety_lexicon_path() -> str:
    return os.path.join(_app_root(), "ai", "safety_lexicon.json")


def load_safety_lexicon() -> list:
    """载入开源 MIT 敏感词库（含 6 类：政治违禁/辱骂/色情/暴力/自伤/赌博）。"""
    path = _safety_lexicon_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        words = []
        if isinstance(data, dict):
            for cat, lst in data.items():
                if isinstance(lst, list):
                    words.extend([str(w) for w in lst if w])
        elif isinstance(data, list):
            words = [str(w) for w in data if w]
        return words
    except (OSError, json.JSONDecodeError, ValueError):
        return []


# 模块级词库（启动时载入一次；空则不拦截，降级为放行）
_SAFETY_LEXICON = load_safety_lexicon()


def _safety_filter(raw: str) -> str:
    """扫描 AI 输出，命中敏感词则降级为兜底文本；不改游戏状态。

    返回 (text, hit)：text 为过滤后文本（命中时返回兜底说明），hit 为是否命中。
    """
    if not raw:
        return raw, False
    for w in _SAFETY_LEXICON:
        if w and w in raw:
            # 命中：降级为安全兜底，不打印玩家可见原文中的敏感片段
            return "（阁臣所奏措辞或不妥，已为陛下隐去。）", True
    return raw, False


# ============================================================
# 大臣真 function calling（可选能力：端点支持 tools 则启用，否则降级纯文本）
# 执行权在程序：模型只描述意图（tool_calls），由 _tool_dispatch 改 GameState。
# ============================================================
# 7 个工具的 JSON schema（OpenAI 兼容 tools 格式）
_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "register_draft",
            "description": "大臣为陛下草拟诏草，立案待会签。仅登记草案，不自动颁发。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "诏草事由，如『蠲免京东夏税』"},
                    "summary": {"type": "string", "description": "诏草要旨，30字内"},
                    "effects": {"type": "object", "description": "预期效果，键如 treasury/prestige/population_satisfaction/faction_sat 等，值为档位 1~5", "additionalProperties": True},
                    "secret": {"type": "boolean", "description": "是否密诏（袖中奉行），默认 false"}
                },
                "required": ["title", "summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "secret_order",
            "description": "大臣请降密令（袖中奉行，不泄于人）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "密令事由"},
                    "summary": {"type": "string", "description": "密令要旨，30字内"},
                    "longterm": {"type": "boolean", "description": "是否长期密令（持续奉行），默认 false"}
                },
                "required": ["title", "summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_treasury",
            "description": "查核国库度支实数（只读，不改状态）。用于回奏时给陛下实数。",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "propose_governance",
            "description": "大臣提长期施政或在办事务，立案俟陛下批红。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "施政条目"},
                    "summary": {"type": "string", "description": "要旨，30字内"},
                    "effects": {"type": "object", "description": "预期效果，值档位 1~5", "additionalProperties": True}
                },
                "required": ["title", "summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "personnel_nominate",
            "description": "大臣举荐或奏请任免官员。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "所举荐/处置之人名"},
                    "post": {"type": "string", "description": "拟任职务或处置，如『权知开封府』『罢黜』"},
                    "note": {"type": "string", "description": "荐语，20字内"}
                },
                "required": ["name", "post"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "military_dispatch",
            "description": "大臣请调兵或整军，奏请斧钺之命。",
            "parameters": {
                "type": "object",
                    "properties": {
                    "army": {"type": "string", "description": "军种，如 禁军/厢军/西军/北军"},
                    "action": {"type": "string", "description": "动作，如 调赴/操练/整编/增募"},
                    "target": {"type": "string", "description": "目标地或对象，如 陕西/燕京"},
                    "scale": {"type": "integer", "description": "规模档位 1~5"}
                },
                "required": ["army", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "relief_grant",
            "description": "大臣请发仓廪赈灾恤民，稍纾倒悬。",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {"type": "string", "description": "赈济地域，如 河北/淮南"},
                    "grain": {"type": "integer", "description": "发粟档位 1~5"},
                    "silver": {"type": "integer", "description": "赈银档位 1~5，可缺省"}
                },
                "required": ["region"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "offer_blueprint",
            "description": "大臣依其职司献营造新法/新制（科技或建筑蓝图），立案待陛下嘉纳。仅可在职权相关领域献策，勿越职。",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["科技", "建筑"], "description": "献的是新科技还是新建筑蓝图"},
                    "name": {"type": "string", "description": "新法/新制名，如『龙骨翻车改良』"},
                    "desc": {"type": "string", "description": "施用之法，30字内"},
                    "effect_dim": {"type": "string", "description": "预期增益维度：yield_bonus/trade_income/mining_income/army_power/build_cost/production/exam_talent/decree_speed/epidemic_risk/canal_efficiency 等"},
                    "effect_tier": {"type": "string", "enum": ["无", "微", "小", "中", "大"], "description": "增益档位"},
                    "prereq_hint": {"type": "string", "description": "所需前置科技名，须为朝中已有"}
                },
                "required": ["kind", "name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_state",
            "description": "按需查询朝廷准确数值（问到才查：本地状态直接读，不耗 AI 推理、防瞎编数字）。"
                         "target 枚举见参数；faction/road_mood 需填 name。同回合重复查询直接返回缓存。",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string",
                               "enum": ["treasury", "imperial_treasury", "granary",
                                        "army_grain", "army_pay", "people_mood", "faction",
                                        "road_mood", "grain_price", "transport", "tech_level",
                                        "talent_pool", "jiaozi_issue", "prestige"],
                               "description": "查什么：treasury=国库/imperial_treasury=内帑/"
                                             "granary=太仓/army_grain=军粮月耗/army_pay=军饷月耗/"
                                             "people_mood=民情/faction=派系满意度影响力/road_mood=某路民情/"
                                             "grain_price=粮价/transport=漕运/tech_level=科技/talent_pool=人才池/"
                                             "jiaozi_issue=交子发行/prestige=皇威"},
                    "name": {"type": "string", "description": "对象名：faction=派系名、road_mood=路名"}
                },
                "required": ["target"]
            }
        }
    },
]


def _resolve_query_target(state, target: str, name: str = "") -> str:
    """本地读精准值（不耗 AI 推理；数值直接来自 GameState，防推演漂移）。"""
    tgt = str(target or "")
    try:
        if tgt == "treasury":
            return f"国库{int(getattr(state, 'treasury', 0)):,}贯"
        if tgt == "imperial_treasury":
            return f"内帑{int(getattr(state, 'imperial_treasury', 0)):,}贯"
        if tgt == "granary":
            return f"太仓{int(getattr(state, 'granary', 0)):,}石"
        if tgt == "army_grain":
            try:
                g, _ = state.calc_army_grain(for_issue=True)
                return f"军粮实发约{int(g):,}石/月"
            except Exception:
                return "军粮数暂缺"
        if tgt == "army_pay":
            try:
                c, _ = state.calc_army_cash(for_issue=True)
                return f"军饷实发约{int(c):,}贯/月"
            except Exception:
                return "军饷数暂缺"
        if tgt == "people_mood":
            return f"民情{int(getattr(state, 'population_satisfaction', 50))}"
        if tgt == "road_mood":
            p = state.prefectures.get(name)
            if p:
                return f"{name}民情{p.get('mood', '中')}"
            return f"无{name}路"
        if tgt == "faction":
            f = state.factions.get(name)
            if f:
                return f"{name}满意度{f.get('satisfaction', 50)}影响力{f.get('influence', 50)}"
            return f"无{name}派系"
        if tgt == "grain_price":
            return f"粮价{float(getattr(state, 'grain_price', 1.0)):.2f}贯/石"
        if tgt == "transport":
            return f"漕运{int(getattr(state, 'transport', 0)):,}石/月"
        if tgt == "tech_level":
            return f"科技{int(getattr(state, 'tech', {}).get('level', 50))}"
        if tgt == "talent_pool":
            return f"人才池{int(getattr(state, 'exam', {}).get('talent_pool', 0))}"
        if tgt == "jiaozi_issue":
            return f"交子发行{int(getattr(state, 'jiaozi', {}).get('issued', 0)):,}贯"
        if tgt == "prestige":
            return f"皇威{int(getattr(state, 'prestige', 50))}"
    except Exception:
        pass
    return f"查「{tgt}」暂不可用"


def _tool_dispatch(state, tool_calls: list, minister_name: str = "") -> list:
    """程序端执行大臣的工具调用。返回 [(tool_call_id, result_text)]。

    执行权在程序：所有数值经 tier_to_value() 档位封顶，模型无权直接改状态。
    """
    mem = getattr(state, "minister_memory", None)
    if not isinstance(mem, dict):
        mem = {}
        state.minister_memory = mem
    results = []

    for tc in tool_calls or []:
        fn = tc.get("function", {})
        name = fn.get("name", "")
        try:
            args = json.loads(fn.get("arguments", "{}") or "{}")
        except (ValueError, TypeError):
            args = {}
        call_id = tc.get("id", name)
        try:
            if name == "register_draft":
                draft = {
                    "title": str(args.get("title", "未名诏草")),
                    "summary": str(args.get("summary", "")),
                    "effects": args.get("effects", {}),
                    "secret": bool(args.get("secret", False)),
                }
                did = state.add_edict_draft(draft)
                state.edict_drafts[-1]["proposer"] = minister_name
                res = f"诏草已立案，草案号 d{did}：「{draft['title']}」"
                mem.setdefault(minister_name, []).append(f"立诏草 d{did}：{draft['title']}")

            elif name == "secret_order":
                item = {
                    "title": str(args.get("title", "未名密令")),
                    "summary": str(args.get("summary", "")),
                    "longterm": bool(args.get("longterm", False)),
                }
                if item["longterm"]:
                    state.longterm_secret.append(item)
                else:
                    state.pending_secret_decrees.append(item)
                res = f"密令已藏袖中奉行：「{item['title']}」"
                mem.setdefault(minister_name, []).append(f"降密令：{item['title']}")

            elif name == "check_treasury":
                # 勾校度支消耗诏令带宽（模拟皇帝亲勾精力成本），带宽不足则只给定性
                _bw_cost = 1
                if getattr(state, "decree_bandwidth", 0) >= _bw_cost:
                    state.decree_bandwidth -= _bw_cost
                    t = getattr(state, "treasury", 0)
                    inc = state.statistics.get("total_income", 0) if isinstance(state.statistics, dict) else 0
                    exp = state.statistics.get("total_expenditure", 0) if isinstance(state.statistics, dict) else 0
                    res = f"陛下亲勾度支（耗圣旨额度{_bw_cost}）：府库约 {t:,} 缗；本月入 {inc:,}、出 {exp:,}。"
                    mem.setdefault(minister_name, []).append("奉命勾校度支（亲勾实数）")
                else:
                    # 带宽不足：只给定性，模拟"无暇细查"
                    from content.data import desensitize_treasury
                    res = f"陛下圣旨额度不足，无暇亲勾，仅知府库{desensitize_treasury(getattr(state, 'treasury', 0))}。"
                    mem.setdefault(minister_name, []).append("欲勾校度支，然无暇亲查")

            elif name == "propose_governance":
                item = {
                    "title": str(args.get("title", "未名政条")),
                    "summary": str(args.get("summary", "")),
                    "effects": args.get("effects", {}),
                }
                state.longterm_public.append(item)
                res = f"施政已立案俟批：「{item['title']}」"
                mem.setdefault(minister_name, []).append(f"提施政：{item['title']}")

            elif name == "query_state":
                # 省 token（用户定稿）：按需查询——问到才查本地精准值，同回合缓存
                tgt = str(args.get("target", ""))
                oname = str(args.get("name", ""))
                key = f"{tgt}:{oname}"
                cache = getattr(state, "_query_state_cache", None)
                if cache is None:
                    cache = {}
                    state._query_state_cache = cache
                if key in cache:
                    res = f"{tgt}（本回合已查）{cache[key]}"
                else:
                    val = _resolve_query_target(state, tgt, oname)
                    cache[key] = val
                    res = f"{tgt} {val}"
                mem.setdefault(minister_name, []).append(f"查{tgt}")

            elif name == "personnel_nominate":
                nm = str(args.get("name", "某人"))
                post = str(args.get("post", ""))
                note = str(args.get("note", ""))
                if "yamen" in state.__dict__ and isinstance(state.yamen, dict):
                    for y in state.yamen.values():
                        if isinstance(y, dict):
                            y["backlog"] = int(y.get("backlog", 0)) + 1
                res = f"已录荐牍：举 {nm} 任 {post}。{('荐语：' + note) if note else ''}"
                mem.setdefault(minister_name, []).append(f"举 {nm}→{post}")

            elif name == "military_dispatch":
                tier = str(args.get("army", "禁军"))   # army 参数实为军籍
                act = str(args.get("action", "整编"))
                tgt = str(args.get("target", ""))
                scale = max(1, min(5, int(args.get("scale", 3) or 3)))
                if tier in ("西军", "北军"):
                    tier = "禁军"
                units = [u for u in state.army_units if u.tier == tier]
                if units:
                    # 档位 scale 1~5 → 直接数值增减并封顶 0~100（勿套 tier 换算，那是档位词专用）
                    if act in ("操练", "整编"):
                        for u in units:
                            u.training = max(0, min(100, u.training + scale * 2))
                    elif act == "增募":
                        for u in units:
                            u.troops += scale * 2000   # 增募按档加兵额（真实人数）
                            u.training = max(0, min(100, u.training + scale))
                    if act == "调赴" and tgt:
                        for u in units:
                            u.station = tgt   # ArmyUnit 无 deployed_to，用 station 表达调赴
                if units:
                    res = f"军令已录：{tier} {act}{('赴' + tgt) if tgt else ''}（档 {scale}）。"
                else:
                    res = f"无此军籍：{tier}，军令未录。"
                mem.setdefault(minister_name, []).append(f"请调 {tier}{act}")

            elif name == "relief_grant":
                region = str(args.get("region", "畿内"))
                grain = max(1, min(5, int(args.get("grain", 3) or 3)))
                silver = max(0, min(5, int(args.get("silver", 0) or 0)))
                before = state.treasury
                cost = grain * 200000 + silver * 100000
                # 直接扣帑（勿套 tier 换算，before-cost 是具体金额而非档位词，套用会归零）
                state.treasury = max(0, before - cost)
                state.population_satisfaction = max(0, min(100,
                    state.population_satisfaction + grain * 2))
                state.refugee_count = max(0, state.refugee_count - grain * 5000)
                res = f"已发 {region} 仓廪赈济（粟档 {grain}，银档 {silver}），发帑约 {cost:,} 缗，民心稍纾。"
                mem.setdefault(minister_name, []).append(f"赈 {region}")

            elif name == "offer_blueprint":
                kind = str(args.get("kind", "科技"))
                bname = str(args.get("name", "")).strip()
                bdesc = str(args.get("desc", "")).strip()
                effect_dim = str(args.get("effect_dim", ""))
                effect_tier = str(args.get("effect_tier", "微"))
                prereq_hint = str(args.get("prereq_hint", "")).strip()
                if not bname:
                    res = "献策需具名（name）。"
                else:
                    tech = getattr(state, "tech", {}) or {}
                    pend = tech.setdefault("pending_inventions", [])
                    # 去重：同名献策不重复立案
                    if any(p.get("name") == bname for p in pend):
                        res = f"「{bname}」前已有大臣献策，可不必重复。"
                    else:
                        if effect_tier not in ("无", "微", "小", "中", "大", "巨", "极"):
                            effect_tier = "微"
                        pend.append({
                            "kind": "科技" if kind == "科技" else "建筑",
                            "name": bname,
                            "desc": bdesc or "未见具体施用之法",
                            "effect_dim": effect_dim,
                            "effect_tier": effect_tier,
                            "prereq_hint": prereq_hint,
                            "minister": minister_name,
                            "source": "对话献策",
                        })
                        res = f"已为陛下录「{bname}」献策（{effect_dim}·{effect_tier}），立案俟嘉纳。"
                        mem.setdefault(minister_name, []).append(f"献新制：{bname}")

            else:
                res = f"未知工具：{name}"

        except Exception as e:  # 单工具失败不影响其它
            res = f"办差受阻：{name} 执行出错（{e}）"
        # 记忆知识库（Phase 3a）：召对工具调用结构化写入图谱（promise/stance，不从叙事挖）
        try:
            mg = getattr(state, "memory", None)
            if mg is not None and minister_name:
                mg.add_entity(f"minister_{minister_name}", "minister", minister_name, turn=getattr(state, "turn", 0))
                tname = str(args.get("title", "") or args.get("target", "") or name)[:24]
                if name in ("register_draft", "secret_order", "propose_governance",
                            "personnel_nominate", "military_dispatch", "relief_grant",
                            "offer_blueprint", "check_treasury"):
                    mg.add_relation(f"minister_{minister_name}", f"tool_{name}_{tname}",
                                    "promises", weight=1.0, turn=getattr(state, "turn", 0),
                                    note=f"办差·{name}：{tname}")
                else:
                    mg.add_relation(f"minister_{minister_name}", f"tool_{name}",
                                    "stance", weight=0.8, turn=getattr(state, "turn", 0),
                                    note=f"表态·{name}")
        except Exception:
            pass
        results.append((call_id, res))

    return results


# ============================================================
# 职权献策上下文（动态按大臣当前在朝所任机构判定，非写死某臣）
# ============================================================
# 机构 → 献策领域与提示（工部最熟悉营造工技；其余机构各司其职）
_ORG_OFFER_SCOPE = {
    "工部":     "营造工技（新法新制：水利机械、冶铸营造、屯田山泽）",
    "将作监":   "营造工技（新法新制）",
    "军器监":   "军械军备（甲仗、火器新制）",
    "兵部":     "军械军备（甲仗、火器新制）",
    "枢密院":   "军械军备（甲仗、火器新制）",
    "户部":     "钱法仓储（交子、常平仓、度支盐铁会计新制）",
    "礼部":     "印书历法教育（印书局、观星台新制）",
    "翰林学士院": "印书历法教育（印书局、观星台新制）",
    "国子监":   "印书历法教育（印书局、州县学新制）",
    "内侍省":   "内廷营造（宫殿园囿新制）",
}
# 各领域可选的新制候选（AI 可从中挑，也可自行发明，须在职权内）
_ORG_OFFER_CANDIDATES = {
    "营造工技": ["水力大纺车", "焦炭冶铁", "砖石高炉", "蒸汽抽水机", "钢铁精炼"],
    "军械军备": ["火药成熟", "制式化军械", "钢铁精炼"],
    "钱法仓储": ["复式记账", "标准化", "邮政驿站"],
    "印书历法教育": ["金属活字", "邮政驿站", "标准化"],
    "内廷营造": ["标准化", "流水线"],
}


# 内廷/政府/地方 归属 → 代表机构（廷议选相关大臣时，按归属取对应中枢机构）
_ORG_BY_AFFILIATION = {
    "内廷": ["内侍省", "翰林学士院"],
    "政府": ["中书省", "门下省", "尚书省", "户部"],
    "地方": ["开封府"],
}


def _org_by_affiliation(state, org_hint: str) -> str:
    """按机构归属（内廷/政府/地方）取一个代表机构，供廷议选「相关大臣」。
    优先取该归属下第一个未裁撤且有人任职的机构。
    """
    orgs = getattr(state, "central_orgs", {}) or {}
    for key in _ORG_BY_AFFILIATION.get(org_hint, []):
        o = orgs.get(key)
        if o and not o.get("abolished") and (o.get("holders") or o.get("lead")):
            return key
    for key in _ORG_BY_AFFILIATION.get(org_hint, []):
        if key in orgs:
            return key
    return ""


def _build_offer_context(state, minister_name: str) -> str:
    """为召对注入「职权献策」上下文：让在朝大臣可依职权献新制（专家团动态回答）。

    仅当 AI 工具可用且大臣在朝时注入；不写死某人，按 current 机构 lead 判定。
    """
    try:
        orgs = getattr(state, "central_orgs", {}) or {}
        scope = ""
        candidates = []
        for oname, o in orgs.items():
            if not isinstance(o, dict):
                continue
            if o.get("lead") == minister_name and not o.get("abolished"):
                scope = _ORG_OFFER_SCOPE.get(oname, "")
                candidates = _ORG_OFFER_CANDIDATES.get(scope, [])
                if scope:
                    break
        if not scope:
            # 非实权营造机构，或非在任主官：仍给泛化的建言空间，但不强求献策
            return "\n【卿所司】卿可据己见进言国事；若涉工技营造，亦许献新法新制。"
        lines = [f"\n【卿所司之权】卿掌{scope}，工技多所谙熟，可依职权献新法新制。"]
        if candidates:
            lines.append(f"　本朝可兴之新制候选：{'、'.join(candidates)}（亦可自出新意，须在职权之内、验于实用）")
        # 注入本朝已得资产（按需，营造类召对相关则带出）
        try:
            from core.asset_context import build_asset_summary
            summ = build_asset_summary(state)
            if summ:
                lines.append(f"　{summ}（新制须承旧有之器，勿凭空杜撰）")
        except Exception:
            pass
        return "\n".join(lines)
    except Exception:
        return ""


# ============================================================
# JSON 验收层
# ============================================================
_ALLOWED_DIMS = set(_TIER_BASE.keys()) | {"faction_change"}


def _clean_text(s: str) -> str:
    if not isinstance(s, str):
        return s
    s = s.replace("“", "").replace("”", "").replace('"', "")
    s = re.sub(r"[\u2014\u2013-]{2,}", "，", s)   # 清洗破折号
    return s.strip()


def _extract_json(raw: str):
    """从模型输出里抠出第一个 JSON 对象。"""
    if raw is None:
        return None
    raw = raw.strip()
    # 去掉 ```json ... ``` 包裹：只提取围栏内文本，不用非贪婪匹配 JSON 本体，
    # 避免嵌套 JSON 被截断到第一个 } 而解析失败。
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.S)
    if fence:
        raw = fence.group(1)
    # 取第一个 { 到最后一个 }，支持嵌套对象
    a, b = raw.find("{"), raw.rfind("}")
    if a == -1 or b == -1 or b <= a:
        return None
    raw = raw[a:b + 1]
    try:
        return json.loads(raw)
    except Exception:
        return None


def _valid_tier(t: str) -> bool:
    return t in TIER_RANGE


def _normalize_effects(raw_effects) -> list:
    """把模型给出的原始 effects 归一为契约内合法列表（单一权威校验）。

    - 只保留前 4 条（[:4] 截断，防溢出）
    - faction_change：内层 value 每个键取值必须在 TIER_RANGE 内
    - commerce_tax：必须能转 float 且 0<v<=1，程序封顶后四舍五入两位
    - 其余 dim 须在 _ALLOWED_DIMS 且 tier 合法（_valid_tier）

    draft_decree / polish_decree / council_review 共用，消除三份重复。
    """
    effs = []
    for e in raw_effects[:4]:
        if not isinstance(e, dict):
            continue
        dim = e.get("dim")
        tier = e.get("tier", "无")
        if dim == "faction_change":
            fc = {}
            for k, v in (e.get("value") or {}).items():
                if v in TIER_RANGE:
                    fc[k] = v
            if fc:
                effs.append({"dim": "faction_change", "value": fc})
        elif dim == "commerce_tax":
            # 工商征率：玩家诏"征几成"可直接带精确税率值（0~1），程序封顶后应用
            v = e.get("value")
            try:
                v = float(v)
            except (TypeError, ValueError):
                v = None
            if v is not None and 0 < v <= 1:
                effs.append({"dim": "commerce_tax", "value": round(v, 2)})
        elif dim in _ALLOWED_DIMS and _valid_tier(tier):
            effs.append({"dim": dim, "tier": tier})
    return effs


def _similar(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _ai_unavailable(kind, **extra):
    """AI 不可用 / 解析失败且无补调余量时，返回统一错误标记（拒绝式，不伪造）。

    错误码见 content.data.AI_ERROR_CODES（AI_NOT_CONFIGURED 等）；上层据 `_error` 码提示配置 AI。
    """
    from content.data import AI_ERROR_CODES
    return {"_error": "AI_NOT_CONFIGURED",
            "message": AI_ERROR_CODES.get("AI_NOT_CONFIGURED", ""),
            "kind": kind, **extra}


def _error_marker(code: str, kind="", **extra):
    """按统一错误码构造错误标记（AI_TIMEOUT/AI_AUTH_FAILED/...）。"""
    from content.data import AI_ERROR_CODES
    return {"_error": code, "message": AI_ERROR_CODES.get(code, code), "kind": kind, **extra}


def _fallback_parse(text, is_secret):
    """AI 未配置时的错误标记（与在线 parse 同 schema，标注 _error 码 = AI_NOT_CONFIGURED）。"""
    from content.data import AI_ERROR_CODES
    return {
        "category": "free_edict",
        "exec_mode": "longterm",
        "title": "（AI 未接入）",
        "body": text or "",
        "params": {},
        "effects": None,
        "task": None,
        "rename": None,
        "narrative": AI_ERROR_CODES.get("AI_NOT_CONFIGURED", "AI 未接入"),
        "_error": "AI_NOT_CONFIGURED",
    }


# 便捷：把档位效果换算成可被 issue_decree 消费的 effects 字典


def effects_to_dict(effects_list, authority=1.0):
    """[{dim,tier}|{dim:'faction_change',value:{f: tier}}] → 数值字典。"""
    out = {}
    for e in effects_list:
        dim = e.get("dim")
        if dim == "faction_change":
            fc = {}
            for f, t in (e.get("value") or {}).items():
                v = tier_to_value("prestige", t, 1.0)
                fc[f] = int(v)
            if fc:
                out["faction_change"] = fc
        elif dim == "commerce_tax":
            # 工商征率：优先用 AI/玩家给的精确值（value 0~1），无 value 才回退档位
            v = e.get("value")
            try:
                v = float(v)
            except (TypeError, ValueError):
                v = None
            if v is not None and 0 < v <= 1:
                out["commerce_tax"] = round(v, 2)
            else:
                out["commerce_tax"] = tier_to_value("commerce_tax", e.get("tier", "无"), authority)
        elif dim in _TIER_BASE:
            out[dim] = tier_to_value(dim, e.get("tier", "无"), authority)
    return out


# 御笔直发可程序落地的效果键白名单（值须为数值）。
# 与 _TIER_BASE 对齐：凡 tier_to_value 能换算的键都允许 AI 给出（仍经档位→数值→封顶，
# 不会越权）。此前仅放行 7 键，导致 _apply_decree_effect 已支持的外部态度/城防/人心/
# 士绅囤粮/金融/科技/科举/军力/改革等键被丢弃，AI 拟诏能力被大幅压制。
_EFFECT_WHITELIST = tuple(_TIER_BASE.keys())


def _normalize_decree_effects(effects: dict):
    """归一化拟旨的 effects：仅保留白名单键并强制数值类型，非法键丢弃。"""
    if not isinstance(effects, dict):
        return None
    out = {}
    for k, v in effects.items():
        if k not in _EFFECT_WHITELIST:
            continue
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            continue
    return out or None


