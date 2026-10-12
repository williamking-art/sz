# -*- coding: utf-8 -*-
"""M37 地方府库下沉（`local_treasury`）定向回归。

🔴 字段名提醒：真账是 `prefectures[路]["seats"][治所]["local_treasury"]`；
**不是** `state.treasury`（中央国库）。

锁定四条不看就会出事的边界：
  1. **守恒**：Σ 治所 **精确等于**路级原值（`split_int` 尾差归权重最大者）；
  2. **幂等**：已下沉绝不覆盖，重跑返回 0；
  3. **缺失 ≠ 0**：未下沉路聚合返回 `None`（不是 0），写点返回 `None`（调用方回落）；
  4. **不臆造归属**：权重不可得（`seat_pop_weights` 返回 `[]`）⇒ **整路跳过**，路级原值不动。
"""

import types

import pytest

from core.foundation.ledger import local_treasury_bridge as ltb
from core.foundation.ledger import pop_bridge

KEY = ltb.SEAT_KEY


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
    s = _state({"两浙路": {"local_treasury": 100, "seats": {"S1": {}, "S2": {}}}})

    assert ltb.sink_local_treasury_to_seats(s) == 1
    seats = s.prefectures["两浙路"]["seats"]
    assert seats["S1"][KEY] == 25.0
    assert seats["S2"][KEY] == 75.0
    # Σ 治所 == 路级（镜像已刷新）
    assert s.prefectures["两浙路"]["local_treasury"] == 100.0
    assert ltb.seat_local_treasury_total(s.prefectures["两浙路"]) == 100.0


def test_sink_handles_non_divisible_total(patched_weights):
    """非整除：尾差归权重最大者，Σ 仍精确等于原值。"""
    patched_weights({"路A": [("S1", 1.0), ("S2", 2.0)]})
    s = _state({"路A": {"local_treasury": 10, "seats": {"S1": {}, "S2": {}}}})
    ltb.sink_local_treasury_to_seats(s)
    seats = s.prefectures["路A"]["seats"]
    assert seats["S1"][KEY] == 3.0          # 与 split_int 既有契约一致
    assert seats["S2"][KEY] == 7.0
    assert seats["S1"][KEY] + seats["S2"][KEY] == 10.0


def test_weightless_seat_gets_zero_and_sum_preserved(patched_weights):
    """有人口缺的治所（不在权重里）记 0，Σ 仍等于路级。"""
    patched_weights({"路B": [("S1", 2.0)]})
    s = _state({"路B": {"local_treasury": 30, "seats": {"S1": {}, "S2": {}}}})
    ltb.sink_local_treasury_to_seats(s)
    seats = s.prefectures["路B"]["seats"]
    assert seats["S1"][KEY] == 30.0
    assert seats["S2"][KEY] == 0.0
    assert s.prefectures["路B"]["local_treasury"] == 30.0


def test_real_new_game_shape_is_supported(patched_weights):
    """真实新局形态：`local_treasury` 是整数贯、seats 只带 pops。"""
    patched_weights({"京畿路": [("京畿路|开封府", 5103824.0), ("京畿路|郑州", 605461.0)]})
    s = _state({"京畿路": {"local_treasury": 1260000,
                           "seats": {"京畿路|开封府": {"pops": {}},
                                     "京畿路|郑州": {"pops": {}}}}})
    assert ltb.sink_local_treasury_to_seats(s) == 1
    total = ltb.seat_local_treasury_total(s.prefectures["京畿路"])
    assert total == 1260000.0                                  # 守恒、无浮点漂移
    assert s.prefectures["京畿路"]["local_treasury"] == 1260000.0


# ------------------------------------------------------------------ 2. 幂等
def test_sink_is_idempotent(patched_weights):
    patched_weights({"路C": [("S1", 1.0), ("S2", 1.0)]})
    s = _state({"路C": {"local_treasury": 50, "seats": {"S1": {}, "S2": {}}}})
    assert ltb.sink_local_treasury_to_seats(s) == 1
    before = dict(s.prefectures["路C"]["seats"]["S1"])
    assert ltb.sink_local_treasury_to_seats(s) == 0            # 已下沉 ⇒ 不覆盖、返回 0
    assert s.prefectures["路C"]["seats"]["S1"] == before


