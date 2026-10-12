# -*- coding: utf-8 -*-
"""M42a 逐维流量账（登记式测量仪器）—— 定向回归。

锁定：按月分桶（**不改编排器**）· in/out 与 by_reason 累加 · 只记**实际发生量**（非正不记）·
取不到月序落 `unknown` 桶（**不假装落在某月**）· 无登记 ⇒ 该维缺席（**不是 0**）·
`residual_for_custody` 闭合判定（flows 没给 ⇒ unclosed）· **登记不抛**（测量仪器不得中断结算）。
"""

import types

import pytest

from core.domains.economy import stock_flow as sf
from core.domains.economy import stock_identity as si


def _state(flow=None):
    st = types.SimpleNamespace()
    # 流量账容器＝**独立属性** `state.stock_flow`（不放进 statistics：
    # 后者被财政隔离契约整表比对，见模块常量注释）
    if flow is not None:
        st.stock_flow = flow
    st.month = 3
    st.turn = 0
    return st


@pytest.fixture
def m7(monkeypatch):
    monkeypatch.setattr(sf, "current_month", lambda state: 7)
    return 7


# ------------------------------------------------------------------ 1. 登记与分桶
def test_record_in_out_by_month(m7):
    s = _state()
    assert sf.record_in(s, "木", 100, reason="produce") == 100
    assert sf.record_in(s, "木", 50, reason="procure_buy") == 50
    assert sf.record_out(s, "木", 30, reason="consume") == 30
    f = sf.flows_for(s)
    assert f["木"]["in"] == 150 and f["木"]["out"] == 30 and f["木"]["net"] == 120
    assert f["木"]["by_reason"]["in:produce"] == 100
    assert sf.flows_delta(s) == {"木": 120}
    # 分桶形态：{月序: {custody: {dim: {...}}}}（custody 默认全国仓）
    assert sf.flows_container(s, create=True)["7"][sf.CUSTODY_NATIONAL]["木"]["in"] == 150


def test_records_are_month_isolated(m7):
    s = _state()
    sf.record_in(s, "木", 10, reason="produce")
    sf.flows_container(s, create=True)["8"] = {sf.CUSTODY_NATIONAL: {"木": {"in": 5, "out": 1, "by_reason": {}}}}
    assert sf.flows_delta(s, month=7) == {"木": 10}
    assert sf.flows_delta(s, month=8) == {"木": 4}
    assert sf.flows_for(s, month=9) == {}                 # 未登记月份 ⇒ 空（不是 0）


def test_custody_isolation(m7):
    """**custody 分列**：全国仓与 POP 侧互不污染（否则两条链的残差都算不准）。"""
    s = _state()
    sf.record_in(s, "木", 100, reason="produce")                              # 默认＝全国仓
    sf.record_in(s, "木", 30, reason="produce_pop", custody=sf.CUSTODY_POP)
    sf.record_out(s, "木", 10, reason="consume", custody=sf.CUSTODY_POP)
    assert sf.flows_delta(s) == {"木": 100}
    assert sf.flows_delta(s, custody=sf.CUSTODY_POP) == {"木": 20}
    assert sf.cumulative_flows(s) == {"木": 100}
    assert sf.cumulative_flows(s, custody=sf.CUSTODY_POP) == {"木": 20}


def test_nonpositive_and_bad_values_are_ignored(m7):
    s = _state()
    assert sf.record_in(s, "木", 0) == 0
    assert sf.record_out(s, "木", -5) == 0
    assert sf.record_in(s, "木", "abc") == 0
    assert sf.flows_for(s) == {}                          # 一条都没登记


def test_unknown_month_bucket_when_unreadable(monkeypatch):
    monkeypatch.setattr(sf, "current_month", lambda state: None)
    s = _state()
    sf.record_in(s, "石", 3, reason="produce")
    assert "unknown" in sf.flows_container(s)            # **不假装**落在某月


def test_record_does_not_raise_on_broken_state(monkeypatch):
    """测量仪器**不得中断结算**：state 不可写 ⇒ 返回 0 且不抛。"""
    class _Boom:
        def __setattr__(self, k, v):
            raise RuntimeError("state 不可写")
    monkeypatch.setattr(sf, "current_month", lambda state: 1)
    assert sf.record_in(_Boom(), "木", 5) == 0


# ------------------------------------------------------------------ 2. 覆盖率
def test_coverage(m7):
    s = _state()
    assert sf.coverage(s)["registered"] is False
    sf.record_in(s, "木", 4, reason="produce")
    sf.record_out(s, "木", 1, reason="consume")
    cov = sf.coverage(s)
    assert cov["dims"] == ["木"] and cov["dim_count"] == 1
    assert cov["reasons"] == {"in:produce": 4, "out:consume": 1}
    # ⚠️ 当前月之外还有登记时，`all_months=True` 才看得到（默认只看当前月 ⇒ 会显示 0）
    sf.flows_container(s, create=True)["9"] = {sf.CUSTODY_NATIONAL: {"石": {"in": 3, "out": 0,
                                                                           "by_reason": {"in:produce": 3}}}}
    assert sf.coverage(s, month=8)["dim_count"] == 0            # 第 8 月无登记
    am = sf.coverage(s, all_months=True)
    assert am["all_months"] is True
    assert set(am["dims"]) == {"石", "木"} and am["reasons"]["in:produce"] == 7


# ------------------------------------------------------------------ 3. 单 custody 残差
def _snap(res):
    return {"by_custody": {"pop_goods": {}, "national_resources": res,
                           "in_transit": {}, "pending_stock": {}}}


def test_residual_for_custody_closes_with_flows():
    prev, curr = _snap({}), _snap({"木": 100.0})
    rep = sf.residual_for_custody(prev, curr, "national_resources", flows={"木": 100})
    assert rep["residual"]["木"] == 0.0 and rep["ok"] is True


def test_residual_for_custody_unclosed_without_flows():
    prev, curr = _snap({}), _snap({"木": 100.0})
    rep = sf.residual_for_custody(prev, curr, "national_resources")
    assert rep["residual"]["木"] is None
    assert rep["unclosed"] == ["木"] and rep["ok"] is False


def test_residual_for_custody_flags_gap():
    prev, curr = _snap({}), _snap({"木": 100.0})
    rep = sf.residual_for_custody(prev, curr, "national_resources", flows={"木": 60})
    assert rep["nonzero"] == ["木"] and rep["ok"] is False
