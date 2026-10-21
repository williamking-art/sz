# -*- coding: utf-8 -*-
"""M58 作坊产权落点候选盘点 —— 定向回归。

锁定：六个候选齐备 · 货主 id **复用既有词表** · 资金池一律走**既有单点**（不可读 ⇒ None+reason）·
**「作坊自持」被判违规**（`parallel_ledger_violation=True` + 改造条件）· 工资需求 `None` + reason
（不拿建筑口径硬套作坊）· 采购需求 Σ 既有 `recipe_cost`（缺价维 ⇒ 合计 None）· **零写入**。
"""

import copy
import types

import pytest

from core.domains.economy import owner_candidates_shadow as oc


def _state(workshops=None, treasury=1000, imperial=None, routes=("路A",), pops=None):
    st = types.SimpleNamespace()
    st.workshops = workshops if workshops is not None else {}
    st.treasury = treasury
    if imperial is not None:
        st.imperial_treasury = imperial
    st.prefectures = {}
    for r in routes:
        st.prefectures[r] = {"name": r, "pops": pops or {"士绅": {"wealth": 500},
                                                       "商人": {"wealth": 300}}}
    return st


def test_candidates_cover_expected_keys_and_forms():
    keys = [c["key"] for c in oc.CANDIDATES]
    assert keys == ["state_treasury", "imperial", "pop_gentry", "pop_merchant",
                    "local_route", "workshop_self"]
    forms = {c["key"]: c["owner_id_form"] for c in oc.CANDIDATES}
    assert forms["pop_gentry"] == "pop:<路>:士绅"          # **复用既有词表**
    assert forms["local_route"] == "local:<路>"


def test_workshop_self_is_flagged_as_violation():
    rep = oc.survey_owner_candidates(_state())
    assert "workshop_self" in rep["violations"]
    row = next(r for r in rep["candidates"] if r["key"] == "workshop_self")
    assert row["parallel_ledger_violation"] is True
    assert "§3-1" in row["note"] and "改造条件" in row["note"]
    assert row["pool"] is None and "不敢臆造" in row["pool_reason"]


# ------------------------------------------------------------------ 资金池（走既有单点）
def test_pools_read_from_existing_sources():
    st = _state(treasury=1234, imperial=99)
    assert oc.pool_of(st, "state_treasury")["value"] == 1234
    assert oc.pool_of(st, "imperial")["value"] == 99
    g = oc.pool_of(st, "pop_gentry")
    assert g["value"] == 500 and "pop_get" in g["source"]
    assert oc.pool_of(st, "pop_merchant")["value"] == 300


def test_pool_missing_reports_none_and_reason():
    st = _state(treasury=None)
    r = oc.pool_of(st, "state_treasury")
    assert r["value"] is None and "缺失≠0" in r["reason"]
    r2 = oc.pool_of(st, "imperial")
    assert r2["value"] is None and r2["reason"]
    r3 = oc.pool_of(st, "不存在的候选")
    assert r3["value"] is None and "未知候选" in r3["reason"]


def test_local_route_pool_uses_bridge():
    st = _state()
    r = oc.pool_of(st, "local_route")
    # 该局未下沉地方府库 ⇒ None + reason（不回落 0）
    assert r["value"] is None and "地方府库" in (r["reason"] or "")
    assert "local_treasury_bridge" in r["source"]


# ------------------------------------------------------------------ 需求
def test_procure_need_sums_recipe_cost_or_none(monkeypatch):
    from core.domains.economy import workshop_fund_shadow as wfs
    monkeypatch.setattr(wfs, "recipe_cost",
                        lambda state, wid: {"cost": 100 if wid != "坏坊" else None})
    st = _state(workshops={"甲坊": {}, "乙坊": {}, "坏坊": {}})
    rep = oc.procure_need(st)
    assert rep["value"] is None and rep["unreadable"] == ["坏坊"]      # 缺价维 ⇒ 合计不可定义
    st2 = _state(workshops={"甲坊": {}, "乙坊": {}})
    assert oc.procure_need(st2)["value"] == 200


def test_wage_need_sums_table_or_none_for_unknown():
    # 空作坊 ⇒ 合计 0（真实空集，不是缺失）
    assert oc.wage_need(_state())["value"] == 0
    st = _state(workshops={"酒坊_路A_0": {"name": "酒坊"},
                           "麻坊_路A_1": {"name": "麻坊"}})
    w = oc.wage_need(st)
    assert w["value"] == 120_000 + 90_000, w
    st2 = _state(workshops={"谜之坊_路A_0": {"name": "谜之坊"}})
    w2 = oc.wage_need(st2)
    assert w2["value"] is None and w2["unreadable"] == ["谜之坊_路A_0"]


def test_affordability_none_when_unreadable():
    assert oc.affordability(None, 100) is None
    assert oc.affordability(50, None) is None
    assert oc.affordability(50, 0) is None
    assert oc.affordability(50, 100) == 0.5
    assert oc.affordability(500, 100) == 1.0


# ------------------------------------------------------------------ 汇总 + 只读
def test_survey_is_readonly_and_has_no_default_pick():
    st = _state(treasury=10_000)
    before = copy.deepcopy(st.__dict__)
    rep = oc.survey_owner_candidates(st)
    assert rep["workshops"] == 0
    assert "不预选" in rep["note"]
    assert copy.deepcopy(st.__dict__) == before                      # **零写入**