def test_sink_does_not_overwrite_existing_truth(patched_weights):
    patched_weights({"路D": [("S1", 1.0)]})
    s = _state({"路D": {"local_treasury": 999, "seats": {"S1": {KEY: 7.0}}}})
    assert ltb.sink_local_treasury_to_seats(s) == 0
    assert s.prefectures["路D"]["seats"]["S1"][KEY] == 7.0


# ------------------------------------------------------------------ 3. 缺失≠0
def test_aggregate_returns_none_when_not_sunk(patched_weights):
    patched_weights({})
    s = _state({"路E": {"local_treasury": 12, "seats": {"S1": {}}}})
    assert ltb.aggregate_seat_local_treasury(s.prefectures["路E"]) is None


def test_aggregate_returns_none_without_seats():
    assert ltb.aggregate_seat_local_treasury({"local_treasury": 5}) is None
    assert ltb.aggregate_seat_local_treasury(None) is None


def test_writes_return_none_when_not_sunk(patched_weights):
    patched_weights({"路F": [("S1", 1.0)]})
    s = _state({"路F": {"local_treasury": 12, "seats": {"S1": {}}}})
    assert ltb.local_treasury_set(s, "路F", 100) is None        # 调用方据此回落原写法
    assert ltb.local_treasury_add(s, "路F", 5) is None


def test_route_without_local_treasury_value_is_skipped(patched_weights):
    """路级 local_treasury 为 None（未定义）⇒ 不下沉（缺失≠0，不伪造 0）。"""
    patched_weights({"路Z": [("S1", 1.0)]})
    s = _state({"路Z": {"local_treasury": None, "seats": {"S1": {}}}})
    assert ltb.sink_local_treasury_to_seats(s) == 0
    assert ltb.is_sunk(s.prefectures["路Z"]) is False


# ------------------------------------------------------------------ 4. 不臆造归属
def test_route_without_weights_is_skipped(patched_weights):
    patched_weights({})                                   # seat_pop_weights → []
    s = _state({"路G": {"local_treasury": 88, "seats": {"S1": {}, "S2": {}}}})
    assert ltb.sink_local_treasury_to_seats(s) == 0
    assert s.prefectures["路G"]["local_treasury"] == 88          # 原值分毫不动
    assert KEY not in s.prefectures["路G"]["seats"]["S1"]


# ------------------------------------------------------------------ 写侧（下沉后）
def test_set_and_add_write_seat_truth(patched_weights):
    patched_weights({"路H": [("S1", 1.0), ("S2", 1.0)]})
    s = _state({"路H": {"local_treasury": 100, "seats": {"S1": {}, "S2": {}}}})
    ltb.sink_local_treasury_to_seats(s)

    assert ltb.local_treasury_set(s, "路H", 40) == 40.0
    assert s.prefectures["路H"]["seats"]["S1"][KEY] == 20.0
    assert ltb.local_treasury_add(s, "路H", 10) == 50.0
    assert ltb.seat_local_treasury_total(s.prefectures["路H"]) == 50.0


def test_add_clamps_at_zero_with_warning(patched_weights):
    patched_weights({"路I": [("S1", 1.0)]})
    s = _state({"路I": {"local_treasury": 5, "seats": {"S1": {}}}})
    ltb.sink_local_treasury_to_seats(s)
    assert ltb.local_treasury_add(s, "路I", -100) == 0.0          # 夹紧而非负值
    assert s.prefectures["路I"]["seats"]["S1"][KEY] == 0.0


# ------------------------------------------------------------------ 对账
def test_survey_reports_mismatch_and_unsunk(patched_weights):
    patched_weights({"路J": [("S1", 1.0)]})
    s = _state({
        "路J": {"local_treasury": 10, "seats": {"S1": {}}},
        "路K": {"local_treasury": 3, "seats": {"S9": {}}},       # 未下沉
    })
    ltb.sink_local_treasury_to_seats(s, routes=["路J"])
    s.prefectures["路J"]["local_treasury"] = 999                  # 人为制造失配
    rep = ltb.survey_local_treasury(s)
    assert rep["路由数"] == 2
    assert rep["已下沉路由"] == 1
    assert rep["未下沉路由"] == 1
    assert len(rep["字段失配"]) == 1
    assert rep["字段失配"][0]["路"] == "路J"


