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
# 档位→数值换算基值/封顶：单一权威源在 content/data.py（审查 P1-2/P2-3 修复）。
# content.data 顶层只 import os/sys，无循环导入风险，可直接顶层 import。
from content.data import TIER_VALUE_BASE as _TIER_BASE, TIER_VALUE_CAP as _TIER_CAP

# 向后兼容别名（部分测试/旧代码直接引用 _TIER_BASE/_TIER_CAP）
# _TIER_BASE/_TIER_CAP 已是 content.data.TIER_VALUE_BASE/TIER_VALUE_CAP 的引用


def _ensure_tier_tables():
    """兼容占位：_TIER_BASE/_TIER_CAP 已在顶层填充，此函数保留供旧调用路径无副作用调用。"""
    pass


def _load_tier_tables():
    return _TIER_BASE, _TIER_CAP


def tier_to_value(dim: str, tier: str, authority: float = 1.0) -> float:
    """档位 → 数值。dim 不在表内返回 0。tier 经 normalize_tier 归一（丰富表达→标准档）。"""
    from content.data import normalize_tier
    tier = normalize_tier(tier)
    if dim == "commerce_tax":
        # 工商征率是"设定值"而非增量：tier 档位直接映射税率（玩家诏"征几成"由 AI 归档）。
        _COMMERCE_TAX_TIER = {"无": 0.05, "微": 0.10, "小": 0.15, "中": 0.20, "大": 0.25, "巨": 0.30, "极": 0.35}
        return _COMMERCE_TAX_TIER.get(tier, 0.15)
    base_v = _TIER_BASE.get(dim, 0)
    mult = TIER_RANGE.get(tier, 0.0)
    cap = _TIER_CAP.get(dim, 0)
    val = base_v * mult * authority
    if cap > 0:
        val = max(-cap, min(cap, val))
    # 保留小数精度（小档位 微0.25/小0.5 不能被 round 成 0）
    return round(val, 4)


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

# ============================================================
# T1 · 结构化变更工具 schema（降级链 fallback 用；审查 P1-4 修复注释）
# 审查澄清：当前生产中 AI 改状态的实际通道是「JSON 契约 + 12 步结算/free_effect/
# _tool_dispatch 消费」，而非 Function Call + update_state。STATE_TOOL_SCHEMAS 作为
# _call_with_tools 降级链的 fallback schema 保留（_call_with_tools 暂无生产调用方，
# 为未来接线预留）。update_state 的 path 白名单须与 engine/state_applier.VALID_PATHS
# 对齐后再接线。叙事文本绝不改状态（铁律 1 本质已落地）。
# ============================================================
STATE_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "update_state",
            "description": "通过结构化变更修改游戏状态（AI 唯一改状态通道）。"
                           "changes 数组每项必带 reason；op 枚举 set/add/mul/remove/push。"
                           "数值只给档位词或程序换算量级，守恒由程序校验。",
            "parameters": {
                "type": "object",
                "properties": {
                    "changes": {
                        "type": "array",
                        "description": "状态变更列表",
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "JSON 路径，如 treasury / factions.新党.satisfaction"},
                                "op": {"type": "string", "enum": ["set", "add", "mul", "remove", "push"],
                                       "description": "set=覆盖/add=加/mul=乘/remove=删/push=数组追加"},
                                "value": {"description": "变更值（op=remove 时省略）"},
                                "reason": {"type": "string", "description": "必填：变更理由（叙事/档位依据）"}
                            },
                            "required": ["path", "op", "reason"]
                        }
                    },
                    "triggered_events": {
                        "type": "array",
                        "description": "可选：触发的连锁事件",
                        "items": {"type": "object",
                                  "properties": {"event_id": {"type": "string"},
                                                 "context": {"type": "string"}},
                                  "required": ["event_id"]}
                    },
                    "narrative_hint": {"type": "string", "description": "可选：变更叙事按语（≤120字）"}
                },
                "required": ["changes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_state",
            "description": "按 JSON 路径查询游戏状态（本地直接读，不耗 AI 推理）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "paths": {"type": "array", "items": {"type": "string"},
                              "description": "JSON 路径数组，如 [\"treasury\", \"factions.新党.satisfaction\"]"}
                },
                "required": ["paths"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_event",
            "description": "触发一个事件（event_id 须在事件表内，context 为上下文说明）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "事件 id"},
                    "context": {"type": "string", "description": "触发上下文（≤80字）"}
                },
                "required": ["event_id"]
            }
        }
    },
]


