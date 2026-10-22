# -*- coding: utf-8 -*-
"""B1-b：仓储域两个天道消费点改「概率连续」＋ D3 逃散口径统一 ＋ S2/S3 纪律修复。

审查项与验收基准
----------------
- **B1-1 平粜**：`_changping_sell_ratio` 按门闸**超阈强度**连续缩放（0 ⇒ 不平粜，1 ⇒ 满额）；
  同一档（都判"开仓"）不同概率 ⇒ 平粜回收额**不同**。
- **B1-2 仓场贪墨**：`_granary_corruption_factor` = `1 − (1−s)×0.5`（连续）；同档不同概率 ⇒ 折损额不同。
- **D3 逃散**：宋侧扰子**折进增量** `1 + (amp−1)×jit`，与外邦侧同构；p=0 ⇒ **精确 1.0**（不吃扰子）。
- **S2**：`_pay_overland_freight` 的国库扣减走单点 `GameState.change_treasury`（返回实际生效 Δ），
  `treasury ≥ 0` 且**商人 POP 增量 == 国库减量**。
- **S3**：和籴计划阶段读 `grain_get`（与写入同口径）；`grain_add` 返回 int（原 `is None` 分支是死代码）。
- **缺失语义不变**：无 `_tiandao_observe` ⇒ 平粜满额 / 贪墨不折减（与改前逐字节等价）；
  旧格式记录（只有 `decisions`、无 `strengths`）⇒ 回退旧二值口径。
"""
from __future__ import annotations

import copy
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.settlement_granary import (  # noqa: E402
    GATE_THRESHOLD,
    GRANARY_CORRUPTION_MIN_FACTOR,
    _buy_grain_via_local_treasury,
    _changping_sell_ratio,
    _flee_after_verdict,
    _flee_amp_with_jitter,
    _granary_corruption_factor,
    _pay_overland_freight,
    _settle_granary,
)
from core.ai.tiandao_effects import FLEE_VERDICT_MULT  # noqa: E402


# ---------------------------------------------------------------------------
# 夹具 / 工具
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def base_state():
    from core.commands import new_game

    return new_game()


class _NoState:
    """无任何属性的替身（缺失语义：无 `_tiandao_observe`）。"""


def _state(base, decisions=None, strengths=None, distributions=None, legacy=None):
    """deepcopy 一局并注入观测副本。

    - 全 None ⇒ **无记录**（最贴近旧测试/旧档）；
    - `legacy` 非 None ⇒ 旧格式记录（只有 `decisions`，无 `strengths`）；
    - 否则构造带 `strengths` / `distributions` 的新格式记录（模拟 `observe_monthly`）。
    """
    s = copy.deepcopy(base)
    if legacy is not None:
        s._tiandao_observe = {"decisions": dict(legacy)}
    elif decisions is not None or strengths is not None or distributions is not None:
        s._tiandao_observe = {"turn": 0, "read_only": True, "context_defined": True,
                              "decisions": dict(decisions or {}),
                              "strengths": dict(strengths or {}),
                              "distributions": dict(distributions or {})}
    return s


def _granary_run(base, *, decisions=None, strengths=None, distributions=None,
                 legacy=None, month=3, seed=4242, prep=None):
    random.seed(seed)
    s = _state(base, decisions, strengths, distributions, legacy=legacy)
    s.month = month                      # 三运制发纲月 ⇒ 漕运真有起运量
    if prep is not None:
        prep(s)
    log = []
    _settle_granary(s, log)
    return s, log


def _merchant_wealth(s):
    return sum(int(_p["pops"]["商人"]["wealth"]) for _p in s.prefectures.values())


# ---------------------------------------------------------------------------
# B1-1 平粜：按强度连续
# ---------------------------------------------------------------------------
def test_changping_ratio_missing_record_is_full_neutral():
    """缺失语义不变：无记录 ⇒ 1.0（＝改前"允许满额平粜"），不是新造的默认档。"""
    assert _changping_sell_ratio(_NoState()) == 1.0


def test_changping_ratio_legacy_record_is_binary(base_state):
    """旧格式记录（只有 decisions）⇒ 回退旧二值：False ⇒ 0（不卖）、True ⇒ 1（满额）。"""
    s = _state(base_state, legacy={"changping_intervene_gate": False})
    assert _changping_sell_ratio(s) == 0.0
    s = _state(base_state, legacy={"changping_intervene_gate": True})
    assert _changping_sell_ratio(s) == 1.0
    # 有 strengths 容器但该门面未记录 ⇒ 同样回退旧二值（不臆造强度）
    s = _state(base_state, decisions={"changping_intervene_gate": False}, strengths={})
    assert _changping_sell_ratio(s) == 0.0


