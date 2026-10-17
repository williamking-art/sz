# -*- coding: utf-8 -*-
"""M39c-1 漕运淤塞（`canal_block`）治所级下沉 —— 定向回归。

口径（Jev 2026-10-13）：真账落治所（**首府承载**，无逐治所来源**不编造**，P=0.513）；
路级/全国 = **按水路档位加权平均**（choose B 0.502）；量纲恒在 0~100；缺失≠0（未登记治所**缺席**，
不写 0——0 是「通畅」这一声明）。

锁定边界：
  1. 下沉：全国值 → 每路首府；路级镜像 == 首府值；**派生全国 == 原全国值**（零行为变化）；
  2. 幂等：已下沉不覆盖；
  3. 加权平均口径（权重 强3/有2/弱1，未知按 1）；
  4. 缺失≠0：无值治所 ⇒ `None` 且不参与平均；全无值 ⇒ 聚合 `None`；
  5. 写桥：未下沉 ⇒ `None`（调用方回落）；下沉后写首府并刷镜像；量纲钳 0~100；
  6. 全国级写点 `canal_set_national`：未下沉 ⇒ `None`；下沉后所有路首府与全国同步；
  7. 对账：`survey_canal` 失配 0，破坏后能报出。
"""

import types

import pytest

from core.domains.economy import canal_bridge as cb

KEY = cb.SEAT_KEY


def _state(routes, national=None):
    st = types.SimpleNamespace(prefectures=routes)
    if national is not None:
        st.canal_block = national
    return st


@pytest.fixture
def cap(monkeypatch):
    """首府判定打桩（生产口径不变）。"""
    def _patch(mapping):
        monkeypatch.setattr(cb, "_capital_of", lambda pdata, route: mapping.get(route))
    return _patch


# ------------------------------------------------------------------ 1. 下沉与守恒
def test_sink_puts_national_value_on_each_capital(cap):
    cap({"路A": "A|首府", "路B": "B|首府"})
    s = _state({"路A": {"seats": {"A|首府": {}}},
                "路B": {"seats": {"B|首府": {}}}}, national=30)
    assert cb.sink_canal_to_seats(s) == 2
    assert s.prefectures["路A"]["seats"]["A|首府"][KEY] == 30.0
    assert s.prefectures["路B"]["seats"]["B|首府"][KEY] == 30.0
    assert s.prefectures["路A"][KEY] == 30.0           # 路级镜像
    # **派生全国 == 原全国值**（零行为变化）
    assert cb.aggregate_national_canal_block(s) == 30.0


def test_sink_is_idempotent(cap):
    cap({"路C": "C|首府"})
    s = _state({"路C": {"seats": {"C|首府": {}}}}, national=12)
    assert cb.sink_canal_to_seats(s) == 1
    assert cb.sink_canal_to_seats(s) == 0
    assert s.prefectures["路C"]["seats"]["C|首府"][KEY] == 12.0


def test_sink_skips_when_national_missing(cap):
    cap({"路D": "D|首府"})
    s = _state({"路D": {"seats": {"D|首府": {}}}})        # 无 canal_block
    assert cb.sink_canal_to_seats(s) == 0


def test_sink_skips_without_capital(cap):
    cap({"路E": None})
    s = _state({"路E": {"seats": {"E|某": {}}}}, national=5)
    assert cb.sink_canal_to_seats(s) == 0


# ------------------------------------------------------------------ 2. 加权平均口径
def test_weighted_mean_uses_tier_weights(monkeypatch, cap):
    cap({"路F": "F|首府"})
    monkeypatch.setattr(cb, "_tier_weight", lambda route, seat: 3.0 if seat == "F|首府" else 1.0)
    s = _state({"路F": {"seats": {"F|首府": {KEY: 40.0}, "F|次": {KEY: 0.0}}}}, national=40)
    cb.sink_canal_to_seats(s)
    # 首府 40 权重3 + 次所 0 权重1 ⇒ (40*3 + 0*1)/4 = 30
    assert cb.aggregate_route_canal_block(s.prefectures["路F"], "路F") == 30.0


def test_weighted_mean_defaults_to_one_for_unknown_tier():
    """未登记档位（假路名）⇒ 权重 1 ⇒ 退化为等权平均。"""
    pdata = {"seats": {"X|1": {KEY: 10.0}, "X|2": {KEY: 20.0}}}
    assert cb.aggregate_route_canal_block(pdata, "假路") == 15.0


