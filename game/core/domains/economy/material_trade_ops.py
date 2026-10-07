# -*- coding: utf-8 -*-
"""domains/economy · 建材交易与补给操作（丙批二 · 2026-10-06 自 `core/material_holding.py` 拆出）。

**归属判据**（`specs/cross-cutting/甲批_符号归属与新旧路径表.md` §一）：
本包三项都是**搬运/成交规则**（Step 4 调度语义），不是账本接口 ⇒ 归经济域，
向下依赖 `foundation/ledger/material_holding` 的持有/读写口。

- `commodity_dims(goods)` —— 商品维键识别（排除州府桶），迁移期防「桶被当维算术」。
- `supply_merchant_materials(state)` —— **历史入口**：建材三维差额搬运（幂等、守恒）。
  ⚠️ G-2 起全商品供给走 ledger 的 `supply_goods_to_seats()`；本函数**生产零调用**
  （实测 `62977dfeb0`），保留因测试仍依赖，**不得按死代码删**。
- `trade_material(state, ...)` —— 同路市集成交薄适配器，复用 `market.trade_goods`，
  🔴 跨州府**拒绝**（C-c 护栏：建材不得瞬移）。

✅ **§6 规则 2 偏离已销账（第十包，2026-10-07）**：本模块不再借用 ledger 私有符号，
   改用显式接口 `attribute_to_seats` / `route_of`（旧私有名在 ledger 里仅作兼容别名保留，
   供 `core/material_holding.py` 薄桩守恒其公开面；跨模块**不得**再取用下划线名）。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from core.foundation.ledger.material_holding import (
    MATERIAL_DIMS, attribute_to_seats, goods_add, goods_amount,
    merchant_goods, merchant_of, route_of,
)

__all__ = ["commodity_dims", "supply_merchant_materials", "trade_material"]


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
            attributed = attribute_to_seats(merchant_of(state, route), route, dim, int(qty))
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
    from core.domains.economy.market import trade_goods

    if dim not in MATERIAL_DIMS:
        raise KeyError(f"非建材维度：{dim!r}")
    if buyer_pop is seller_pop:
        raise ValueError("买方与卖方不得为同一 POP（自成交不构成市场）")

    # 🔴 **C-c 护栏**：跨州府成交**不得瞬移**。
    # 建材必须"先运到"才能用——若本函数让货直接落进买方货栈，
    # "运没运到"就不可观测，物流便没有意义。
    # ⇒ 同路（市集内）走本函数；**跨路请用 `transport.dispatch`**。
    prefs = getattr(state, "prefectures", {}) or {}
    bc = route_of(prefs, buyer_pop)
    sc = route_of(prefs, seller_pop)
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
