# -*- coding: utf-8 -*-
"""M80 P1 试点纵向链条**只读读数**（绸：丝→绸）—— 定向回归。

锁定：① 原料/成品取**治所真账**（Σ治所×阶层）；② 作坊按**所属路**归集（M47/M66），
**在岗如实 `undefined`**（M67：作坊岗位无权威来源；作坊不在 `buildings` 里）；③ 需求走 M74 口径；
④ 缺口＝需求−成品（**夹 0**）；⑤ 缺失 ⇒ `None`（**不是 0**）；⑥ 只读。
"""

import copy
import types

from core.domains.economy import p1_pilot_chain as pc


def _state(seat_goods=None, workshops=None, seats_pops=None):
    st = types.SimpleNamespace()
    seats = {"路A|甲": {"pops": seats_pops or {"工匠": {"size": 100, "wealth": 1000}},
                        "buildings": {}}}
    st.prefectures = {"路A": {"name": "路A", "seats": seats}}
    st.resources = {}
    st.workshops = workshops if workshops is not None else {
        "丝坊_路A_0": {"name": "丝坊", "active": True, "owner": "pop:路A:商人",
                     "recipe": {"丝": 10000}, "yield": 8000}}
    return st


def test_chain_reports_raw_and_finished_from_seat_truth(monkeypatch):
    st = _state()
    monkeypatch.setattr(pc, "_seat_stock_by_route", lambda state: {"路A": {"丝": 50000, "绸": 9000}})
    monkeypatch.setattr(pc, "_route_demand", lambda state, r, d: 20000.0)
    rep = pc.chain_of_route(st, "路A")
    assert rep["raw_input"] == 50000 and rep["finished_output"] == 9000
    assert rep["demand"] == 20000 and rep["gap"] == 11000        # 需求 20000 − 成品 9000
    assert rep["workshops"]["count"] == 1
    assert rep["theoretical_output_cap_per_round"] == 8000      # Σ yield


def test_workshop_jobs_are_undefined_and_explained(monkeypatch):
    st = _state()
    monkeypatch.setattr(pc, "_seat_stock_by_route", lambda state: {"路A": {"丝": 1, "绸": 1}})
    monkeypatch.setattr(pc, "_route_demand", lambda state, r, d: 0.0)
    row = pc.chain_of_route(st, "路A")["workshops"]["rows"][0]
    assert row["jobs"] is None and "无权威来源" in row["jobs_reason"]
    assert "不按人口均分" in row["jobs_reason"]


def test_gap_is_clamped_at_zero(monkeypatch):
    st = _state()
    monkeypatch.setattr(pc, "_seat_stock_by_route", lambda state: {"路A": {"丝": 1, "绸": 99999}})
    monkeypatch.setattr(pc, "_route_demand", lambda state, r, d: 10.0)
    assert pc.chain_of_route(st, "路A")["gap"] == 0


def test_missing_data_is_none_not_zero(monkeypatch):
    st = _state()
    monkeypatch.setattr(pc, "_seat_stock_by_route", lambda state: None)   # 真账不可读
    monkeypatch.setattr(pc, "_route_demand", lambda state, r, d: None)
    rep = pc.chain_of_route(st, "路A")
    assert rep["raw_input"] is None and rep["finished_output"] is None
    assert rep["demand"] is None and rep["gap"] is None
    assert set(rep["undefined_fields"]) >= {"raw_input", "finished_output", "demand"}


def test_workshops_are_filtered_by_route_and_type(monkeypatch):
    st = _state(workshops={"丝坊_路A_0": {"recipe": {"丝": 1}, "yield": 1, "active": True},
                           "丝坊_路B_0": {"recipe": {"丝": 1}, "yield": 1, "active": True},
                           "麻坊_路A_0": {"recipe": {"麻": 1}, "yield": 1, "active": True}})
    monkeypatch.setattr(pc, "_seat_stock_by_route", lambda state: {"路A": {}, "路B": {}})
    monkeypatch.setattr(pc, "_route_demand", lambda state, r, d: 0.0)
    a = pc.chain_of_route(st, "路A")["workshops"]
    assert a["count"] == 1 and "丝坊_路A_0" in a["owners"] or a["count"] == 1


def test_real_game_survey_runs_and_is_readonly(monkeypatch):
    from core import commands
    s = commands.new_game()
    before = copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()})
    rep = pc.survey_pilot_chain(s)
    assert rep["pilot"]["output_dim"] == "绸"
    assert isinstance(rep["totals"]["workshops"], int)
    assert copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()}) == before
