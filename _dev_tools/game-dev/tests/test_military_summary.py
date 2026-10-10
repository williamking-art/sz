# -*- coding: utf-8 -*-
"""P1 · 省级军政派生断言：兵额守恒 / 只读不改 state / 按路筛选。"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState                       # noqa: E402
import pytest  # noqa: E402

from core.region_brief import route_military_summary, unit_cost_readout  # noqa: E402


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


# ---------------------------------------------------------------
# 单军粮饷明细（面板「点开某一支军」用）—— 与全局口径**同源**，不得另算一套
# ---------------------------------------------------------------
def test_unit_cost_readout_sums_to_army_totals():
    """Σ单军月饷 == calc_army_cash；Σ单军月粮 == calc_army_grain（权威表同一张）。"""
    s = _new_state()
    pay = 0.0
    grain = 0.0
    for u in s.army_units:
        c = unit_cost_readout(u)
        assert set(c) == {"monthly_pay", "monthly_grain"}
        assert c["monthly_pay"] is not None, "开局军队应可算出应发月饷"
        pay += float(c["monthly_pay"])
        grain += float(c["monthly_grain"])
    cash_total, _ = s.calc_army_cash()
    grain_total, _ = s.calc_army_grain()
    assert abs(pay - cash_total) < 0.05, f"Σ单军月饷 {pay} != calc_army_cash {cash_total}"
    assert abs(grain - grain_total) < 0.05, f"Σ单军月粮 {grain} != calc_army_grain {grain_total}"


def test_route_military_units_carry_costs_and_match_route_row():
    """`route_military_summary(route).units` 带月饷/月粮，且逐军求和 == 该路行合计。"""
    s = _new_state()
    station = s.army_units[0].station
    m = route_military_summary(s, station)
    assert m["units"], "该路应有军队"
    for u in m["units"]:
        assert "monthly_pay" in u and "monthly_grain" in u, "单军行缺粮饷明细"
    pay = sum(float(u["monthly_pay"] or 0) for u in m["units"])
    grain = sum(float(u["monthly_grain"] or 0) for u in m["units"])
    assert abs(pay - float(m["summary"]["cash_month"] or 0)) < 0.05
    assert abs(grain - float(m["summary"]["grain_month"] or 0)) < 0.05


def test_unit_cost_readout_stays_consistent_on_unknown_branch():
    """未知兵种：读数不得炸，且必须与权威表（calc_army_* / branch_std）逐分不分岉。

    `branch_std` 对未知兵种回落轻步兵（现行权威行为，calc_army_cash/grain 同样如此）——
    本读数属于同一口径，故不得单方面“严于”权威表（那会让 Σ单军 != calc_army_*）。
    """
    s = _new_state()
    u = s.army_units[0]
    keep = dict(u.branches)
    try:
        u.branches = dict(keep)
        u.branches["不存在的兵种"] = 1000
        c = unit_cost_readout(u)
        assert c["monthly_pay"] is not None, "未知兵种不得让读数整条失败"
        pay = grain = 0.0
        for x in s.army_units:
            cc = unit_cost_readout(x)
            pay += float(cc["monthly_pay"] or 0)
            grain += float(cc["monthly_grain"])
        cash_total, _ = s.calc_army_cash()
        grain_total, _ = s.calc_army_grain()
        assert abs(pay - cash_total) < 0.05, "未知兵种下与 calc_army_cash 分叉"
        assert abs(grain - grain_total) < 0.05, "未知兵种下与 calc_army_grain 分叉"
    finally:
        u.branches = keep


def test_unit_cost_readout_is_read_only():
    """粮饷明细是只读派生：调用前后 army_units 逐字一致。"""
    s = _new_state()
    before = _fingerprint(s)
    for u in s.army_units:
        unit_cost_readout(u)
    assert _fingerprint(s) == before, "粮饷读数改动了 army_units"

