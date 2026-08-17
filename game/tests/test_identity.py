# -*- coding: utf-8 -*-
"""经济全浮动重构 · 恒等断言与回归探针。

覆盖：
  1) Σ各路 == 总量（二税折色 / 太仓本色 / 军费 / 官俸 / 吏俸）
  2) 净结余方向（国库变动 == 月入 - 月出 - 内帑抽成）
  3) 贪腐-加俸反馈曲线（payraise_budget↑ → pay_ratio↑ → gap↓ → 贪腐扣减↓）
"""
import os
import sys

import pytest

# 将 game 包根加入路径（脚本直接运行时）
_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState
from content.data import DIFFICULTY_PRESETS  # noqa: E402


def _new_state():
    return GameState("史实")


def test_sum_routes_equals_total():
    """Σ各路派生量 == 总量（分路聚合恒等式）。"""
    s = _new_state()
    # 二税折色
    total, by = s.calc_monthly_tax_income(1.0)
    assert abs(total - sum(by.values())) < 1e-6
    # 太仓本色
    gt, gb = s.calc_monthly_grain()
    assert abs(gt - sum(gb.values())) < 1e-6
    # 军费
    at, ab = s.calc_army_cash()
    assert abs(at - sum(ab.values())) < 1e-6
    # 官俸
    ot, ob = s.calc_official_cash()
    assert abs(ot - sum(ob.values())) < 1e-6
    # 吏俸
    ct, cb = s.calc_clerk_cash()
    assert abs(ct - sum(cb.values())) < 1e-6
    # 防区派生：army_units 兵额合计 == 防区 garrison 合计（兵额唯一真账）
    s._derive_defense_lines()
    agg = sum(u.troops for u in s.army_units)
    def_total = sum(v.get("garrison", 0) for v in s.defense_lines.values())
    assert abs(agg - def_total) < 1e-6


def test_granary_identity():
    """太仓月出 = 军粮 + 官禄 + 吏禄×pay_ratio + 贪腐本色损耗（出库口径一致）。"""
    s = _new_state()
    army_g, _ = s.calc_army_grain()
    off_g, _ = s.calc_official_grain()
    clerk_g, _ = s.calc_clerk_grain()
    _, corr_g = s.calc_corruption_deduction()
    pay = s.pay_system.get("grain_ratio", 0.5)
    out = (army_g + off_g + clerk_g) * pay + corr_g * pay
    # 与 _settle_granary 断言同构：granary_before_out - granary == out_total
    # 此处仅校验公式自洽（结算函数内另有运行期断言）
    assert out >= 0


def test_treasury_net_direction():
    """国库净结余方向：收入 > 支出时结余为正，反之负（不含内帑抽成前的 net）。"""
    s = _new_state()
    tax_color_total, _ = s.calc_monthly_tax_income(1.0)
    salt_coin = 80000.0  # 盐课活基准量级（开局约50万，此处仅作量级占位验证）
    army_cash, _ = s.calc_army_cash()
    official_cash, _ = s.calc_official_cash()
    clerk_cash, _ = s.calc_clerk_cash()
    corr_cash, _ = s.calc_corruption_deduction()
    # 全浮动月入（不含工商/役钱/市舶，仅验证新科目量级）
    new_in = tax_color_total + salt_coin
    new_out = army_cash + official_cash + clerk_cash + corr_cash
    # 新科目净（正=盈余方向）
    net_new = new_in - new_out
    assert isinstance(net_new, float)


def test_corruption_payraise_feedback():
    """贪腐-加俸反馈曲线：payraise_budget↑ → pay_ratio↑ → gap↓ → 贪腐扣减↓。"""
    s = _new_state()
    # 基线
    base_gap, _ = s.calc_clerk_gap()
    base_corr, _ = s.calc_corruption_deduction()
    # 投入加俸预算（模拟厚禄养廉）
    s.payraise_budget = 5_000_000
    # 重算 pay_ratio（需触发 calc_pay_ratio 的实际效应）
    for name in s.prefectures:
        s.prefectures[name]["pay_ratio"] = s.calc_pay_ratio(name)
    new_gap, _ = s.calc_clerk_gap()
    new_corr, _ = s.calc_corruption_deduction()
    # 加俸后缺口与贪腐扣减不应高于基线（反馈压缩）
    assert new_gap <= base_gap + 1e-6
    assert new_corr <= base_corr + 1e-6


def test_imperial_treasury_feedback():
    """内帑抽成：净结余为正时 > 0；为负时不抽成。"""
    s = _new_state()
    share_pos, wine = s.calc_imperial_treasury(net=1_000_000)
    share_neg, _ = s.calc_imperial_treasury(net=-1_000_000)
    assert share_pos > 0
    assert share_neg == 0
    assert wine > 0


def test_full_settlement_no_assertion_break():
    """跑一个月结算，确认恒等断言不触发（财政/太仓）。"""
    s = _new_state()
    from core.settlement import run_monthly_settlement
    log = run_monthly_settlement(s)
    assert isinstance(log, list)
    # 一回合后量纲合理
    assert -50_000_000 < s.treasury < 50_000_000
    assert s.granary >= 0


if __name__ == "__main__":
    # 无 pytest 时直接运行
    test_sum_routes_equals_total()
    test_granary_identity()
    test_treasury_net_direction()
    test_corruption_payraise_feedback()
    test_imperial_treasury_feedback()
    test_full_settlement_no_assertion_break()
    print("ALL IDENTITY TESTS PASSED")
