# -*- coding: utf-8 -*-
"""批次 2 回归：S2 / S7 / S8 / 定员下限（2026-10-01 全审落地）。

主题：缺失值不得伪造（缺失 ≠ 0 ≠ 1.0）、非有限值不得参与乘算、失败路径必须零副作用。
"""
import math
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState            # noqa: E402
from core.legacy_mechanic import init_legacies     # noqa: E402


@pytest.fixture()
def state():
    s = GameState("史实")
    init_legacies(s)
    return s


def _strip_all_literacy(state):
    """清掉所有 per-POP 识字率与state 级读数（模拟旧档/未迁移）。"""
    state.literacy = None
    for pref in state.prefectures.values():
        for slot in (pref.get("pops") or {}).values():
            if isinstance(slot, dict):
                slot.pop("literacy", None)


# ---------------------------------------------------------------- S2 识字率不伪造
def test_s2_missing_literacy_not_fabricated(state):
    """S2：识字率读数缺失时不得用 `calc_arrival_rate()*100` 伪造（实测造出 58.75）。"""
    from core.decree_effect import CIVIL_FLOOR, CIVIL_LITERACY_W, effect_channels
    _strip_all_literacy(state)
    ch = effect_channels(state, route=next(iter(state.prefectures)), kind="民政")
    assert ch.get("literacy_defined") is False, "缺失维度必须显式标注未定义"
    assert ch["literacy"] is None
    assert CIVIL_LITERACY_W > 0
    assert CIVIL_FLOOR <= ch["civil_mult"] <= 1.0


def test_s2_civil_mult_matches_hand_computed_without_literacy(state):
    """S2：缺识字率时 civil_mult == FLOOR + 民心项（精确等式，不含伪造项）。"""
    from core.decree_effect import CIVIL_FLOOR, CIVIL_SAT_W, _clamp, effect_channels
    _strip_all_literacy(state)
    route = next(iter(state.prefectures))
    ch = effect_channels(state, route=route, kind="民政")
    pub = state.prefectures[route].get("public_support")
    sat = float(pub) if pub is not None else float(state.population_satisfaction)
    expect = round(_clamp(CIVIL_FLOOR + CIVIL_SAT_W * _clamp(sat, 0.0, 100.0) / 100.0,
                          CIVIL_FLOOR, 1.0), 4)
    assert ch["civil_mult"] == expect, f"缺识字率时不应含识字率项：{ch['civil_mult']} != {expect}"


def test_s2_reading_present_path_not_regressed(state):
    """S2 反向：有读数时仍按 民心 + 识字率 两项计算，标注 defined=True。"""
    from core.decree_effect import (CIVIL_FLOOR, CIVIL_SAT_W, CIVIL_LITERACY_W,
                                   _clamp, _literacy_channel, effect_channels)
    route = next(iter(state.prefectures))
    ch = effect_channels(state, route=route, kind="民政")
    assert ch.get("literacy_defined") is True, "有 per-POP 读数时应为已定义"
    lit = _literacy_channel(state, route)
    assert lit is not None
    pub = state.prefectures[route].get("public_support")
    sat = float(pub) if pub is not None else float(state.population_satisfaction)
    expect = round(_clamp(CIVIL_FLOOR
                          + CIVIL_SAT_W * _clamp(sat, 0.0, 100.0) / 100.0
                          + CIVIL_LITERACY_W * _clamp(lit, 0.0, 100.0) / 100.0,
                          CIVIL_FLOOR, 1.0), 4)
    assert ch["civil_mult"] == expect


def test_s2_nan_literacy_not_treated_as_full(state):
    """S2 + 非有限值：NaN 识字率不得被当成 100%（min/max 遇 NaN 会返回边界）。"""
    from core.decree_effect import effect_channels
    _strip_all_literacy(state)
    state.literacy = float("nan")
    ch = effect_channels(state, route=next(iter(state.prefectures)), kind="民政")
    assert ch.get("literacy_defined") is False
    assert ch["civil_mult"] < 1.0, "NaN 不得变成满值"


# ---------------------------------------------------------------- S7 原子性
def test_s7_failed_transfer_has_zero_side_effects(state):
    """S7：民间钱池不足以摊满时返回 False 且**零副作用**（旧实现先扣后失败）。"""
    from core.free_effect import _apply_money_delta
    road = next(iter(state.prefectures))
    pool = state.prefectures[road]["pops"]["农"]
    pool["wealth"] = 1_000
    before_wealth = int(pool["wealth"])
    before_tre = int(state.treasury)
    assert _apply_money_delta(state, 999_999_999) is False
    assert int(pool["wealth"]) == before_wealth, "失败路径不得改动钱池"
    assert int(state.treasury) == before_tre, "失败路径不得改动国库"