def test_changping_ratio_is_continuous_in_strength(base_state):
    """超阈强度：p=0.55 ⇒ 0.10、p=0.75 ⇒ 0.50、p=0.95 ⇒ 0.90；p≤0.50 ⇒ 0（不平粜）。"""
    for p, expected in ((0.55, 0.10), (0.75, 0.50), (0.95, 0.90), (1.0, 1.0)):
        s = _state(base_state, strengths={"changping_open": p})
        assert _changping_sell_ratio(s) == pytest.approx(expected), p
    for p in (GATE_THRESHOLD, 0.30, 0.0):
        s = _state(base_state, strengths={"changping_open": p})
        assert _changping_sell_ratio(s) == 0.0, p


def test_changping_same_tier_different_probability_changes_volume(base_state):
    """同一档（都判"开仓平粜"）但概率不同 ⇒ 回收额不同（不是二值开关）。"""

    def run(strength):
        def prep(s):
            for _p in s.prefectures.values():
                _p["grain_price"] = 3.0
                _p["changping_stock"] = 10_000

        s, log = _granary_run(base_state, strengths={"changping_open": strength}, prep=prep)
        return int(s.statistics.get("changping_recycled", 0) or 0), log

    low, _ = run(0.65)
    high, _ = run(0.95)
    assert low > 0 and high > low, f"平粜幅度未随强度变化：0.65⇒{low}, 0.95⇒{high}"


# ---------------------------------------------------------------------------
# B1-2 仓场贪墨：连续折减
# ---------------------------------------------------------------------------
def test_corruption_factor_missing_record_is_one():
    assert _granary_corruption_factor(_NoState()) == 1.0


def test_corruption_factor_legacy_record_is_binary(base_state):
    s = _state(base_state, legacy={"granary_corruption_check": False})
    assert _granary_corruption_factor(s) == GRANARY_CORRUPTION_MIN_FACTOR
    s = _state(base_state, legacy={"granary_corruption_check": True})
    assert _granary_corruption_factor(s) == 1.0
    s = _state(base_state, decisions={"granary_corruption_check": False}, strengths={})
    assert _granary_corruption_factor(s) == GRANARY_CORRUPTION_MIN_FACTOR


def test_corruption_factor_is_continuous_in_strength(base_state):
    """`1 − (1−s)×0.5`：s=0 ⇒ 0.5（不归零）、s=1 ⇒ 1.0、中间连续。"""
    for p, s_exp in ((0.55, 0.10), (0.75, 0.50), (0.95, 0.90)):
        s = _state(base_state, strengths={"granary_corruption": p})
        expected = 1.0 - (1.0 - s_exp) * GRANARY_CORRUPTION_MIN_FACTOR
        assert _granary_corruption_factor(s) == pytest.approx(expected), p
    s = _state(base_state, strengths={"granary_corruption": 1.0})
    assert _granary_corruption_factor(s) == 1.0
    s = _state(base_state, strengths={"granary_corruption": 0.30})
    assert _granary_corruption_factor(s) == GRANARY_CORRUPTION_MIN_FACTOR


def test_corruption_same_tier_different_probability_changes_loss(base_state):
    """同一档（都判"有贪墨"）但概率不同 ⇒ 本月本色折损额不同。"""

    def run(strength):
        s, log = _granary_run(base_state, strengths={"granary_corruption": strength})
        return int(s.granary_stats.get("corruption_grain", 0) or 0), log

    low, _ = run(0.65)
    high, _ = run(0.95)
    assert low > 0 and high > low, f"贪墨折损未随强度变化：0.65⇒{low}, 0.95⇒{high}"


# ---------------------------------------------------------------------------
# D3 逃散公式统一：扰子折进增量、p=0 精确 1.0
# ---------------------------------------------------------------------------
def test_flee_amp_neutral_is_exactly_one():
    """p=0 / 缺失 ⇒ 倍数精确 1.0；扰子折进增量 ⇒ 恒 1.0（不吃扰子）。"""
    assert _flee_after_verdict(0, 0, 0.0) == 1.0
    assert _flee_after_verdict(0, 0, None) == 1.0
    assert _flee_after_verdict(0, 0, float("nan")) == 1.0
    for jit in (0.90, 0.97, 1.0, 1.10):
        assert _flee_amp_with_jitter(1.0, jit) == 1.0


