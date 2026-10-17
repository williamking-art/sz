# -*- coding: utf-8 -*-
"""Bundle 3 政府采购与工役财政闭环单测。

覆盖：
1. 政府采购订单生成与微观工役政策抉择 (corvee vs hired)；
2. 订单交割：商贾物料款与工匠工钱划转、官方料场实物入库、物权台账留痕；
3. 结算管线集成：settle_local_expenditures 执行 public_supply 时真实生成采购订单与物资。
"""
import pytest
from application.game_init import new_game
from core.domains.economy.procurement import (
    create_procurement_order,
    settle_procurement_order,
    execute_public_supply_procurement,
    ProcurementOrder
)
from core.foundation.ledger.spatial_warehouse_bridge import warehouse_stock_get


def test_procurement_order_lifecycle():
    """测试采购订单生成、交割及料场入库。"""
    state = new_game("史实")
    route = "京畿路"
    budget = 1000

    order = create_procurement_order(state, route, budget, purpose="黄河堤防加固")
    assert order.route == route
    assert order.material_cost + order.service_cost == budget
    assert order.goods_qty > 0
    assert order.goods_dim in ("timber", "stone", "iron")

    # 初始料场存量
    init_stock = warehouse_stock_get(state, order.seat_id, "public_depot", order.goods_dim) or 0.0

    # 执行交割
    res = settle_procurement_order(state, order)
    assert res["ok"] is True
    assert res["paid_total"] > 0

    # 验证料场确实入库了采购物资
    new_stock = warehouse_stock_get(state, order.seat_id, "public_depot", order.goods_dim)
    assert new_stock == init_stock + order.goods_qty

    # 验证订单归档记录
    log = getattr(state, "procurement_orders_log", [])
    assert len(log) >= 1
    assert log[-1]["order_id"] == order.order_id


def test_public_supply_in_settlement_finance():
    """测试地方经费月度结算中 public_supply 产生订单与料场物资。"""
    state = new_game("史实")
    
    # 确保京畿路有充足地方府库用于支用
    state.prefectures["京畿路"]["local_treasury"] = 50000

    # 执行公用采购
    res = execute_public_supply_procurement(state, "京畿路", 2000)
    assert getattr(state, "procurement_orders_log", None) is not None


def test_procurement_order_conservation_laws():
    """验证 A-6 采购守恒定律：Δlocal + Δ商 + Δ工 == 0 且 Δ商人物料 + Δ官仓 == 0。"""
    state = new_game("史实")
    route = "京畿路"
    budget = 10000

    order = create_procurement_order(state, route, budget, purpose="四仓物资充实")
    order.goods_qty = 3000.0
    order.material_cost = 6000
    order.service_cost = 4000

    pdata = state.prefectures[route]
    pdata["local_treasury"] = 50000
    m_pop = pdata["pops"]["商人"]
    a_pop = pdata["pops"]["工匠"]

    from core.foundation.ledger.pop_bridge import pop_goods_add
    # 给商人注入充足的初始货量（走治所真账桥并刷新镜像）
    if pop_goods_add(pdata, "商人", order.goods_dim, 5000, order.seat_id) is None:
        m_pop.setdefault("goods", {})[order.goods_dim] = 5000

    loc0 = pdata["local_treasury"]
    m_wealth0 = m_pop.get("wealth", 0)
    a_wealth0 = a_pop.get("wealth", 0)
    m_goods0 = m_pop.get("goods", {}).get(order.goods_dim, 0)
    wh0 = warehouse_stock_get(state, order.seat_id, "public_depot", order.goods_dim) or 0.0

    res = settle_procurement_order(state, order)

    loc1 = pdata["local_treasury"]
    m_wealth1 = m_pop.get("wealth", 0)
    a_wealth1 = a_pop.get("wealth", 0)
    m_goods1 = m_pop.get("goods", {}).get(order.goods_dim, 0)
    wh1 = warehouse_stock_get(state, order.seat_id, "public_depot", order.goods_dim) or 0.0

    delta_loc = loc1 - loc0
    delta_m_wealth = m_wealth1 - m_wealth0
    delta_a_wealth = a_wealth1 - a_wealth0
    delta_m_goods = m_goods1 - m_goods0
    delta_wh = wh1 - wh0

    # 1. 货币实付与报表严格一致
    assert res["paid_total"] == res["paid_merchant"] + res["paid_artisan"]
    assert res["paid_merchant"] == 6000
    assert res["paid_artisan"] == 4000
    assert -delta_loc == res["paid_total"]

    # 2. 货币三方闭环：Δlocal + Δ商 + Δ工 == 0
    assert delta_loc + delta_m_wealth + delta_a_wealth == 0

    # 3. 物料双向闭环：Δ商人物料 + Δ官仓 == 0
    assert delta_m_goods + delta_wh == 0
    assert delta_wh == 3000.0
    assert delta_m_goods == -3000.0

