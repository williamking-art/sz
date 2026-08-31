# -*- coding: utf-8 -*-
"""宋祚 · 叙事模板库（AI 失败分级降级 · 本地兜底）

**定位**：AI 缺失/失败时，叙事类（月报/事件/召对/建言/拟旨/结局/通用叙事）用
**本地组装模板**兜底，让游戏可继续（体验韧性，防崇祯式差评）。

**原则（不破底线）**：
- 模板是**程序本地文本**，明确标注"有司补录/暂阙/程序代拟"，**不伪造 AI 口吻**；
- **不伪造数字**：结构化 changes 组装只引用 `state.settlement_log` / `short_term_log`
  中的**程序真值**（已发生的结算事实），不凭空编造数值或档位；
- 模板兜底**只影响叙事呈现**，不触碰结算/守恒/GameState 状态；
- 推演类（economy/military/diplomacy/relief 等 _decide）**不在此兜底**——仍拒绝式
  （`_ai_unavailable` / AIRuntimeError，必须 AI，不伪造）。

**场景**：report(月报) / event(事件，按 severity 分档) / decree(拟旨) /
         dialogue(召对) / advice(建言) / eval(结局) / narrative(通用部门叙事)。
"""
import os

# 句式库：每场景多句式，按确定性轮换（避免固定复读，可测试复现）
_MONTHLY_TEMPLATES = (
    "（本月初报缺漏，暂由有司补录：朝局平稳，诸司奉行如仪。）",
    "（起居注官未及具奏，兹录存档：是月政务按章施行，无甚波澜。）",
    "（史官暂阙其文，先录有司简报：百官循例奏对，政令如常。）",
)

_EVENT_TEMPLATES = {
    "轻": ("（此间细故，史官暂阙其文，录存待考。）",),
    "中": ("（此事程序未及推演，暂录存档，俟有司复核。）",),
    "重": ("（事态骤起，奏报未及详述，先录要略，待朝议定夺。）",),
}

_DIALOGUE_TEMPLATES = (
    "（{name}今日未及具奏，容臣退朝再拟，改日详奏。）",
    "（{name}奏称政事繁杂，容稍后条陈所见。）",
)

_ADVICE_TEMPLATES = (
    "（谋臣今日未及陈言，暂阙。）",
    "（近臣未及献议，容后再奏。）",
)

_EVAL_TEMPLATES = (
    "（史臣未及撰评，暂录朝政要略，俟后补论。）",
    "（国史待修，兹先存其事迹，论赞容后。）",
)

_NARRATIVE_TEMPLATES = (
    "（此事程序未及推演，暂录存档，俟有司复核。）",
    "（有司未及详报，先录其概，容后补叙。）",
)

# 拟旨模板：AI 缺失时返回合法 free_edict 契约对象（effects=None → 程序不落地假效果）
_DECREE_TEMPLATE = {
    "category": "free_edict",
    "exec_mode": "longterm",
    "title": "（AI 未接入·待定）",
    "params": {},
    "effects": None,
    "task": None,
    "rename": None,
    "reform": None,
    "new_material": None,
    "narrative": "（AI 未接入，此诏未及推演。诏意已录存档，待接入 AI 后重拟。程序不代拟效果。）",
    "_error": "AI_NOT_CONFIGURED",
    "_fallback": True,
}


def _pick(templates, seed_key):
    """确定性轮换：seed_key 的 crc32 取模（同 seed_key 同句式，跨进程可复现）。

    不用内置 hash()——Python 字符串 hash 有进程级随机化（PYTHONHASHSEED），
    会导致同 seed_key 在不同进程选中不同句式，破坏模板可复现性。
    """
    if not templates:
        return ""
    try:
        import zlib
        idx = zlib.crc32(seed_key.encode("utf-8", "ignore")) % len(templates)
    except Exception:
        idx = 0
    return templates[idx]


def fallback_report(year=0, month=0, era_name="", state=None) -> dict:
    """月报模板兜底：本地句式 + 结构化真值组装（不伪造数字）。

    state 提供 settlement_log（程序真值：国库/民心/事件等已发生事实）；
    仅把真值摘要填入模板，无 state 时用纯固定句式。
    """
    txt = _pick(_MONTHLY_TEMPLATES, f"report:{year}:{month}:{era_name}")
    # 结构化 changes 组装：只引用程序真值（结算日志），不编造
    facts = _recent_facts(state, limit=2)
    if facts:
        txt = txt[:-1] + f"本月要略：{'；'.join(facts)}。）"
    return {"report": txt, "_fallback": True}


