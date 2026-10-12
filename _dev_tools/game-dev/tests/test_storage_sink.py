# -*- coding: utf-8 -*-
"""M40a 常平仓（`changping_stock`）治所级下沉 —— 定向回归。

口径（Jev 2026-10-13）：真账落治所（**首府承载**，不编造差异，Q3 0.730）；
路级 = **Σ 各治所**（Q2 choose A 0.874）；缺失≠0（未登记治所**缺席**，不写 0——0 石是「空仓」声明）。

锁定：首府承载/Σ 恒等 · 幂等 · 缺失≠0 · 写桥（+ 累加、− 钳 0）· 对账 · 不臆造。
"""

import types

import pytest

from core.foundation.ledger import storage_bridge as sb

K = sb.CHANGPING_KEY


def _state(routes):
    return types.SimpleNamespace(prefectures=routes)


@pytest.fixture
def cap(monkeypatch):
    def _patch(mapping):
        monkeypatch.setattr(sb, "_capital_of", lambda pdata, route: mapping.get(route))
    return _patch


# ------------------------------------------------------------------ 1. 首府承载 + Σ 恒等
def test_sink_puts_route_stock_on_capital(cap):
    cap({"路A": "A|首府"})
    s = _state({"路A": {"changping_stock": 1234, "seats": {"A|首府": {}, "A|次": {}}}})
    assert sb.sink_storage_to_seats(s) == 1
    seats = s.prefectures["路A"]["seats"]
    assert seats["A|首府"][K] == 1234
    assert K not in seats["A|次"]                    # 未登记治所**缺席**（不写 0）
    assert s.prefectures["路A"][K] == 1234           # 路级 Σ == 原值
    assert sb.seat_stock(s.prefectures["路A"], "A|次") is None


def test_sink_skips_when_no_value_or_no_capital(cap):
    cap({"路B": None})
    s = _state({"路B": {"changping_stock": 10, "seats": {"B|某": {}}}})
    assert sb.sink_storage_to_seats(s) == 0           # 无首府 ⇒ 不臆造
    cap({"路C": "C|首府"})
    s2 = _state({"路C": {"seats": {"C|首府": {}}}})     # 无存量 ⇒ False
    assert sb.sink_storage_to_seats(s2) == 0


def test_sink_is_idempotent_and_no_overwrite(cap):
    cap({"路D": "D|首府"})
    s = _state({"路D": {"changping_stock": 50, "seats": {"D|首府": {}}}})
    assert sb.sink_storage_to_seats(s) == 1
    assert sb.sink_storage_to_seats(s) == 0
    assert s.prefectures["路D"]["seats"]["D|首府"][K] == 50
    s2 = _state({"路E": {"changping_stock": 999,
                         "seats": {"E|首府": {K: 7}}}})
    assert sb.sink_storage_to_seats(s2) == 0           # 已下沉 ⇒ 绝不覆盖
    assert s2.prefectures["路E"]["seats"]["E|首府"][K] == 7


# ------------------------------------------------------------------ 2. 缺失≠0
def test_aggregate_none_when_unsunk_or_absent():
    assert sb.aggregate_route_changping({"changping_stock": 5, "seats": {"A|1": {}}}) is None
    assert sb.aggregate_route_changping({"changping_stock": 5}) is None
    assert sb.aggregate_route_changping(None) is None
    assert sb.is_sunk({"seats": {"A|1": {K: 0}}}) is True      # 0 石是合法值（空仓）
    assert sb.is_sunk({"seats": {"A|1": {}}}) is False          # 缺席 ≠ 0


def test_sum_over_multiple_seats(cap):
    cap({"路F": "F|首府"})
    pdata = {"seats": {"F|首府": {K: 100}, "F|次": {K: 30}}}
    assert sb.route_stock_total(pdata) == 130


# ------------------------------------------------------------------ 3. 写桥
def test_writes_none_when_not_sunk():
    s = _state({"路G": {"changping_stock": 5, "seats": {"G|首府": {}}}})
    assert sb.changping_add(s, "路G", 5) is None
    assert sb.changping_set(s, "路G", 5) is None
    assert sb.changping_get(s, "路G") is None


def test_add_accumulates_and_clamps_at_zero(cap):
    cap({"路H": "H|首府"})
    s = _state({"路H": {"changping_stock": 100, "seats": {"H|首府": {}}}})
    sb.sink_storage_to_seats(s)
    assert sb.changping_add(s, "路H", 25) == 125        # 籴入 +
    assert s.prefectures["路H"][K] == 125               # 路级 Σ 同步
    assert sb.changping_add(s, "路H", -500) == 0        # 粜出 − 钳 0（同原 max(0,…)）
    assert s.prefectures["路H"][K] == 0
    assert sb.changping_get(s, "路H") == 0


# ------------------------------------------------------------------ 4. 对账
def test_survey_clean_then_detects(cap):
    cap({"路I": "I|首府"})
    s = _state({"路I": {"changping_stock": 88, "seats": {"I|首府": {}}}})
    sb.sink_storage_to_seats(s)
    assert sb.survey_storage(s)["字段失配"] == []
    s.prefectures["路I"][K] = 999                       # 人为破坏镜像
    rep = sb.survey_storage(s)
    assert len(rep["字段失配"]) == 1
    assert rep["字段失配"][0]["路"] == "路I"


def test_new_game_all_routes_sunk():
    """真实新局：20/20 路已下沉且对账 0 失配（首府判定走生产口径）。"""
    from core import commands
    s = commands.new_game()
    rep = sb.survey_storage(s)
    assert rep["已下沉路由"] == rep["路由数"] == 20
    assert rep["字段失配"] == []
