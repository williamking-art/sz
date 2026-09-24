# -*- coding: utf-8 -*-
"""宋祚 · AI 客户端工具函数（拆分自 ai/client.py）"""
import os, sys, json, re
import ipaddress
import socket
import urllib.request
import urllib.error
import urllib.parse
from difflib import SequenceMatcher
from typing import Any

# ============================================================
# 出站 URL 安全（SSRF，审查 P1-2）
# ============================================================
# 规则：仅 http(s)；拒绝 userinfo；拒绝回环/私网/链路本地/云 metadata/组播/未指定；
# 域名先解析、任一解析地址落入禁用段即拒（防 DNS rebinding）；每次连接前重解析。
# 可选 provider 白名单：环境变量 SONGZUO_AI_HOST_ALLOWLIST（逗号分隔的域名后缀）。
_ALLOWED_HOST_SUFFIXES = tuple(
    h.strip().lower().lstrip(".")
    for h in (os.environ.get("SONGZUO_AI_HOST_ALLOWLIST") or "").split(",")
    if h.strip()
)


def is_forbidden_outbound_ip(ip_str) -> bool:
    """IP 是否属于禁止外联段（回环/私网/链路本地/保留/组播/未指定…）。

    依据 ipaddress.is_global：非全球可路由地址一律视为危险（含 169.254.169.254
    云 metadata、10/8、172.16/12、192.168/16、127/8、::1、fe80::/10、ff00::/8）。
    解析失败也按危险处理（拒绝式）。
    """
    try:
        token = str(ip_str).strip().strip("[]").split("%")[0]
        ip = ipaddress.ip_address(token)
    except ValueError:
        return True
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    # 组播地址 ipaddress 仍视为 is_global=True，须显式拒绝
    if getattr(ip, "is_multicast", False):
        return True
    try:
        return not ip.is_global
    except Exception:
        return True


def _host_allowed_by_allowlist(host: str) -> bool:
    if not _ALLOWED_HOST_SUFFIXES:
        return True
    h = str(host or "").strip().lower().rstrip(".")
    return any(h == s or h.endswith("." + s) for s in _ALLOWED_HOST_SUFFIXES)


def _resolve_host_ips(host: str, port: int) -> set:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return {str(info[4][0]).split("%")[0] for info in infos if info and info[4]}


def validate_outbound_url(url: str, *, allow_private: bool = False) -> str:
    """校验 AI 出站 http(s) URL；不合法抛 ValueError。返回 strip 后的原 URL。"""
    raw = str(url or "").strip()
    if not raw:
        raise ValueError("Base URL 不可为空")
    try:
        parsed = urllib.parse.urlsplit(raw)
    except ValueError as e:
        raise ValueError("Base URL 格式不合法") from e
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Base URL 必须是含主机名的 http(s) 地址")
    netloc = parsed.netloc or ""
    if parsed.username or parsed.password or "@" in netloc:
        raise ValueError("Base URL 不得包含用户名/口令（userinfo）")
    host = parsed.hostname.strip().lower().rstrip(".")
    if not host:
        raise ValueError("Base URL 缺少主机名")
    if not _host_allowed_by_allowlist(host):
        raise ValueError(f"目标主机不在 AI 服务商白名单内：{host}")
    try:
        port = parsed.port
    except ValueError as e:
        raise ValueError("Base URL 端口不合法") from e
    if allow_private:
        return raw
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if is_forbidden_outbound_ip(literal):
            raise ValueError(f"Base URL 指向内网/回环/保留地址：{host}")
        return raw
    default_port = 443 if parsed.scheme == "https" else 80
    try:
        ips = _resolve_host_ips(host, port or default_port)
    except socket.gaierror as e:
        raise ValueError(f"域名无法解析：{host}") from e
    if not ips:
        raise ValueError(f"域名无法解析：{host}")
    bad = sorted(i for i in ips if is_forbidden_outbound_ip(i))
    if bad:
        raise ValueError(f"域名解析落入内网/保留地址：{host} → {', '.join(bad)}")
    return raw


