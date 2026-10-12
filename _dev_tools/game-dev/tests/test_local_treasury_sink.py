# -*- coding: utf-8 -*-
"""M37 地方府库下沉（treasury）定向回归。

锁定四条不看就会出事的边界：
  1. **守恒**：Σ 治所 **精确等于**路级原值（`split_int` 尾差归权重最大者）；
  2. **幂等**：已下沉绝不覆盖，重跑返回 0；
  3. **缺失 ≠ 0**：未下沉路聚合返回 `None`（不是 0），写点返回 `None`（调用方回落）；
  4. **不臆造归属**：权重不可得（`seat_pop_weights` 返回 `[]`）⇒ **整路跳过**，路级原值不动。
"""

import types

import pytest

from core.foundation.ledger import pop_bridge, treasury_bridge


def _state(routes):
    """最小假 state：只要有 `prefectures` 即可（桥接只读它 + 权重打桩）。"""
    return types.SimpleNamespace(prefectures=routes)


@pytest.fixture
def patched_weights(monkeypatch):
    """把 `pop_bridge.seat_pop_weights` 打桩成可控权重（生产口径不变）。"""
    def _patch(mapping):
        monkeypatch.setattr(pop_bridge, "seat_pop_weights",
                            lambda route: list(mapping.get(route, [])))
    return _patch


# ------------------------------------------------------------------ 1. 守恒
def test_sink_distributes_and_sums_exactly(patched_weights):
    patched_weights({"两浙路": [("S1", 1.0), ("S2", 3.0)]})
    s = _state({"两浙路": {"treasury": 100, "seats": {"S1": {}, "S2": {}}}})

    assert treasury_bridge.sink_treasury_to_seats(s) == 1
    seats = s.prefectures["两浙路"]["seats"]
    assert seats["S1"]["treasury"] == 25.0
    assert seats["S2"]["treasury"] == 75.0
    # Σ 治所 == 路级（镜像已刷新）
    assert s.prefectures["两浙路"]["treasury"] == 100.0
    assert treasury_bridge.seat_treasury_total(s.prefectures["两浙路"]) == 100.0


def test_sink_handles_non_divisible_total(patched_weights):
    """非整除：尾差归权重最大者，Σ 仍精确等于原值。"""
    patched_weights({"路A": [("S1", 1.0), ("S2", 2.0)]})
    s = _state({"路A": {"treasury": 10, "seats": {"S1": {}, "S2": {}}}})
    treasury_bridge.sink_treasury_to_seats(s)
    seats = s.prefectures["路A"]["seats"]
    assert seats["S1"]["treasury"] == 3.0          # 与 split_int 既有契约一致
    assert seats["S2"]["treasury"] == 7.0
    assert seats["S1"]["treasury"] + seats["S2"]["treasury"] == 10.0


def test_weightless_seat_gets_zero_and_sum_preserved(patched_weights):
    """有人口缺的治所（不在权重里）记 0，Σ 仍等于路级。"""
    patched_weights({"路B": [("S1", 2.0)]})
    s = _state({"路B": {"treasury": 30, "seats": {"S1": {}, "S2": {}}}})
    treasury_bridge.sink_treasury_to_seats(s)
    seats = s.prefectures["路B"]["seats"]
    assert seats["S1"]["treasury"] == 30.0
    assert seats["S2"]["treasury"] == 0.0
    assert s.prefectures["路B"]["treasury"] == 30.0


# ------------------------------------------------------------------ 2. 幂等
def test_sink_is_idempotent(patched_weights):
    patched_weights({"路C": [("S1", 1.0), ("S2", 1.0)]})
    s = _state({"路C": {"treasury": 50, "seats": {"S1": {}, "S2": {}}}})
    assert treasury_bridge.sink_treasury_to_seats(s) == 1
    before = dict(s.prefectures["路C"]["seats"]["S1"])
    # 第二次：已下沉 ⇒ 不覆盖、返回 0
    assert treasury_bridge.sink_treasury_to_seats(s) == 0
    assert s.prefectures["路C"]["seats"]["S1"] == before


