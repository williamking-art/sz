# -*- coding: utf-8 -*-
"""M314 产业物流调拨生产入口（2026-10-18 全审）。

`dispatch_industry_logistics` 此前零外部调用；现经 `commands.dispatch_logistics`
（`/api/action` 同一分派表）成为玩家/AI 可用的真实入口。
"""
import os
import sys

import pytest

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from application.game_init import new_game  # noqa: E402
from core import commands  # noqa: E402
from core.domains.economy.logistics_coupler import survey_logistics_coupling  # noqa: E402
from core.foundation.ledger.building_bridge import capital_seat_id  # noqa: E402
from core.foundation.ledger.spatial_warehouse_bridge import (  # noqa: E402
    warehouse_stock_add, warehouse_stock_get,
)


def _seed(s, route, dim="铁", amount=500.0):
    seat = capital_seat_id(s.prefectures[route], route)
    warehouse_stock_add(s, seat, "public_depot", dim, amount)
    return seat


def test_dispatch_logistics_moves_goods_into_transit():
    s = new_game("史实")
    origin, target = "京畿路", "河北路"
    seat = _seed(s, origin, "铁", 500.0)
    before = warehouse_stock_get(s, seat, "public_depot", "铁")
    assert before and before >= 500.0

    msg = commands.dispatch_logistics(s, origin, target, "铁", 300)
    assert "已调拨" in msg
    after = warehouse_stock_get(s, seat, "public_depot", "铁")
    assert after == pytest.approx(before - 300.0), "始发仓应真扣 300"

    batches = getattr(s, "in_transit_batches", []) or []
    assert len(batches) == 1, "应建立一条在途批次"
    assert float(batches[0].get("gross_amount", 0) or 0) == pytest.approx(300.0)
    assert batches[0].get("transit_mode") in ("waterway", "overland")
    rep = survey_logistics_coupling(s)
    assert rep["in_transit_by_dim"].get("铁", 0) >= 300.0


def test_dispatch_logistics_rejects_bad_params():
    s = new_game("史实")
    origin, target = "京畿路", "河北路"
    with pytest.raises(ValueError):
        commands.dispatch_logistics(s, origin, origin, "铁", 100)   # 同路
    with pytest.raises(ValueError):
        commands.dispatch_logistics(s, origin, target, "铁", 0)      # 数量非正
    with pytest.raises(ValueError):
        commands.dispatch_logistics(s, origin, target, "不存在的物料", 100)
    with pytest.raises(ValueError):
        commands.dispatch_logistics(s, "不存在的路", target, "铁", 100)


def test_dispatch_logistics_rejects_when_no_stock():
    s = new_game("史实")
    # 不种货：始发仓为空 ⇒ 必须拒绝且不建批次
    with pytest.raises(ValueError):
        commands.dispatch_logistics(s, "京畿路", "河北路", "铁", 100)
    assert not (getattr(s, "in_transit_batches", []) or [])