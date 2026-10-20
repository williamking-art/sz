# -*- coding: utf-8 -*-
"""诏令生效月数（2026-10-20，天道档位化 batch4；用户裁定：多因素）。

用户原话：「多方面因素影响，天道，主持官员能力，皇威，后续跟进等等」。

口径（不是单一随机）：
    months = clamp( round( base(天道档位) × 能力修正 × 皇威修正 × 跟进修正 ), 3, 36 )

- **天道档位**：执行节奏 速/常/缓 → 基础月数 6/12/18
  （来源：decree_execute 契约任务的 priority 高/中/低 → 速/常/缓；缺档 ⇒ 常 并标明来源）；
- **主持官员能力**：<40 ×1.25；40–69 ×1.00；≥70 ×0.80（能力越高推行越快）；
- **皇威**：<40 ×1.20；40–69 ×1.00；≥80 ×0.85（皇威越隆，梗阻越少）；
- **后续跟进**：0 次 ×1.10；1 次 ×0.95；≥2 次 ×0.85（催办/召对越多越快）。

设计纪律：
- 天道只出档位；系数表集中本模块（唯一数字来源）；
- 缺省不假装精确：未指定官员/无跟进记录时，修正取 1.00 并在 breakdown 写原因。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = ["BASE_MONTHS", "PRIORITY_TO_PACE", "resolve_decree_duration",
           "duration_breakdown"]

BASE_MONTHS: Dict[str, int] = {"速": 6, "常": 12, "缓": 18}
PRIORITY_TO_PACE: Dict[str, str] = {"高": "速", "中": "常", "低": "缓"}
MONTHS_MIN, MONTHS_MAX = 3, 36


def _ability_mult(ability: Optional[float]) -> tuple:
    if ability is None:
        return 1.00, "主持官员未指定"
    try:
        a = float(ability)
    except (TypeError, ValueError):
        return 1.00, "主持官员能力非数值"
    if a < 40:
        return 1.25, "能力偏低"
    if a < 70:
        return 1.00, "能力中等"
    return 0.80, "能力出众"


def _prestige_mult(prestige: Optional[float]) -> tuple:
    try:
        p = float(prestige)
    except (TypeError, ValueError):
        return 1.00, "皇威缺失"
    if p < 40:
        return 1.20, "皇威不振"
    if p < 80:
        return 1.00, "皇威平平"
    return 0.85, "皇威尚隆"


def _followup_mult(followup: Optional[int]) -> tuple:
    try:
        n = int(followup or 0)
    except (TypeError, ValueError):
        n = 0
    if n >= 2:
        return 0.85, "催办密集"
    if n == 1:
        return 0.95, "有催办"
    return 1.10, "无后续跟进"


def _pace_from_ai(state) -> tuple:
    """天道档位：优先 state._decree_ai.pace；其次任务 priority 最高者；缺档 ⇒ 常。"""
    slot = getattr(state, "_decree_ai", None)
    if isinstance(slot, dict) and slot.get("pace") in BASE_MONTHS:
        return slot["pace"], "天道"
    ex = getattr(state, "_decree_execute_ai", None)
    if isinstance(ex, dict):
        tasks = ex.get("tasks") if isinstance(ex.get("tasks"), list) else []
        rank = {"高": 3, "中": 2, "低": 1}
        best = None
        for t in tasks:
            if not isinstance(t, dict):
                continue
            pr = t.get("priority")
            if pr in rank and (best is None or rank[pr] > rank[best]):
                best = pr
        if best is not None:
            return PRIORITY_TO_PACE[best], "天道(任务优先级)"
    return "常", "缺档默认常(天道未给节奏)"


def resolve_decree_duration(state, *, ability: Optional[float] = None,
                            followup: Optional[int] = None,
                            prestige: Optional[float] = None) -> Dict[str, Any]:
    """返回 {months, base, pace, breakdown, source}；**纯函数**（无随机）。"""
    pace, source = _pace_from_ai(state)
    base = BASE_MONTHS[pace]
    am, an = _ability_mult(ability)
    pm, pn = _prestige_mult(state.prestige if prestige is None
                            else prestige)
    fm, fn = _followup_mult(followup)
    raw = base * am * pm * fm
    months = max(MONTHS_MIN, min(MONTHS_MAX, int(round(raw))))
    return {
        "months": months,
        "base": base,
        "pace": pace,
        "source": source,
        "breakdown": {
            "ability": {"mult": am, "note": an, "value": ability},
            "prestige": {"mult": pm, "note": pn,
                         "value": getattr(state, "prestige", prestige)},
            "followup": {"mult": fm, "note": fn, "value": followup},
            "raw": round(raw, 2),
        },
    }


def duration_breakdown(state, **kw) -> Dict[str, Any]:
    return resolve_decree_duration(state, **kw)
