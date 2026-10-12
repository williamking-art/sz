# -*- coding: utf-8 -*-
"""M53 治所级市场切片影子 —— 定向回归。

锁定：供给/持有人读**治所真账**（兼容治所桶）· 需求走既有单点（未配置 ⇒ `None` + reason，
**不臆造**）· 在途按 `to`/`dim` 过滤 · **价不臆造**（`None` + reason）· 影子成交量＝min(供给, 需求) ·
未满足给 `market_gap` 原因码 · **五段链条逐段有值或 None** · **零写入**。
"""

import copy
import types

import pytest

from core.domains.economy import seat_market_shadow as sm


def _state(seats=None, goods_prices=None):
    st = types.SimpleNamespace()
    st.prefectures = {"路A": {"seats": seats if seats is not None else {},
                              "pops": {"工匠": {"goods": {"绸": 5}}}}}
    return st


def _seat(goods=None, wealth=100, size=10):
    return {"pops": {"工匠": {"goods": goods or {"绸": 10}, "wealth": wealth, "size": size}}}


# ------------------------------------------------------------------ 供给 / 持有人
def test_holders_and_supply_read_seat_truth_with_buckets():
    st = _state({"A|甲": _seat({"绸": 10}), "A|乙": _seat({"A|乙": {"绸": 3}})})
    assert sm.seat_holders(st, "路A", "A|甲", "绸") == {"工匠": 10}
    assert sm.seat_supply(st, "路A", "A|甲", "绸") == 10
    assert sm.seat_supply(st, "路A", "A|乙", "绸") == 3          # 治所桶被摊平
    assert sm.seat_supply(st, "路A", "不存在", "绸") is None
    assert sm.seat_supply(_state(), "路A", "A|甲", "绸") is None  # 无 seats（缺失≠0）


def test_purchasing_power():
    st = _state({"A|甲": _seat(wealth=250)})
    assert sm.seat_purchasing_power(st, "路A", "A|甲") == {"工匠": 250}
    assert sm.seat_purchasing_power(st, "路A", "无") == {}


# ------------------------------------------------------------------ 需求（走既有单点）
def test_demand_uses_existing_module_and_reports_missing(monkeypatch):
    from core.domains.economy import demand as dm
    monkeypatch.setattr(dm, "basic_need", lambda cls, dim, size: 2.0 if dim == "绸" else None)
    monkeypatch.setattr(dm, "demand_release", lambda cls, pc: 1.0)
    st = _state({"A|甲": _seat(size=10)})
    got = sm.seat_demand(st, "路A", "A|甲", "绸")
    assert got["total"] == 20.0 and got["by_class"]["工匠"]["effective"] == 20.0
    # 未配置的维 ⇒ 不可定义（不臆造）
    got2 = sm.seat_demand(st, "路A", "A|甲", "谜之货")
    assert got2["total"] is None and got2["reasons"]


# ------------------------------------------------------------------ 在途 / 可达 / 价
def test_in_transit_filters_by_seat_and_dim(monkeypatch):
    import core.transport as tp
    monkeypatch.setattr(tp, "in_transit", lambda state: [
        {"to": "路A|A|甲", "qty": {"绸": 4}},
        {"to": "路A|A|乙", "qty": {"绸": 7}},
        {"to": "路A|A|甲", "qty": {"布": 9}},
    ])
    st = _state()
    st.material_transit = []                          # 容器已在 ⇒ 才会走 in_transit
    assert sm.in_transit_to(st, "路A", "A|甲", "绸") == 4
    assert sm.in_transit_to(st, "路A", "A|甲", "布") == 9
    # 无容器 ⇒ 0 且**不创建容器**（真·只读；`in_transit` 读时会惰性建它）
    st2 = _state()
    assert sm.in_transit_to(st2, "路A", "A|甲", "绸") == 0
    assert not hasattr(st2, "material_transit")
    monkeypatch.setattr(tp, "in_transit", lambda state: None)
    assert sm.in_transit_to(st, "路A", "A|甲", "绸") is None      # 不可用 ⇒ None（不冒充 0）


def test_reachability_and_price_not_invented():
    st = _state({"A|甲": _seat({"绸": 0}), "A|乙": _seat({"绸": 6})})
    rep = sm.seat_reachability(st, "路A", "A|甲", "绸")
    assert rep["same_route_seats_with_stock"] == 1 and "A|乙" in rep["detail"]
    pr = sm.seat_price_or_none(st, "路A", "绸")
    assert pr["price"] is None and "不臆造" in pr["reason"]


# ------------------------------------------------------------------ 影子撮合 / 五段链条
def test_shadow_match_and_gap_reasons(monkeypatch):
    from core.domains.economy import demand as dm
    monkeypatch.setattr(dm, "basic_need", lambda cls, dim, size: 5.0)
    monkeypatch.setattr(dm, "demand_release", lambda cls, pc: 1.0)
    st = _state({"A|甲": _seat({"绸": 3}, size=10)})           # 供给 3，需求 50
    m = sm.shadow_match(st, "路A", "A|甲", "绸")
    assert m["supply"] == 3 and m["demand"] == 50.0
    assert m["shadow_trade_qty"] == 3 and m["unmet"] == 47
    codes = [g.get("code") for g in m["gap_reasons"] if g]
    assert "insufficient_stock" in codes                     # 复用 market_gap 原因码

    # 供给为 0 ⇒ no_stock_local
    st0 = _state({"A|甲": _seat({"绸": 0}, size=10)})
    m0 = sm.shadow_match(st0, "路A", "A|甲", "绸")
    assert m0["supply"] == 0 and m0["shadow_trade_qty"] == 0
    assert any((g or {}).get("code") == "no_stock_local" for g in m0["gap_reasons"])


def test_chain_diagnosis_has_five_stages(monkeypatch):
    from core.domains.economy import demand as dm
    monkeypatch.setattr(dm, "basic_need", lambda cls, dim, size: 5.0)
    monkeypatch.setattr(dm, "demand_release", lambda cls, pc: 1.0)
    st = _state({"A|甲": _seat({"绸": 3}, size=10)})
    ch = sm.chain_diagnosis(st, "路A", "A|甲", "绸")
    assert set(sm.CHAIN_STAGES) <= set(ch)
    assert ch["origin"]["value"] == 3 and ch["trade"]["value"] == 3
    # 未接的两段如实 None + reason（不留空白）
    assert ch["arrival"]["value"] is None and ch["arrival"]["reason"]
    assert ch["processing"]["value"] is None and ch["processing"]["reason"]


# ------------------------------------------------------------------ 汇总 + 只读
def test_survey_is_readonly(monkeypatch):
    from core.domains.economy import demand as dm
    monkeypatch.setattr(dm, "basic_need", lambda cls, dim, size: 1.0)
    monkeypatch.setattr(dm, "demand_release", lambda cls, pc: 1.0)
    st = _state({"A|甲": _seat({"绸": 10}, size=10)})
    before = copy.deepcopy(st.__dict__)
    rep = sm.survey_seat_market_shadow(st)
    assert rep["pairs_with_stock"] == 1 and rep["sampled"] == 1
    assert rep["rows"][0]["dim"] == "绸"
    assert copy.deepcopy(st.__dict__) == before              # **零写入**
