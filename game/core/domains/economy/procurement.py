# -*- coding: utf-8 -*-
"""政府采购与工役物料核算引擎（procurement）。

定性与契约：
- 落实方案 B（Jev 0.7856）：彻底破除 4:6 死比例，将政府采购分解为【物料采购】与【劳务工役】两段；
- 物料采买：向本地商贾采买木石铁等物料，货款如实划转至商人 POP，物料实物入库治所官方料场（public_depot）；
  🔴 **物料维必须走权威表**（`material_holding.MATERIAL_DIMS` = 木/石/铁，中文轨）：
  旧实现用已废弃的英文轨 `timber/stone/iron`，`to_material_dim()` 认不出 ⇒ 交割时商人物权扣减为 0、
  入库却记在**不存在的幽灵维度**上（全库无人交易该维，工程取料永远取不到）——钱花了、料用不了。
  🔴 **成交受本路商人实有物料约束**（Jev p=0.979）：实扣多少才入库多少、才付多少物料款；
  无料 ⇒ 本单不成交（`paid_total=0`、不入库），由调用方归因为缺料。
- 工役政策：由 EmbeddedDecisionFacade.labor_service_policy 决策：
  * hired (雇役)：府库支付工匠工钱（划转至工匠 POP），工匠满意；
  * corvee (差役)：免付工钱（由农丁无偿轮差），但扣减劳力并轻微累加地方民怨（unrest +0.2）。
- 严格遵循守恒律与 POP 挂载律。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.ai.decision_facade import EmbeddedDecisionFacade
from core.foundation.ledger.material_holding import MATERIAL_DIMS
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

    # 3. 决定采购物料类型（木/石/铁 —— 必须用 `material_holding.MATERIAL_DIMS` 权威中文轨）
    goods_dims = list(MATERIAL_DIMS)
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
    """交割采购订单：钱货两讫（成交多少付多少）、实物入库、扣减劳力/民怨。

    🔴 成交口径（Jev p=0.979）：
    · **只入实扣到的量**：`transfer_goods_ownership` 返回的 `stock_deducted` 才是成交物料；
      商人没有那么多料 ⇒ 少买少付，**不得按订单量凭空入库**（旧实现全额入库）；
    · **只付成交部分**：物料款与工钱都按成交比例支付（无料 ⇒ 本单不成交，`paid_total=0`）；
    · 物料维必须是 `MATERIAL_DIMS` 中文轨（旧英文轨 `timber/stone/iron` 已废，扣不到货）。
    """
    paid_merchant = 0
    paid_artisan = 0
    planned_qty = float(order.goods_qty or 0.0)
    delivered = 0.0

    # 1. 先交割物权：只扣商人物权、不付款（钱在下一步按成交比例付）
    if planned_qty > 0:
        tx_res = transfer_goods_ownership(
            state,
            dim=order.goods_dim,
            amount=planned_qty,
            from_owner=f"pop:{order.route}:商人",
            to_owner=f"local:{order.route}",
            reason="procurement_delivery",
            money_consideration=0,
            seat_id=order.seat_id
        )
        delivered = float(tx_res.get("stock_deducted") or 0.0)
        # 流量账登记（POP custody）：货物离开商人民间持有；漏登记会让
        # `test_stock_flow_identity::test_pop_custody_identity_closes_exactly` 逐维残差非 0。
        if delivered > 0:
            try:
                from core.domains.economy import stock_flow as _sf
                _sf.record_out(state, order.goods_dim, int(delivered),
                               reason="procurement_delivery", custody=_sf.CUSTODY_POP)
            except Exception as _e:  # noqa: BLE001 — 测量仪器不得中断交割
                log.warning("采购流量登记失败（不影响交割）：%s", _e)

    ratio = min(1.0, delivered / planned_qty) if planned_qty > 0 else 0.0

    # 2. 付款：物料款与工钱都按成交比例（无料 ⇒ 不付）
    if ratio > 0 and hasattr(state, "transfer_money"):
        pay_merchant = int(round(float(order.material_cost or 0) * ratio))
        if pay_merchant > 0:
            paid_merchant = int(state.transfer_money(
                f"local:{order.route}", f"pop:{order.route}:商人", pay_merchant))
        if order.service_cost > 0:
            pay_artisan = int(round(float(order.service_cost) * ratio))
            if pay_artisan > 0:
                paid_artisan = int(state.transfer_money(
                    f"local:{order.route}", f"pop:{order.route}:工匠", pay_artisan))

    # 3. 真实入库官方料场 public_depot（只入实扣到的量）
    if delivered > 0:
        warehouse_stock_add(
            state,
            order.seat_id,
            "public_depot",
            order.goods_dim,
            delivered,
            reason="procurement_completed"
        )

    # 4. 差役劳力惩罚（成交才征发劳役）
    if order.labor_mode == "corvee" and delivered > 0:
        pdata = (getattr(state, "prefectures", {}) or {}).get(order.route)
        if isinstance(pdata, dict):
            # 差役增加轻微民怨 (+0.2)
            cur_unrest = float(pdata.get("unrest", 0.0) or 0.0)
            pdata["unrest"] = round(cur_unrest + 0.2, 2)

    # 5. 归档订单（记录计划量与成交量，便于对账/诊断）
    orders_log = getattr(state, "procurement_orders_log", None)
    if orders_log is None:
        orders_log = []
        setattr(state, "procurement_orders_log", orders_log)
    _rec = order.to_dict()
    _rec["delivered_qty"] = round(delivered, 2)
    orders_log.append(_rec)

    return {
        "ok": True,
        "order_id": order.order_id,
        "paid_merchant": paid_merchant,
        "paid_artisan": paid_artisan,
        "paid_total": paid_merchant + paid_artisan,
        "goods_dim": order.goods_dim,
        "goods_qty": order.goods_qty,
        "delivered_qty": round(delivered, 2),
        "shortfall_qty": round(max(0.0, planned_qty - delivered), 2),
        "material_short": bool(planned_qty > 0 and delivered <= 0),
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