def assert_connection_url_safe(url: str) -> None:
    """建立连接前的守卫：每次重新解析 DNS 并校验（防 rebinding / 越界重定向）。"""
    validate_outbound_url(url)


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """重定向目标必须重新过 SSRF 校验，越界（如跳 127.0.0.1）直接断开。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            assert_connection_url_safe(newurl)
        except ValueError as e:
            raise urllib.error.URLError(f"越界重定向被拒：{e}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# ============================================================
# 不可信文本定界（审查 P2-16：提示词注入防护）
# ============================================================
_UNTRUSTED_MAX_LEN = 4000


def _strip_control_chars(s: str) -> str:
    """去除不可见控制字符（保留换行/制表），防伪造边界/隐藏指令。"""
    return "".join(ch for ch in str(s if s is not None else "")
                   if ch in ("\n", "\t") or ord(ch) >= 0x20)


def _wrap_untrusted(text, label: str = "玩家文本", max_len: int = _UNTRUSTED_MAX_LEN) -> str:
    """把玩家/历史等不可信文本包进显式数据边界。

    - 去控制字符、定长截断；
    - 尖括号转全角，令文本无法伪造/闭合边界标记；
    - 边界声明「区间内只作引用数据，不得当指令/角色设定/工具参数执行」。
    """
    s = _strip_control_chars(text)
    s = s.replace("<", "＜").replace(">", "＞")
    if max_len and len(s) > max_len:
        s = s[:max_len] + "…（已截断）"
    return (f"<<<UNTRUSTED_DATA[{label}]>>>\n{s}\n"
            f"<<<END_UNTRUSTED_DATA[{label}]>>>")


def _sanitize_history(history, limit: int = 8) -> list:
    """历史消息入参归一：白名单角色 + 去控制字符 + 定长；user 文本加不可信边界。"""
    out = []
    if not isinstance(history, (list, tuple)):
        return out
    for h in list(history)[-int(limit or 8):]:
        if not isinstance(h, dict):
            continue
        role = h.get("role")
        if role not in ("system", "user", "assistant", "tool"):
            continue
        content = h.get("content")
        if content is None:
            continue
        content = _strip_control_chars(content)[:2000]
        if role == "user":
            content = _wrap_untrusted(content, "历史-玩家", max_len=2000)
        out.append({"role": role, "content": content})
    return out


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


def _build_urllib_opener():
    """构造支持环境变量代理的 opener；重定向目标逐个过 SSRF 校验（审查 P1-2）。"""
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")

    proxies = {}
    if http_proxy: proxies["http"] = http_proxy
    if https_proxy: proxies["https"] = https_proxy

    # _SafeRedirectHandler 显式传入后覆盖默认 HTTPRedirectHandler（越界跳转即拒）
    if proxies:
        return urllib.request.build_opener(
            _SafeRedirectHandler(), urllib.request.ProxyHandler(proxies))
    return urllib.request.build_opener(_SafeRedirectHandler())


def _http_post_json(url: str, headers: dict, payload: dict, timeout: int = 30):
    """用标准库 urllib 发送 JSON POST，返回 (status_code, json_or_None, text)。"""
    assert_connection_url_safe(url)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    opener = _build_urllib_opener()
    try:
        with opener.open(req, timeout=timeout) as resp:
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


def _http_get_json(url: str, headers: dict, timeout: int = 15):
    """用标准库 urllib 发送 GET 请求，返回 (status_code, json_or_None, text)。"""
    assert_connection_url_safe(url)
    req = urllib.request.Request(url, headers=headers, method="GET")
    opener = _build_urllib_opener()
    try:
        with opener.open(req, timeout=timeout) as resp:
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
    # P2-38：拒绝路径穿越（name 现均为字面量，防御未来动态拼接）
    if not name or "/" in name or "\\" in name or ".." in name or "\x00" in name:
        return f"[提示词名非法: {name!r}]"
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
# 单一权威源已迁至 content/data.py（TIER_RANGE），此处只做导入转发
# ============================================================
from content.data import TIER_RANGE

# 各维度档位 → 基准数值（再乘皇威乘数等）
# 档位→数值换算基值/封顶：单一权威源在 content/data.py（审查 P1-2/P2-3 修复）。
# content.data 顶层只 import os/sys，无循环导入风险，可直接顶层 import。
from content.data import TIER_VALUE_BASE as _TIER_BASE, TIER_VALUE_CAP as _TIER_CAP

# 向后兼容别名（部分测试/旧代码直接引用 _TIER_BASE/_TIER_CAP）
# _TIER_BASE/_TIER_CAP 已是 content.data.TIER_VALUE_BASE/TIER_VALUE_CAP 的引用


def tier_to_value(dim: str, tier: str, authority: float = 1.0) -> float:
    """档位 → 数值。dim 不在表内返回 0。tier 经 normalize_tier 归一（丰富表达→标准档）。"""
    from content.data import normalize_tier
    tier = normalize_tier(tier)
    if dim == "commerce_tax":
        # 工商征率是"设定值"而非增量：tier 档位直接映射税率（玩家诏"征几成"由 AI 归档）。
        # 审查 P1：单一权威源收敛——表定义于 content/data.py COMMERCE_TAX_RATE_BY_TIER
        from content.data import COMMERCE_TAX_RATE_BY_TIER, COMMERCE_TAX_RATE_MIN
        return COMMERCE_TAX_RATE_BY_TIER.get(tier, COMMERCE_TAX_RATE_MIN)
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
    """敏感词库路径：frozen 时打包在 _MEIPASS/ai（与提示词一致），
    否则源码 ai/ 目录。审查 P1：原用 _app_root()（frozen=exe 同级）致打包版
    必然找不到词库 → 输出过滤静默失效（fail-open）。"""
    if getattr(sys, "frozen", False):
        return os.path.join(getattr(sys, "_MEIPASS", ""), "ai", "safety_lexicon.json")
    return os.path.join(_app_root(), "ai", "safety_lexicon.json")


def load_safety_lexicon() -> list:
    """载入开源 MIT 敏感词库（含 6 类：政治违禁/辱骂/色情/暴力/自伤/赌博）。

    审查 P2-17：词库缺失/损坏**不得完全 fail-open** —— 记录显式状态（mode/reason），
    `_safety_filter` 在词库不可用时把文本判为「未校验」并暂停高风险输出，
    由上层降级（本地模板/拒绝式），同时 `safety_filter_status()` 对外暴露明确状态。
    """
    global _SAFETY_LEXICON
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
        if words:
            _set_lexicon_status(True, "lexicon", "", path, len(words))
        else:
            _set_lexicon_status(False, "empty", "词库文件无有效词条", path, 0)
            import logging
            logging.getLogger("client_utils").warning("敏感词库为空：%s", path)
        _SAFETY_LEXICON = words
        return words
    except FileNotFoundError:
        _set_lexicon_status(False, "missing", "词库文件缺失", path, 0)
        import logging
        logging.getLogger("client_utils").warning("敏感词库缺失：%s", path)
    except (OSError, json.JSONDecodeError, ValueError):
        _set_lexicon_status(False, "corrupt", "词库文件损坏/解析失败", path, 0)
        import logging
        logging.getLogger("client_utils").warning("敏感词库损坏：%s", path)
    _SAFETY_LEXICON = []
    return []


# 模块级输出过滤状态（启动时载入一次）；词库不可用时 _safety_filter 拒绝式处理
_SAFETY_FILTER_STATE = {
    "operational": False, "mode": "unavailable", "reason": "尚未加载", "path": "", "count": 0,
}


def _set_lexicon_status(operational, mode, reason, path, count=0):
    _SAFETY_FILTER_STATE.update({
        "operational": bool(operational), "mode": str(mode), "reason": str(reason),
        "path": str(path), "count": int(count),
    })


def safety_filter_status() -> dict:
    """输出安全过滤状态（供 UI/诊断显示明确状态，不再静默 fail-open）。"""
    return dict(_SAFETY_FILTER_STATE)


def safety_filter_operational() -> bool:
    return bool(_SAFETY_FILTER_STATE.get("operational"))


_SAFETY_LEXICON = load_safety_lexicon()

#: 词库不可用时的显式降级文案（hit=True → 暂停该段高风险文本，交上层走本地兜底）
_SAFETY_FILTER_UNAVAILABLE_TEXT = "（敏感词库不可用，AI 文本暂缓展示。）"


def _safety_filter(raw: str):
    """扫描 AI 输出，命中敏感词则降级为兜底文本；不改游戏状态。

    返回 (text, hit)：
      - hit=True：命中敏感词 **或** 词库不可用（未校验 → 暂停，不静默放行）；
      - hit=False：文本干净（仅在词库可用时可能返回）。
    """
    if not raw:
        return raw, False
    if not safety_filter_operational():
        # 词库缺失/损坏/为空：不 fail-open，标记未校验并暂停该段文本
        return _SAFETY_FILTER_UNAVAILABLE_TEXT, True
    for w in _SAFETY_LEXICON:
        if w and w in raw:
            # 命中：降级为安全兜底，不打印玩家可见原文中的敏感片段
            return "（阁臣所奏措辞或不妥，已为陛下隐去。）", True
    return raw, False


# ============================================================
# 大臣真 function calling（可选能力：端点支持 tools 则启用，否则降级纯文本）
# 执行权在程序：模型只描述意图（tool_calls），由 _tool_dispatch 改 GameState。
# ============================================================
# 9 个工具的 JSON schema（OpenAI 兼容 tools 格式）：register_draft / secret_order /
# check_treasury / propose_governance / personnel_nominate / military_dispatch /
# relief_grant / offer_blueprint / query_state
# （E 修复：原注释写「7 个」，与实际条目数不符。）
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
    {
        "type": "function",
        "function": {
            "name": "kb_search",
            "description": "检索大宋典章知识库（只读，本地库，不耗推理）。查证制度细节：三冗/官制差遣/"
                         "货币交子/财力维持费/常平仓/产业链等。问到才查；query 用 1~3 个关键词，"
                         "空格分隔，如『冗官 差遣』『交子 准备金』。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词，空格分隔"},
                    "top_k": {"type": "integer", "description": "返回条数 1~5，默认 3"}
                },
                "required": ["query"]
            }
        }
    },
]

#: 服务端工具白名单（审查 P2-16：模型只能调这些，参数/对象/数值由程序校验）
_TOOL_NAMES = frozenset({
    "register_draft", "secret_order", "check_treasury", "propose_governance",
    "personnel_nominate", "military_dispatch", "relief_grant", "offer_blueprint",
    "query_state", "kb_search",
})


def _normalize_tool_call(tc):
    """把两种 tool_call 形态归一为 (name, arguments(dict), call_id)。

    - 原生 OpenAI：{id, function: {name, arguments(str|dict)}}
    - parse_tool_calls 归一：{call_id, name, arguments(dict)}
    无法解析 → 空名/空参（由白名单 + 必填校验拒绝式处理）。
    """
    if not isinstance(tc, dict):
        return "", {}, ""
    fn = tc.get("function")
    if isinstance(fn, dict):
        name = str(fn.get("name", "") or "")
        raw_args = fn.get("arguments", "")
        call_id = str(tc.get("id", "") or name)
    else:
        name = str(tc.get("name", "") or "")
        raw_args = tc.get("arguments", {})
        call_id = str(tc.get("call_id", "") or tc.get("id", "") or name)
    if isinstance(raw_args, str):
        try:
            args = json.loads(raw_args or "{}")
        except (ValueError, TypeError):
            args = {}
    elif isinstance(raw_args, dict):
        args = raw_args
    else:
        args = {}
    if not isinstance(args, dict):
        args = {}
    return name, args, call_id


def _safe_int(v, default, lo, hi) -> int:
    try:
        iv = int(v)
    except (TypeError, ValueError):
        iv = int(default)
    return max(int(lo), min(int(hi), iv))


def _cap_str(v, n: int) -> str:
    return str(v if v is not None else "")[:int(n)]


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
    {
        # 第四轮全审补入：kb_search 只读、零副作用、不耗推理，正合「弱模型可用」的
        # 精简面标准；此前只在全量 10 工具面里，simple 档的大臣永远看不到典章库。
        "type": "function",
        "function": {
            "name": "kb_search",
            "description": "查典章（必填：query 关键词，空格分隔）",
            "parameters": {"type": "object",
                           "properties": {"query": {"type": "string"},
                                          "top_k": {"type": "integer"}},
                           "required": ["query"]},
        },
    },
]


def _resolve_query_target(state, target: str, name: str = "") -> str:
    """本地读值（不耗 AI 推理；数值来自 GameState，防推演漂移）。

    审查 P1 修复：财政/兵力读数一律**区间脱敏**（含认知层滞后），与召对脱敏
    口径一致——大臣可见量级（"约X至Y万"）而非精确实数；精确亲勾走
    check_treasury（耗圣旨带宽）。杜绝 query_state 免带宽精确读值绕过查账代价。
    """
    tgt = str(target or "")
    try:
        from ai.desensitize import desensitize_band
        from content.data import (desensitize_treasury, desensitize_satisfaction,
                                  desensitize_tech, desensitize_talent, desensitize_prestige)
        _lag = getattr(state, "economy_knowledge", None)
        def _band(v, unit="", lag_key=None):
            lag = (_lag or {}).get(lag_key) if lag_key else None
            return desensitize_band(float(v), unit, width_pct=0.15, jitter_pct=0.0,
                                    lag_value=lag)
        if tgt == "treasury":
            return f"国库{_band(getattr(state, 'treasury', 0), '缗', 'treasury')}（{desensitize_treasury(getattr(state, 'treasury', 0))}）"
        if tgt == "imperial_treasury":
            return f"内帑{_band(getattr(state, 'imperial_treasury', 0), '缗', 'imperial_treasury')}"
        if tgt == "granary":
            return f"太仓{_band(getattr(state, 'granary', 0), '石', 'granary')}"
        if tgt == "army_grain":
            try:
                g, _ = state.calc_army_grain(for_issue=True)
                return f"军粮实发约{_band(g, '石/月')}"
            except Exception:
                return "军粮数暂缺"
        if tgt == "army_pay":
            try:
                c, _ = state.calc_army_cash(for_issue=True)
                return f"军饷实发约{_band(c, '贯/月')}"
            except Exception:
                return "军饷数暂缺"
        if tgt == "people_mood":
            return f"民情{desensitize_satisfaction(getattr(state, 'population_satisfaction', 50))}"
        if tgt == "road_mood":
            p = state.prefectures.get(name)
            if p:
                return f"{name}民情{p.get('mood', '中')}"
            return f"无{name}路"
        if tgt == "faction":
            f = state.factions.get(name)
            if f:
                sat = desensitize_satisfaction(f.get("satisfaction", 50))
                inf = _band(f.get("influence", 50), "", None)
                return f"{name}满意度{sat}影响力{inf}"
            return f"无{name}派系"
        if tgt == "grain_price":
            gr = getattr(state, "granary_ext", {}) or {}
            return f"粮价{gr.get('price', '适中')}"
        if tgt == "transport":
            return f"漕运约{_band(getattr(state, 'transport', 0), '石/月')}"
        if tgt == "tech_level":
            return f"科技{desensitize_tech(getattr(state, 'tech', {}).get('level', 50))}"
        if tgt == "talent_pool":
            return f"人才池{desensitize_talent(getattr(state, 'exam', {}).get('talent_pool', 0))}"
        if tgt == "jiaozi_issue":
            return f"交子发行约{_band(getattr(state, 'jiaozi', {}).get('issued', 0), '贯')}"
        if tgt == "prestige":
            pi = state.get_prestige_info() if hasattr(state, "get_prestige_info") else {}
            return f"皇威{pi.get('description', desensitize_prestige(getattr(state, 'prestige', 50)))}"
    except Exception:
        pass
    return f"查「{tgt}」暂不可用"


def _resolve_region(state, region) -> str | None:
    """赈济/查报地域俗名 → prefectures 稳定键（20 路）；未识别返回 None。

    规则：全等键 > 路内 name 全等 > 键/名互含 > 常见别名表。绝不兜底到固定路
    （兜底会把钱粮写进错误路径，造成凭空造灭——见审查 P0-4）。
    """
    if not region:
        return None
    r = str(region).strip()
    if r in state.prefectures:
        return r
    _alias = {
        "畿内": "京畿路", "京畿": "京畿路", "东京": "京畿路", "开封": "京畿路",
        "河北": "河北路", "河东": "河东路", "陕西": "陕西路", "京西": "京西路",
        "京东": "京东东路", "两浙": "两浙路", "江南": "江南东路",
        "淮南": "淮南东路", "荆湖": "荆湖南路", "荆南": "荆湖南路",
        "川峡": "成都府路", "四川": "成都府路", "广南": "广南东路",
    }
    for _k, _v in _alias.items():
        if _k == r:
            return _v
    for key, p in state.prefectures.items():
        if p.get("name") == r:
            return key
    for key, p in state.prefectures.items():
        _n = p.get("name", key)
        if r in key or r in _n or key in r:
            return key
    return None


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
        # 审查 P2-16：统一 tool_call 形态 + 服务端工具白名单，未授权工具直接拒绝
        name, args, call_id = _normalize_tool_call(tc)
        if name not in _TOOL_NAMES:
            results.append((call_id or name or "invalid",
                            f"未授权工具被拒：{name or '（空名）'}"
                            "（不在服务端工具白名单内）。"))
            continue
        try:
            # 审查 P1（parse_tool_calls 容错把坏参转 {}，缺参绝不默认落地——拒绝式）：
            # 各工具必填缺失 → 明确报错回给 AI，不立案/不建默认对象。
            _REQUIRED = {
                "register_draft": ("title", "summary"),
                "secret_order": ("title", "summary"),
                "propose_governance": ("title", "summary"),
                "personnel_nominate": ("name", "post"),
                "relief_grant": ("region",),
                "military_dispatch": ("army", "action"),
                "kb_search": ("query",),
            }
            _missing = [k for k in _REQUIRED.get(name, ())
                        if not str(args.get(k, "")).strip()]
            if _missing:
                res = f"办差缺参被拒：{name} 需提供 {('、'.join(_missing))}（缺参不默认落地）。"
                mem.setdefault(minister_name, []).append(f"{name} 缺参被拒")
            elif name == "register_draft":
                # C3 修复：工具契约的 effects 是**对象** {dim: 档位}，而诏草全链路
                # （会签/下发 _draft_to_effects_dict → effects_to_dict）消费的是
                # [{dim,tier}] 列表。原样落库会让审批时对 dict 迭代 → AttributeError。
                # 此处统一归一为列表形态（档位合法性交 _normalize_effects 拒绝式处理）。
                draft = {
                    "title": str(args.get("title", "")).strip(),
                    "summary": str(args.get("summary", "")).strip(),
                    "effects": _normalize_effects(
                        _coerce_effects_to_list(args.get("effects", []))),
                    "secret": bool(args.get("secret", False)),
                }
                did = state.add_edict_draft(draft)
                state.edict_drafts[-1]["proposer"] = minister_name
                res = f"诏草已立案，草案号 d{did}：「{draft['title']}」"
                mem.setdefault(minister_name, []).append(f"立诏草 d{did}：{draft['title']}")

            elif name == "secret_order":
                item = {
                    "title": str(args.get("title", "")).strip(),
                    "summary": str(args.get("summary", "")).strip(),
                    "longterm": bool(args.get("longterm", False)),
                }
                # 严格待批：AI 只入队，批红后才写入 pending/longterm
                aid = state.enqueue_ai_action(
                    "secret_order", item["title"], item["summary"],
                    {"longterm": item["longterm"]}, proposer=minister_name)
                res = f"密令已拟「{item['title']}」，入待批队列（{aid}），俟陛下批红奉行。"
                mem.setdefault(minister_name, []).append(f"拟密令待批：{item['title']}")

            elif name == "check_treasury":
                # 勾校度支消耗诏令带宽（模拟皇帝亲勾精力成本），带宽不足则只给定性
                _bw_cost = 1
                if getattr(state, "decree_bandwidth", 0) >= _bw_cost:
                    state.decree_bandwidth -= _bw_cost
                    t = getattr(state, "treasury", 0)
                    inc = state.statistics.get("total_income", 0) if isinstance(state.statistics, dict) else 0
                    exp = state.statistics.get("total_expenditure", 0) if isinstance(state.statistics, dict) else 0
                    res = f"陛下亲勾度支（耗圣旨额度{_bw_cost}）：府库约 {t:,} 缗；累计入 {inc:,}、出 {exp:,}。"
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
                aid = state.enqueue_ai_action(
                    "propose_governance", item["title"], item["summary"],
                    {"effects": item["effects"]}, proposer=minister_name)
                res = f"施政条陈已拟「{item['title']}」，入待批队列（{aid}），俟批红立案。"
                mem.setdefault(minister_name, []).append(f"提施政待批：{item['title']}")

            elif name == "query_state":
                # 省 token（用户定稿）：按需查询——问到才查本地精准值，同回合缓存
                tgt = str(args.get("target", ""))
                oname = str(args.get("name", ""))
                # 审查 P2-38 修复：缓存 key 原为 target:name，且全库无清理点 →
                # 跨回合命中旧值（AI 查到的是历史数）。现把回合号纳入 key，
                # 并对缓存容量设上限（长局 key 不断新增，防无限累积）。
                key = f"{tgt}:{oname}@{getattr(state, 'turn', 0)}"
                cache = getattr(state, "_query_state_cache", None)
                if cache is None:
                    cache = {}
                    state._query_state_cache = cache
                if len(cache) > 200:
                    cache.clear()
                if key in cache:
                    res = f"{tgt}（本回合已查）{cache[key]}"
                else:
                    val = _resolve_query_target(state, tgt, oname)
                    cache[key] = val
                    res = f"{tgt} {val}"
                mem.setdefault(minister_name, []).append(f"查{tgt}")

            elif name == "kb_search":
                # 本地典章知识库检索（只读，同 query_state 的「问到才查」哲学）：
                # 库缺失/FTS5 不可用/异常时 kb_query 返回空串 → 降级话术，不炸管线。
                from ai.kb_query import kb_search as _kb_search, kb_stats
                # 同 prereq_hint 的 _cap_str 口径：AI 可能回传整段话，先截到 100 字
                _q = str(args.get("query", "")).strip()[:100]
                try:
                    _tk = max(1, min(5, int(args.get("top_k", 3))))
                except (TypeError, ValueError):
                    _tk = 3
                # 埋点（第四轮全审）：典章库此前无任何调用观测手段，calls/hits 供 /api/meter
                _st = kb_stats(state)
                _st["calls"] += 1
                _hit = _kb_search(_q, top_k=_tk)
                if _hit:
                    _st["hits"] += 1
                    res = _hit
                    mem.setdefault(minister_name, []).append(f"查典章：{_q[:20]}")
                else:
                    res = "典章库中未查到相关条目（或本机未部署典章库），请凭已有学识回奏。"
                    mem.setdefault(minister_name, []).append(f"查典章无获：{_q[:20]}")

            elif name == "personnel_nominate":
                nm = str(args.get("name", "某人"))
                post = str(args.get("post", ""))
                note = str(args.get("note", ""))
                # P2-36 修复：原对**所有** yamen backlog+1（一次荐举=处处增压）。
                # 现按 post 关键词匹配单一 yamen；无匹配则记到第一个，只 +1。
                if "yamen" in state.__dict__ and isinstance(state.yamen, dict) and state.yamen:
                    _target_y = None
                    for _yn, _y in state.yamen.items():
                        if isinstance(_y, dict) and _yn and (_yn in post or post in _yn):
                            _target_y = _y
                            break
                    if _target_y is None:
                        _target_y = next(
                            (y for y in state.yamen.values() if isinstance(y, dict)), None)
                    if isinstance(_target_y, dict):
                        _target_y["backlog"] = int(_target_y.get("backlog", 0)) + 1
                res = f"已录荐牍：举 {nm} 任 {post}。{('荐语：' + note) if note else ''}"
                mem.setdefault(minister_name, []).append(f"举 {nm}→{post}")

            elif name == "military_dispatch":
                tier = str(args.get("army", "禁军"))   # army 参数实为军籍
                act = str(args.get("action", "整编"))
                tgt = str(args.get("target", ""))
                scale = _safe_int(args.get("scale", 3), 3, 1, 5)
                # 严格待批：军令只入队，批红时再校验钱粮并落地
                aid = state.enqueue_ai_action(
                    "military_dispatch", f"{tier}·{act}",
                    f"军籍 {tier}，动作 {act}，档 {scale}"
                    + (f"，赴 {tgt}" if tgt else ""),
                    {"army": tier, "action": act, "target": tgt, "scale": scale},
                    proposer=minister_name)
                res = f"军令已拟：{tier} {act}（档 {scale}），入待批队列（{aid}），俟批红施行。"
                mem.setdefault(minister_name, []).append(f"请调待批 {tier}{act}")

            elif name == "relief_grant":
                region = str(args.get("region", ""))
                grain = _safe_int(args.get("grain", 3), 3, 1, 5)
                silver = _safe_int(args.get("silver", 0), 0, 0, 5)
                cost = grain * 200000 + silver * 100000
                region_key = _resolve_region(state, region)
                if region_key is None:
                    # 拒绝式：地域无法落 20 路 → 不落地（防凭空造灭/钱粮错位），
                    # 并把合法取值回给 AI（AI 缺失/失败 → 不执行 + 明确报错，铁律 4）。
                    res = ("赈济未录：地域「%s」无法对应诸路。请指定一路，如：京畿路/两浙路/河北路/"
                           "淮南东路/荆湖南路 等（PREFECTURE_LIST）。" % (region or "空"))
                    mem.setdefault(minister_name, []).append("请赈被拒（地域无效）")
                else:
                    region = region_key
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
                        # 兜底禁止直写（审查 P0）：applier 失败即整单不落地，守恒不旁路
                        res = "赈济未能落地（状态应用层异常，已拒绝）"
                    mem.setdefault(minister_name, []).append(f"赈 {region}")

            elif name == "offer_blueprint":
                kind = str(args.get("kind", "科技"))
                bname = str(args.get("name", "")).strip()
                bdesc = str(args.get("desc", "")).strip()
                effect_dim = str(args.get("effect_dim", ""))
                # 对象/枚举校验：只接受程序可换算的效果维度，其余丢空
                if effect_dim and effect_dim not in _ALLOWED_DIMS:
                    effect_dim = ""
                effect_tier = str(args.get("effect_tier", "微"))
                prereq_hint = _cap_str(args.get("prereq_hint", ""), 80).strip()
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
        # parse_constant：拒绝 NaN/Infinity（模型输出可触发；下游数值通道会被 NaN 击穿）
        return json.loads(raw, parse_constant=_reject_json_constant)
    except Exception:
        return None


def _reject_json_constant(name):
    raise ValueError(f"非法 JSON 常量: {name}")


def _valid_tier(t: str) -> bool:
    return t in TIER_RANGE


def _coerce_effects_to_list(raw_effects) -> list:
    """把 effects 的两种形态统一为契约列表 [{dim,tier} | {dim,value}]。

    C3 修复：本仓库存在两套 effects 约定——
      · 拟旨/会签契约：列表 [{dim, tier}]（_normalize_effects / effects_to_dict 消费）；
      · 办差工具 register_draft 契约：对象 {dim: 档位}（_TOOL_SCHEMAS 声明为 object）。
    原 register_draft 直接把对象形态落库，下游 `_draft_to_effects_dict` →
    `effects_to_dict` 按列表迭代 → 对 dict 迭代得到 str key → `e.get` AttributeError，
    且会签审批路径无 try 包裹 → 直接崩溃。
    此处仅做**形态**归一，档位合法性仍由 _normalize_effects 按既有「拒绝式」策略处理
    （非法档位一律丢弃，不臆造数值映射）。
    """
    if isinstance(raw_effects, (list, tuple)):
        return list(raw_effects)
    if isinstance(raw_effects, dict):
        out = []
        for dim, val in raw_effects.items():
            if dim == "faction_change" and isinstance(val, dict):
                out.append({"dim": dim, "value": val})
            elif dim == "commerce_tax":
                out.append({"dim": dim, "value": val})
            else:
                out.append({"dim": dim, "tier": val})
        return out
    return []


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
    # 审查 P2-41 修复：validate 只检查 "effects" 键存在、未查类型；模型给出 null/dict/str
    # 时原 raw_effects[:4] 抛 TypeError，穿透成笼统 AIRuntimeError（绕过 _ai_unavailable
    # 与错误码诊断）。此处归一为非 list → 空列表（下游按"无效果"处理）。
    if not isinstance(raw_effects, (list, tuple)):
        return []
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
    """[{dim,tier}|{dim:'faction_change',value:{f: tier}}] → 数值字典。

    C3 防御：容忍 `{dim: 档位}` 对象形态（办差工具 register_draft 的契约为对象）。
    原实现对 dict 迭代得到 str key → `e.get` AttributeError，会让会签审批崩溃。
    """
    effects_list = _coerce_effects_to_list(effects_list)
    out = {}
    for e in effects_list:
        if not isinstance(e, dict):
            continue
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


