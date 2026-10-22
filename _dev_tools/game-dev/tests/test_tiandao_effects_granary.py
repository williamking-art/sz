# -*- coding: utf-8 -*-
"""L3-b 天道数值接线（仓储/军事域）· 2026-10-22 改为**概率加权**。

被测：
- ① `_canal_route_loss_mult(state)` —— 途耗乘子 = `Σ p_o × mult_o`（**期望值**，非 argmax 查表）
- ①a `_pay_overland_freight` —— 脚钱 = 起运×0.01×`p(overland_cart)`，国库→商人 POP
- ①b `_buy_grain_via_local_treasury` —— 补粮 = 起运×3%×`p(borrow_grain)`，府库出钱、民粮入太仓
- ② `_recruit_refugees_as_xiangjun` —— 募集率 = 2%×`gate_intensity(p)`，再受单地上限
- ③ 宋侧饥荒逃散放大 = `1 + (MULT−1)×p(flee_refugee)`

判定基准：
1. **幅度随概率连续变化**（同一档位不同概率 ⇒ 不同力度）；
2. **缺失/未定义 ⇒ 中性**，且与「无观测副本」逐字节一致；
3. 钱/粮/人三腿守恒（每笔扣减都有对手方）；
4. 兵 POP 的 `size` 不手改，由 finance 步按 Σtroops 重派生（当月对齐、不双计）。
"""
from __future__ import annotations

import copy
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.settlement_granary import (  # noqa: E402
    CANAL_BORROW_GRAIN_PERMILLE,
    CANAL_OVERLAND_COST_PERMILLE,
    CANAL_ROUTE_LOSS_MULT,
    RECRUIT_REFUGEE_CAP_PER_ROUTE,
    _buy_grain_via_local_treasury,
    _canal_borrow_target,
    _canal_overland_cost,
    _canal_route_loss_mult,
    _flee_after_verdict,
    _pay_overland_freight,
    _recruit_refugees_as_xiangjun,
    _settle_granary,
)


class _NoState:
    """无任何属性的替身（验证读取点对缺失 state 的中性）。"""


@pytest.fixture(scope="module")
def base_state():
    from core.commands import new_game

    return new_game()


def _fresh():
    from core.commands import new_game

    return new_game()


def _state(base, *, dists=None, strengths=None, decisions=None, turn=None):
    s = copy.deepcopy(base)
    if turn is not None:
        s.turn = turn
    if dists is not None or strengths is not None or decisions is not None:
        s._tiandao_observe = {
            "turn": getattr(s, "turn", 0), "read_only": True,
            "decisions": dict(decisions or {}),
            "distributions": dict(dists or {}),
            "strengths": dict(strengths or {}),
        }
    return s


def _canal(state, option, prob=1.0):
    """只给一个漕运选项概率（其余均分余额，保证是合法分布）。"""
    others = [o for o in CANAL_ROUTE_LOSS_MULT if o != option]
    dist = {option: prob}
    if prob < 1.0:
        for o in others:
            dist[o] = (1.0 - prob) / len(others)
    return _state(state, dists={"canal_reroute": dist})


def _local_treasury_sum(s):
    from core.settlement_common import _local_treasury_pool

    return sum(_local_treasury_pool(_p) for _p in s.prefectures.values())


# ---------------------------------------------------------------------------
# ① 读取点：中性 + 概率期望
# ---------------------------------------------------------------------------
def test_loss_mult_is_neutral_without_distribution():
    assert _canal_route_loss_mult(_NoState()) == 1.0
    assert _canal_route_loss_mult(_fresh()) == 1.0                 # 无观测副本
    assert _canal_route_loss_mult(_state(_fresh(), dists={})) == 1.0


def test_loss_mult_is_probability_expectation():
    """纯等疏浚 = 1.00；对半 = 0.90；纯陆路 = 0.80（期望，不是 argmax）。"""
    p_wait = _canal_route_loss_mult(_canal(_fresh(), "wait_dredge"))
    p_half = _canal_route_loss_mult(_canal(_fresh(), "overland_cart", 0.5))
    p_over = _canal_route_loss_mult(_canal(_fresh(), "overland_cart"))
    # 天意扰子同月同源（"national"）⇒ 比值关系稳定
    assert abs(p_wait - 1.0) < 0.06
    assert p_over < p_half < p_wait
    assert abs((p_half / p_wait) - 0.90) < 0.03
    assert abs((p_over / p_wait) - 0.80) < 0.03


def test_rates_are_fixed_point_not_float():
    """0.01 贯/石、3% 补粮都按千分位定点实现（不落 float 字段）。"""
    assert _canal_overland_cost(1_234_567) == (1_234_567 * CANAL_OVERLAND_COST_PERMILLE) // 1000
    assert _canal_borrow_target(1_234_567) == (1_234_567 * CANAL_BORROW_GRAIN_PERMILLE) // 1000
    assert isinstance(_canal_overland_cost(999), int)
    assert isinstance(_canal_borrow_target(999), int)