def test_s7_normal_transfer_conserves(state):
    """S7 反向：可承受的划转仍要守恒落地（国库入账 = 民间被摊扣）。"""
    from core.free_effect import _apply_money_delta, _money_pools
    pools = _money_pools(state)
    for pp in pools:
        pp["wealth"] = 100_000
    total_before = sum(int(pp["wealth"]) for pp in pools)
    tre_before = int(state.treasury)
    amount = 1_000
    assert _apply_money_delta(state, amount) is True
    total_after = sum(int(pp["wealth"]) for pp in pools)
    assert total_after == total_before - amount
    assert int(state.treasury) == tre_before + amount


def test_s7_empty_pool_returns_false(state):
    """S7：无民间钱池时返回 False 且不动国库。"""
    from core import free_effect as FE
    before = int(state.treasury)
    orig = FE._money_pools
    FE._money_pools = lambda st: []
    try:
        assert FE._apply_money_delta(state, 500) is False
        assert int(state.treasury) == before
    finally:
        FE._money_pools = orig


# ---------------------------------------------------------------- S8 钱粮/识字通道
def test_s8_research_literacy_nan_not_full_bonus(state):
    """S8：`state.literacy = NaN` 不得让研发速率拿到满额识字率加成。"""
    from content.data_tech import TECH_RESEARCH_LITERACY_W
    from core.settlement_tech import _research_rate_mult
    node = (0, "文教", "", 0, 0, {}, 1, 0, 0, 0)
    state.literacy = float("nan")
    mult_nan = _research_rate_mult(state, node, {}, log=[])
    state.literacy = 100.0
    mult_full = _research_rate_mult(state, node, {}, log=[])
    state.literacy = 0.0
    mult_zero = _research_rate_mult(state, node, {}, log=[])
    assert mult_nan == pytest.approx(mult_zero), "NaN 应按无加成处理，不得等同满值"
    assert mult_full > mult_nan
    assert TECH_RESEARCH_LITERACY_W > 0


def test_s8_missing_literacy_logged_not_faked(state):
    """S8：缺失识字率要在玩家可见日志里留痕，不静默当 0 处理。"""
    from core.settlement_tech import _research_rate_mult
    node = (0, "文教", "", 0, 0, {}, 1, 0, 0, 0)
    state.literacy = None
    log = []
    _research_rate_mult(state, node, {}, log=log)
    assert any("[研发]" in line and "识字率" in line for line in log), \
        f"缺失识字率应留痕，实际日志：{log}"
    assert getattr(state, "_settle_warned", None), "诊断键也应记录"


def test_s8_research_fee_channel_strict(state):
    """S8：研发月费通道与settlement.py 同为**严格模式**（通道坏≠经费不济）。"""
    import inspect
    from core.domains.construction import settlement_tech as ST
    src = inspect.getsource(ST)
    assert "raise_on_unavailable=True" in src, "研发月费必须开启严格模式"
    # 且严格模式异常不得被吞成 idle_months（须经note_settlement_error 留痕）
    assert "MoneyChannelUnavailable" in src


# ---------------------------------------------------------------- 定员下限加固
def test_quota_never_negative_on_hostile_save(state):
    """定员下限：越界存档（手改 mult=-1）不得让 posts_quota 变负、官制冻结。"""
    from core import officialdom as OD
    OD.ensure_all(state)
    OD.ensure_quota(state)
    positive = int(state.posts_quota)
    assert positive > 0
    state.institution_params["posts_quota_mult"] = -1.0     # 绕过 set_param 的钳位
    OD.rescale_quota(state)
    assert int(state.posts_quota) >= 0, "定员不得为负"
    state.institution_params["posts_quota_mult"] = 1.0
    OD.rescale_quota(state)
    assert int(state.posts_quota) == positive, "参数恢复后定员应回到原值"


def test_quota_sane_path_unchanged(state):
    """反向：正规 clamp 路径的定员不受加固影响。"""
    from core import institution as INST
    from core import officialdom as OD
    OD.ensure_all(state)
    OD.ensure_quota(state)
    base = int(state.posts_quota)
    for mult, expect_ge_zero in ((0.4, True), (1.0, True), (1.6, True)):
        INST.set_param(state, "posts_quota_mult", mult)
        OD.rescale_quota(state)
        assert int(state.posts_quota) >= 0
        assert math.isfinite(float(state.posts_quota))
    INST.set_param(state, "posts_quota_mult", 1.0)
    OD.rescale_quota(state)
    assert int(state.posts_quota) == base