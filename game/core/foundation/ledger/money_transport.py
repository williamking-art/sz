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

import math

from typing import Any, Dict, Optional

__all__ = [
    "allocate_funds",
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


def dispatch_along(state, *, frm_kind: str, to_kind: str, amount: int,
                   frm_seat: Optional[str] = None, to_seat: Optional[str] = None,
                   mode: str = "land", escort_fee: int = 0) -> Dict[str, Any]:
    """**多段运输**（P5c）：按 `route_path` 的最短路径与指定方式建**一个**在途批次。

    与 `dispatch_money` 的差别：本函数先做**能力校验**（`transport_capability`：方式可用/运力/耗时），
    并把**分段时刻表**（`legs`）写进批次，供读数与 AI 判断「走到哪一段」。

    账务语义（刻意简化，避免中转仓平账）：
    · 源账户**立刻**扣 `amount + escort_fee`；
    · **钱只在终点入账**（`arrive_month` 到期一次入账），中途不落任何账户；
    · 分批：一批不超过该方式月运力；超出 ⇒ 返回 `over_capacity` 与可分批数（调用方决定是否分批）。
    """
    from core.transport import _book, _now, route_path, transport_capability, transport_fee

    want = max(0, int(amount))
    if want <= 0:
        return {"ok": True, "reason": "no_demand", "shipped": 0}
    if frm_kind not in HOLDER_KINDS or to_kind not in HOLDER_KINDS:
        return {"ok": False, "reason": "bad_holder_kind"}
    if not to_seat:
        return {"ok": False, "reason": "missing_destination"}
    frm_seat = frm_seat or ("京畿路|开封府" if frm_kind in ("treasury", "imperial_treasury") else to_seat)
    cap = transport_capability(state, frm_seat, to_seat, mode)
    if not cap.get("ok"):
        return {"ok": False, "reason": cap.get("reason"), "mode": mode, "capability": cap}
    capacity = int(cap.get("capacity") or 0)
    if capacity <= 0:
        return {"ok": False, "reason": "zero_capacity", "mode": mode}
    if want > capacity:
        return {"ok": False, "reason": "over_capacity", "mode": mode,
                "capacity": capacity, "batches_needed": (want + capacity - 1) // capacity}
    if str(mode) == "sea":
        path = [frm_seat, to_seat]
    else:
        rp = route_path(frm_seat, to_seat)
        if not rp or not rp.get("reachable"):
            return {"ok": False, "reason": "unreachable"}
        path = list(rp["path"])
    now = _now(state)
    if now is None:
        return {"ok": False, "reason": "time_undefined"}
    read, write = resolve_holder(state, frm_kind, frm_seat)
    if read is None:
        return {"ok": False, "reason": "source_unavailable", "from": frm_kind}
    escort = max(0, int(escort_fee))
    freight = int(transport_fee(str(mode), want, float(cap.get("km") or 0)) or 0)
    total_cost = want + freight + escort
    cur = read()
    if cur < total_cost:
        return {"ok": False, "reason": "insufficient_funds", "available": int(cur),
                "need": int(total_cost), "freight": freight, "escort_fee": escort}
    write(int(cur) - total_cost)
    days = int(cap.get("days") or 0) or 1
    # 分段时刻表：按每段均分天数（仅用于读数，不落账）
    per_leg = max(0, days // max(1, len(path) - 1))
    legs = []
    acc = 0
    for i, (a, b) in enumerate(zip(path, path[1:])):
        acc += per_leg
        legs.append({"from": a, "to": b, "arrive_month": now + acc})
    batch = {
        "trade_id": None,
        "cargo_kind": MONEY_CARGO_KIND,
        "from": frm_seat, "to": to_seat,
        "dim": "coins", "qty": int(want),
        "mode": str(mode),
        "from_kind": frm_kind, "to_kind": to_kind,
        "from_seat": frm_seat, "to_seat_holder": to_seat,
        "path": path, "legs": legs,
        "arrive_month": now + days, "days": days,
        "escort_fee": int(escort),
        "freight": int(freight),
        "km": cap.get("km"),
    }
    _book(state).append(batch)
    return {"ok": True, "reason": "ok", "shipped": int(want), "mode": mode,
            "arrive_month": batch["arrive_month"], "days": days,
            "capacity": capacity, "km": cap.get("km"), "batch": batch}


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


def allocate_funds(state, *, dst_seat: str, amount: int, src: str = "treasury",
                   mode: str = "draft", transport_mode: str = "land",
                   escort_fee: int = 0) -> Dict[str, Any]:
    """拨款三方式（G-3/P6a）：国库/内帑 → 指定治所地方府库。

    用户 2026-10-18 定调，三选一：
    · draft      划账：立刻到账；仅限同路或 1 月内可达，远路大额拒办并给建议；
    · transport  押运：走 dispatch_along（陆/水/海/驿），按路程天数到账，收运费；
    · jiaozi     交子便换：立刻兑付，收手续费；按交子信任/挤兑状态承担兑付损失或拒办。

    不改任何既有 transfer_money 调用；本函数是新增的显式动作。
    返回 {ok, mode, reason?, days, fee, credited, loss?, batch?}。
    """
    from content.data_constants import (DRAFT_MAX_KM, JIAOZI_DRAFT_FEE_RATE,
                                        JIAOZI_DRAFT_MAX_RUN, JIAOZI_DRAFT_MIN_TRUST)
    from core.transport import route_path

    if not dst_seat or "|" not in str(dst_seat):
        return {"ok": False, "mode": mode, "reason": "bad_destination"}
    want = max(0, int(amount))
    if want <= 0:
        return {"ok": True, "mode": mode, "reason": "no_demand", "credited": 0}
    if src not in ("treasury", "imperial_treasury"):
        return {"ok": False, "mode": mode, "reason": "bad_source"}
    route = str(dst_seat).split("|", 1)[0]
    dst_acct = "local:%s:%s" % (route, dst_seat)
    dst_read, dst_write = resolve_holder(state, "local_treasury", dst_seat)

    if mode == "draft":
        rp = route_path("京畿路|开封府", dst_seat)
        km = float((rp or {}).get("km") or 0) if (rp or {}).get("reachable") else None
        if km is None:
            return {"ok": False, "mode": mode, "reason": "unreachable"}
        if km > float(DRAFT_MAX_KM):
            return {"ok": False, "mode": mode, "reason": "draft_too_far",
                    "km": round(km, 1), "limit_km": int(DRAFT_MAX_KM),
                    "suggest": ["transport", "jiaozi"]}
        moved = int(state.transfer_money(src, dst_acct, want))
        if moved <= 0:
            return {"ok": False, "mode": mode, "reason": "transfer_failed"}
        return {"ok": True, "mode": mode, "days": 0, "fee": 0, "credited": moved}

    if mode == "transport":
        r = dispatch_along(state, frm_kind=src, to_kind="local_treasury", amount=want,
                           to_seat=dst_seat, mode=transport_mode, escort_fee=escort_fee)
        if not r.get("ok"):
            return {"ok": False, "mode": mode, "reason": r.get("reason"),
                    "detail": {k: r.get(k) for k in ("capacity", "batches_needed") if k in r}}
        return {"ok": True, "mode": mode, "days": int(r.get("days") or 0),
                "fee": int(r["batch"].get("freight") or 0) + int(r["batch"].get("escort_fee") or 0),
                "credited": 0, "arrive_month": r.get("arrive_month"), "batch": r.get("batch")}

    if mode == "jiaozi":
        jz = getattr(state, "jiaozi", None) or {}
        trust = float(jz.get("trust", 100) or 0)
        run = float(jz.get("run_pressure", 0) or 0)
        if trust < float(JIAOZI_DRAFT_MIN_TRUST):
            return {"ok": False, "mode": mode, "reason": "jiaozi_distrusted", "trust": trust}
        if run > float(JIAOZI_DRAFT_MAX_RUN):
            return {"ok": False, "mode": mode, "reason": "jiaozi_run", "run_pressure": run}
        fee = int(math.ceil(want * float(JIAOZI_DRAFT_FEE_RATE)))
        avail = int(getattr(state, src, 0) or 0)
        if avail < want + fee:
            return {"ok": False, "mode": mode, "reason": "insufficient_funds",
                    "available": avail, "need": want + fee}
        discount = float(jz.get("discount", 0) or 0)
        loss = int(round(want * discount))
        credited = max(0, want - loss)
        setattr(state, src, avail - want - fee)
        if dst_write is None:
            return {"ok": False, "mode": mode, "reason": "destination_unavailable"}
        dst_write(int(dst_read() if dst_read else 0) + credited)
        return {"ok": True, "mode": mode, "days": 0, "fee": fee,
                "credited": credited, "loss": loss}

    return {"ok": False, "mode": mode, "reason": "unknown_mode"}