# ---------------------------------------------------------------------------
# ①a 陆运脚钱：守恒 + 概率缩放 + 国库封顶
# ---------------------------------------------------------------------------
def test_overland_freight_is_conserved_and_scaled(base_state):
    from core import money

    s = _canal(base_state, "overland_cart")
    m0 = money.m_all(s)
    t0 = int(s.treasury)
    spent = _pay_overland_freight(s, [], 1_000_000)
    assert spent > 0
    assert int(s.treasury) == t0 - spent, "国库扣减 == 实付"
    assert abs(money.m_all(s) - m0) < 1e-4, "货币不得凭空消失（对手方=商人 POP）"
    assert int(s.statistics["canal_overland_cost"]) == spent

    s_half = _canal(base_state, "overland_cart", 0.5)
    spent_half = _pay_overland_freight(s_half, [], 1_000_000)
    assert 0 < spent_half < spent, "概率减半 ⇒ 期望脚钱减少"


def test_overland_freight_zero_without_probability(base_state):
    assert _pay_overland_freight(_canal(base_state, "wait_dredge"), [], 1_000_000) == 0


def test_overland_freight_capped_by_treasury(base_state):
    s = _canal(base_state, "overland_cart")
    s.treasury = 10
    spent = _pay_overland_freight(s, [], 1_000_000)
    assert spent <= 10


# ---------------------------------------------------------------------------
# ①b 和籴借兑：钱粮双守恒 + 概率缩放 + 缺失价中性
# ---------------------------------------------------------------------------
def test_borrow_grain_is_conserved_and_scaled(base_state):
    s = _canal(base_state, "borrow_grain")
    lt0 = _local_treasury_sum(s)
    g0 = int(s.granary)
    bought = _buy_grain_via_local_treasury(s, [], 1_000_000)
    if bought > 0:
        assert int(s.granary) == g0 + bought, "补粮只增加太仓（入仓，非支出）"
        assert _local_treasury_sum(s) <= lt0, "钱只能从地方府库出"
        assert int(s.statistics["canal_borrow_grain"]) == bought

    s_half = _canal(base_state, "borrow_grain", 0.5)
    bought_half = _buy_grain_via_local_treasury(s_half, [], 1_000_000)
    assert 0 <= bought_half <= bought


def test_borrow_grain_zero_when_price_missing(base_state):
    s = _canal(base_state, "borrow_grain")
    s.grain_price = None
    assert _buy_grain_via_local_treasury(s, [], 1_000_000) == 0


def test_borrow_grain_zero_without_probability(base_state):
    assert _buy_grain_via_local_treasury(_canal(base_state, "wait_dredge"), [], 1_000_000) == 0


# ---------------------------------------------------------------------------
# ② 募流民：强度缩放 + 人守恒 + 无实体军还原
# ---------------------------------------------------------------------------
def test_recruit_scales_with_gate_strength(base_state):
    def run(p):
        s = _state(base_state, strengths={"recruit_refugees_to_soldiers_gate": p})
        n = _recruit_refugees_as_xiangjun(s, [])
        return s, n

    s_lo, n_lo = run(0.55)          # 超阈强度 0.10
    s_hi, n_hi = run(0.95)          # 超阈强度 0.90
    assert 0 <= n_lo < n_hi, (n_lo, n_hi)
    for s in (s_lo, s_hi):
        for _name, p in s.prefectures.items():
            assert int(p.get("refugees", 0) or 0) >= 0
        assert n_hi <= RECRUIT_REFUGEE_CAP_PER_ROUTE * len(s.prefectures)


def test_recruit_neutral_without_strength(base_state):
    for st in (_state(base_state, strengths={}), _state(base_state, decisions={})):
        assert _recruit_refugees_as_xiangjun(st, []) == 0


def test_recruit_route_without_unit_restores_refugees(base_state):
    """无实体军的地：不扣流民、不造单位（人口不得凭空消失）。"""
    s = _state(base_state, strengths={"recruit_refugees_to_soldiers_gate": 0.99})
    units = set(u.station for u in s.army_units)
    no_unit = [n for n in s.prefectures if n not in units]
    assert no_unit, "本局应存在无实体军的地（否则本用例失去意义）"
    before = {n: int(s.prefectures[n].get("refugees", 0) or 0) for n in no_unit}
    _recruit_refugees_as_xiangjun(s, [])
    for n in no_unit:
        assert int(s.prefectures[n].get("refugees", 0) or 0) == before[n], n


