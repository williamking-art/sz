# -*- coding: utf-8 -*-
"""B4 · 营造造价/工期/赶工预算的定向回归（规格 `market-civilian-economy` B4-3/4/5）

锁定用户定论：
- **造价挂材料**（`Σ材料量×单价` 单一真源；单价缺失 → `unresolved`，**不按 0 计价**）；
- **加大投入缩短工期**（凹函数 α=0.5：投入×2 → 工期÷1.41；单调、边际递减）；
- **总额封顶**（累计不超基准造价）；
- **赶工预算独立且可退**（溢价不占基准；未用余额能算出应退额）。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.construction_cost import (  # noqa: E402
    ACCEL_ALPHA, accel_speed_mult, base_material_cost, monthly_due,
    plan_construction_cost, rush_budget_spent, rush_refund,
)


# ====================================================== B4-3 造价挂材料
def test_base_cost_is_sum_of_material_times_price():
    r = base_material_cost(materials={"布": 100.0, "绸": 10.0})
    # 布 base=120、绸 base=800（内容数据表）
    assert r["unresolved"] is False
    assert r["total"] == pytest.approx(100 * 120 + 10 * 800)
    assert len(r["lines"]) == 2


def test_missing_price_is_unresolved_not_zero_cost():
    """单价缺失 → `unresolved`，**不按 0 计价**（否则低估造价）。"""
    r = base_material_cost(materials={"不存在之物": 100.0})
    assert r["unresolved"] is True
    assert "不存在之物" in r["missing_price"]
    assert r["total"] == pytest.approx(0.0)


def test_zero_qty_material_ignored():
    r = base_material_cost(materials={"布": 0})
    assert r["total"] == pytest.approx(0.0)


# ====================================================== B4-4 凹函数加速
def test_accel_is_neutral_at_intensity_one():
    assert accel_speed_mult(1.0) == pytest.approx(1.0)


def test_accel_doubles_halves_duration():
    """投入 ×2 → 工期 ÷1.41（α=0.5）。"""
    assert accel_speed_mult(2.0) == pytest.approx(math_pow(2.0, ACCEL_ALPHA))
    assert accel_speed_mult(2.0) == pytest.approx(1.414, abs=0.01)


def test_accel_is_monotonic_sublinear():
    """单调递增且**相对**增益递减（凹函数）。

    注意：凹性看的是**相对**速度倍率增益，不是绝对增量——
    `k^α` 在低基数段绝对增量小、高基数段大，但相对增幅 `k^α/k` 单调下降。
    """
    m1, m2, m4 = accel_speed_mult(1), accel_speed_mult(2), accel_speed_mult(4)
    assert m1 < m2 < m4
    # 相对增幅递减：每翻一倍带来的边际提速越来越小
    rel_first = (m2 - m1) / m1
    rel_second = (m4 - m2) / m2
    assert rel_first > rel_second


def test_accel_invalid_intensity_is_neutral():
    assert accel_speed_mult(0) == pytest.approx(1.0)
    assert accel_speed_mult(-1) == pytest.approx(1.0)
    assert accel_speed_mult(None) == pytest.approx(1.0)


# ====================================================== 总额封顶
def test_monthly_due_never_exceeds_total():
    total = 1000.0
    months = 10
    for k in (1, 2, 4, 8):
        due = monthly_due(base_total=total, months=months, intensity=k)
        assert due >= 0
        # 单月不应超总额（即使高强度）
        assert due <= total + 1e-6


def test_plan_effective_months_shorten_with_intensity():
    base = plan_construction_cost(materials={"布": 100.0}, months=10)
    fast = plan_construction_cost(materials={"布": 100.0}, months=10, intensity=2.0)
    assert fast["effective_months"] < base["effective_months"]
    assert fast["speed_mult"] > 1.0


# ====================================================== B4-5 赶工预算
def test_rush_premium_only_when_accelerating():
    assert rush_budget_spent(base_total=1000.0, intensity=1.0) == 0.0
    assert rush_budget_spent(base_total=1000.0, intensity=2.0) > 0.0


def test_rush_premium_independent_from_base():
    """溢价不占基准预算：total_commitment = base + rush。"""
    r = plan_construction_cost(materials={"布": 100.0}, months=10, intensity=2.0)
    assert r["total_commitment"] == pytest.approx(r["base_total"] + r["rush_premium"])
    assert r["rush_premium"] >= 0


def test_rush_refund_computes_unused_balance():
    assert rush_refund(rush_granted=100.0, rush_used=40.0) == pytest.approx(60.0)
    assert rush_refund(rush_granted=100.0, rush_used=100.0) == pytest.approx(0.0)
    assert rush_refund(rush_granted=100.0, rush_used=150.0) == pytest.approx(0.0)


def math_pow(x, y):
    return x ** y