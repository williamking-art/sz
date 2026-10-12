# -*- coding: utf-8 -*-
"""M49 建筑经营闸门只读投影 —— 定向回归。

锁定：岗位需求复用既有 `song_job_cfg` 单点（不另立表）· 缺工乘数取**最短板** ·
**工价缺失 ⇒ wage_need/到位率 一律 None**（不臆造工价）· 付款池**三种并列不预选** ·
缺失≠0 · **零写入**。
"""

import copy
import types

import pytest

from core.domains.economy import wage_gate_readout as wg


def _state(buildings=None, pops=None, treasury=1000, routes=("路A",)):
    st = types.SimpleNamespace()
    st.treasury = treasury
    st.prefectures = {}
    for r in routes:
        st.prefectures[r] = {
            "buildings": buildings if buildings is not None else {},
            "pops": pops if pops is not None else {},
        }
    return st


@pytest.fixture
def jpl(monkeypatch):
    monkeypatch.setattr(wg, "_jobs_per_level",
                        lambda: {"工坊": {"工匠": 160}, "商铺": {"商人": 40}, "民居": {}})


# ------------------------------------------------------------------ 需求/供给
def test_route_job_demand_uses_single_source(jpl):
    st = _state(buildings={"工坊": {"lv": 2}, "商铺": 1, "民居": {"lv": 5}})
    assert wg.route_job_demand(st, "路A") == {"工匠": 320, "商人": 40}
    assert wg.route_job_demand(st, "路X") is None          # 路不存在
    assert wg.route_job_demand(_state(buildings=None), "路A") == {}   # 有路无建筑 ⇒ 空


def test_route_labor_supply():
    st = _state(pops={"工匠": {"size": 100}, "商人": {"size": 30}})
    assert wg.route_labor_supply(st, "路A") == {"工匠": 100, "商人": 30}
    assert wg.route_labor_supply(_state(pops=None), "路A") == {}


# ------------------------------------------------------------------ 闸门投影
def test_gate_takes_worst_ratio_and_wage_rate(monkeypatch, jpl):
    monkeypatch.setattr(wg, "wage_rate_for", lambda b, regime=None: 2.0)
    st = _state(buildings={"工坊": {"lv": 1}},          # 需 160 工匠
                pops={"工匠": {"size": 80}, "士绅": {"wealth": 100},
                      "商人": {"wealth": 100}})
    rep = wg.project_route_gate(st, "路A")
    assert rep["job_demand"] == {"工匠": 160}
    # 最短板：80/160 = 0.5
    assert rep["labor_multiplier_upper_bound"] == 0.5
    assert rep["wage_need"] == 320                       # 160 岗 × 2.0
    assert rep["wage_detail"]["工坊"] == {"jobs": 160, "rate": 2.0, "basis": "positions"}
    assert rep["pools"]["treasury"] == 1000
    assert abs(rep["cover_by_pool"]["treasury"] - 1.0) < 1e-9
    assert abs(rep["cover_by_pool"]["gentry_merchant"] - 200 / 320) < 1e-9
    assert rep["cover_by_pool"]["artisan"] is None       # 工匠 wealth 未登记 ⇒ 不可读


def test_gate_does_not_invent_wage_when_rate_missing(monkeypatch, jpl):
    monkeypatch.setattr(wg, "wage_rate_for", lambda b, regime=None: None)
    st = _state(buildings={"工坊": {"lv": 1}}, pops={"工匠": {"size": 999}})
    rep = wg.project_route_gate(st, "路A")
    assert rep["wage_need"] is None
    assert all(v is None for v in rep["cover_by_pool"].values())    # 不臆造到位率
    assert any("工价单点缺失" in r for r in rep["reasons"])


def test_survey_marks_labor_tight(monkeypatch, jpl):
    monkeypatch.setattr(wg, "wage_rate_for", lambda b, regime=None: 1.0)
    st = _state(buildings={"工坊": {"lv": 1}}, pops={"工匠": {"size": 10}})
    rep = wg.survey_wage_gate(st)
    assert rep["routes_with_jobs"] == 1
    assert rep["routes_labor_tight"][0][0] == "路A"
    assert rep["routes_labor_tight"][0][1] == pytest.approx(10 / 160)


def test_survey_no_prefectures():
    rep = wg.survey_wage_gate(types.SimpleNamespace())
    assert rep["routes"] == 0 and "缺失≠0" in rep["reason"]


# ------------------------------------------------------------------ 只读
def test_survey_is_readonly(jpl, monkeypatch):
    monkeypatch.setattr(wg, "wage_rate_for", lambda b, regime=None: 1.5)
    st = _state(buildings={"工坊": {"lv": 3}}, pops={"工匠": {"size": 100}})
    before = copy.deepcopy({"p": st.prefectures, "t": st.treasury})
    wg.survey_wage_gate(st)
    assert before == {"p": st.prefectures, "t": st.treasury}