def test_flee_amp_matches_external_side_formula():
    """宋侧组合 ≡ 外邦侧 `1 + (MULT−1)×p×jit`（同一口径，逐值相等）。"""
    for p in (0.0, 0.2, 0.5, 1.0):
        for jit in (0.90, 1.0, 1.10):
            base = _flee_after_verdict(0, 0, p)
            got = _flee_amp_with_jitter(base, jit)
            assert got == pytest.approx(1.0 + (FLEE_VERDICT_MULT - 1.0) * p * jit)


def test_flee_amp_never_below_one_when_probability_positive():
    """扰子乘在增量上 ⇒ 幅度恒 ≥ 1.0；旧写法 `amp × jit` 在 p→0 时会掉到 1.0 以下。"""
    base = _flee_after_verdict(0, 0, 0.01)      # ≈ 1.005
    assert base * 0.90 < 1.0, "旧口径（整体乘扰子）确实会把逃散压到 1:1 以下"
    for jit in (0.90, 1.0, 1.10):
        amp = _flee_amp_with_jitter(base, jit)
        assert amp >= 1.0 and amp > 1.0


# ---------------------------------------------------------------------------
# S2 国库单点 + 守恒
# ---------------------------------------------------------------------------
def _canal_mix(option: str, p: float) -> dict:
    rest = max(0.0, 1.0 - p)
    return {"canal_reroute": {option: p, "wait_dredge": rest}}


def test_overland_freight_conserved_with_probability(base_state):
    """`treasury ≥ 0` 且商人 POP 增量 == 国库减量（按概率缩放的期望额）。"""
    s = _state(base_state, distributions=_canal_mix("overland_cart", 0.5))
    t0, m0 = int(s.treasury), _merchant_wealth(s)
    log = []
    paid = _pay_overland_freight(s, log, 5_000_000)
    assert paid == 25_000                       # 50,000 × p(0.5)
    assert int(s.treasury) >= 0
    assert t0 - int(s.treasury) == paid
    assert _merchant_wealth(s) - m0 == paid
    assert int(s.statistics["canal_overland_cost"]) == paid
    assert any("陆运" in _x for _x in log)


def test_overland_freight_goes_through_change_treasury(base_state, monkeypatch):
    """S2：国库扣减必须走 `GameState.change_treasury` 单点（不再直写 `state.treasury`）。"""
    from core.game_state import GameState

    calls = []
    original = GameState.change_treasury

    def wrapper(self, delta):
        calls.append(int(delta))
        return original(self, delta)

    monkeypatch.setattr(GameState, "change_treasury", wrapper)
    s = _state(base_state, distributions=_canal_mix("overland_cart", 1.0))
    t0 = int(s.treasury)
    paid = _pay_overland_freight(s, [], 5_000_000)
    assert paid > 0 and calls, "未走 change_treasury 单点"
    assert -calls[0] == paid, "首笔单点调用应就是国库扣减额"
    assert t0 - int(s.treasury) == paid


def test_overland_freight_refunds_uncredited_part(base_state, monkeypatch):
    """分摊不足（商人侧未到账）⇒ 未到账部分退回国库，钱不得凭空消失。"""
    import core.settlement_granary as mod

    monkeypatch.setattr(mod, "_distribute_pop_wealth", lambda *a, **k: 0)
    s = _state(base_state, distributions=_canal_mix("overland_cart", 1.0))
    t0 = int(s.treasury)
    log = []
    assert _pay_overland_freight(s, log, 5_000_000) == 0
    assert int(s.treasury) == t0
    assert any("无商人可收款" in _x for _x in log)


def test_overland_freight_capped_by_treasury(base_state):
    s = _state(base_state, distributions=_canal_mix("overland_cart", 1.0))
    s.change_treasury(100 - int(s.treasury))     # 前置也走单点（不直写账户）
    paid = _pay_overland_freight(s, [], 5_000_000)
    assert paid == 100 and int(s.treasury) == 0


# ---------------------------------------------------------------------------
# S3 和籴：计划阶段与写入同口径（grain_get）
# ---------------------------------------------------------------------------
def _zero_all_pop_grain(s):
    from core.foundation.ledger import grain_bridge as gb

    for _p in s.prefectures.values():
        for _o in _p["pops"].values():
            if isinstance(_o, dict):
                gb.grain_set(_o, 0, s)


