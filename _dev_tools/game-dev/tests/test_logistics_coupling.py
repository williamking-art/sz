# -*- coding: utf-8 -*-
"""测试 M314 产业上游原料物理入仓与水陆物流运力调拨深度耦合。"""

import types
import pytest

from core.domains.economy import logistics_coupler as lc
from core.foundation.ledger import spatial_warehouse_bridge as swb
from core.domains.economy.macro_climate import ALL_CIRCUITS_21


def _create_mock_state():
    state = types.SimpleNamespace()
    state.treasury = 500000
    state.canal_block = 12
    state.turn = 1
    state.in_transit_batches = []
    state.statistics = {"barges_pool": 60}
    state.prefectures = {}
    for r in ALL_CIRCUITS_21:
        state.prefectures[r] = {
            "land": 20000000.0,
            "seats": {
                f"{r}_seat_1": {
                    "name": f"{r}府",
                    "warehouses": {
                        "public_depot": {"stocks": {}},
                        "public_granary": {"stocks": {}},
                        "civilian_depots": {"stocks": {}},
                        "private_storage": {"stocks": {}},
                    }
                }
            }
        }
    return state


def test_upstream_production_ingest_into_spatial_warehouses():
    state = _create_mock_state()
    # 模拟河东路开采出煤矿与铁矿
    raw = {"iron_ore": 10000.0, "coal": 20000.0}
    res = lc.ingest_upstream_production(state, "河东路", raw, clerk_grip=0.40)

    assert res["total_ingested"] == 30000.0
    cap_sid = res["capital_seat"]

    wh = state.prefectures["河东路"]["seats"][cap_sid]["warehouses"]
    # 验证官工料场与民间货栈均有物料物理入库
    assert wh["public_depot"]["stocks"].get("iron_ore", 0) > 0
    assert wh["civilian_depots"]["stocks"].get("coal", 0) > 0


def test_dispatch_industry_logistics_waterway():
    state = _create_mock_state()
    # 先向江南东路官方料场注入 50,000 斤铜料
    seat_obj = next(iter(state.prefectures["江南东路"]["seats"].values()))
    wh = seat_obj["warehouses"]
    wh["public_depot"]["stocks"]["铜"] = 50000.0

    # 从江南东路向两浙路调拨 20,000 斤铜料（两浙江南皆为水路强路）
    res = lc.dispatch_industry_logistics(
        state,
        origin_circuit="江南东路",
        target_circuit="两浙路",
        goods_dim="铜",
        amount=20000.0,
        owner="state:treasury",
    )

    assert res["ok"] is True
    assert res["transit_mode"] == "waterway"

    # 始发仓真实扣减
    assert wh["public_depot"]["stocks"]["铜"] == 30000.0

    # 在途批次生成，且占用水路运力
    batches = state.in_transit_batches
    assert len(batches) == 1
    assert batches[0]["goods_dim"] == "铜"
    assert batches[0]["gross_amount"] == 20000.0
    assert batches[0]["transit_mode"] == "waterway"


def test_dispatch_industry_logistics_canal_block_fallback():
    state = _create_mock_state()
    # 将运河淤塞拉高到 40（严重淤塞断航），验证自动降级为陆运
    state.canal_block = 40
    seat_obj = next(iter(state.prefectures["河北路"]["seats"].values()))
    wh = seat_obj["warehouses"]
    wh["public_depot"]["stocks"]["铁"] = 30000.0

    res = lc.dispatch_industry_logistics(
        state,
        origin_circuit="河北路",
        target_circuit="京畿路",
        goods_dim="铁",
        amount=10000.0,
        owner="state:treasury",
    )

    assert res["ok"] is True
    # 因运河淤塞严重，被迫降级为驿道陆运
    assert res["transit_mode"] == "overland"
    assert wh["public_depot"]["stocks"]["铁"] == 20000.0
