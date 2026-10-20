# -*- coding: utf-8 -*-
"""圣旨核销闭环（2026-10-20，用户裁定第二轮）。

用户裁定三条：
1. **皇帝发出的旨意不存在「未决」**——发出即生效，只是可能**被拖延/搁置**；
   因此每道旨都必须落到终态（executed / dragged / failed），不允许悬挂。
2. **中旨落地率不是固定的 0.75**（拍脑袋）——取决于**执行系统 × 皇威**：
   文官体系对中旨抵触（皇威低时更低，皇威高时回升）；皇威越高，文官越不敢拖。
3. **宦官、武将不适用文官那套**——内侍/禁军通常不敢不遵中旨，基础落地率高、且对皇威不敏感。

模型（可解释、有界）：
    landed = clamp( base(system) × (sens(system) + (1-sens(system)) × prestige/100) × ai_mult, 0.05, 1.0 )

- base：文官 0.55 / 宦官 0.92 / 武将 0.88 / 宗室 0.70 / 地方 0.60；
- sens：文官 0.55（最敏感）/ 武将 0.75 / 宗室 0.70 / 地方 0.60 / 宦官 0.90（几乎不敏感）；
- ai_mult：天道档位（低/中/高/极）→ 0.70 / 0.85 / 1.00 / 1.10；缺档 = 不乘（1.0，不假装）。

落点：state.statistics["decree_exec_ledger"]（既有执行台账，存档白名单内）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.decree_confirm import (DECREE_QUEUES, OUTCOME_EXECUTED, OUTCOME_FAILED,
                                 decree_id_of, ensure_decree_id, exec_ledger_of,
                                 record_execution)

OUTCOME_DRAGGED = "dragged"

__all__ = ["EXECUTOR_SYSTEMS", "SYSTEM_BASE", "SYSTEM_SENS", "AI_LANDING",
           "OUTCOME_DRAGGED", "STALE_TURNS", "is_zhongzhi", "executor_system_of",
           "landing_effect", "closure_status", "sweep_edict_closure"]

EXECUTOR_SYSTEMS = ("文官", "宦官", "武将", "宗室", "地方")

SYSTEM_BASE: Dict[str, float] = {
    "文官": 0.55, "宦官": 0.92, "武将": 0.88, "宗室": 0.70, "地方": 0.60,
}
SYSTEM_SENS: Dict[str, float] = {
    "文官": 0.55, "宦官": 0.90, "武将": 0.75, "宗室": 0.70, "地方": 0.60,
}
AI_LANDING: Dict[str, float] = {"低": 0.70, "中": 0.85, "高": 1.00, "极": 1.10}

STALE_TURNS = 3

_ZHONGZHI_MARKS = ("中旨", "御笔", "内降")
_EUNUCH_MARKS = ("内侍", "宦", "入内", "内东门", "御药院", "内库")
_MILITARY_MARKS = ("枢密", "禁军", "殿前", "三衙", "都指挥")
_CLAN_MARKS = ("宗室", "宗正", "大宗正")
_LOCAL_MARKS = ("转运使", "提刑", "州县", "府州")


def is_zhongzhi(decree: Any) -> bool:
    """是否中旨（御笔直发）：category / visibility / delivery 任一命中即算。"""
    if not isinstance(decree, dict):
        return False
    for k in ("category", "visibility", "delivery", "kind"):
        v = decree.get(k)
        if isinstance(v, str) and any(m in v for m in _ZHONGZHI_MARKS):
            return True
    return False


def _texts_of(decree: Dict[str, Any]) -> str:
    parts: List[str] = []
    for k in ("addressees", "target_org", "org", "title", "body", "target"):
        v = decree.get(k)
        if isinstance(v, (list, tuple)):
            parts.extend(str(x) for x in v)
        elif isinstance(v, str):
            parts.append(v)
    return " ".join(parts)


def executor_system_of(decree: Any) -> str:
    """判定执行系统；判不出 ⇒ 文官（默认官僚体系）。"""
    if not isinstance(decree, dict):
        return "文官"
    txt = _texts_of(decree)
    if any(m in txt for m in _EUNUCH_MARKS):
        return "宦官"
    if any(m in txt for m in _MILITARY_MARKS):
        return "武将"
    if any(m in txt for m in _CLAN_MARKS):
        return "宗室"
    if any(m in txt for m in _LOCAL_MARKS):
        return "地方"
    return "文官"


def _ai_landing_mult(state, system: str) -> Optional[float]:
    slot = getattr(state, "_decree_ai", None)
    if isinstance(slot, dict):
        per = slot.get("landing")
        if isinstance(per, dict) and per.get(system) in AI_LANDING:
            return AI_LANDING[per[system]]
        if slot.get("landing") in AI_LANDING:
            return AI_LANDING[slot["landing"]]
    ex = getattr(state, "_decree_execute_ai", None)
    if isinstance(ex, dict) and ex.get("landing") in AI_LANDING:
        return AI_LANDING[ex["landing"]]
    return None


def landing_effect(decree: Any, state=None, *, prestige: Optional[float] = None) -> Dict[str, Any]:
    """落地效果（不是固定 0.75）：执行系统 × 皇威曲线 × 天道档位。"""
    system = executor_system_of(decree)
    base = SYSTEM_BASE.get(system, 0.55)
    sens = SYSTEM_SENS.get(system, 0.55)
    if prestige is None:
        prestige = getattr(state, "prestige", 55) if state is not None else 55
    try:
        p = max(0.0, min(100.0, float(prestige)))
    except (TypeError, ValueError):
        p = 55.0
    curve = sens + (1.0 - sens) * (p / 100.0)
    ai = _ai_landing_mult(state, system) if state is not None else None
    raw = base * curve * (ai if ai is not None else 1.0)
    landed = round(max(0.05, min(1.0, raw)), 4)
    return {"landed": landed, "system": system, "base": base, "sens": sens,
            "prestige": p, "curve": round(curve, 4), "ai_mult": ai,
            "source": ("天道档位" if ai is not None else "程序曲线")}


def _issued_turn(decree: Dict[str, Any]) -> Optional[int]:
    for k in ("turn_issued", "turn", "issued_turn"):
        v = decree.get(k)
        if isinstance(v, (int, float)):
            return int(v)
    return None


def closure_status(state) -> Dict[str, Any]:
    """当前闭环读数（纯读）：队列内、已核销、悬挂清单。"""
    led = exec_ledger_of(state)
    dangling: List[Dict[str, Any]] = []
    total = 0
    for q in DECREE_QUEUES:
        for d in (getattr(state, q, None) or []):
            if not isinstance(d, dict):
                continue
            total += 1
            did = decree_id_of(d)
            if not did or did not in led:
                dangling.append({"decree_id": did or "", "queue": q,
                                 "title": d.get("title"),
                                 "zhongzhi": is_zhongzhi(d),
                                 "system": executor_system_of(d)})
    return {"in_queue": total, "closed": len(led), "dangling": dangling,
            "dangling_count": len(dangling)}


def sweep_edict_closure(state, *, stale_turns: int = STALE_TURNS,
                        turn: Optional[int] = None) -> Dict[str, Any]:
    """月度兜底核销：**每道旨都给终态**（发出即生效，无「未决」）。"""
    now = int(turn if turn is not None else (getattr(state, "turn", 0) or 0))
    ledger = exec_ledger_of(state)
    closed_now: List[Dict[str, Any]] = []
    kept: List[Dict[str, Any]] = []
    for q in DECREE_QUEUES:
        for d in (getattr(state, q, None) or []):
            if not isinstance(d, dict):
                continue
            did = decree_id_of(d)
            if not any(d.get(k) for k in ("decree_id", "id", "task_id")):
                did = ensure_decree_id(state, d) or did
            if not did or did in ledger:
                continue
            issued = _issued_turn(d)
            if issued is None:
                issued = now
                d["turn_issued"] = now
            if now - issued < stale_turns:
                kept.append({"decree_id": did, "queue": q, "title": d.get("title")})
                continue
            zz = is_zhongzhi(d)
            eff = landing_effect(d, state)
            outcome = OUTCOME_DRAGGED if zz else OUTCOME_FAILED
            record_execution(
                state, did, by="礼部·核销", title=d.get("title"),
                outcome=outcome, turn=now,
                detail=("中旨逾限·拖而不办（%s 落地 %s）" % (eff["system"], eff["landed"]))
                if zz else "逾限未办·核销",
                landed=eff["landed"],
            )
            led = exec_ledger_of(state)
            if did in led:
                led[did]["zhongzhi"] = zz
                led[did]["system"] = eff["system"]
                led[did]["landing_source"] = eff["source"]
                led[did]["auto_closed"] = True
            closed_now.append({"decree_id": did, "queue": q, "title": d.get("title"),
                               "zhongzhi": zz, "landed": eff["landed"],
                               "system": eff["system"], "outcome": outcome})
    return {"closed": closed_now, "kept": kept,
            "closed_count": len(closed_now), "kept_count": len(kept)}
