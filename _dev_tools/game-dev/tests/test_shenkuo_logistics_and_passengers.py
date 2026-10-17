# -*- coding: utf-8 -*-
"""Bundle 4 三维交通沈括民夫口粮途耗与客运时空流动单测。

覆盖：
1. 沈括民夫口粮途耗模型：陆运在途扣粮与运抵净入库（守恒律：净入库 + 途耗 == 始发量）；
2. 三维交通效能比：水运耗时与口粮损耗显著低于陆运；
3. 客运时空流动：官员赴任、举子赴考、流民迁徙的时空位移与到埠结算。
"""
import pytest
from application.game_init import new_game
from core.foundation.ledger.spatial_warehouse_bridge import (
    warehouse_stock_add,
    warehouse_stock_get,
    dispatch_spatial_transfer,
    advance_in_transit_batches,
    dispatch_passenger_trip,
    advance_passenger_trips
)


def test_shenkuo_grain_ration_loss_overland():
    """测试沈括民夫口粮途耗模型（陆运运粮自然递减与严格物理守恒）。"""
    state = new_game("史实")
    
    # 1. 在开封官仓注入 1000 石实粮
    warehouse_stock_add(state, "kaifeng", "public_granary", "grain", 1000.0)

    # 2. 发起开封 -> 江宁陆运调拨 600 石实粮 (陆路 30 天)
    disp = dispatch_spatial_transfer(
        state,
        origin_seat="kaifeng",
        target_seat="jiangning",
        goods_dim="grain",
        amount=600.0,
        owner="state:kaifeng",
        transit_mode="overland"
    )
    assert disp["ok"] is True
    assert disp["days"] == 30
    assert disp["porters"] > 0
    # 始发地即刻扣除 600 石
    assert warehouse_stock_get(state, "kaifeng", "public_granary", "grain") == 400.0

    # 3. 推进 15 天 (在途一半，民夫吃掉部分口粮)
    mid_arrived = advance_in_transit_batches(state, days=15)
    assert len(mid_arrived) == 0
    batches = state.in_transit_batches
    assert len(batches) == 1
    b = batches[0]
    assert b["remaining_days"] == 15
    assert b["rations_consumed"] > 0
    assert b["gross_amount"] < 600.0
    # 严格守恒检查
    assert round(b["gross_amount"] + b["rations_consumed"], 4) == 600.0

    # 4. 推进剩余 15 天 (运抵目的地江宁官仓)
    final_arrived = advance_in_transit_batches(state, days=15)
    assert len(final_arrived) == 1
    arr = final_arrived[0]
    assert arr["status"] == "delivered"
    net_in = arr["net_delivered"]
    total_loss = arr["rations_consumed"]
    assert round(net_in + total_loss, 4) == 600.0

    # 验证江宁官仓实入库量正是 net_in (绝无隔空虚增)
    assert warehouse_stock_get(state, "jiangning", "public_granary", "grain") == net_in


def test_waterway_vs_overland_efficiency():
    """测试水运与陆运效能差异：水运耗时短、民夫口粮损耗低。"""
    state = new_game("史实")
    warehouse_stock_add(state, "kaifeng", "public_granary", "grain", 2000.0)

    # 水运调拨 500 石
    disp_water = dispatch_spatial_transfer(
        state, "kaifeng", "jiangning", "grain", 500.0, "state:kaifeng", "waterway"
    )
    # 陆运调拨 500 石
    disp_land = dispatch_spatial_transfer(
        state, "kaifeng", "jiangning", "grain", 500.0, "state:kaifeng", "overland"
    )

    # 水运仅需 15 天，陆运需 30 天
    assert disp_water["days"] == 15
    assert disp_land["days"] == 30
    assert disp_water["porters"] < disp_land["porters"]

    # 推进 15 天，水运到达
    arrived_15 = advance_in_transit_batches(state, days=15)
    assert len(arrived_15) == 1
    water_batch = arrived_15[0]
    assert water_batch["transit_mode"] == "waterway"
    water_loss = water_batch["rations_consumed"]

    # 再推进 15 天，陆运到达
    arrived_30 = advance_in_transit_batches(state, days=15)
    assert len(arrived_30) == 1
    land_batch = arrived_30[0]
    assert land_batch["transit_mode"] == "overland"
    land_loss = land_batch["rations_consumed"]

    # 水运损耗显著低于陆运损耗 (沈括运粮经典结论)
    assert water_loss < land_loss


def test_passenger_mobility():
    """测试官员赴任与举子赴考时空旅程。"""
    state = new_game("史实")

    # 1. 发起江宁通判赴任开封
    res1 = dispatch_passenger_trip(
        state,
        origin_seat="jiangning",
        target_seat="kaifeng",
        passenger_type="official",
        count=1,
        transit_mode="waterway"
    )
    assert res1["ok"] is True
    assert res1["days"] == 15

    # 2. 发起 100 名举子进京赶考 (陆运)
    res2 = dispatch_passenger_trip(
        state,
        origin_seat="jiangning",
        target_seat="kaifeng",
        passenger_type="scholar",
        count=100,
        transit_mode="overland"
    )
    assert res2["ok"] is True
    assert res2["days"] == 30

    # 3. 推进 15 天：官员水运到达，举子仍在途中
    arr15 = advance_passenger_trips(state, days=15)
    assert len(arr15) == 1
    assert arr15[0]["passenger_type"] == "official"
    assert len(state.passenger_trips) == 1

    # 4. 再推进 15 天：举子到达开封
    arr30 = advance_passenger_trips(state, days=15)
    assert len(arr30) == 1
    assert arr30[0]["passenger_type"] == "scholar"
    assert len(state.passenger_trips) == 0
