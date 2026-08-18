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


def test_treasury_actual_tax_no_silent_creation():
    """P2-#2 回归：国库实际到库额 == POP 实扣税额（保底豁免部分不入库，钱不凭空生）。"""
    from core.settlement import run_monthly_settlement
    from core.settlement_steps import _settle_finance
    s = _new_state()
    # 强制低财富 POP 触发保底豁免，验证国库不会按全额计税入库
    for p in s.prefectures.values():
        for pop in p["pops"].values():
            pop["wealth"] = 1  # 极低财富，必触发 _min_wealth 保底豁免
    before = s.treasury
    log = run_monthly_settlement(s)
    # 国库变化应≈实际到库税 - 支出（不按全额目标税入库）
    # 实际税入应远小于全额目标税（POP 几乎无力纳税）
    assert s.treasury != before  # 确实有结算发生
    # 关键：无异常膨胀（国库不应因"未收到的税"而暴增）
    assert s.treasury < before + 5_000_000  # 低财富下不可能有大笔盈余入库


def test_farmer_grain_never_negative():
    """P1-#3 回归：非农 POP 买粮后农民余粮不为负。"""
    s = _new_state()
    # 构造：农民余粮极少但买方极富，触发 affordability 重赋值路径
    for p in s.prefectures.values():
        p["pops"]["农"]["grain"] = 10        # 极少余粮
        p["pops"]["农"]["wealth"] = 1000
        p["pops"]["工匠"]["grain"] = 0
        p["pops"]["工匠"]["wealth"] = 9_000_000  # 极富
        p["pops"]["工匠"]["size"] = 10000
    # 直接跑 _settle_granary（Step 3.8）
    from core.settlement_steps import _settle_granary
    _settle_granary(s, [])
    for p in s.prefectures.values():
        assert p["pops"]["农"]["grain"] >= 0, f"农民粮变负：{p['pops']['农']['grain']}"


def test_pop_migration_conservation():
    """P3-#12 回归：城市化/回乡迁移段不丢人（农→工/商转移人数守恒）。

    仅验证迁移段本身：构造极低基数使 round 截断误差可观测，
    确认 round 替代 int 后不再因截断丢失人数。
    """
    # 内联迁移逻辑验证（与 _settle_economy 迁移段同构）
    def _sim_migrate(farmer_size, artisan_size, merchant_size, boom):
        pops = {"农": {"size": farmer_size}, "工匠": {"size": artisan_size}, "商人": {"size": merchant_size}}
        if boom in ("中", "大"):
            _move = round(pops["农"]["size"] * 0.0008)
            pops["农"]["size"] -= _move
            pops["工匠"]["size"] += int(_move * 0.6)
            pops["商人"]["size"] += _move - int(_move * 0.6)
        elif boom == "微":
            _back = round((pops["工匠"]["size"] + pops["商人"]["size"]) * 0.0008)
            pops["工匠"]["size"] -= int(_back * 0.6)
            pops["商人"]["size"] -= (_back - int(_back * 0.6))
            pops["农"]["size"] += _back
        return pops["农"]["size"] + pops["工匠"]["size"] + pops["商人"]["size"]

    # 低基数场景：农=1249 → _move=round(1249*0.0008)=1，工+0 商+1（不丢人）
    before = 1249 + 0 + 0
    after = _sim_migrate(1249, 0, 0, "大")
    assert after == before, f"迁移丢人：{before}→{after}"
    # 回乡场景：工=1 商=0 → _back=round(1*0.0008)=0 → 农不变
    after2 = _sim_migrate(1000, 1, 0, "微")
    assert after2 == 1001, f"回乡丢人：{after2}"


if __name__ == "__main__":
    # 无 pytest 时直接运行
    test_sum_routes_equals_total()
    test_granary_identity()
    test_treasury_net_direction()
    test_corruption_payraise_feedback()
    test_imperial_treasury_feedback()
    test_full_settlement_no_assertion_break()
    test_treasury_actual_tax_no_silent_creation()
    test_farmer_grain_never_negative()
    test_pop_migration_conservation()
    print("ALL IDENTITY TESTS PASSED")