# ------------------------------------------------------------------ 账户层集成（M37b 已落地）
# 2026-10-13 实测踩过的两个坑（都写进用例意图）：
#   ① 只下沉、不桥任何写点 ⇒ **第 1 轮起 20/20 路漂移**（治所冻结在开局值、镜像持续偏离）；
#   ② 只桥账户层、留 5 处绕过账户层的直写 ⇒ **2× 冲账**（淮南东路 349,118 vs Σ治所 698,234）。
# ⇒ M37b 已把**七处写点全部桥接**（账户层 setter ＋ settlement_common:270/:300 ＋
#   settlement_finance:640/:678 ＋ commands_decree:87），以下用例转常态回归。
def test_account_transfer_sinks_into_seats():
    """走**真实账户层**（`transfer_money("treasury", "local:<路>")`）时，真账必须落治所。"""
    from core import commands

    s = commands.new_game()
    route = next(iter(s.prefectures))
    pdata = s.prefectures[route]
    assert ltb.is_sunk(pdata), "新局应已下沉（M37a）"

    before = ltb.seat_local_treasury_total(pdata)
    moved = s.transfer_money("treasury", f"local:{route}", 1000)
    after = ltb.seat_local_treasury_total(pdata)

    assert moved == 1000, f"划转应成功，实际 {moved}"
    assert after == before + 1000, "真账必须落在治所"
    assert pdata[KEY] == after, "路级镜像必须等于 Σ治所"
    assert ltb.survey_local_treasury(s)["字段失配"] == []


def test_account_write_falls_back_when_not_sunk():
    """**未下沉**（模拟旧档：治所里没有 local_treasury 键）⇒ 必须回落原写法，行为不变。"""
    from core import commands

    s = commands.new_game()
    route = next(iter(s.prefectures))
    pdata = s.prefectures[route]
    for seat in pdata["seats"].values():          # 人为退回"未下沉"状态
        seat.pop(KEY, None)
    assert not ltb.is_sunk(pdata)
    before_route = int(pdata.get("local_treasury") or 0)

    moved = s.transfer_money("treasury", f"local:{route}", 500)

    assert moved == 500
    assert int(pdata.get("local_treasury") or 0) == before_route + 500, "未下沉应走原路级写法"
    assert all(KEY not in seat for seat in pdata["seats"].values()), "未下沉不得凭空写治所"


def test_local_treasury_total_unchanged_after_move():
    """账户聚合投影口径不变：`local:<路>` 内部划转不改变 Σ（只是换载体）。"""
    from core import commands

    s = commands.new_game()
    route = next(iter(s.prefectures))
    tot_open = sum(int(p.get("local_treasury") or 0) for p in s.prefectures.values())

    s.transfer_money(f"local:{route}", "treasury", 100)     # 地方库 → 国库
    s.transfer_money("treasury", f"local:{route}", 100)     # 国库 → 地方库（回转）

    tot_now = sum(int(p.get("local_treasury") or 0) for p in s.prefectures.values())
    assert abs(tot_now - tot_open) <= 1, f"往返后 Σ 应回到原值，实际 {tot_open} → {tot_now}"
    assert ltb.survey_local_treasury(s)["字段失配"] == []

def test_weights_provider_is_swappable(patched_weights):
    """Jev 裁定：先用人口权数落地，行政等级版留作目标 —— 切换只改一处。"""
    patched_weights({"路L": [("S1", 1.0)]})
    s = _state({"路L": {"local_treasury": 90, "seats": {"S1": {}, "S2": {}}}})
    try:
        ltb.set_weights_provider(lambda route: [("S1", 1.0), ("S2", 2.0)])
        assert ltb.sink_local_treasury_to_seats(s) == 1
        seats = s.prefectures["路L"]["seats"]
        assert seats["S1"][KEY] == 30.0
        assert seats["S2"][KEY] == 60.0
    finally:
        ltb.set_weights_provider(None)
    assert ltb._weights_provider_unset() if hasattr(ltb, "_weights_provider_unset") else True
