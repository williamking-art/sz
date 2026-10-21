# -*- coding: utf-8 -*-
"""M51 工坊经营资金影子预算（主线 D 第一切片） —— 定向回归。

锁定：**无 owner ⇒ `undefined`**（不臆造货主）· 作坊**不在岗位表** ⇒ 工资义务 `None` + reason
（不拿建筑岗位数硬套）· 采购预算**缺基准价 ⇒ `None` + 列出缺价维** · 地点由键内路名单点解析 ·
候选资金**三档并列不预选** · 规格七项逐项有值或 `None`（不做"缺就跳过"）· **零写入 + M_ALL 守恒**。
"""

import copy
import types

import pytest

from core.domains.economy import workshop_fund_shadow as wfs


def _state(workshops=None):
    st = types.SimpleNamespace()
    st.workshops = workshops if workshops is not None else {}
    st.treasury = 1000
    st.prefectures = {"路A": {"pops": {"工匠": {"wealth": 100}, "士绅": {"wealth": 50}}}}
    return st


# ------------------------------------------------------------------ 货主
def test_owner_undefined_when_no_property_model():
    st = _state({"麻坊_路A_1": {"name": "麻坊", "recipe": {"麻": 10}, "active": True}})
    own = wfs.owner_of(st, "麻坊_路A_1")
    assert own["defined"] is False and own["owner"] is None
    assert "产权模型未实现" in own["reason"]
    assert wfs.owner_of(st, "不存在")["reason"] == "作坊不存在"


def test_owner_read_when_field_present():
    st = _state({"麻坊_路A_1": {"name": "麻坊", "owner": "pop:路A:士绅", "active": True}})
    own = wfs.owner_of(st, "麻坊_路A_1")
    assert own["defined"] is True and own["owner"] == "pop:路A:士绅"


# ------------------------------------------------------------------ 地点 / 工资 / 采购
def test_route_from_key():
    st = _state({"麻坊_路A_1": {"name": "麻坊", "active": True}})
    assert wfs.workshop_route(st, "麻坊_路A_1") == "路A"
    assert wfs.workshop_route(st, "无名坊_9") is None       # 判不出 ⇒ None（不臆造地点）


def test_wage_obligation_from_workshop_table_or_none():
    st = _state({"酒坊_路A_2": {"name": "酒坊", "active": True}})
    w = wfs.wage_obligation(st, "酒坊_路A_2")
    # 2026-10-21：显式作坊岗位/工价表（玩法设定）已登记 酒坊 ⇒ 工资义务可算
    assert w["jobs"] == 80_000 and w["obligation"] == 120_000
    assert w["rate"] == 1.5 and w["reason"] is None
    # 未登记类型仍按缺失处理（不拿来历不明的岗数硬套）
    st2 = _state({"谜之坊_路A_1": {"name": "谜之坊", "active": True}})
    w2 = wfs.wage_obligation(st2, "谜之坊_路A_1")
    assert w2["jobs"] is None and w2["obligation"] is None
    assert "未登记该类型" in w2["reason"]


def test_recipe_cost_reports_missing_price(monkeypatch):
    monkeypatch.setattr(wfs, "_num", wfs._num)
    st = _state({"麻坊_路A_1": {"name": "麻坊", "recipe": {"麻": 10, "谜之料": 2},
                               "active": True}})
    got = wfs.recipe_cost(st, "麻坊_路A_1")
    assert got["cost"] is None                               # 有缺价维 ⇒ 整项不可定义
    assert "谜之料" in got["missing_price"]
    assert got["dims"]["麻"]["qty"] == 10


# ------------------------------------------------------------------ 影子读数与守恒
def test_workshop_shadow_lists_missing_and_status():
    st = _state({"麻坊_路A_1": {"name": "麻坊", "recipe": {"麻": 10}, "active": True}})
    rep = wfs.workshop_shadow(st, "麻坊_路A_1")
    assert rep["status"] == "undefined"                      # 无 owner ⇒ 未定义（wage 已可读）
    # `麻` 有基准价 ⇒ 采购预算**可算**；工资表已登记 麻坊 ⇒ 不再缺 wage
    assert set(rep["missing"]) == {"owner"}
    assert rep["purchase"]["cost"] is not None
    assert rep["location"] == "路A"
    # 规格七项逐项存在（值或 None），第二轮项明确列出
    assert all(k in rep for k in ("owner", "location", "wage", "purchase"))
    assert "sales" in rep["not_in_this_batch"]


def test_workshop_shadow_marks_purchase_missing_when_price_absent():
    st = _state({"麻坊_路A_1": {"name": "麻坊", "recipe": {"谜之料": 3}, "active": True}})
    rep = wfs.workshop_shadow(st, "麻坊_路A_1")
    assert rep["purchase"]["cost"] is None
    assert "purchase" in rep["missing"]


def test_survey_counts_and_conservation():
    st = _state({"麻坊_路A_1": {"name": "麻坊", "recipe": {"麻": 10}, "active": True},
                 "丝坊_路B_1": {"name": "丝坊", "recipe": {"丝": 5}, "active": True}})
    before = copy.deepcopy(st.__dict__)
    rep = wfs.survey_workshop_fund_shadow(st)
    assert rep["workshops"] == 2 and rep["undefined_no_owner"] == 2
    assert rep["conservation"]["ok"] is True                 # 只读 ⇒ M_ALL 不变
    assert copy.deepcopy(st.__dict__) == before              # **零写入**
    # 候选资金三档并列（不预选）
    assert set(rep["funding_source_candidates"]) == {"treasury", "artisan", "gentry_merchant"}
    assert rep["funding_source_candidates"]["artisan"] == 100
    assert rep["funding_source_candidates"]["gentry_merchant"] == 50


def test_survey_without_workshops():
    st = types.SimpleNamespace()
    assert wfs.survey_workshop_fund_shadow(st)["workshops"] == 0
