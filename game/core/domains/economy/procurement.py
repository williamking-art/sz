# -*- coding: utf-8 -*-
"""政府采购与工役物料核算引擎（procurement）。

定性与契约：
- 落实方案 B（Jev 0.7856）：彻底破除 4:6 死比例，将政府采购分解为【物料采购】与【劳务工役】两段；
- 物料采买：向本地商贾采买木石铁等物料，货款如实划转至商人 POP，物料实物入库治所官方料场（public_depot）；
- 工役政策：由 EmbeddedDecisionFacade.labor_service_policy 决策：
  * hired (雇役)：府库支付工匠工钱（划转至工匠 POP），工匠满意；
  * corvee (差役)：免付工钱（由农丁无偿轮差），但扣减劳力并轻微累加地方民怨（unrest +0.2）。
- 严格遵循守恒律与 POP 挂载律。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.ai.decision_facade import EmbeddedDecisionFacade
from core.foundation.ledger.spatial_warehouse_bridge import (
    warehouse_stock_add,
    transfer_goods_ownership
)

log = logging.getLogger(__name__)

__all__ = [
    "ProcurementOrder",
    "create_procurement_order",
    "settle_procurement_order",
    "execute_public_supply_procurement",
]


class ProcurementOrder:
    """政府采购订单结构。"""

    def __init__(
        self,
        order_id: str,
        route: str,
        seat_id: str,
        purpose: str,
        goods_dim: str,
        goods_qty: float,
        material_cost: int,
        service_cost: int,
        labor_mode: str
    ):
        self.order_id = order_id
        self.route = route
        self.seat_id = seat_id
        self.purpose = purpose
        self.goods_dim = goods_dim
        self.goods_qty = goods_qty
        self.material_cost = material_cost
        self.service_cost = service_cost
        self.labor_mode = labor_mode

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "route": self.route,
            "seat_id": self.seat_id,
            "purpose": self.purpose,
            "goods_dim": self.goods_dim,
            "goods_qty": self.goods_qty,
            "material_cost": self.material_cost,
            "service_cost": self.service_cost,
            "labor_mode": self.labor_mode
        }


def create_procurement_order(
    state: Any,
    route: str,
    budget: int,
    purpose: str = "营造水利"
) -> ProcurementOrder:
    """基于预算与内嵌微观决策生成政府采购订单。"""
    # 1. 寻径承载治所（默认该路首府）
    pdata = (getattr(state, "prefectures", {}) or {}).get(route, {})
    seat_id = route
    if isinstance(pdata, dict):
        try:
            from core.foundation.ledger.building_bridge import capital_seat_id
            cap = capital_seat_id(pdata, route)
            if cap:
                seat_id = cap
        except Exception:
            pass

    # 2. 决策工役制度: corvee (差役) vs hired (雇役)
    # 取该路府库现钱（若无则回落中央国库），确保财政决策能读到真实财力
    local_money = 0.0
    if isinstance(pdata, dict):
        local_money = float(pdata.get("local_treasury") or pdata.get("local_finance") or 0.0)
    if local_money <= 0 and hasattr(state, "treasury"):
        local_money = float(getattr(state, "treasury", 0.0) or 0.0)

    turn = int(getattr(state, "turn", 1) or 1)
    state_ctx = {
        "route": route,
        "budget": budget,
        "treasury": local_money,
        "unrest": float(pdata.get("unrest", 0.0) or 0.0) if isinstance(pdata, dict) else 0.0,
        "turn": turn,
    }
    labor_mode = EmbeddedDecisionFacade.labor_service_policy(state_ctx)

    # 3. 决定采购物料类型（工程木料 timber / 石料 stone / 铁料 iron）
    goods_dims = ["timber", "stone", "iron"]
    # 确定性伪随机哈希，避免 Python 进程间随机种子导致的非确定性
    route_seed = sum(ord(c) * (31 ** i) for i, c in enumerate(route)) % 1000000
    chosen_dim = goods_dims[(route_seed + turn) % len(goods_dims)]
    unit_price = 2.0  # 每单位物料基准价格（贯）

    # 4. 计算物料与工费
    if labor_mode == "corvee":
        # 差役法：工费为 0，预算全部购买物料，劳动力无偿征发
        material_cost = budget
        service_cost = 0
    else:
        # 雇役法：物料占 60%，工匠工钱占 40%
        material_cost = int(budget * 0.6)
        service_cost = budget - material_cost

    goods_qty = round(float(material_cost) / unit_price, 2)
    order_id = f"proc_{route}_{turn}_{(route_seed + budget) % 100000}"

    return ProcurementOrder(
        order_id=order_id,
        route=route,
        seat_id=seat_id,
        purpose=purpose,
        goods_dim=chosen_dim,
        goods_qty=goods_qty,
        material_cost=material_cost,
        service_cost=service_cost,
        labor_mode=labor_mode
    )


def settle_procurement_order(state: Any, order: ProcurementOrder) -> Dict[str, Any]:
    """交割采购订单：划拨款项、入库料场、扣减劳力/民怨。"""
    paid_merchant = 0
    paid_artisan = 0

    # 1. 支付商贾物料款
    if order.material_cost > 0 and hasattr(state, "transfer_money"):
        paid_merchant = state.transfer_money(
            f"local:{order.route}",
            f"pop:{order.route}:商人",
            order.material_cost
        )
        # 记录物权转移
        transfer_goods_ownership(
            state,
            dim=order.goods_dim,
            amount=order.goods_qty,
            from_owner=f"pop:{order.route}:商人",
            to_owner=f"local:{order.route}",
            reason="procurement_delivery",
            money_consideration=paid_merchant
        )

    # 2. 支付工匠工钱（若是雇役）
    if order.service_cost > 0 and hasattr(state, "transfer_money"):
        paid_artisan = state.transfer_money(
            f"local:{order.route}",
            f"pop:{order.route}:工匠",
            order.service_cost
        )

    # 3. 真实入库官方料场 public_depot
    if order.goods_qty > 0:
        warehouse_stock_add(
            state,
            order.seat_id,
            "public_depot",
            order.goods_dim,
            order.goods_qty,
            reason="procurement_completed"
        )

    # 4. 差役劳力惩罚（若是差役）
    if order.labor_mode == "corvee":
        pdata = (getattr(state, "prefectures", {}) or {}).get(order.route)
        if isinstance(pdata, dict):
            # 差役增加轻微民怨 (+0.2)
            cur_unrest = float(pdata.get("unrest", 0.0) or 0.0)
            pdata["unrest"] = round(cur_unrest + 0.2, 2)

    # 5. 归档订单
    orders_log = getattr(state, "procurement_orders_log", None)
    if orders_log is None:
        orders_log = []
        setattr(state, "procurement_orders_log", orders_log)
    orders_log.append(order.to_dict())

    return {
        "ok": True,
        "order_id": order.order_id,
        "paid_merchant": paid_merchant,
        "paid_artisan": paid_artisan,
        "paid_total": paid_merchant + paid_artisan,
        "goods_dim": order.goods_dim,
        "goods_qty": order.goods_qty,
        "labor_mode": order.labor_mode
    }


def execute_public_supply_procurement(
    state: Any,
    route: str,
    budget: int
) -> Dict[str, Any]:
    """主线结算入口：执行某路月度公用经费政府采购。"""
    if budget <= 0:
        return {"paid_total": 0, "paid_merchant": 0, "paid_artisan": 0}
    
    order = create_procurement_order(state, route, budget)
    res = settle_procurement_order(state, order)
    return res