def test_borrow_plan_reads_grain_get_not_legacy_column(base_state):
    """S3：已迁移载体（`goods[米]`）与旧 `.grain` 并存时，计划阶段必须读 `grain_get`。

    构造：目标 POP 的 `goods[米]=800`，而旧 `.grain` 仍是 6,673,125（迁移后未清）。
    读 `grain_get` ⇒ 只当 800 石可用；旧写法读 `pp["grain"]` ⇒ 会按 6.6M 下计划。
    """
    from core.foundation.ledger import grain_bridge as gb
    from core.foundation.ledger import pop_bridge as pb

    def run(with_bucket: bool) -> int:
        s = _state(base_state, distributions=_canal_mix("borrow_grain", 1.0))
        _zero_all_pop_grain(s)
        route = next(iter(s.prefectures))
        farmer = s.prefectures[route]["pops"]["农"]
        if with_bucket:
            # 构造「已迁移但旧列未清」：goods[米]=800（真载体）+ .grain=6,000,000（陈旧旧列）
            assert pb.pop_obj_goods_add(s, farmer, "米", 800) == 800
            pb.pop_obj_set(s, farmer, "grain", 6_000_000)
            assert gb.grain_get(farmer) == 800
            assert int(farmer.get("grain", 0) or 0) == 6_000_000, \
                "旧列确实远大于载体粮（否则本用例失去意义）"
        else:
            gb.grain_set(farmer, 800, s)
            assert gb.grain_get(farmer) == 800
        return _buy_grain_via_local_treasury(s, [], 5_000_000)

    with_bucket = run(True)
    legacy = run(False)
    assert legacy == 800
    assert with_bucket == legacy, (
        f"计划阶段未按 grain_get 读数：载体 800 石却买了 {with_bucket} 石（旧列 6.6M）")


def test_grain_add_never_returns_none(base_state):
    """S3：`grain_bridge.grain_add` 返回写后值（int），原 `is None` 回落分支为死代码。"""
    from core.foundation.ledger import grain_bridge as gb

    s = _state(base_state)
    pop = next(iter(s.prefectures.values()))["pops"]["农"]
    for delta in (0, -1, 1, -10**9):
        assert isinstance(gb.grain_add(pop, delta, s), int), delta


def test_borrow_conservation_with_probability(base_state):
    """和籴按概率缩放时仍是「民粮 − ↔ 太仓 +」「府库 − ↔ 民间 +」两腿成对。"""
    from core.settlement_granary import _local_treasury_pool

    s = _state(base_state, distributions=_canal_mix("borrow_grain", 1.0))
    lt0 = sum(_local_treasury_pool(_p) for _p in s.prefectures.values())
    pg0 = sum(int(_o.get("grain", 0) or 0) for _p in s.prefectures.values()
              for _o in _p["pops"].values() if isinstance(_o, dict))
    gr0 = int(s.granary)
    bought = _buy_grain_via_local_treasury(s, [], 5_000_000)
    paid = int(s.statistics["canal_borrow_cost"])
    assert bought > 0 and paid > 0
    assert int(s.granary) - gr0 == bought
    assert pg0 - sum(int(_o.get("grain", 0) or 0) for _p in s.prefectures.values()
                     for _o in _p["pops"].values() if isinstance(_o, dict)) == bought
    assert lt0 - sum(_local_treasury_pool(_p) for _p in s.prefectures.values()) == paid


# ---------------------------------------------------------------------------
# 缺失语义：无记录 ≡ 旧格式「真/真」（逐字节）
# ---------------------------------------------------------------------------
def test_missing_record_equals_legacy_true_true(base_state):
    """无 `_tiandao_observe` ≡ 旧格式 decisions 全 True：granary/国库/统计/日志全等。"""
    a, log_a = _granary_run(base_state)
    b, log_b = _granary_run(base_state, legacy={"changping_intervene_gate": True,
                                                "granary_corruption_check": True})
    assert int(a.granary) == int(b.granary)
    assert int(a.treasury) == int(b.treasury)
    assert dict(a.granary_stats) == dict(b.granary_stats)
    assert log_a == log_b
    # 旧格式 decisions=False 仍按旧二值生效（兼容路径未被新逻辑吃掉）
    c, log_c = _granary_run(base_state, legacy={"changping_intervene_gate": False,
                                                "granary_corruption_check": False})
    assert int(c.granary) >= int(a.granary)
    assert any("仓场" in _x for _x in log_c)
