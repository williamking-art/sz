# -*- coding: utf-8 -*-
"""M52 家计影子 + 经济归属守恒读数 —— 定向回归。

锁定：**任一分项不可读 ⇒ 家计 `None`**（不缺项回落 0）· 分项可读则**单列**且明标"不是家计" ·
**等第阈值必须由调用方给**（缺省 ⇒ `None` + reason；**不臆造阈值**）· 非法阈值**拒绝**（ValueError）·
五等判据与文档一致（≥阈值4 上户 … <阈值1 无业）· 归属守恒逐 `(路,类,字段)` 比对 Σ子池 vs 父 POP ·
**零写入**。
"""

import copy
import types

import pytest

from core.domains.economy import livelihood_shadow as ls


def _state(pops=None, aff=None):
    st = types.SimpleNamespace()
    row = {"wealth": 100, "grain": 10}
    if aff is not None:
        row["economic_affiliation"] = aff
    st.prefectures = {"路A": {"pops": {"农": row, "工匠": {"wealth": 5}}}}
    if pops is not None:
        st.prefectures = {"路A": {"pops": pops}}
    return st


# ------------------------------------------------------------------ 等第（阈值不臆造）
def test_tier_none_without_thresholds():
    got = ls.tier_of(1000, None)
    assert got["tier"] is None and "阈值未给" in got["reason"]


def test_tier_boundaries_follow_doc():
    th = (10, 100, 1000, 10000)
    assert ls.tier_of(10000, th)["tier"] == "上户"
    assert ls.tier_of(9999, th)["tier"] == "中户"
    assert ls.tier_of(1000, th)["tier"] == "中户"
    assert ls.tier_of(999, th)["tier"] == "下户"
    assert ls.tier_of(100, th)["tier"] == "下户"
    assert ls.tier_of(99, th)["tier"] == "贫民"
    assert ls.tier_of(10, th)["tier"] == "贫民"
    assert ls.tier_of(9, th)["tier"] == "无业/逃户"


def test_tier_rejects_invalid_thresholds():
    with pytest.raises(ValueError):
        ls.tier_of(1, (1, 2, 3))                       # 长度≠4
    with pytest.raises(ValueError):
        ls.tier_of(1, (3, 2, 1, 0))                    # 非升序
    with pytest.raises(ValueError):
        ls.tier_of(1, (1, 2, 3, "x"))                  # 非数值


def test_tier_none_when_value_none():
    got = ls.tier_of(None, (1, 2, 3, 4))
    assert got["tier"] is None and "缺失≠0" in got["reason"]


# ------------------------------------------------------------------ 家计影子
def test_livelihood_value_none_with_missing_items():
    st = _state()
    rep = ls.livelihood(st, "路A", "农")
    assert rep["value"] is None                        # 生业应收/支出侧不可读 ⇒ 家计 None
    assert "operating_receivable" in rep["missing"]
    assert set(rep["missing"]) >= {"operating_receivable", "food", "rent", "tax", "corvee"}
    # 可读分项**单列**，并明标不是家计
    assert rep["partial_income_sum"] is not None
    assert "不是家计" in rep["partial_note"]
    assert rep["tier"] is None and rep["tier_reason"] is not None


def test_income_items_reports_reasons():
    st = _state()
    inc = ls.income_items(st, "路A", "农")
    assert inc["items"]["wealth"] == 100
    assert inc["items"]["grain_value"] is not None
    assert inc["items"]["operating_receivable"] is None
    assert "无权威单点" in inc["reason"]


def test_missing_pop_row_is_handled():
    st = _state()
    inc = ls.income_items(st, "路X", "农")
    assert inc["items"]["wealth"] is None and "缺失≠0" in inc["reason"]


# ------------------------------------------------------------------ 归属守恒
def test_affiliation_conservation_ok_and_mismatch():
    # 子池须覆盖父 POP 的**全部** AFFILIATION_FIELDS 里"父侧有值"的字段（份额和 == 父 POP）
    aff = {"自耕": {"wealth": 60, "size": 6, "grain": 6},
           "佃耕": {"wealth": 40, "size": 4, "grain": 4}}
    ok = types.SimpleNamespace()
    ok.prefectures = {"路A": {"pops": {"农": {"wealth": 100, "size": 10, "grain": 10,
                                             "economic_affiliation": aff}}}}
    rep = ls.affiliation_conservation(ok)
    assert rep["ok"] is True and rep["classes_with_affiliation"] == 1

    bad = types.SimpleNamespace()
    bad.prefectures = {"路A": {"pops": {"农": {"wealth": 100, "size": 10, "grain": 10,
                                              "economic_affiliation": {"自耕": {"wealth": 60}}}}}}
    rep2 = ls.affiliation_conservation(bad)
    assert rep2["ok"] is False
    assert any(m["field"] == "wealth" and m["parent"] == 100 for m in rep2["mismatches"])


def test_affiliation_absent_reports_undefined():
    rep = ls.affiliation_conservation(_state())
    assert rep["ok"] is None and "未登记归属" in rep["reason"]


# ------------------------------------------------------------------ 汇总 + 只读
def test_survey_is_readonly_and_counts():
    st = _state(aff={"自耕": {"wealth": 60}, "佃耕": {"wealth": 40}})
    st.prefectures["路A"]["pops"]["农"]["wealth"] = 100
    before = copy.deepcopy(st.__dict__)
    rep = ls.survey_livelihood_shadow(st)
    assert rep["pop_rows"] == 2
    assert rep["livelihood_computable"] == 0           # 分项不全 ⇒ 一个都算不出（如实）
    assert rep["tier_known"] == 0                      # 未给阈值 ⇒ 等第一律未定义
    assert copy.deepcopy(st.__dict__) == before
