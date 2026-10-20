# -*- coding: utf-8 -*-
"""圣旨核销闭环（2026-10-20，用户裁定）。

用户原话：「每一份圣旨都要能被核销，哪怕是中旨这种，只是落地效果的区别而已」。

口径：
- 每一道进入队列的旨意都必须有终态台账条目（executed / failed / vetoed / registered_only…），
  不存在「发了就算完、无人过问」的悬挂旨意；
- **中旨**（御笔直发、绕开会签）同样核销，但**落地效果打折**（ZHONGZHI_LANDING）；
- 核销是**兜底**：优先由 settlement_decree 正常执行并记 outcome；
  只有超期仍未记账的，才由本模块补记（outcome=failed，detail 注明「逾限未办·核销」）；
- 幂等：已有台账条目的旨意绝不改写（同一 decree_id 只核销一次）。

落点：复用 state.statistics["decree_exec_ledger"]（decree_confirm 执行台账，存档白名单内）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.decree_confirm import (DECREE_QUEUES, OUTCOME_EXECUTED, OUTCOME_FAILED,
                                 decree_id_of, ensure_decree_id, exec_ledger_of,
                                 record_execution)

__all__ = ["ZHONGZHI_LANDING", "STALE_TURNS", "is_zhongzhi", "closure_status",
           "sweep_edict_closure", "landing_effect"]

#: 中旨落地系数（绕开宰相会签 ⇒ 执行走样）
ZHONGZHI_LANDING = 0.75
#: 逾限核销阈值（回合；超过仍无台账 ⇒ 兜底核销为未办）
STALE_TURNS = 3

_ZHONGZHI_MARKS = ("中旨", "御笔", "内降")


def is_zhongzhi(decree: Any) -> bool:
    """是否中旨（御笔直发）：category / visibility / delivery 任一命中即算。"""
    if not isinstance(decree, dict):
        return False
    for k in ("category", "visibility", "delivery", "kind"):
        v = decree.get(k)
        if isinstance(v, str) and any(m in v for m in _ZHONGZHI_MARKS):
            return True
    return False


def landing_effect(decree: Any, base: float = 1.0) -> float:
    """落地效果系数：中旨打折，普通诏令原值。"""
    try:
        b = float(base)
    except (TypeError, ValueError):
        b = 1.0
    return round(b * (ZHONGZHI_LANDING if is_zhongzhi(decree) else 1.0), 4)


def _issued_turn(decree: Dict[str, Any]) -> Optional[int]:
    for k in ("turn_issued", "turn", "issued_turn"):
        v = decree.get(k)
        if isinstance(v, (int, float)):
            return int(v)
    return None


def closure_status(state) -> Dict[str, Any]:
    """当前闭环读数（纯读）：队列内旨意、已核销、悬挂清单。"""
    led = exec_ledger_of(state)
    closed = len(led)
    dangling: List[Dict[str, Any]] = []
    total = 0
    for q in DECREE_QUEUES:
        for d in (getattr(state, q, None) or []):
            if not isinstance(d, dict):
                continue
            total += 1
            did = decree_id_of(d)
            if not did or did not in led:
                dangling.append({"decree_id": did or "",
                                 "queue": q,
                                 "title": d.get("title"),
                                 "zhongzhi": is_zhongzhi(d)})
    return {"in_queue": total, "closed": closed, "dangling": dangling,
            "dangling_count": len(dangling)}


def sweep_edict_closure(state, *, stale_turns: int = STALE_TURNS,
                        turn: Optional[int] = None) -> Dict[str, Any]:
    """月度兜底核销：超期仍未记账的旨意补记终态（幂等，不改已有条目）。"""
    now = int(turn if turn is not None else (getattr(state, "turn", 0) or 0))
    ledger = exec_ledger_of(state)
    closed_now: List[Dict[str, Any]] = []
    kept: List[Dict[str, Any]] = []
    for q in DECREE_QUEUES:
        for d in (getattr(state, q, None) or []):
            if not isinstance(d, dict):
                continue
            did = decree_id_of(d)
            # 只有 title 兜底出的 id 不算真身份 ⇒ 显式补 decree_id（不产生「无名悬挂」）
            if not any(d.get(k) for k in ("decree_id", "id", "task_id")):
                did = ensure_decree_id(state, d) or did
            if not did:
                continue
            if did in ledger:
                continue
            issued = _issued_turn(d)
            # 颁布回合未知 ⇒ 视为**未决/挂起**（如受命人权限未定），绝不兜底核销（会误判为已办）
            if issued is None:
                kept.append({"decree_id": did, "queue": q, "title": d.get("title"),
                             "reason": "颁布回合未知，挂起"})
                continue
            if now - issued < stale_turns:
                kept.append({"decree_id": did, "queue": q, "title": d.get("title")})
                continue
            zz = is_zhongzhi(d)
            landed = landing_effect(d)
            entry = record_execution(
                state, did, by="礼部·核销",
                title=d.get("title"),
                outcome=OUTCOME_EXECUTED if zz else OUTCOME_FAILED,
                turn=now,
                detail=("中旨逾限，按落地效果 %s 核销" % landed) if zz
                else "逾限未办·核销",
                landed=landed,
            )
            # record_execution 存的是副本 ⇒ 补充字段必须写回台账本体（exec_ledger_of 返回原字典）
            led = exec_ledger_of(state)
            if did in led:
                led[did]["zhongzhi"] = zz
                led[did]["auto_closed"] = True
            closed_now.append({"decree_id": did, "queue": q,
                               "title": d.get("title"), "zhongzhi": zz,
                               "landed": landed})
    return {"closed": closed_now, "kept": kept, "closed_count": len(closed_now),
            "kept_count": len(kept)}
