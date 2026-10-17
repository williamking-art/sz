# -*- coding: utf-8 -*-
"""系统级全息经济变动总表（Master Economic Balance Sheet）—— 定向回归用例。

锁定：
1. 粮食五大保管方（中央太仓、地方州仓、常平仓、POP各阶层私粮、在途粮食）分列；
2. 缺失≠0（不可读 ⇒ None + warning，绝不默认回落 0）；
3. 治所桶形态兼容（`seats[*]["storage"]` 与 `pop["grain"]` 字典）；
4. 全息变动总表（粮食 + 20维商品 + 货币）闭合与残差判定；
5. 纯只读投影（零写入守卫：调用前后 state 保持深比较严格不变）。
"""

import copy
import types
import pytest

from core.domains.economy import stock_identity as si


def _full_state(
    granary=None,
    prefs=None,
    resources=None,
    transit=None,
    pending=None,
    treasury=None,
):
    st = types.SimpleNamespace()
    if granary is not None:
        st.granary = granary
    if prefs is not None:
        st.prefectures = prefs
    if resources is not None:
        st.resources = resources
    if transit is not None:
        st.material_transit = transit
    if pending is not None:
        st.pending_stock = pending
    if treasury is not None:
        st.treasury = treasury
    return st


# ------------------------------------------------------------------ 1. 粮食五大保管方只读读取
def test_grain_custody_reads_flat_and_seat_buckets():
    """测试粮食在路级扁平与治所下沉桶形态下的正确累加与分列。"""
    prefs = {
        "两浙路": {
            "storage": 500,
            "changping_stock": 200,
            "seats": {
                "两浙路|杭州": {"storage": 300, "changping_stock": 120},
                "两浙路|越州": {"storage": 200, "changping_stock": 80},
            },
            "pops": {
                "农": {"grain": {"两浙路|杭州": 1000, "两浙路|越州": 800}},
                "士绅": {"grain": 5000},
            },
        },
        "京畿路": {
            "storage": 1000,
            "changping_stock": 400,
            # 无 seats，回落路级值
            "pops": {
                "农": {"grain": 3000},
            },
        },
    }
    st = _full_state(granary=20000, prefs=prefs)

    # 中央太仓
    assert si.central_granary(st) == 20000.0

    # 州仓：两浙路有 seats 优先用 seats (300+200=500)，京畿路用路级 1000 -> 合计 1500
    assert si.prefectural_storage(st) == 1500.0

    # 常平仓：两浙路 120+80=200，京畿路 400 -> 合计 600
    assert si.prefectural_changping(st) == 600.0

    # POP 私粮：1000 + 800 + 5000 + 3000 = 9800
    assert si.pop_grain(st) == 9800.0


def test_grain_custody_missing_not_zero():
    """测试缺失属性返回 None，不伪造为 0。"""
    st_empty = types.SimpleNamespace()
    assert si.central_granary(st_empty) is None
    assert si.prefectural_storage(st_empty) is None
    assert si.prefectural_changping(st_empty) is None
    assert si.pop_grain(st_empty) is None

    snap = si.grain_snapshot(st_empty)
    assert snap["all_readable"] is False
    assert snap["total"] is None
    assert len(snap["warnings"]) >= 4


def test_in_transit_grain(monkeypatch):
    """测试粮食在途批次的提取与纯只读特性。"""
    st = types.SimpleNamespace()
    # 容器未创建时返回 0.0 且不创建属性
    assert si.in_transit_grain(st) == 0.0
    assert not hasattr(st, "material_transit")

    st.material_transit = []
    import core.transport as tp
    monkeypatch.setattr(
        tp,
        "in_transit",
        lambda state: [
            {"dim": "grain", "qty": 150},
            {"qty": {"grain": 250, "timber": 10}},
            {"dim": "木", "qty": 50},
        ],
    )
    assert si.in_transit_grain(st) == 400.0


# ------------------------------------------------------------------ 2. 粮食快照与 Δ
def test_grain_snapshot_and_delta(monkeypatch):
    import core.transport as tp
    monkeypatch.setattr(tp, "in_transit", lambda state: [{"dim": "grain", "qty": 100}])

    st1 = _full_state(
        granary=10000,
        prefs={"路A": {"storage": 1000, "changping_stock": 500, "pops": {"农": {"grain": 2000}}}},
        transit=[],
    )
    st2 = _full_state(
        granary=11000,
        prefs={"路A": {"storage": 900, "changping_stock": 600, "pops": {"农": {"grain": 2200}}}},
        transit=[],
    )

    s1 = si.grain_snapshot(st1)
    s2 = si.grain_snapshot(st2)
    assert s1["all_readable"] is True
    assert s2["all_readable"] is True
    assert s1["total"] == 13600.0  # 10000 + 1000 + 500 + 2000 + 100
    assert s2["total"] == 14800.0  # 11000 + 900 + 600 + 2200 + 100

    delta = si.grain_delta(s1, s2)
    assert delta["all_readable"] is True
    assert delta["total"] == 1200.0
    assert delta["by_custody"]["central_granary"] == 1000.0
    assert delta["by_custody"]["prefectural_storage"] == -100.0
    assert delta["by_custody"]["changping_stock"] == 100.0
    assert delta["by_custody"]["pop_grain"] == 200.0
    assert delta["by_custody"]["in_transit_grain"] == 0.0


