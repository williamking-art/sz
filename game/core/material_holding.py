# -*- coding: utf-8 -*-
"""`core.material_holding` —— 迁移期兼容入口（丙批一 · 2026-10-06 拆分）。

- **账本侧 42 符号**的唯一实现已迁至 `core.foundation.ledger.material_holding`，
  本模块**显式转发**（含私有名，运行时 dir() 口径 52 名不变、不复制实现）。
- **交易侧 3 项**（`trade_material`/`supply_merchant_materials`/`commodity_dims`）
  **暂住本模块**，目标批次迁 `domains/economy/material_trade_ops.py`
  （归属判据与生产零调用实测见 `specs/cross-cutting/甲批_符号归属与新旧路径表.md` §一/§五）。
- ⚠️ 勿在此新增实现；新代码请 import `foundation.ledger.material_holding`。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.foundation.ledger.material_holding import (
    HOLDER_IMPERIAL, HOLDER_MAP, HOLDER_PROVENANCE, HOLDER_TREASURY,
    MATERIAL_DIMS, SEAT_SEP, SEAT_SLOT, SEAT_W, TRIBUTE_WEIGHT_BONUS,
    _TRIBUTE_BY_CIRCUIT, _TRIBUTE_BY_SEAT, _attribute_by_weights,
    _attribute_to_seats, _build_tribute_index, _num, _route_of,
    _seat_name_of, circuit_seats, circuit_tribute_dims, consume_for_circuit,
    consume_for_seat, goods_add, goods_amount, goods_bucket, goods_set,
    holder_pops_of_circuit, holding_report, is_seat_bucket_key,
    material_holding_for_circuit, material_holding_for_seat, merchant_goods,
    merchant_of, resolve_holder, seat_holding_report, seat_slot,
    seat_tribute_dims, seat_weights_for, seat_weights_of_circuit,
    seat_yield_weights_of_circuit, supply_goods_to_seats, to_material_dim,
    tribute_circuits,
)



def commodity_dims(goods) -> List[str]:
    """🔴 `goods` 里的**商品维键**（排除州府桶）。

    迁移期 `goods` 可能含 `治所→{dim:n}` 桶；任何
    `for dim in goods` / `goods.keys()` 的旧代码都**必须**改走本函数，
    否则会把桶（dict）当商品维参与算术（实测炸出 158 例）。

    仅返回**数值型**的键 —— 这是比「排除含 `|` 的键」更严也更稳的判据：
    桶是 dict、不是数，天然被排除；扁平项若被误写成非数值也不会混进来。
    """
    if not isinstance(goods, dict):
        return []
    return [k for k, v in goods.items()
            if isinstance(k, str) and not isinstance(v, (dict, bool))
            and isinstance(v, (int, float))]



def supply_merchant_materials(state, total: Optional[Dict[str, int]] = None
                             ) -> Dict[str, int]:
    """把 `state.resources[dim]["stock"]` 的料**搬进各路商人货栈**（Step 4.45）。

    ⚠️ **只是搬运，总量守恒、不凭空增物**：每次按
    `stock − Σ(商人已持有)` 的**差额**补足，因此重复调用**幂等**、
    不会因"每月都跑一次"而无限膨胀。

    分配依据：**商人 POP 规模**（代表商业容量）；无商人的路不参与分配
    （其份额留在总账，**不按比例代填**）。

    ⚠️ **G-2 起**：本函数仅保留建材三维的历史入口；全商品供给走
    `supply_goods_to_seats()`（可限定维度、可按产地证据归属）。
    """
    prefs = getattr(state, "prefectures", {}) or {}
    res = getattr(state, "resources", None) or {}
    out: Dict[str, int] = {}
    for dim in MATERIAL_DIMS:
        stock = int((res.get(dim) or {}).get("stock", 0) or 0) \
            if total is None else int(total.get(dim, 0) or 0)
        if stock <= 0:
            continue
        held = 0
        wts = []
        for route in prefs:
            goods = merchant_goods(state, route)
            if goods is None:
                continue
            cur = goods_amount(goods, dim)
            if cur is None:
                continue
            m = merchant_of(state, route)
            wts.append([route, max(1.0, float(m.get("size", 0) or 0))])
            held += int(cur)
        need = stock - held
        if need <= 0 or not wts:
            continue
        wsum = sum(w for _r, w in wts)
        anchor = max(wts, key=lambda kv: kv[1])[0]
        parts = {r: int(round(need * w / wsum)) for r, w in wts}
        parts[anchor] += need - sum(parts.values())
        for route, qty in parts.items():
            goods = merchant_goods(state, route)
            # 2026-10-03（州府桶）：新到手的量**按州府人口拆进 `goods[治所]` 桶**。
            # 🔴 **只写一处** —— 桶是权威，扁平区仅作「无州府归属」的如实单列；
            # 两处都写会**双计**（`goods_amount` 会把两者相加）。
            attributed = _attribute_to_seats(merchant_of(state, route), route, dim, int(qty))
            if attributed <= 0:
                # 该路无治所人口权重（如无地图府块）⇒ **不臆造归属**，如实落扁平区
                goods_add(goods, dim, int(qty))
        out[dim] = held + need
    return out



def trade_material(state, *, buyer_pop: dict, seller_pop: dict,
                   dim: str, qty: int, price: float,
                   purpose: str = "resale", trade_id: Optional[str] = None):
    """州府间**建材成交**（真·商人供货）—— **复用 `market.trade_goods`**。

    🔴 **E-1 后不再需要视图适配器**：料本来就在 POP `goods` 上，
    可直接把真 POP 交给 `trade_goods`（它本就按 `buyer/seller` 的
    `wealth` 与 `goods` 做**就地原子转移**）。

    不变量：
    ① `ΣPOP wealth` **不变**（钱从买方移到卖方，不创造不销毁）；
    ② `ΣPOP goods[建材]` **不变**（料只是换了持有者）；
    ③ 自成交由 `trade_goods` 自身 `buyer is seller` **拒绝**；
    ④ `unmet_qty` **原样返回**，调用方须归因，**不静默丢弃**。
    """
    from core.market import trade_goods

    if dim not in MATERIAL_DIMS:
        raise KeyError(f"非建材维度：{dim!r}")
    if buyer_pop is seller_pop:
        raise ValueError("买方与卖方不得为同一 POP（自成交不构成市场）")

    # 🔴 **C-c 护栏**：跨州府成交**不得瞬移**。
    # 建材必须"先运到"才能用——若本函数让货直接落进买方货栈，
    # "运没运到"就不可观测，物流便没有意义。
    # ⇒ 同路（市集内）走本函数；**跨路请用 `transport.dispatch`**。
    prefs = getattr(state, "prefectures", {}) or {}
    bc = _route_of(prefs, buyer_pop)
    sc = _route_of(prefs, seller_pop)
    if bc and sc and bc != sc:
        raise ValueError(
            f"跨州府建材成交不得瞬移（买方 {bc} / 卖方 {sc}）："
            f"请用 `core.transport.dispatch` 走真实在途")

    before_buyers = int((buyer_pop.get("goods") or {}).get(dim, 0) or 0)
    before_seller = int((seller_pop.get("goods") or {}).get(dim, 0) or 0)

    res = trade_goods(state, dim=dim, qty=int(qty), price=float(price),
                      buyer=buyer_pop, seller=seller_pop,
                      purpose=purpose, trade_id=trade_id)

    after_buyers = int((buyer_pop.get("goods") or {}).get(dim, 0) or 0)
    after_seller = int((seller_pop.get("goods") or {}).get(dim, 0) or 0)
    res["material_delta"] = {
        "buyer": after_buyers - before_buyers,
        "seller": after_seller - before_seller,
        "sum": (after_buyers - before_buyers) + (after_seller - before_seller),
    }
    return res

__all__ = ['MATERIAL_DIMS', 'to_material_dim', 'seat_yield_weights_of_circuit', 'seat_weights_for', 'supply_goods_to_seats', 'circuit_seats', 'merchant_of', 'merchant_goods', 'material_holding_for_circuit', 'consume_for_circuit', 'supply_merchant_materials', 'trade_material', 'holding_report', 'SEAT_SEP', 'is_seat_bucket_key', 'goods_bucket', 'goods_amount', 'goods_set', 'goods_add', 'commodity_dims', 'seat_slot', 'seat_weights_of_circuit', 'holder_pops_of_circuit', 'material_holding_for_seat', 'consume_for_seat', 'seat_holding_report']