# ------------------------------------------------------------------ 3. 缺失≠0
def test_absent_seat_is_none_and_excluded():
    pdata = {"seats": {"A|1": {KEY: 20.0}, "A|2": {}}}
    assert cb.seat_canal_block(pdata, "A|2") is None
    assert cb.aggregate_route_canal_block(pdata, "A") == 20.0     # 只算有值的


def test_aggregate_none_when_no_values():
    assert cb.aggregate_route_canal_block({"seats": {"A|1": {}}}, "A") is None
    assert cb.aggregate_national_canal_block(_state({"A": {"seats": {"A|1": {}}}})) is None


def test_is_sunk_requires_a_value_not_just_key():
    assert cb.is_sunk({"seats": {"A|1": {KEY: 0.0}}}) is True     # 0 是合法值（通畅）
    assert cb.is_sunk({"seats": {"A|1": {}}}) is False            # 缺席 ≠ 0


# ------------------------------------------------------------------ 4. 写桥
def test_canal_set_none_when_not_sunk():
    s = _state({"路G": {"seats": {"G|首府": {}}}})
    assert cb.canal_set(s, "路G", 50) is None
    assert cb.canal_add(s, "路G", 5) is None
    assert cb.canal_set_national(s, 50) is None


def test_canal_set_and_add_clamp_and_refresh(cap):
    cap({"路H": "H|首府"})
    s = _state({"路H": {"seats": {"H|首府": {}}}}, national=10)
    cb.sink_canal_to_seats(s)
    assert cb.canal_set(s, "路H", 60) == 60.0
    assert s.prefectures["路H"][KEY] == 60.0
    assert cb.canal_add(s, "路H", 50) == 100.0                    # 钳到 100
    assert cb.canal_add(s, "路H", -500) == 0.0                    # 钳到 0


def test_canal_set_national_syncs_all_routes(cap):
    cap({"路I": "I|首府", "路J": "J|首府"})
    s = _state({"路I": {"seats": {"I|首府": {}}},
                "路J": {"seats": {"J|首府": {}}}}, national=10)
    cb.sink_canal_to_seats(s)
    assert cb.canal_set_national(s, 77) == 77.0
    assert s.canal_block == 77.0
    for r in ("路I", "路J"):
        assert s.prefectures[r]["seats"][f"{r[1]}|首府"][KEY] == 77.0
        assert s.prefectures[r][KEY] == 77.0


# ------------------------------------------------------------------ 5. 对账
def test_survey_clean_then_detects_mismatch(cap):
    cap({"路K": "K|首府"})
    s = _state({"路K": {"seats": {"K|首府": {}}}}, national=25)
    cb.sink_canal_to_seats(s)
    assert cb.survey_canal(s)["字段失配"] == []

    s.prefectures["路K"][KEY] = 99.0                              # 人为破坏镜像
    rep = cb.survey_canal(s)
    assert len(rep["字段失配"]) == 1
    assert rep["字段失配"][0]["路"] == "路K"


def test_survey_reports_unsunk(cap):
    cap({"路L": None})
    s = _state({"路L": {"seats": {"L|某": {}}}}, national=5)
    rep = cb.survey_canal(s)
    assert rep["未下沉路由"] == 1
    assert rep["已下沉路由"] == 0


def test_grain_price_consumes_route_canal_block_and_falls_back():
    """M39c-2：路线粮价优先消费本路 canal_block，未下沉时安全回退全国值。"""
    from core.game_state import GameState
    state = GameState("史实")
    route_name = "两浙路"
    p = state.prefectures[route_name]

    # 1. 初始情况下：两浙路 canal_block 尚未特殊改动，粮价正常计算
    p0 = state.calc_region_grain_price(route_name)

    # 2. 本路发生重度淤塞 (canal_block = 90)
    p["canal_block"] = 90
    p_blocked = state.calc_region_grain_price(route_name)
    assert p_blocked > p0  # 运输加价生效，粮价显著升高

    # 3. 本路疏浚畅通 (canal_block = 0)
    p["canal_block"] = 0
    p_clear = state.calc_region_grain_price(route_name)
    assert p_clear < p0    # 运费消除，粮价降低

    # 4. 回退测试：删除本路键，安全回退读 state.canal_block
    del p["canal_block"]
    p_fallback = state.calc_region_grain_price(route_name)
    assert abs(p_fallback - p0) < 1e-6