# ------------------------------------------------------------------ 3. 全息变动总表闭合与残差
def test_master_economic_balance_sheet_closed():
    """测试全息变动总表在流量闭合时的检验判定。"""
    st1 = _full_state(
        granary=5000,
        prefs={"路A": {"storage": 500, "changping_stock": 200, "pops": {"工匠": {"goods": {"木": 10}}, "农": {"grain": 1000}}}},
        resources={"木": {"stock": 100}},
    )
    st2 = _full_state(
        granary=5200,  # +200
        prefs={"路A": {"storage": 450, "changping_stock": 250, "pops": {"工匠": {"goods": {"木": 25}}, "农": {"grain": 1100}}}},
        resources={"木": {"stock": 95}},
    )
    # 粮食变化：太仓+200, 州仓-50, 常平+50, 农+100 -> net = +300
    # 木材变化：工匠+15, 全国-5 -> net = +10
    flows = {
        "grain": {"harvest": 500, "consume": -200},  # net = 300
        "木": {"produce": 30, "consume": -20},        # net = 10
    }
    report = si.master_economic_balance_sheet(st1, st2, monthly_flows=flows)

    assert "grain" in report["balance_sheet"]
    assert "木" in report["balance_sheet"]

    g_row = report["balance_sheet"]["grain"]
    assert g_row["initial"] == 6700.0
    assert g_row["final"] == 7000.0
    assert g_row["delta"] == 300.0
    assert g_row["residual"] == 0.0
    assert g_row["is_closed"] is True

    m_row = report["balance_sheet"]["木"]
    assert m_row["delta"] == 10.0
    assert m_row["residual"] == 0.0
    assert m_row["is_closed"] is True

    assert report["all_closed"] is True
    assert report["unclosed"] == []
    assert report["nonzero"] == []


def test_master_economic_balance_sheet_detects_leak():
    """测试当存在未入账的漏物或虚刷时，残差非零并被精准标出。"""
    st1 = _full_state(
        granary=5000,
        prefs={"路A": {"storage": 500, "changping_stock": 200, "pops": {"农": {"grain": 1000}}}},
    )
    st2 = _full_state(
        granary=5000,
        prefs={"路A": {"storage": 500, "changping_stock": 200, "pops": {"农": {"grain": 1200}}}},  # 凭空多出 200 粮
    )
    # 声明流量只有 100
    flows = {"grain": 100.0}
    report = si.master_economic_balance_sheet(st1, st2, monthly_flows=flows)

    assert report["all_closed"] is False
    assert "grain" in report["nonzero"]
    assert report["balance_sheet"]["grain"]["residual"] == 100.0  # 多出 100 没对上


def test_format_master_balance_sheet():
    st = _full_state(
        granary=1000,
        prefs={"路A": {"storage": 100, "changping_stock": 50, "pops": {"农": {"grain": 200}}}},
        resources={"木": {"stock": 10}},
    )
    report = si.master_economic_balance_sheet(st, st)
    text = si.format_master_balance_sheet(report)
    assert "系统级全息经济变动总表" in text
    assert "grain" in text or "粮食" in text
    assert "[OK]" in text


def test_master_economic_balance_sheet_zero_write():
    """守卫：调用前后的 state 必须完全一致，杜绝任何隐式写。"""
    st1 = _full_state(
        granary=1000,
        prefs={"路A": {"storage": 100, "changping_stock": 50, "pops": {"农": {"grain": 200}}}},
    )
    st2 = _full_state(
        granary=1100,
        prefs={"路A": {"storage": 100, "changping_stock": 50, "pops": {"农": {"grain": 200}}}},
    )
    backup1 = copy.deepcopy(st1.__dict__)
    backup2 = copy.deepcopy(st2.__dict__)

    si.master_economic_balance_sheet(st1, st2, monthly_flows={"grain": 100})

    assert st1.__dict__ == backup1
    assert st2.__dict__ == backup2
