# -*- coding: utf-8 -*-
"""钱（与银）作为 cargo 走交通层 —— G-3/P4a（2026-10-18 用户指示）。

## 为什么需要它

用户：「钱也要能押运，这样交子的存在就有意义了」。
现状：国库/内帑/地方府库三个标量，调拨**瞬时**（41 处直接改数，无在途）。
而 `core.transport` 已有完整的**交通边 + 在途批次**，但只服务货物（商人 goods）。

本模块把「钱」接进同一套在途机制：

- 扣源**立刻**（钱货两清或两不做，扣不到不建批次）；
- 建**在途批次**（`cargo_kind="money"`），`arrive_month` 才入账；
- 到期由 `arrive_money_due(state)` 入账到目标持有方；
- 押运可选（`escort=`），复用 `livestock_and_escort.hire_escort_guard` 的费率口径（1%–3.5%）。

## 纪律

1. **不新增平行账本**：钱仍在 `state.treasury` / `state.imperial_treasury` / 治所 `local_treasury`，
   本模块只「搬」不「记」；
2. **缺失 ≠ 0**：源账户不存在或余额不足 ⇒ 拒绝发货（`ok=False`），**不建批次**；
3. **未到不入账**：`arrive_money_due` 只处理 `arrive_month <= 当月`；
4. **守恒**：`源扣 + 在途 + 到账 == 常数`（押运费另计，转入镖师账户前先记流水）。

## 与交子的关系

钱能押运（有运费/时效/风险）之后，交子（便换/汇兑）才有比较优势——
`issue_draft/redeem_draft`（P4c）将以此模块为对照物。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = [
    "MONEY_CARGO_KIND", "HOLDER_KINDS", "resolve_holder", "dispatch_money",
    "arrive_money_due", "money_in_transit", "money_transit_total",
]

#: 批次里标记「这是钱」的字段值（与货物批次共用一个队列，靠它分流）
MONEY_CARGO_KIND = "money"

#: 支持的持有方类型
HOLDER_KINDS = ("treasury", "imperial_treasury", "local_treasury")


def _seat_pdata(state, seat_id: str):
    """按治所 id（`路|治所`）取所属路 dict；找不到 ⇒ None。"""
    if not isinstance(seat_id, str) or "|" not in seat_id:
        return None
    route = seat_id.split("|", 1)[0]
    prefs = getattr(state, "prefectures", None) or {}
    pdata = prefs.get(route)
    return pdata if isinstance(pdata, dict) else None


def resolve_holder(state, kind: str, seat_id: Optional[str] = None):
    """解析持有方 → (读函数, 写函数)；非法/缺失 ⇒ (None, None)。

    读函数不接受参数返回当前值；写函数接受新值。
    """
    kind = str(kind or "")
    if kind == "treasury":
        return (lambda: int(getattr(state, "treasury", 0) or 0),
                lambda v: setattr(state, "treasury", int(v)))
    if kind == "imperial_treasury":
        return (lambda: int(getattr(state, "imperial_treasury", 0) or 0),
                lambda v: setattr(state, "imperial_treasury", int(v)))
    if kind == "local_treasury":
        pdata = _seat_pdata(state, seat_id or "")
        if not isinstance(pdata, dict):
            return (None, None)
        seats = pdata.get("seats") or {}
        srow = seats.get(seat_id) if isinstance(seats, dict) else None
        if isinstance(srow, dict) and isinstance(srow.get("local_treasury"), (int, float)):
            return (lambda: int(srow.get("local_treasury", 0) or 0),
                    lambda v: srow.__setitem__("local_treasury", int(v)))
        # 未下沉：路级标量
        if isinstance(pdata.get("local_treasury"), (int, float)):
            return (lambda: int(pdata.get("local_treasury", 0) or 0),
                    lambda v: pdata.__setitem__("local_treasury", int(v)))
        return (None, None)
    return (None, None)


def dispatch_money(state, *, frm_kind: str, to_kind: str, amount: int,
                   frm_seat: Optional[str] = None, to_seat: Optional[str] = None,
                   escort_fee: int = 0) -> Dict[str, Any]:
    """发钱：**立刻扣源**，建在途批次；`arrive_money_due` 才入账。

    返回 `{ok, reason, shipped, arrive_month, days, batch}`。
    · 源不存在/余额不足 ⇒ `ok=False`，**不建批次**（不产生凭空在途）；
    · 目的地必须是治所 id（`路|治所`）；未登记路线 ⇒ `route_undefined`。
    """
    from core.transport import _now, _book, route_days, _seat_index

    want = max(0, int(amount))
    if want <= 0:
        return {"ok": True, "reason": "no_demand", "shipped": 0}
    if to_kind not in HOLDER_KINDS or frm_kind not in HOLDER_KINDS:
        return {"ok": False, "reason": "bad_holder_kind"}
    if not to_seat:
        return {"ok": False, "reason": "missing_destination"}
    days = route_days(to_seat, to_seat)  # 占位，下面用真实起点重算
    idx = _seat_index()
    dst = idx.get(to_seat)
    if not dst:
        return {"ok": False, "reason": "unknown_destination", "to": to_seat}
    now = _now(state)
    if now is None:
        return {"ok": False, "reason": "time_undefined"}
    # 起点：国库/内帑默认从**京师**出发（钱在太仓/国库，位于开封府）；地方府库用自身治所
    frm_seat = frm_seat or ("京畿路|开封府" if frm_kind in ("treasury", "imperial_treasury") else to_seat)
    days = route_days(frm_seat, to_seat)
    if days is None:
        return {"ok": False, "reason": "route_undefined", "from": frm_seat, "to": to_seat}
    read, write = resolve_holder(state, frm_kind, frm_seat)
    if read is None:
        return {"ok": False, "reason": "source_unavailable", "from": frm_kind}
    cur = read()
    fee = max(0, int(escort_fee))
    need = want + fee
    if cur < need:
        return {"ok": False, "reason": "insufficient_funds", "available": int(cur), "need": int(need)}
    write(int(cur) - need)
    batch = {
        "trade_id": None,
        "cargo_kind": MONEY_CARGO_KIND,
        "from": frm_seat, "to": to_seat,
        "dim": "coins", "qty": int(want),
        "from_circuit": (idx.get(frm_seat) or {}).get("circuit"),
        "to_circuit": dst.get("circuit"),
        "from_kind": frm_kind, "to_kind": to_kind,
        "from_seat": frm_seat, "to_seat_holder": to_seat,
        "arrive_month": now + int(days), "days": int(days),
        "escort_fee": int(fee),
    }
    _book(state).append(batch)
    return {"ok": True, "reason": "ok", "shipped": int(want),
            "arrive_month": batch["arrive_month"], "days": int(days), "batch": batch}


def arrive_money_due(state) -> list:
    """把本月至期的**钱批次**入账到目标持有方；货物批次原样保留（互不干扰）。"""
    from core.transport import _now, _book, _set_book

    now = _now(state)
    if now is None:
        return []
    book = _book(state)
    arrived, keep = [], []
    for b in book:
        if b.get("cargo_kind") != MONEY_CARGO_KIND:
            keep.append(b)
            continue
        if int(b.get("arrive_month", 0)) > now:
            keep.append(b)
            continue
        _read, write = resolve_holder(state, b.get("to_kind", ""), b.get("to"))
        if write is None:
            keep.append(b)       # 目的地账户缺失 ⇒ 保留批次，不静默丢弃（缺失≠0）
            continue
        got = _read()
        write(int(got) + int(b.get("qty", 0) or 0))
        arrived.append({**b, "arrived_month": now})
    _set_book(state, keep)
    return arrived


def money_in_transit(state) -> list:
    """当前在途的**钱**批次（只读）。"""
    from core.transport import _book

    return [dict(b) for b in _book(state) if b.get("cargo_kind") == MONEY_CARGO_KIND]


def money_transit_total(state) -> int:
    """在途钱合计（贯）；无在途 ⇒ 0（这是**真零**，不是缺失）。"""
    return sum(int(b.get("qty", 0) or 0) for b in money_in_transit(state))