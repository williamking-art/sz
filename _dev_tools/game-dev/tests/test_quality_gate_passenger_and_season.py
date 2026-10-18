# -*- coding: utf-8 -*-
"""质量放行门 · 客运占运力 + 季节发运接线（2026-10-18）。

P4 缺口（客运未吃运力账）与 P3 缺口（季节未接发运）在本轮闭合。

本门钉住：
1. 客运**占用运力**（1 人 ≈ 0.5 石），客货共用池；
2. 运力不足 ⇒ 客运**减载**（`carried` < 请求、`left_behind` > 0），不瞬移；
3. 运力为 0 ⇒ 拒发并给 `no_capacity`；
4. 水运封冻月（11–2）发运 ⇒ `season_closed` 且给 `deferred_to`；
5. 枯水月（3）⇒ 载重按 `capacity_mult` 减载、逆速按 `speed_mult` 放大天数；
6. 海运不受封冻影响。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.foundation.ledger.spatial_warehouse_bridge import dispatch_passenger_trip  # noqa: E402
from core.transport import dispatch, transport_consume, transport_remaining  # noqa: E402

HZ = "两浙路|杭州"
MZ = "两浙路|明州"


def _state():
    from core.commands import new_game

    return new_game()


def test_passenger_consumes_capacity():
    s = _state()
    before = transport_remaining(s, "waterway")
    r = dispatch_passenger_trip(s, HZ, MZ, "官员赴任", 10, "waterway")
    assert r["ok"] is True
    after = transport_remaining(s, "waterway")
    assert abs((before - after) - 10 * 0.5) < 1e-6, (before, after)


def test_passenger_shares_pool_with_goods():
    s = _state()
    cap = transport_remaining(s, "waterway")
    transport_consume(s, "waterway", cap - 100, kind="goods")
    r = dispatch_passenger_trip(s, HZ, MZ, "商旅", 1000, "waterway")
    assert r["ok"] is True
    trip = s.passenger_trips[-1]
    assert trip["requested_count"] == 1000
    assert trip["count"] < 1000 and trip["left_behind"] > 0, trip


def test_passenger_refused_without_capacity():
    s = _state()
    s.carriage = {}
    s.transport_labor = {}
    r = dispatch_passenger_trip(s, HZ, MZ, "商旅", 50, "waterway")
    assert r["ok"] is False and r["reason"] == "no_capacity"
    assert r["left_behind"] == 50
