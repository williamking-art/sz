# -*- coding: utf-8 -*-
"""M64a 资源存量桥（**先桥**步）—— 定向回归。

锁定：**未下沉 ⇒ 所有写口返回 `None`**（调用方保留原写法 ⇒ **零行为变化**）·
已下沉 ⇒ 写**治所真账**并把全国池刷成 **Σ已下沉路** · `stock_take` 按持仓占比 + 逐个夹紧 + **夹紧留痕** ·
`sink_route_resource_stock` **幂等**（已下沉不覆盖）· `cap` 不被动 · **缺失≠0** · 读数只读。
"""

import copy
import types

import pytest

from core.foundation.ledger import resource_stock_bridge as rsb


def _pdata_sunk(dim="木", seat="A|甲", v=100, extra=None):
    seats = {seat: {"resources": {dim: v}}}
    if extra:
        seats.update(extra)
    return {"name": "路A", "seats": seats, "resources": {dim: {"stock": v, "cap": 999}}}


def _state(pdata=None, dim="木", national=0):
    st = types.SimpleNamespace()
    st.prefectures = {"路A": pdata} if pdata is not None else {"路A": {"name": "路A"}}
    st.resources = {dim: {"stock": national, "cap": 999}}
    return st


def _state_sunk(dim="木", seat="A|甲", v=100, national=100):
    return _state(_pdata_sunk(dim, seat, v), dim, national)


# ------------------------------------------------------------------ ① 零接管契约
def test_unsunk_all_ports_return_none():
    """**未下沉 ⇒ 一律 `None`** ⇒ 调用方保留原写法（这就是"零行为变化"的机制保证）。"""
    st = _state()                                   # 无 seats ⇒ 未下沉
    assert rsb.is_sunk(st.prefectures["路A"]) is False
    assert rsb.stock_add(st, "木", 10, route="路A") is None
    assert rsb.stock_set(st, "木", 10, route="路A") is None
    assert rsb.stock_take(st, "木", 10, route="路A") is None
    assert rsb.stock_get(st, "木", route="路A") is None
    # 无 route（全国口径操作）⇒ 同样不接管
    assert rsb.stock_add(st, "木", 10) is None
    assert rsb.stock_add(st, "木", 10, route="不存在的路") is None


def test_national_pool_not_touched_when_unsunk():
    st = _state(national=7)
    before = copy.deepcopy(st.resources)
    rsb.stock_add(st, "木", 10, route="路A")
    rsb.stock_take(st, "木", 5, route="路A")
    assert st.resources == before                   # 桥未接管 ⇒ 全国池一字未动


# ------------------------------------------------------------------ ② 已下沉 ⇒ 走治所真账
def test_add_and_set_write_seat_truth_and_refresh_national():
    st = _state_sunk(v=100, national=100)
    assert rsb.stock_add(st, "木", 50, route="路A", seat_id="A|甲") == 150
    assert rsb.seat_stock(st.prefectures["路A"], "A|甲", "木") == 150
    assert st.resources["木"]["stock"] == 150        # 全国池 = Σ已下沉路
    assert st.resources["木"]["cap"] == 999          # **cap 不被动**

    assert rsb.stock_set(st, "木", 20, route="路A", seat_id="A|甲") == 20
    assert st.resources["木"]["stock"] == 20


def test_add_clamps_at_zero_and_records():
    st = _state_sunk(v=5, national=5)
    rsb._CLAMP_EVENTS.clear()
    assert rsb.stock_add(st, "木", -50, route="路A", seat_id="A|甲") == 0
    assert rsb.seat_stock(st.prefectures["路A"], "A|甲", "木") == 0
    assert any(e["dim"] == "木" for e in rsb.clamp_events())     # **夹紧留痕**


def test_take_is_proportional_and_clamped():
    pdata = _pdata_sunk("木", "A|甲", 60, extra={"A|乙": {"resources": {"木": 40}}})
    st = _state(pdata, "木", 100)
    rsb._CLAMP_EVENTS.clear()
    got = rsb.stock_take(st, "木", 50, route="路A")
    assert got == 50
    a = rsb.seat_stock(pdata, "A|甲", "木")
    b = rsb.seat_stock(pdata, "A|乙", "木")
    assert a + b == 50 and a >= 0 and b >= 0          # Σ 精确、逐个非负
    assert st.resources["木"]["stock"] == 50          # Σ治所 → 全国池
    # 取超过存量 ⇒ 全取 + 留痕
    got2 = rsb.stock_take(st, "木", 999, route="路A")
    assert got2 == 50 and rsb.clamp_events()


def test_get_reads_seat_sum():
    st = _state_sunk(v=33, national=33)
    assert rsb.stock_get(st, "木", route="路A") == 33
    assert rsb.stock_get(st, "木") is None            # 无路 ⇒ 不接管，调用方按原口径读


# ------------------------------------------------------------------ ③ 幂等下沉（本批不调用，但要有单测）
def test_sink_is_idempotent_and_capital_carried():
    pdata = {"name": "路A", "seats": {"A|甲": {"pops": {}}, "A|乙": {"pops": {}}},
             "resources": {"木": {"stock": 77, "cap": 999}}}
    assert rsb.sink_route_resource_stock(pdata, "路A", "木") is True
    assert rsb.is_sunk(pdata) is True
    total = rsb.route_stock_total(pdata, "木")
    assert total == 77                                # **首府承载**：全量落一个治所
    assert rsb.sink_route_resource_stock(pdata, "路A", "木") is False   # 已下沉 ⇒ 不覆盖


# ------------------------------------------------------------------ ④ 对账读数
def test_survey_reports_counts_and_mismatch():
    st = _state_sunk(v=10, national=10)
    st.prefectures["路B"] = {"name": "路B"}            # 未下沉路
    rep = rsb.survey_resource_stock(st)
    assert rep["sunk_routes"] == 1 and rep["unsunk_routes"] == 1
    st.resources["木"]["stock"] = 999                  # 人为制造镜像失配
    assert rsb.survey_resource_stock(st)["mismatch_count"] >= 1


def test_real_new_game_is_unsunk_so_zero_change():
    """真实新局：**20 路全未下沉** ⇒ 所有写口不接管 ⇒ 与改造前行为一致。"""
    from core import commands
    s = commands.new_game()
    unsunk = [r for r, p in s.prefectures.items() if not rsb.is_sunk(p)]
    assert len(unsunk) == 20
    assert rsb.stock_add(s, "木", 1, route=next(iter(s.prefectures))) is None
