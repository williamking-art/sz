# -*- coding: utf-8 -*-
"""P1 · 省级军政派生断言：兵额守恒 / 只读不改 state / 按路筛选。"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState                       # noqa: E402
from core.region_brief import route_military_summary        # noqa: E402


def _new_state():
    return GameState("史实")


def _fingerprint(state):
    return [(u.unit_id, int(u.troops), int(u.arrears), dict(u.branches)) for u in state.army_units]


def test_nation_troops_equal_sum_of_units():
    """**兵额守恒**：逐路求和 == 全部 army_units 的 troops 求和（唯一真账）。"""
    s = _new_state()
    m = route_military_summary(s)
    total = sum(int(u.troops) for u in s.army_units)
    assert m["nation"]["troops"] == total, f"Σ路={m['nation']['troops']} ≠ Σ军={total}"
    assert m["nation"]["units"] == len(s.army_units)
    assert m["nation"]["troops"] > 0, "开局应有军队"


def test_route_filter_returns_only_that_route():
    """按路筛选：只给该路 `station` 的军队，且汇总与该路军表一致。"""
    s = _new_state()
    station = s.army_units[0].station
    m = route_military_summary(s, station)
    assert m["route"] == station
    assert m["units"], "该路应有军队"
    assert all(u["station"] == station for u in m["units"])
    assert m["summary"]["troops"] == sum(u["troops"] for u in m["units"])
    assert m["summary"]["units"] == len(m["units"])


def test_military_summary_is_read_only():
    """**只读**：调用前后 army_units 原样（兵额是真账，派生视图不得改动）。"""
    s = _new_state()
    before = _fingerprint(s)
    route_military_summary(s)
    route_military_summary(s, s.army_units[0].station)
    assert _fingerprint(s) == before, "派生视图改动了 army_units"


def test_cash_and_grain_reuse_region_brief_totals():
    """军饷/军粮复用路由行派生：Σ路 == nation 合计（不另算一套口径）。"""
    s = _new_state()
    m = route_military_summary(s)
    assert abs(sum(r["cash_month"] or 0 for r in m["routes"]) - m["nation"]["cash_month"]) < 0.05
    assert abs(sum(r["grain_month"] or 0 for r in m["routes"]) - m["nation"]["grain_month"]) < 0.05
