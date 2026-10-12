# -*- coding: utf-8 -*-
"""M41b 库存/货币恒等式只读投影 —— 定向回归。

锁定：按保管方分列 · **待定货不并入合计**（裁定 6.33）· 缺失≠0（不可读 ⇒ None + warning）·
在途读不出 ⇒ None（不冒充「没有在途」）· 货币残差口径（复用 money.snapshot，不重算公式）·
**零写入**（调用前后 state 深比较不变）。
"""

import copy
import types

import pytest

from core.domains.economy import stock_identity as si


def _state(prefs=None, resources=None, pending=None):
    st = types.SimpleNamespace()
    st.prefectures = prefs if prefs is not None else {}
    st.resources = resources if resources is not None else {}
    if pending is not None:
        st.pending_stock = pending
    return st


# ------------------------------------------------------------------ 1. 各保管方
def test_pop_goods_handles_seat_bucket_shape():
    """`goods` 的**州府桶形态** `{治所: {dim: n}}` 必须被摊平计入（否则读数恒 0）。

    2026-10-13 实测教训：只看数值会把下沉档的州府桶**整片跳过** ⇒ 恒等式假"闭合"。
    """
    prefs = {
        "路A": {"pops": {"工匠": {"goods": {"路A|甲": {"绸": 5}, "路A|乙": {"绸": 2, "布": 1}}}}},
        "路B": {"pops": {"工匠": {"goods": {"绸": 3}}}},          # 扁平形态也支持
    }
    assert si.pop_goods_by_dim(_state(prefs)) == {"绸": 10.0, "布": 1.0}


def test_pop_goods_by_dim_sums_across_routes_and_classes():
    prefs = {
        "路A": {"pops": {"工匠": {"goods": {"绸": 5, "布": 2}},
                          "商人": {"goods": {"绸": 1}}}},
        "路B": {"pops": {"工匠": {"goods": {"绸": 4}}}},
    }
    assert si.pop_goods_by_dim(_state(prefs)) == {"绸": 10.0, "布": 2.0}
    # **无 `prefectures` 属性** ⇒ None（缺失≠0）；注意 `SimpleNamespace()` 才是"没有属性"，
    # `_state(None)` 给的是空 dict（那是"有容器但为空"）
    assert si.pop_goods_by_dim(types.SimpleNamespace()) is None
    # 不可读的槽被跳过，不炸、不臆造 0
    bad = {"路C": {"pops": {"农": {"goods": None}, "士绅": {}}}}
    assert si.pop_goods_by_dim(_state(bad)) == {}


def test_national_resources_accepts_dict_or_scalar_cell():
    res = {"木": {"stock": 100, "cap": 200}, "石": 30}
    assert si.national_resources_by_dim(_state(resources=res)) == {"木": 100.0, "石": 30.0}
    assert si.national_resources_by_dim(types.SimpleNamespace()) is None


def test_in_transit_by_dim(monkeypatch):
    import core.transport as tp
    monkeypatch.setattr(tp, "in_transit",
                        lambda state: [{"qty": {"木": 5}}, {"qty": {"木": 2, "石": 1}}])
    assert si.in_transit_by_dim(_state()) == {"木": 7.0, "石": 1.0}

    def _boom(state):
        raise RuntimeError("transport 坏了")
    monkeypatch.setattr(tp, "in_transit", _boom)
    assert si.in_transit_by_dim(_state()) is None             # 不可用 ⇒ None（不冒充无在途）


def test_pending_stock_separate_and_optional():
    assert si.pending_stock_by_dim(_state()) is None          # 无该属性 ⇒ None
    assert si.pending_stock_by_dim(_state(pending={"木": 9})) == {"木": 9.0}


# ------------------------------------------------------------------ 2. 快照与合计
def test_snapshot_totals_exclude_pending(monkeypatch):
    import core.transport as tp
    monkeypatch.setattr(tp, "in_transit", lambda state: [{"qty": {"木": 5}}])
    st = _state(
        prefs={"路A": {"pops": {"工匠": {"goods": {"木": 10}}}}},
        resources={"木": {"stock": 100}},
        pending={"木": 999},                                   # 待定：**不得并入 totals**
    )
    snap = si.stock_snapshot(st)
    assert snap["all_readable"] is True
    assert snap["totals"]["木"] == 115.0                       # 10 + 100 + 5
    assert snap["by_custody"]["pending_stock"] == {"木": 999.0}
    assert snap["by_custody"]["pop_goods"] == {"木": 10.0}
    assert "不并入" in snap["note"]


def test_snapshot_totals_none_when_any_custody_unreadable(monkeypatch):
    import core.transport as tp
    monkeypatch.setattr(tp, "in_transit", lambda state: None)  # 在途不可读
    st = _state(prefs={"路A": {"pops": {"工匠": {"goods": {"木": 1}}}}},
                resources={"木": {"stock": 1}})
    snap = si.stock_snapshot(st)
    assert snap["all_readable"] is False
    assert snap["totals"]["木"] is None                        # 缺失≠0
    assert any("in_transit" in w for w in snap["warnings"])


# ------------------------------------------------------------------ 3. 货币（真实 state）
def test_money_identity_on_real_new_game():
    """复用既有单点：残差必须为 0。

    ⚠️ 实测事实：`money.snapshot` 并**不**同时提供 m0–m3 四层（本机 `m1` 恒为 `None`）⇒
    本用例只断言**确实存在**的层（`m0`）与 `M_ALL`，不对缺层臆断。
    """
    from core import commands
    s = commands.new_game()
    mon = si.money_identity(s)
    assert mon["available"] is True
    assert isinstance(mon["m_all"], (int, float))
    assert mon["residual"] is not None and abs(mon["residual"]) < 1e-6
    assert isinstance(mon["m0"], (int, float))
    # m1 允许为 None（快照未提供该层）——**缺失≠0**，本模块如实透传
    assert mon["m1"] is None or isinstance(mon["m1"], (int, float))


def test_identity_report_is_readonly():
    """**零写入**：报表前后 state（prefectures/resources）深比较必须一致。"""
    from core import commands
    s = commands.new_game()
    before = copy.deepcopy({"p": s.prefectures, "r": getattr(s, "resources", None)})
    rep = si.identity_report(s)
    after = {"p": s.prefectures, "r": getattr(s, "resources", None)}
    assert before == after
    assert rep["schema_version"] == si.SCHEMA_VERSION
    assert "stock" in rep and "money" in rep