def parse_tool_calls(response):
    """从 LLM 响应提取 tool_calls → 结构化列表（模型适配层扩展）。

    - 标准 openai：{tool_calls: [{id, function: {name, arguments}}]}
    - content_json 变体：{tool_calls: [{id, function: {name}, content: '{"args"...}'}]}
      ——arguments 空时从 content 提取 JSON（参数嵌 content 的端点）。
    - 弱参数：arguments 空/坏 JSON → 从 content 提取；仍缺 → {}（必填缺失由
      _tool_dispatch 拒绝式处理）。
    输出统一 {call_id, name, arguments(dict)}；无 tool_calls → []。
    """
    if not isinstance(response, dict):
        return []
    tcs = response.get("tool_calls")
    if not isinstance(tcs, list):
        return []
    out = []
    for tc in tcs:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") or {}
        args = fn.get("arguments") or ""
        if not isinstance(args, str) or not args.strip():
            # content_json 变体：参数嵌 content（JSON 字符串或 JSON 对象）
            _content = tc.get("content") or fn.get("content") or ""
            if isinstance(_content, str) and _content.strip():
                args = _content
            else:
                args = "{}"
        try:
            args = json.loads(args) if isinstance(args, str) else (args or {})
        except (ValueError, TypeError):
            args = {}
        if not isinstance(args, dict):
            args = {}
        out.append({"call_id": tc.get("id", ""), "name": fn.get("name", ""),
                    "arguments": args})
    return out