# ---------------------------------------------------------------------------
# ③ 宋侧饥荒逃散放大（概率版）
# ---------------------------------------------------------------------------
def test_flee_after_verdict_pure_cases():
    """纯函数：倍数随概率连续（p=0 ⇒ 1.0，p=1 ⇒ MULT），缺失/NaN ⇒ 1.0。"""
    from core.ai.tiandao_effects import FLEE_VERDICT_MULT

    assert _flee_after_verdict(0, 0, 0.0) == 1.0
    assert _flee_after_verdict(0, 0, None) == 1.0
    assert abs(_flee_after_verdict(0, 0, 1.0) - FLEE_VERDICT_MULT) < 1e-9
    mid = _flee_after_verdict(0, 0, 0.5)
    assert 1.0 < mid < FLEE_VERDICT_MULT
    assert _flee_after_verdict(0, 0, 2.0) == _flee_after_verdict(0, 0, 1.0)   # 钳到 [0,1]
    assert _flee_after_verdict(0, 0, -1.0) == 1.0


def test_song_famine_flee_scales_with_probability(base_state, monkeypatch):
    """p(flee_refugee) 越大，饥荒逃散越多；p=0 与基线一致；人总量不变。"""
    from core import settlement_common

    monkeypatch.setattr(settlement_common, "food_insecure_headcount",
                        lambda pops, price: {"农": 1000})

    def run(dists):
        s = _state(base_state, dists=dists, turn=11)
        s.month = 11
        log = []
        random.seed(4242)
        _settle_granary(s, log)
        ref = sum(int(p.get("refugees", 0) or 0) for p in s.prefectures.values())
        nong = sum(int(p["pops"]["农"]["size"]) for p in s.prefectures.values())
        return ref, nong, log

    r0, a0, log0 = run({})
    rh, ah, logh = run({"farmer_destitution_path":
                        {"mortgage_land": 0.5, "flee_refugee": 0.5}})
    r1, a1, log1 = run({"farmer_destitution_path": {"flee_refugee": 1.0}})
    assert r0 < rh < r1, (r0, rh, r1)
    assert a0 > ah > a1, "农 POP 应同步减少（只转移人口）"
    assert (r0 + a0) == (r1 + a1), "人口总量不得凭空增减"
    assert any("举家逃亡" in x for x in log1)
    assert not any("举家逃亡" in x for x in log0)


# ---------------------------------------------------------------------------
# ④ 中性档 ≡ 无记录（逐字节）
# ---------------------------------------------------------------------------
def _granary_run(base, *, dists=None, strengths=None, month=3):
    random.seed(4242)
    s = _state(base, dists=dists, strengths=strengths)
    s.month = month
    log = []
    _settle_granary(s, log)
    return s, log


def test_neutral_is_byte_identical_to_no_record(base_state):
    a, log_a = _granary_run(base_state)
    b, log_b = _granary_run(base_state, dists={}, strengths={})
    assert int(a.granary) == int(b.granary)
    assert int(a.treasury) == int(b.treasury)
    assert dict(a.granary_stats) == dict(b.granary_stats)
    assert log_a == log_b, "中性档不得新增任何结算日志"
    for _k in ("canal_overland_cost", "canal_borrow_cost", "canal_borrow_grain"):
        assert _k not in a.statistics and _k not in b.statistics


# ---------------------------------------------------------------------------
# ⑤ 端到端接线
# ---------------------------------------------------------------------------
def test_granary_overland_wiring(base_state):
    base, _ = _granary_run(base_state)
    over, log = _granary_run(base_state, dists={"canal_reroute": {"overland_cart": 1.0}})
    assert int(over.statistics.get("canal_overland_cost", 0)) > 0
    assert any("陆运" in x for x in log)
    assert int(over.treasury) < int(base.treasury)


def test_granary_borrow_wiring(base_state):
    bor, log = _granary_run(base_state, dists={"canal_reroute": {"borrow_grain": 1.0}})
    assert int(bor.granary) >= 0
    assert any("和籴借兑" in x for x in log)


def test_full_month_bing_size_derives_from_troops(base_state, monkeypatch):
    from core.ai.tiandao_facade import TianDaoFacade
    from core.settlement import run_monthly_settlement

    s = _state(base_state, strengths={"recruit_refugees_to_soldiers_gate": 0.99},
               dists={"canal_reroute": {"wait_dredge": 1.0}})

    def _neutral(cls, st):
        rec = {"turn": getattr(st, "turn", 0), "read_only": True, "decisions": {},
               "distributions": {}, "strengths": {}}
        st._tiandao_observe = rec
        return rec

    monkeypatch.setattr(TianDaoFacade, "observe_monthly", classmethod(_neutral))
    run_monthly_settlement(s)
    for route, p in s.prefectures.items():
        expected = sum(u.troops for u in s.army_units if u.station == route and u.troops > 0)
        assert p["pops"]["兵"]["size"] == expected, f"{route}: 兵.size 双计/漂移"
