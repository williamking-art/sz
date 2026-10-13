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
    """`basic_need` **已含 size**（返回阶层需求总量）⇒ 本模块**不得再乘 size**（M74b 修双重计数）。"""
    from core.domains.economy import demand as dm
    monkeypatch.setattr(dm, "basic_need", lambda cls, dim, size: 2.0 if dim == "绸" else None)
    monkeypatch.setattr(dm, "demand_release", lambda cls, pc: 1.0)
    st = _state({"A|甲": _seat(size=10)})
    got = sm.seat_demand(st, "路A", "A|甲", "绸")
    # `basic_need` 桩返回 **2.0（总量）** ⇒ 有效需求 = 2.0 × 余量释放 1.0 = 2.0（**不是 20**）
    assert got["total"] == 2.0 and got["by_class"]["工匠"]["effective"] == 2.0
    assert got["by_class"]["工匠"]["need_total"] == 2.0
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


def test_price_goes_through_public_single_point(monkeypatch):
    """价走公开单点：能读 ⇒ 给值并标 `level="route"`（**明示非治所级**）；读不到 ⇒ None + reason。"""
    import core.market_price as mp
    monkeypatch.setattr(mp, "effective_buy_price",
                        lambda **kw: {"price": 1.5, "kind": "base", "reason": "基准价"})
    st = _state()
    pr = sm.seat_price_or_none(st, "路A", "绸")
    assert pr["price"] == 1.5 and pr["level"] == "route" and pr["kind"] == "base"
    assert "路级" in pr["note"] and "欠账" in pr["note"]      # 口径与欠账都写清

    monkeypatch.setattr(mp, "effective_buy_price",
                        lambda **kw: {"price": None, "kind": "none", "reason": "无价"})
    assert sm.seat_price_or_none(st, "路A", "绸")["price"] is None

    def _boom(**kw):
        raise RuntimeError("价单点炸了")
    monkeypatch.setattr(mp, "effective_buy_price", _boom)
    pr3 = sm.seat_price_or_none(st, "路A", "绸")
    assert pr3["price"] is None and "不可用" in pr3["reason"]


def test_demand_coverage_matrix(monkeypatch):
    """需求**通道矩阵**（M73 更正口径）：逐**维**报 basket/durable/grain 三通道；无通道 ⇒ 列入。"""
    import content.data as cd
    monkeypatch.setattr(cd, "BASIC_NEED_BASKET", {"绸": 0.2, "布": 0.3}, raising=False)
    monkeypatch.setattr(cd, "DURABLE_TARGET_STOCK", {"绸": 5.0}, raising=False)
    st = _state({"A|甲": _seat({"绸": 10, "布": 5, "木": 3}, size=10)})
    cov = sm.demand_coverage(st, dims=["绸", "布", "木", "粮"])
    rows = {r["dim"]: r for r in cov["dims"]}
    assert rows["绸"]["channels"] == ["basket", "durable"]      # 两条通道都有
    assert rows["布"]["channels"] == ["basket"]
    assert rows["木"]["channels"] == []                          # **无来源不启用**
    assert cov["no_channel"] == ["木"] or "木" in cov["no_channel"]
    assert cov["checked"] == 4 and cov["with_channel"] == 3      # 绸/布/粮 有通道，木没有
    assert rows["粮"]["channels"] == ["grain"]                   # 粮走**按阶层**的口粮通道
    assert "维级" in cov["note"] and "不启用" in cov["note"] and "不得拍数" in cov["note"]


def test_reachability_and_price_not_invented():
    """可达性按事实报；价走**公开单点**——**无基准价的商品 ⇒ `None` + reason**（缺失≠0）。"""
    st = _state({"A|甲": _seat({"绸": 0}), "A|乙": _seat({"绸": 6})})
    rep = sm.seat_reachability(st, "路A", "A|甲", "绸")
    assert rep["same_route_seats_with_stock"] == 1 and "A|乙" in rep["detail"]
    # 价**走公开单点**：本 fixture 的 `绸` 实际上有价（单点走 state 的基准/动态价）
    # ⇒ 断言"确实问到了单点、且明示是路级价"；"不可定价"的场景由 monkeypatch 用例覆盖
    pr = sm.seat_price_or_none(st, "路A", "绸")
    assert pr["price"] is not None and pr["level"] == "route"
    assert pr["kind"] in ("official", "dynamic", "base")
    assert "effective_buy_price" in pr["source"]


# ------------------------------------------------------------------ 影子撮合 / 五段链条
def test_shadow_match_and_gap_reasons(monkeypatch):
    from core.domains.economy import demand as dm
    monkeypatch.setattr(dm, "basic_need", lambda cls, dim, size: 5.0)
    monkeypatch.setattr(dm, "demand_release", lambda cls, pc: 1.0)
    st = _state({"A|甲": _seat({"绸": 3}, size=10)})           # 供给 3
    m = sm.shadow_match(st, "路A", "A|甲", "绸")
    # 需求 = **max(基本需求 5, 耐用品缺口 7)** = 7（绸目标库存 1.0/人 × 10 人 − 已持 3 = 7）
    #   ⇒ 这条同时**证明耐用品通道已生效**（M74）
    assert m["supply"] == 3 and m["demand"] == 7.0
    assert m["shadow_trade_qty"] == 3 and m["unmet"] == 4
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