# ============================================================
# 模型适配层（言枢密设计）：SIMPLE_TOOL_SCHEMAS（精简工具 schema）
# 每工具 2-3 核心必填参数 + 描述清晰 + 无深嵌套（弱模型可用）；
# 最终 fallback = STATE_TOOL_SCHEMAS（3 通用工具）。
# ============================================================
SIMPLE_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "register_draft",
            "description": "登记诏草（必填：title 诏令名、summary 大意）",
            "parameters": {"type": "object",
                           "properties": {"title": {"type": "string"},
                                          "summary": {"type": "string"}},
                           "required": ["title", "summary"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "relief_grant",
            "description": "赈济（必填：region 路名）",
            "parameters": {"type": "object",
                           "properties": {"region": {"type": "string"},
                                          "grain": {"type": "integer"},
                                          "silver": {"type": "integer"}},
                           "required": ["region"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_treasury",
            "description": "勾校度支（无参数）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_state",
            "description": "查询状态（必填：target 查什么）",
            "parameters": {"type": "object",
                           "properties": {"target": {"type": "string"},
                                          "name": {"type": "string"}},
                           "required": ["target"]},
        },
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
                        # 征兵转换（用户指示：POP 转换非凭空加兵额——人口守恒）：
                        #   流民 → 厢军（史实优先：征流民为厢军，防乱+充实军力）；
                        #   农 → 兵（流民不足时从该路农 POP size 扣，募农为兵；
                        #            农最多募一半——保农生存，农富时难募）。
                        _total_taken = 0
                        for u in units:
                            _N = scale * 2000
                            _station = getattr(u, "station", "") if getattr(u, "station", "") in state.prefectures else "东京开封府"
                            _p = state.prefectures[_station]
                            _taken = 0
                            if u.tier == "厢军":          # 流民 → 厢军（史实优先）
                                _ref = int(_p.get("refugees", 0))
                                _t = min(_N, _ref)
                                if _t > 0:
                                    _p["refugees"] = _ref - _t
                                    _taken += _t
                            if _taken < _N:               # 农 → 兵（流民不足；农最多募一半）
                                _farm = int(_p["pops"]["农"]["size"])
                                _t2 = min(_N - _taken, max(0, _farm - int(_farm * 0.5)))
                                _p["pops"]["农"]["size"] = _farm - _t2
                                _taken += _t2
                            # 兵额真账 = Σbranches（troops property 只读）——增募入兵种人数
                            if u.branches:
                                _bk = next(iter(u.branches))
                                u.branches[_bk] = u.branches.get(_bk, 0) + _taken
                            else:
                                u.branches["轻步兵"] = _taken
                            # 即时回填兵 POP size（兵额 == 兵 POP 一致；settle 会再聚合）
                            _p["pops"]["兵"]["size"] = _p["pops"]["兵"].get("size", 0) + _taken
                            _total_taken += _taken
                            u.training = max(0, min(100, u.training + scale))
                        # 征发 cost（守恒扣款）：征兵费 = 实募人数 × 5 贯，
                        # 国库出 → 兵 POP 安家费入（ΣΔ==0，不凭空）
                        if _total_taken > 0 and getattr(state, "treasury", 0) >= _total_taken * 5:
                            _cost = _total_taken * 5
                            state.treasury -= _cost
                            _sold = sum(p["pops"]["兵"]["size"] for p in state.prefectures.values()) or 1
                            for _p in state.prefectures.values():
                                _p["pops"]["兵"]["wealth"] = _p["pops"]["兵"].get("wealth", 0) + int(_cost * _p["pops"]["兵"]["size"] / max(_sold, 1))
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
                cost = grain * 200000 + silver * 100000
                if region not in getattr(state, "prefectures", {}):
                    region = "东京开封府"
                # 代码审理（旧机制融入新机制）：改状态经 engine/state_applier（验证/守恒）——
                # 修复旧直写派生字段 state.refugee_count（与 prefectures 不一致 → 凭空造灭）
                # 审查 P2-7 澄清：此处 reason=「赈济发帑」= 出钱购粮赈济（钱从 treasury 出，
                # 粮从市场买），非「开仓发粟」直扣 granary。钱组守恒已闭合（treasury -cost
                # → 农/工匠 +cost）。若改语义为开仓发粟，须另走 granary 扣减 + 粮组守恒。
                try:
                    from engine.state_applier import applier_pipeline
                    _r = applier_pipeline(state, [("relief_grant", [
                        {"path": "treasury", "op": "add", "value": -cost, "reason": "赈济发帑"},
                        {"path": f"prefectures.{region}.pops.农.wealth", "op": "add",
                         "value": int(cost * 0.6), "reason": "赈济购粮（农）"},
                        {"path": f"prefectures.{region}.pops.工匠.wealth", "op": "add",
                         "value": int(cost * 0.4), "reason": "赈济工赈（工匠）"},
                        {"path": f"prefectures.{region}.refugees", "op": "add",
                         "value": -grain * 5000, "reason": "赈济安置流民"},
                    ])])
                    if _r.get("conservation_failed"):
                        res = "赈济未能落地（守恒校验失败：钱粮来源不足）"
                    else:
                        state.population_satisfaction = max(0, min(100,
                            state.population_satisfaction + grain * 2))
                        res = (f"已发 {region} 仓廪赈济（粟档 {grain}，银档 {silver}），"
                               f"发帑约 {cost:,} 缗，民心稍纾。")
                except Exception:
                    # 兜底（state_applier 不可用）：旧逻辑但**不再直写派生字段 refugee_count**
                    state.treasury = max(0, getattr(state, "treasury", 0) - cost)
                    state.population_satisfaction = max(0, min(100,
                        state.population_satisfaction + grain * 2))
                    res = (f"已发 {region} 仓廪赈济（粟档 {grain}，银档 {silver}），"
                           f"发帑约 {cost:,} 缗，民心稍纾。")
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
    - faction_change：内层 value 每个键取值先 normalize_tier 归一再校验 ∈ TIER_RANGE
    - commerce_tax：必须能转 float 且 0<v<=1，程序封顶后四舍五入两位
    - 其余 dim 须在 _ALLOWED_DIMS 且 tier 经 normalize_tier 归一后合法（审查 P2-6 修复：
      原直接 _valid_tier 不归一丰富表达如「显著」→ 静默丢弃，与全库归一设计矛盾）

    draft_decree / polish_decree / council_review 共用，消除三份重复。
    """
    from content.data import normalize_tier
    effs = []
    for e in raw_effects[:4]:
        if not isinstance(e, dict):
            continue
        dim = e.get("dim")
        tier = e.get("tier", "无")
        if dim == "faction_change":
            fc = {}
            for k, v in (e.get("value") or {}).items():
                nv = normalize_tier(str(v)) if isinstance(v, str) else v
                if nv in TIER_RANGE:
                    fc[k] = nv
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
        elif dim in _ALLOWED_DIMS:
            # 审查 P2-6：先归一丰富表达再校验，避免「显著」等合法别名被静默丢弃
            ntier = normalize_tier(str(tier)) if isinstance(tier, str) else tier
            if _valid_tier(ntier):
                effs.append({"dim": dim, "tier": ntier})
    return effs


def _similar(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _ai_unavailable(kind, code="AI_NOT_CONFIGURED", **extra):
    """AI 不可用 / 解析失败且无补调余量时，返回统一错误标记（拒绝式，不伪造）。

    审查 P2-5 修复：支持指定错误码（区分无配置/无效JSON/契约失败），默认 AI_NOT_CONFIGURED。
    错误码见 content.data.AI_ERROR_CODES（6 码）；上层据 `_error` 码提示配置 AI 或诊断。
    """
    from content.data import AI_ERROR_CODES
    _valid_codes = set(AI_ERROR_CODES.keys())
    if code not in _valid_codes:
        code = "AI_NOT_CONFIGURED"
    return {"_error": code,
            "message": AI_ERROR_CODES.get(code, ""),
            "kind": kind, **extra}


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
        elif dim in _ALLOWED_DIMS and dim != "faction_change":
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


