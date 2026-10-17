# -*- coding: utf-8 -*-
"""Bundle 1 空间确权仓储底座单测。

覆盖：
1. 治所物理四仓位下沉与幂等；
2. 物理库存读写与零下限钳位；
3. 四大物权主体间划转与货币对价原子性；
4. 跨治所物理在途调拨与到货推进。
"""
import pytest
from application.game_init import new_game
from core.foundation.ledger.spatial_warehouse_bridge import (
    warehouse_stock_get,
    warehouse_stock_add,
    transfer_goods_ownership,
    dispatch_spatial_transfer,
    advance_in_transit_batches,
    survey_spatial_warehouses,
    WAREHOUSE_TYPES
)


def test_spatial_warehouses_init_and_survey():
    """测试开局全域治所物理仓位下沉。"""
    state = new_game("史实")
    survey = survey_spatial_warehouses(state)
    assert survey["defined"] is True
    assert survey["total_seats"] > 0
    assert survey["with_warehouses"] == survey["total_seats"]
    assert survey["ratio"] == 1.0

    # 抽检开封府 (kaifeng)
    for wh_type in WAREHOUSE_TYPES:
        val = warehouse_stock_get(state, "kaifeng", wh_type, "grain")
        assert val == 0.0


def test_warehouse_stock_add_and_get():
    """测试物理库存读写与缺失值保护。"""
    state = new_game("史实")
    
    # 增加开封官仓粮食 5000 石
    res = warehouse_stock_add(state, "kaifeng", "public_granary", "grain", 5000.0)
    assert res == 5000.0
    assert warehouse_stock_get(state, "kaifeng", "public_granary", "grain") == 5000.0

    # 扣减 2000 石
    res2 = warehouse_stock_add(state, "kaifeng", "public_granary", "grain", -2000.0)
    assert res2 == 3000.0
    assert warehouse_stock_get(state, "kaifeng", "public_granary", "grain") == 3000.0

    # 超额扣减钳位为 0
    res3 = warehouse_stock_add(state, "kaifeng", "public_granary", "grain", -5000.0)
    assert res3 == 0.0

    # 缺失治所返回 None (缺失≠0)
    assert warehouse_stock_get(state, "non_existent_seat", "public_granary", "grain") is None


def test_transfer_goods_ownership():
    """测试物权流转原子操作与货币对价。"""
    state = new_game("史实")

    # 开封知府向当地商人采购 200 匹绢，单价 1.5 贯，货款 300 贯
    # 买方 local:jingdongdong 支付 300 贯给 pop:jingdongdong:商人
    res = transfer_goods_ownership(
        state,
        dim="silk",
        amount=200.0,
        from_owner="pop:jingdongdong:商人",
        to_owner="local:jingdongdong",
        reason="procurement_silk",
        money_consideration=300.0
    )
    assert res["ok"] is True
    assert res["amount"] == 200.0
    assert res["from_owner"] == "pop:jingdongdong:商人"
    assert res["to_owner"] == "local:jingdongdong"


def test_dispatch_spatial_transfer_and_advance():
    """测试跨治所物理在途运输与运抵入库。"""
    state = new_game("史实")

    # 1. 在开封官方料场注入 1000 斤铁
    warehouse_stock_add(state, "kaifeng", "public_depot", "iron", 1000.0)

    # 2. 发起开封 -> 江宁府调拨 400 斤铁
    disp = dispatch_spatial_transfer(
        state,
        origin_seat="kaifeng",
        target_seat="jiangning",
        goods_dim="iron",
        amount=400.0,
        owner="state:kaifeng",
        transit_mode="waterway"
    )
    assert disp["ok"] is True
    assert disp["days"] == 15
    # 始发地即刻扣除
    assert warehouse_stock_get(state, "kaifeng", "public_depot", "iron") == 600.0
    # 目的地尚未到达
    assert warehouse_stock_get(state, "jiangning", "public_depot", "iron") == 0.0

    # 3. 推进 10 天 (尚未到达)
    arrived_mid = advance_in_transit_batches(state, days=10)
    assert len(arrived_mid) == 0
    assert warehouse_stock_get(state, "jiangning", "public_depot", "iron") == 0.0

    # 4. 再推进 10 天 (累计 20 天 > 15 天，运抵入库)
    arrived_final = advance_in_transit_batches(state, days=10)
    assert len(arrived_final) == 1
    assert warehouse_stock_get(state, "jiangning", "public_depot", "iron") == 400.0
