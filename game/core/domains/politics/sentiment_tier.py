# -*- coding: utf-8 -*-
"""民心趋势 · 天道档位化（2026-10-20）。

问题（实测 60 月回放）：legacy_mechanic._eff_huashigang 写死「每月民心 -1」，
60 个月直接把民心从 55 打到 0 —— 这是一个拍脑袋的固定数，且无上限、无反馈。

改法（与项目天道纪律一致）：
- 天道/Jev 出**民情档位**（大坏/转坏/持平/转好/大好），程序换算成月度民心增量；
- 缺档 ⇒ **程序先验**（花石纲在册 ⇒ -1/月，其余 0），保证未接线时行为与改动前一致；
- 有界：单月增量夹在 [-3, +3]，民心夹在 [0, 100]；
- 只改民心这一项的**月度趋势**；具体事件的民心影响仍由各事件自己负责（不重复计）。

槽位：state._sentiment_ai = {"tier": "转好", "note": "..."}（前置注入，结算只读）。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = ["SENTIMENT_TIERS", "SENTIMENT_DELTA", "SENTIMENT_PRIOR",
           "resolve_sentiment", "apply_sentiment_trend", "register_sentiment_provider",
           "UNREST_TIERS", "UNREST_DELTA", "resolve_unrest", "register_unrest_provider"]

#: 民情档位（从坏到好）
SENTIMENT_TIERS = ("大坏", "转坏", "持平", "转好", "大好")

#: 档位 → 月度民心增量（程序换算；唯一数字来源）
SENTIMENT_DELTA: Dict[str, int] = {"大坏": -3, "转坏": -1, "持平": 0, "转好": 1, "大好": 3}

#: 缺档时的程序先验（按在册"民心负修正"数量计，每项 -1/月；上限 -3）
#: 现有两项：huashigang（花石纲）、new_party_dominance（新党专权）——旧版各扣 1，
#: 合计 -2/月；先验按此回退，保证未接线时行为与旧版一致。
SENTIMENT_PRIOR_KEYS = ("huashigang", "new_party_dominance")
SENTIMENT_PRIOR_MAX = 3

_PROVIDERS: list = []

#: 民变档位（2026-10-20 天道化「激变」）：原来写死「民心<30 时 15% 概率 -1」，
#: 现由天道判「本月有没有乱」，程序换算骚乱对民心的冲击。
UNREST_TIERS = ("无", "小乱", "骚乱", "大乱")
UNREST_DELTA: Dict[str, int] = {"无": 0, "小乱": -1, "骚乱": -2, "大乱": -4}

_UNREST_PROVIDERS: list = []


def register_unrest_provider(fn) -> None:
    """注册民变档位提供者：fn(state) -> {"tier": 无|小乱|骚乱|大乱}（前置/离线注入）。"""
    _UNREST_PROVIDERS.append(fn)


def register_sentiment_provider(fn) -> None:
    """注册民情档位提供者：fn(state) -> {"tier": 档位, "note": ...}（前置/离线注入）。"""
    _PROVIDERS.append(fn)


def _legacy_pressure(state) -> int:
    """在册的"民心负修正"数量（花石纲/新党专权…）；用于缺档时的程序先验。"""
    keys = set()
    for attr in ("legacy_modifiers", "legacy_active", "legacy_effects"):
        v = getattr(state, attr, None)
        if isinstance(v, dict):
            keys.update(str(k) for k in v)
        elif isinstance(v, (list, tuple)):
            for it in v:
                if isinstance(it, str):
                    keys.add(it)
                elif isinstance(it, dict):
                    keys.add(str(it.get("key") or it.get("id") or ""))
    return min(SENTIMENT_PRIOR_MAX, sum(1 for k in SENTIMENT_PRIOR_KEYS if k in keys))


def resolve_sentiment(state) -> Dict[str, Any]:
    """民情档位：天道优先 → provider → 缺档（返回程序先验，source 标注）。"""
    slot = getattr(state, "_sentiment_ai", None)
    note = ""
    if isinstance(slot, dict):
        tier = slot.get("tier")
        note = str(slot.get("note") or "")
        if tier in SENTIMENT_TIERS:
            return {"tier": tier, "delta": SENTIMENT_DELTA[tier], "note": note,
                    "source": "天道"}
    for fn in reversed(_PROVIDERS):
        try:
            cand = fn(state)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(cand, dict) and cand.get("tier") in SENTIMENT_TIERS:
            tier = cand["tier"]
            return {"tier": tier, "delta": SENTIMENT_DELTA[tier],
                    "note": str(cand.get("note") or ""), "source": "天道(provider)"}
    delta = -_legacy_pressure(state)
    return {"tier": None, "delta": delta, "note": "天道未裁民情档，走程序先验（按在册修正回退）",
            "source": "程序先验"}


def resolve_unrest(state) -> Dict[str, Any]:
    """民变档位：天道优先 → provider → 缺档（None，调用方保留旧随机先验）。"""
    slot = getattr(state, "_unrest_ai", None)
    if isinstance(slot, dict):
        tier = slot.get("tier")
        if tier in UNREST_TIERS:
            return {"tier": tier, "delta": UNREST_DELTA[tier],
                    "note": str(slot.get("note") or ""), "source": "天道"}
    for fn in reversed(_UNREST_PROVIDERS):
        try:
            cand = fn(state)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(cand, dict) and cand.get("tier") in UNREST_TIERS:
            tier = cand["tier"]
            return {"tier": tier, "delta": UNREST_DELTA[tier],
                    "note": str(cand.get("note") or ""), "source": "天道(provider)"}
    return {"tier": None, "delta": None, "note": "天道未裁民变档，走旧随机先验",
            "source": "缺档"}


def apply_unrest(state, log: Optional[list] = None) -> Dict[str, Any]:
    """应用民变冲击（有界 [0,100]）；缺档返回 applied=None，调用方保留旧随机先验。"""
    log = log if isinstance(log, list) else []
    got = resolve_unrest(state)
    cur = getattr(state, "population_satisfaction", None)
    if got["delta"] is None or cur is None:
        return {**got, "applied": None,
                "satisfaction": None if cur is None else int(cur)}
    d = max(-4, min(0, int(got["delta"])))
    if d:
        state.population_satisfaction = max(0, min(100, int(cur) + d))
        log.append("[激变] 天道裁「%s」：民心 %+d（%d → %d）"
                   % (got["tier"], d, int(cur), int(state.population_satisfaction)))
    return {**got, "applied": d,
            "satisfaction": int(getattr(state, "population_satisfaction", 0) or 0)}


def apply_sentiment_trend(state, log: Optional[list] = None) -> Dict[str, Any]:
    """按月应用民情趋势（有界；返回诊断）。缺档时用程序先验（与改动前一致）。"""
    log = log if isinstance(log, list) else []
    got = resolve_sentiment(state)
    cur = getattr(state, "population_satisfaction", None)
    if cur is None:
        return {**got, "applied": 0, "satisfaction": None}
    try:
        delta = int(got["delta"])
    except (TypeError, ValueError):
        delta = 0
    delta = max(-3, min(3, delta))
    if delta:
        state.population_satisfaction = max(0, min(100, int(cur) + delta))
        if got["source"] == "天道":
            log.append("[民情] 天道裁「%s」：民心 %+d（%d → %d）"
                       % (got["tier"], delta, int(cur), int(state.population_satisfaction)))
    return {**got, "applied": delta,
            "satisfaction": int(getattr(state, "population_satisfaction", 0) or 0)}