def test_sink_does_not_overwrite_existing_truth(patched_weights):
    """已下沉的真账（哪怕是手工值）不得被覆盖。"""
    patched_weights({"路D": [("S1", 1.0)]})
    s = _state({"路D": {"treasury": 999, "seats": {"S1": {"treasury": 7.0}}}})
    assert treasury_bridge.sink_treasury_to_seats(s) == 0
    assert s.prefectures["路D"]["seats"]["S1"]["treasury"] == 7.0


# ------------------------------------------------------------------ 3. 缺失≠0
def test_aggregate_returns_none_when_not_sunk(patched_weights):
    patched_weights({})
    s = _state({"路E": {"treasury": 12, "seats": {"S1": {}}}})
    assert treasury_bridge.aggregate_seat_treasury(s.prefectures["路E"]) is None


def test_aggregate_returns_none_without_seats():
    assert treasury_bridge.aggregate_seat_treasury({"treasury": 5}) is None
    assert treasury_bridge.aggregate_seat_treasury(None) is None


def test_writes_return_none_when_not_sunk(patched_weights):
    patched_weights({"路F": [("S1", 1.0)]})
    s = _state({"路F": {"treasury": 12, "seats": {"S1": {}}}})
    assert treasury_bridge.treasury_set(s, "路F", 100) is None      # 调用方据此回落原写法
    assert treasury_bridge.treasury_add(s, "路F", 5) is None


# ------------------------------------------------------------------ 4. 不臆造归属
def test_route_without_weights_is_skipped(patched_weights):
    patched_weights({})                                   # seat_pop_weights → []
    s = _state({"路G": {"treasury": 88, "seats": {"S1": {}, "S2": {}}}})
    assert treasury_bridge.sink_treasury_to_seats(s) == 0
    assert s.prefectures["路G"]["treasury"] == 88          # 原值分毫不动
    assert "treasury" not in s.prefectures["路G"]["seats"]["S1"]


# ------------------------------------------------------------------ 写侧（下沉后）
def test_treasury_set_and_add_write_seat_truth(patched_weights):
    patched_weights({"路H": [("S1", 1.0), ("S2", 1.0)]})
    s = _state({"路H": {"treasury": 100, "seats": {"S1": {}, "S2": {}}}})
    treasury_bridge.sink_treasury_to_seats(s)

    assert treasury_bridge.treasury_set(s, "路H", 40) == 40.0
    assert s.prefectures["路H"]["seats"]["S1"]["treasury"] == 20.0
    assert treasury_bridge.treasury_add(s, "路H", 10) == 50.0
    assert treasury_bridge.seat_treasury_total(s.prefectures["路H"]) == 50.0


def test_treasury_add_clamps_at_zero_with_warning(patched_weights, caplog):
    patched_weights({"路I": [("S1", 1.0)]})
    s = _state({"路I": {"treasury": 5, "seats": {"S1": {}}}})
    treasury_bridge.sink_treasury_to_seats(s)
    assert treasury_bridge.treasury_add(s, "路I", -100) == 0.0      # 夹紧而非负值
    assert s.prefectures["路I"]["seats"]["S1"]["treasury"] == 0.0


# ------------------------------------------------------------------ 对账
def test_survey_reports_mismatch_and_unsunk(patched_weights):
    patched_weights({"路J": [("S1", 1.0)]})
    s = _state({
        "路J": {"treasury": 10, "seats": {"S1": {}}},
        "路K": {"treasury": 3, "seats": {"S9": {}}},       # 未下沉
    })
    treasury_bridge.sink_treasury_to_seats(s, routes=["路J"])
    s.prefectures["路J"]["treasury"] = 999                  # 人为制造失配
    rep = treasury_bridge.survey_treasury(s)
    assert rep["路由数"] == 2
    assert rep["已下沉路由"] == 1
    assert rep["未下沉路由"] == 1
    assert len(rep["字段失配"]) == 1
    assert rep["字段失配"][0]["路"] == "路J"