def fallback_event(event_title="", severity="中", state=None) -> dict:
    """事件叙事模板兜底：按 severity 分档（轻/中/重），多句式轮换。"""
    sev = severity if severity in ("轻", "中", "重") else "中"
    templates = _EVENT_TEMPLATES.get(sev, _EVENT_TEMPLATES["中"])
    txt = _pick(templates, f"event:{event_title}:{sev}")
    return {"narrative": txt, "severity_hint": sev, "scenes": [],
            "_fallback": True}


def fallback_dialogue(minister_name="", turn=0) -> dict:
    """召对模板兜底：大臣未及具奏（不伪造具体政见）。"""
    name = minister_name or "卿"
    txt = _pick(_DIALOGUE_TEMPLATES, f"dialogue:{minister_name}:{turn}").format(name=name)
    return {"reply": txt, "mood": "中", "intent_hint": "", "_fallback": True}


def fallback_advice(turn=0) -> dict:
    """建言模板兜底。"""
    return {"advice": _pick(_ADVICE_TEMPLATES, f"advice:{turn}"), "_fallback": True}


def fallback_eval(turn=0) -> dict:
    """结局评定模板兜底。"""
    return {"commentary": _pick(_EVAL_TEMPLATES, f"eval:{turn}"), "_fallback": True}


def fallback_narrative(tag="", turn=0) -> dict:
    """通用部门叙事模板兜底（yamen/local/land/finance/exam/...）。"""
    txt = _pick(_NARRATIVE_TEMPLATES, f"narrative:{tag}:{turn}")
    return {"narrative": txt, "tone": "平实", "_fallback": True}


def fallback_decree(text="", is_secret=False) -> dict:
    """拟旨模板兜底：合法 free_edict 契约对象 + _error/_fallback 标志。

    effects=None（程序不落地假效果）；body 回显玩家诏意（真值，非伪造）。
    调用方（issue_free_decree 等）据 `_fallback` 决定：提示 AI 未接入，
    但玩家诏意已录（不静默吞掉、不代拟效果）。
    """
    d = dict(_DECREE_TEMPLATE)
    d["body"] = text or ""
    d["title"] = f"（AI 未接入·{('密旨' if is_secret else '明诏')}）"
    return d


# ---------------------------------------------------------------------------
# 结构化真值组装（月报用）：只引用程序已发生的结算事实
# ---------------------------------------------------------------------------
_FACT_KINDS = {
    "treasury": "国帑",
    "granary": "仓廪",
    "population_satisfaction": "民心",
    "prestige": "皇威",
    "faction": "党争",
    "disaster": "灾荒",
    "external": "邦交",
    "army": "军务",
    "event": "事件",
}


def _recent_facts(state, limit=2) -> list:
    """从 state 结算日志提取最近真值摘要（脱敏档位词/已发生事实，不编造）。"""
    if state is None:
        return []
    facts = []
    try:
        for entry in (getattr(state, "settlement_log", None) or [])[-6:]:
            if not isinstance(entry, dict):
                continue
            kind = str(entry.get("kind", ""))
            title = str(entry.get("title", "") or entry.get("desc", "") or "")
            note = str(entry.get("note", "") or "")
            if kind and title:
                label = _FACT_KINDS.get(kind, kind)
                seg = f"{label}·{title[:24]}"
                if note:
                    seg += f"（{note[:20]}）"
                facts.append(seg)
            if len(facts) >= limit:
                break
    except Exception:
        return facts
    return facts


# 兼容入口：client.py 转发用（保留既有 kind 语义）
def template_for(kind, minister_name="", turn=0, state=None, **kw):
    """按 kind 返回模板对象；未知 kind 返回 None（调用方走拒绝式标记）。"""
    if kind == "report":
        return fallback_report(year=kw.get("year", 0), month=kw.get("month", 0),
                               era_name=kw.get("era_name", ""), state=state)
    if kind == "event":
        return fallback_event(kw.get("event_title", ""), kw.get("severity", "中"), state)
    if kind == "dialogue":
        return fallback_dialogue(minister_name, turn)
    if kind == "advice":
        return fallback_advice(turn)
    if kind == "eval":
        return fallback_eval(turn)
    if kind == "narrative":
        return fallback_narrative(kw.get("tag", ""), turn)
    return None
