# -*- coding: utf-8 -*-
"""诏令生效月数（2026-10-20，天道档位化 batch4；用户裁定：多因素 + AI 判断空间）。

用户原话：「多方面因素影响，天道，主持官员能力，皇威，后续跟进等等」
追加：「还要给ai判断的空间，例如给官员加薪这种，还有敢拖的吗」。

口径：
    months = clamp( round( base(天道节奏档) × 执行态度 × 能力 × 皇威 × 跟进 ), 3, 36 )

- **天道执行态度**（新增，AI 判断"谁敢拖"）：奉行 / 依违 / 阳奉阴违 / 拖延
  → ×1.00 / 1.15 / 1.35 / 1.60；AI 还可给一句叙事（谁在拖、为何拖）；
- **天道节奏**：速/常/缓 → 6/12/18；
- **主持官员能力**：<40 ×1.25 / 40–69 ×1.00 / ≥70 ×0.80；
- **皇威**：<40 ×1.20 / 40–79 ×1.00 / ≥80 ×0.85；
- **后续跟进**：0 ×1.10 / 1 ×0.95 / ≥2 ×0.85。

AI 判断空间的用法（例）：
- 加薪诏（利官）⇒ 官员多「奉行」，但皇威不振/吏治败坏时可能「依违」乃至「拖延」；
- 裁冗诏（损官）⇒ 常「阳奉阴违」；皇威鼎盛 + 强力主持才「奉行」。

纪律：天道只出档位 + 叙事；系数表集中本模块；缺档 ⇒ ×1.00 并标明"天道未判"。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = ["BASE_MONTHS", "PRIORITY_TO_PACE", "ATTITUDE_LEVELS", "ATTITUDE_MULT",
           "resolve_decree_duration", "resolve_execution_attitude", "duration_breakdown",
           "FACTOR_WEIGHTS", "MULT_MIN", "MULT_MAX",
           "DECREE_TIMING", "TIMING_BY_EFFECT", "ATTITUDE_COMPLETION",
           "classify_decree_timing"]

BASE_MONTHS: Dict[str, int] = {"速": 6, "常": 12, "缓": 18}
PRIORITY_TO_PACE: Dict[str, str] = {"高": "速", "中": "常", "低": "缓"}
ATTITUDE_LEVELS = ("奉行", "依违", "阳奉阴违", "拖延")
ATTITUDE_MULT: Dict[str, float] = {"奉行": 1.00, "依违": 1.15, "阳奉阴违": 1.35, "拖延": 1.60}
MONTHS_MIN, MONTHS_MAX = 3, 36

#: 诏令时效：即时（本回合办妥）/ 短期（1–3 月）/ 长期（工程型）
DECREE_TIMING = ("immediate", "short", "long")

#: 效果键 → 时效（未列出默认 long，避免把工程当儿戏）
TIMING_BY_EFFECT = {
    "pay_reform": "immediate", "commerce_tax": "immediate", "single_whip": "immediate",
    "prestige": "immediate", "treasury": "immediate", "imperial_treasury": "immediate",
    "population_satisfaction": "immediate", "faction_change": "immediate",
    "defense_bonus": "immediate", "he_mi": "immediate", "grain_stabilize": "immediate",
    "canal_dredge": "short", "relief": "short", "settle_refugees": "short",
    "army_strength": "short",
    "reduce_office": "long", "curtail_waste": "long", "land_survey": "long",
    "anti_corruption": "long", "granary_reform": "long", "military_supply": "long",
}

#: 即时诏令的「执行完成度」（拖延体现为打折，而非拖成长期）
ATTITUDE_COMPLETION = {"奉行": 1.00, "依违": 0.85, "阳奉阴违": 0.60, "拖延": 0.35}

#: 因素权重（显式，和=1）：加权几何平均的指数，决定各因素话语权
FACTOR_WEIGHTS = {"attitude": 0.40, "ability": 0.25, "prestige": 0.20, "followup": 0.15}

#: 总乘数夹取（防数值爆炸；与加权几何平均共同构成双保险）
MULT_MIN, MULT_MAX = 0.55, 1.90


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


def resolve_execution_attitude(state, *, decree_kind: str = "",
                               beneficiary: str = "") -> Dict[str, Any]:
    """天道判断执行态度（"谁敢拖"）。返回 {level, mult, note, source}。"""
    slot = getattr(state, "_decree_ai", None)
    got = slot if isinstance(slot, dict) else {}
    att = got.get("execution_attitude")
    src = "天道"
    note = got.get("attitude_note") or ""
    if att not in ATTITUDE_LEVELS:
        ex = getattr(state, "_decree_execute_ai", None)
        if isinstance(ex, dict):
            att2 = ex.get("execution_attitude")
            if att2 in ATTITUDE_LEVELS:
                att, src = att2, "天道(执行契约)"
                note = ex.get("attitude_note") or ""
    if att not in ATTITUDE_LEVELS:
        for fn in reversed(_ATTITUDE_PROVIDERS):
            try:
                cand = fn(state, decree_kind, beneficiary)
                if isinstance(cand, dict) and cand.get("execution_attitude") in ATTITUDE_LEVELS:
                    att = cand["execution_attitude"]
                    src = "天道(provider)"
                    note = cand.get("note") or ""
                    break
            except Exception:  # noqa: BLE001
                continue
    if att in ATTITUDE_LEVELS:
        return {"level": att, "mult": ATTITUDE_MULT[att], "note": note, "source": src}
    return {"level": None, "mult": 1.00,
            "note": "天道未判执行态度" + (f"（{beneficiary}）" if beneficiary else ""),
            "source": "缺档"}


_ATTITUDE_PROVIDERS: list = []


def register_attitude_provider(fn) -> None:
    _ATTITUDE_PROVIDERS.append(fn)


def classify_decree_timing(decree_kind: str) -> tuple:
    """效果键 → (时效, 依据)。未知键按 long（工程型）处理并注明。"""
    k = str(decree_kind or "").strip()
    if k in TIMING_BY_EFFECT:
        return TIMING_BY_EFFECT[k], "按效果键"
    return "long", "未知效果键，按长期工程处理"

def resolve_decree_duration(state, *, ability: Optional[float] = None,
                            followup: Optional[int] = None,
                            prestige: Optional[float] = None,
                            decree_kind: str = "", beneficiary: str = "") -> Dict[str, Any]:
    """返回 {months, base, pace, attitude, breakdown, source}；**纯函数**（无随机）。"""
    pace, source = _pace_from_ai(state)
    base = BASE_MONTHS[pace]
    att = resolve_execution_attitude(state, decree_kind=decree_kind, beneficiary=beneficiary)
    am, an = _ability_mult(ability)
    pm, pn = _prestige_mult(state.prestige if prestige is None else prestige)
    fm, fn = _followup_mult(followup)
    timing, timing_reason = classify_decree_timing(decree_kind)
    w = FACTOR_WEIGHTS
    # （权重显式、和=1 ⇒ 结果落在各因素区间内；再对总乘数夹取，双重防爆）
    mult = ((att["mult"] ** w["attitude"]) * (am ** w["ability"])
            * (pm ** w["prestige"]) * (fm ** w["followup"]))
    mult = max(MULT_MIN, min(MULT_MAX, mult))
    raw = base * mult
    if timing == "immediate":
        # 即时诏令：本回合办妥（monhts=1）；拖延不打月数，而是**execution_completion 打折**
        months = 1
    elif timing == "short":
        months = max(1, min(3, int(round(3 * mult))))
    else:
        months = max(MONTHS_MIN, min(MONTHS_MAX, int(round(raw))))
    completion = ATTITUDE_COMPLETION.get(att.get("level") or "", 1.00)
    return {
        "months": months,
        "base": base,
        "pace": pace,
        "source": source,
        "timing": timing,
        "timing_reason": timing_reason,
        "execution_completion": completion,
        "attitude": att,
        "breakdown": {
            "attitude": {"mult": att["mult"], "note": att["note"], "source": att["source"]},
            "ability": {"mult": am, "note": an, "value": ability},
            "prestige": {"mult": pm, "note": pn,
                         "value": getattr(state, "prestige", prestige)},
            "followup": {"mult": fm, "note": fn, "value": followup},
            "weighted_mult": round(mult, 4),
            "weights": dict(w),
            "raw": round(raw, 2),
        },
    }


def duration_breakdown(state, **kw) -> Dict[str, Any]:
    return resolve_decree_duration(state, **kw)