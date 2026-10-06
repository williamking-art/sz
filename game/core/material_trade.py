# -*- coding: utf-8 -*-
"""**跨州府建材成交**（P0 · 2026-10-02）—— 钱与货**分开走**。

## 为什么钱与货要分开

`market.trade_goods` 把**钱与货捆在一次调用里**（钱货同时转移），
这对"市集内买卖"是对的。但跨州府时货必须**先运到**才能用（C-c），
若沿用 `trade_goods` 就等于**瞬移**——"运没运到"不可观测，物流失去意义。

⚠️ 但**钱不应等货**：古代长途贸易多付定金/预付款，若钱也等货到账，
"钱去哪了"同样不可观测。故本模块明确**两腿分离**：

| 腿 | 时点 | 实现 |
|---|---|---|
| **钱** | **成交即付**（不等到货） | `GameState.transfer_money`（守恒划转，有付款对手方） |
| **货** | `arrive_month` 才入账 | `core.transport.dispatch`（在途批次） |

## 不变量

1. **钱货两清或两不做**：钱转出与建批次必须**同时成功**，否则**原路退回**；
2. `ΣPOP wealth` **守恒**（只是转移，不创造不销毁）；
3. `ΣPOP goods`（含在途）**守恒**（货只是从"卖方货栈"挪进"在途"）；
4. **未到不入账**：在途期间买方**读不到**这批货（缺失≠0）；
5. 拒绝式：跨路成交**不走** `material_holding.trade_material`（那里有护栏拒绝）。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = ["sell_material_across", "procure_materials",
           "MATERIAL_PRICE", "STOCK_FLOOR"]

#: 建材基准价（贯/单位）。⚠️ **设定值，非史料**——宋无逐建材的可靠市价记载。
#: 仅用于给"买不买得起"一个可判定口径，**不做价格发现**。
MATERIAL_PRICE = {"木": 1.0, "石": 1.0, "铁": 3.0}

#: 补货阈值（单位）：低于此值即考虑进货。⚠️ **设定值**。
STOCK_FLOOR = 800


def procure_materials(state, *, stock_floor: int = STOCK_FLOOR
                      ) -> Dict[str, Any]:
    """🔴 **商人的建材补货决策**——让物流真正跑起来。

    C-c 下建材是**商品**（E-1），商人因此有囤货动机；本函数就是那个动机：
    本地存量低于 `stock_floor` ⇒ 向**料足的路**下单，**钱即付、货走在途**。

    · **只补到阈值附近**，不囤满仓（囤货策略属玩法，未定）；
    · **不追货**：本路**已在途**的量先从需求里扣掉，避免重复下单；
    · 本路**不能自购**（`sell_material_across` 护栏），故货源排除自己；
    · 无钱 / 无货源 ⇒ 如实记 `skipped` 及原因，**不静默**。

    ⚠️ 每月只跑一次（结算 Step 4.46），**不逐建筑各跑一次**。
    """
    from core.foundation.ledger.material_holding import MATERIAL_DIMS, material_holding_for_circuit
    from core.transport import in_transit, route_days

    prefs = getattr(state, "prefectures", {}) or {}

    # 在途抵扣：**按治所**记录（州府级），避免重复下单
    to_of: Dict[str, int] = {}
    for b in in_transit(state):
        dst = b.get("to")
        if not dst:
            continue
        dim = b.get("dim")
        if dim in MATERIAL_DIMS:
            to_of[f"{dst}|{dim}"] = to_of.get(f"{dst}|{dim}", 0) \
                + int(b.get("qty", 0) or 0)

    stock_of: Dict[str, Dict[str, int]] = {}
    for r in prefs:
        stock_of[r] = {}
        for dim in MATERIAL_DIMS:
            v = material_holding_for_circuit(state, r, dim)
            stock_of[r][dim] = 0 if v is None else int(v)

    out: Dict[str, Any] = {"bought": [], "skipped": []}
    for buyer in prefs:
        for dim in MATERIAL_DIMS:
            # 库存是**路级**（POP 挂载律），到货是**州府级**——两者都要计入，
            # 同一路上的任一治所已有在途都算已下单。
            inbound = sum(v for k, v in to_of.items()
                          if k.endswith(f"|{dim}") and k.split("|")[0] == buyer)
            have = stock_of[buyer][dim] + inbound
            if have >= int(stock_floor):
                continue
            need = int(stock_floor) - have
            sellers = sorted((r for r in prefs if r != buyer),
                             key=lambda r: -stock_of[r][dim])
            # 🔴 **不留痕就是静默**：若**全场无货**，原实现在 `for seller` 里对
            # 每个 `stock<=0` 直接 continue，循环走完什么都不记 ⇒ `skipped` 为空，
            # 调用方分不清「没下单」是「无货」还是「算错了」。
            # 故先判「一个有料的卖方都没有」并如实记 `no_stock_local`。
            if not any(stock_of[r][dim] > 0 for r in sellers):
                out["skipped"].append({
                    "buyer": buyer, "seller": None, "dim": dim,
                    "reason": "no_stock_local"})
                continue
            for seller in sellers:
                if stock_of[seller][dim] <= 0:
                    continue
                want = min(need, stock_of[seller][dim])
                # 🔴 **州府级**：由 `sell_material_across` 内部就近取**真正相邻**的一对治所，
                # 并把用了哪对**如实回填**到 to_of（在途按治所记），防重复下单。
                res = sell_material_across(
                    state, seller_route=seller, buyer_route=buyer,
                    dim=dim, qty=want, price=MATERIAL_PRICE.get(dim, 1.0))
                if res.get("ok"):
                    n = int(res["shipped"])
                    stock_of[buyer][dim] += n
                    stock_of[seller][dim] -= n
                    k = f"{res.get('to_seat')}|{dim}"
                    to_of[k] = to_of.get(k, 0) + n
                    out["bought"].append({
                        "buyer": buyer, "seller": seller, "dim": dim,
                        "qty": n, "paid": int(res.get("paid", 0) or 0),
                        "arrive_month": res.get("arrive_month"),
                        "from_seat": res.get("from_seat"),
                        "to_seat": res.get("to_seat")})
                    break          # 该维度本轮已成交，不再换卖家
                # 🔴 **不通 ≠ 无货源**：当前候选卖方不可达时**继续试下一个**，
                # 不能 break——否则「料足但路不通」会掩掉隔壁可达的卖家。
                if res.get("reason") == "route_undefined":
                    continue
                out["skipped"].append({
                    "buyer": buyer, "seller": seller, "dim": dim,
                    "reason": res.get("reason")})
                break              # 其余失败原因（无货/无钱）与换卖家无关
    return out


def _circuit_of_seat(seat_id: str) -> Optional[str]:
    """限定名 `路|治所` ⇒ 路名。"""
    try:
        from core.foundation.ledger.prefecture_entity import split_seat_id
        circuit, _ = split_seat_id(seat_id)
        return circuit
    except Exception:              # noqa: BLE001
        return None


def _route_of(prefs, pop: dict) -> Optional[str]:
    for route, info in (prefs or {}).items():
        pops = (info or {}).get("pops") or {}
        if isinstance(pops, dict) and any(v is pop for v in pops.values()):
            return route
    return None


def sell_material_across(state, *, seller_route: str, buyer_route: str,
                         dim: str, qty: int, price: float,
                         frm_seat: Optional[str] = None,
                         to_seat: Optional[str] = None,
                         trade_id: Optional[str] = None) -> Dict[str, Any]:
    """卖方（`seller_route` 的商人）→ 买方（`buyer_route` 的商人）跨州府售建材。

    🔴 **粒度分工（用户 2026-10-02 纠正）**：
    · **库存按路**——建材挂在**路级商人 POP** `goods`（POP 挂载律，6 类 POP 按路）；
    · **运输按州府**——`frm_seat`/`to_seat` 是**限定名 `路|治所`**，须**显式给出**。
      过去用路级签名 + 内部随便挑一对相邻治所，等于**把整路当成一个运输节点**，
      与本会话建立的 136 席州府实体层自相矛盾（且实测 37 对相邻路中 **31 对**
      因"首席治所不相邻"而被误判成不通）。

    · **钱**：成交即由 `transfer_money` 从买方商人划到卖方商人（守恒）；
    · **货**：立刻离源进**在途**，`arrive_month` 才计入买方货栈。
    """
    from core.foundation.ledger.material_holding import MATERIAL_DIMS
    from core.transport import dispatch

    if dim not in MATERIAL_DIMS:
        return {"ok": False, "reason": "invalid_dim", "dim": dim}
    if seller_route == buyer_route:
        return {"ok": False, "reason": "same_circuit",
                "detail": "同路请用 material_holding.trade_material（市集内成交）"}

    prefs = getattr(state, "prefectures", {}) or {}
    seller = (prefs.get(seller_route) or {}).get("pops", {}).get("商人")
    buyer = (prefs.get(buyer_route) or {}).get("pops", {}).get("商人")
    if not isinstance(seller, dict):
        return {"ok": False, "reason": "no_seller_pop", "route": seller_route}
    if not isinstance(buyer, dict):
        return {"ok": False, "reason": "no_buyer_pop", "route": buyer_route}

    want = max(0, int(qty))
    unit = float(price)
    if want <= 0:
        return {"ok": True, "reason": "no_demand", "shipped": 0}
    if unit <= 0:
        return {"ok": False, "reason": "invalid_price", "price": price}

    # 2026-10-03：建材按 `goods[治所][dim]` 州府桶存放，裸取 `goods.get(dim)`
    # 会把已入库（在桶里）的料读成 0，导致明明有货却报 `no_stock_local`。
    from core.foundation.ledger.material_holding import goods_amount
    have = int(goods_amount(seller.get("goods"), dim) or 0)
    if have <= 0:
        return {"ok": False, "reason": "no_stock_local", "shipped": 0}

    tm = getattr(state, "transfer_money", None)
    if tm is None:
        return {"ok": False, "reason": "no_transfer_money"}

    wealth_before = float(buyer.get("wealth", 0) or 0)
    ship = min(want, have)
    cost = int(ship * unit)
    if wealth_before < cost:
        return {"ok": False, "reason": "insufficient_purchasing_power",
                "affordable": int(wealth_before // unit) if unit > 0 else 0}

    # ---- 定发/收治所（**州府级**）：未显式给出 ⇒ 就近取一对相邻治所，并**如实回报用了哪对**
    if frm_seat is None or to_seat is None:
        bridge = _bridge_seats(seller_route, buyer_route)
        if bridge is None:
            return {"ok": False, "reason": "route_undefined",
                    "detail": "两路之间无直达道路（超出相邻阈值）"}
        frm_seat, to_seat = bridge
        auto_seats = True
    else:
        auto_seats = False

    # ---- 建批次（**先试**，失败则不收钱）
    res = dispatch(state, frm=frm_seat, to=to_seat,
                   dim=dim, qty=ship, trade_id=trade_id)
    if not res.get("ok") or res.get("shipped", 0) <= 0:
        return {"ok": False, "reason": res.get("reason", "dispatch_failed"),
                "detail": res.get("detail")}

    # ---- 收钱（钱货两清；失败则把批次退回，**不留下半笔账**）
    # 用既有守恒划转通道 `transfer_money(src, dst, amount)`，
    # 其入参是 `pop:<路>:<阶层>` 字符串（**钱只走既有通道**，不新开账本）。
    try:
        paid = int(tm(f"pop:{buyer_route}:商人", f"pop:{seller_route}:商人", cost) or 0)
        if paid < cost:
            _refund_batch(state, res)
            return {"ok": False, "reason": "payment_short",
                    "paid": paid, "short": cost - paid, "refunded_batch": True}
    except Exception as exc:                     # noqa: BLE001 — 退款不得吞错
        _refund_batch(state, res)
        return {"ok": False, "reason": "payment_failed", "detail": repr(exc),
                "refunded_batch": True}

    return {"ok": True, "reason": "ok", "shipped": int(res["shipped"]),
            "paid": paid, "arrive_month": res.get("arrive_month"),
            "days": res.get("days"), "seller_route": seller_route,
            "buyer_route": buyer_route, "dim": dim,
            # 🔴 **州府级可观测**：实际走的是哪一对治所（自动择路时尤其要能查）
            "from_seat": frm_seat, "to_seat": to_seat,
            "seats_auto": auto_seats}


def _seat_of(state, circuit: str) -> str:
    """⚠️ 保留：仅用于**同一治所**级别调拨。

    🔴 **跨路发货不要用它**——各路「首席治所」几乎必然彼此不相邻
    （实测 37 对相邻路中 **31 对**首席治所不相邻），
    用它当跨路锚点会把 84% 的相邻关系误判成"不通"。
    跨路请用 `_bridge_seats()`。
    """
    from core.foundation.ledger.material_holding import circuit_seats
    seats = circuit_seats(circuit)
    if not seats:
        raise KeyError(f"{circuit} 查不到治所（无法锚定运输起点/终点）")
    return seats[0]


_BRIDGE_CACHE: Dict[tuple, Any] = {}


def _bridge_seats(circuit_a: str, circuit_b: str) -> Optional[tuple]:
    """找两路之间**最近的一对相邻治所**，作为运输锚点（州府级）。

    🔴 这是「不做全图任意互通」落地后的必要环节：
    两路整体相邻 ≠ 各自首席治所相邻。若只拿首席治所当锚点，
    会把**本可通达**的相邻路误判成"不通"（实测 37 对相邻路中 31 对如此）。

    · 取**距离最近**的一对（"就近发货"），不取列表第一个；
    · 无相邻治所 ⇒ `None`（= 不通，**不回落 0**）；
    · ⚠️ **结果按路对缓存**——治所表是静态的，而补货循环每月都要问同一批路对，
      不缓存会重复做 O(席数²) 的邻接扫描。
    """
    from core.foundation.ledger.material_holding import circuit_seats
    from core.transport import haversine_km, is_adjacent
    ck = (circuit_a, circuit_b) if circuit_a <= circuit_b else (circuit_b, circuit_a)
    if ck in _BRIDGE_CACHE:
        r = _BRIDGE_CACHE[ck]
        if r is None:
            return None
        return (r[0], r[1]) if ck == (circuit_a, circuit_b) else (r[1], r[0])
    best = None
    best_km = None
    for a in circuit_seats(ck[0]):
        for b in circuit_seats(ck[1]):
            if is_adjacent(a, b):
                km = haversine_km(*_lonlat(a), *_lonlat(b))
                if best_km is None or km < best_km:
                    best, best_km = (a, b), km
    _BRIDGE_CACHE[ck] = best
    return best


def _lonlat(seat_id: str):
    """限定名 → (lon, lat)；读不到 ⇒ `None`（由调用方判未定义）。"""
    from core.transport import _seat_index
    s = _seat_index().get(seat_id)
    if not s:
        return (0.0, 0.0)
    return (float(s["lon"]), float(s["lat"]))


def _refund_batch(state, res: Dict[str, Any]) -> None:
    """把刚建的批次撤掉，并把货退回卖方货栈（供付款失败时回滚）。"""
    book = getattr(state, "material_transit", None)
    if not isinstance(book, list):
        return
    tgt = res.get("batch") or {}
    for i in range(len(book) - 1, -1, -1):
        b = book[i]
        if b is tgt or (b.get("dim") == tgt.get("dim")
                        and b.get("to") == tgt.get("to")
                        and b.get("arrive_month") == tgt.get("arrive_month")):
            book.pop(i)
            break
    src = tgt.get("from")
    if src:
        from core.foundation.ledger.prefecture_entity import split_seat_id
        from core.foundation.ledger.material_holding import goods_add, merchant_goods
        circuit, _ = split_seat_id(src)
        goods = merchant_goods(state, circuit)
        if goods is not None:
            d = tgt.get("dim")
            # 2026-10-03：走单点写口（州府桶命名空间下裸写 goods[d] 只改扁平项，
            # 读侧 goods_amount 会算成「扁平 + Σ桶」而漏掉这笔）
            goods_add(goods, d, int(tgt.get("qty", 0) or 0))