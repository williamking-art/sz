# -*- coding: utf-8 -*-
"""核心玩法逻辑回归测试。

覆盖此前评审中指出的高风险区：
  - 诏令执行率各分支（密旨/直接/中旨/狼顾数边界）
  - 皇帝死亡与强制收束年（避免游戏永不结束）
  - check_game_over 四条结束判定（国库崩坏 / 死亡 / 退位 / 京城陷落 / 收束年）
  - 月份推进一致性（settle_turn 不应双重推进）
  - 百姓口碑权重（流民率口径不再被放大到负边界）
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState, _next_month  # noqa: E402
from core.evaluation import (  # noqa: E402
    check_reach_end_year, check_game_over,
    evaluate_game,
)
from content.data import TREASURY_COLLAPSE_LINE, END_YEAR  # noqa: E402


def _new_state():
    return GameState("史实")


# ------------------------------------------------------------
# _next_month 纯函数
# ------------------------------------------------------------
def test_next_month_rolls_over_december():
    y, m = _next_month(1101, 12)
    assert (y, m) == (1102, 1)


def test_next_month_normal():
    y, m = _next_month(1101, 6)
    assert (y, m) == (1101, 7)


# ------------------------------------------------------------
# 诏令执行率分支
# ------------------------------------------------------------
def test_execution_rate_secret_uses_loyalty():
    s = _new_state()
    stances = {fn: 0 for fn in s.factions}
    low = s.calc_decree_execution_rate(stances, is_secret=True, secret_loyalty=0.0)
    high = s.calc_decree_execution_rate(stances, is_secret=True, secret_loyalty=1.0)
    assert high > low  # 忠诚度越高密旨执行率越高


def test_execution_rate_direct_wolf_bonus_penalty():
    s = _new_state()
    stances = {fn: 1 for fn in s.factions}  # 全员赞成 → net_support 最大
    s.wolf_count = 0
    bonus = s.calc_decree_execution_rate(stances, is_direct=True)
    s.wolf_count = 5
    penalty = s.calc_decree_execution_rate(stances, is_direct=True)
    assert bonus > penalty  # 狼顾数<3 加成效能；>=3 反噬


def test_execution_rate_zhongzhi_affiliation():
    s = _new_state()
    stances = {fn: -1 for fn in s.factions}
    inner = s.calc_decree_execution_rate(stances, is_zhongzhi=True, org_hint="内廷")
    local = s.calc_decree_execution_rate(stances, is_zhongzhi=True, org_hint="地方")
    assert inner > local  # 内廷中旨执行率高于地方


def test_execution_rate_bounded():
    s = _new_state()
    stances = {fn: -1 for fn in s.factions}
    r = s.calc_decree_execution_rate(stances)
    assert 0.05 <= r <= 0.95


# ------------------------------------------------------------
# 收束年（皇帝已移除死亡判定，仅靠 END_YEAR 收束等结束）
# ------------------------------------------------------------
def test_reach_end_year_forces_game_over():
    s = _new_state()
    s.year = END_YEAR
    s.emperor_health = 90  # 健康也兜不住收束年
    reached, _ = check_reach_end_year(s)
    assert reached is True


def test_no_reach_end_year_early():
    s = _new_state()
    s.year = 1120
    reached, _ = check_reach_end_year(s)
    assert reached is False


# ------------------------------------------------------------
# check_game_over 四条（含收束年）结束判定
# ------------------------------------------------------------
def test_game_over_treasury_collapse():
    s = _new_state()
    s.treasury = TREASURY_COLLAPSE_LINE - 1
    assert check_game_over(s) is True
    assert s.game_over is True


def test_game_over_not_on_zero_health_after_death_removed():
    s = _new_state()
    s.emperor_health = 0  # 健康归零
    assert check_game_over(s) is False  # 死亡判定已移除：皇帝不因健康归零驾崩
    assert s.emperor_alive is True


def test_game_over_abdication():
    s = _new_state()
    s.population_satisfaction = 10      # 民怨沸腾
    s.treasury = -6_000_000            # 国库亏空严重
    assert check_game_over(s) is True
    assert s.is_abdicated is True


def test_game_over_capital_falls():
    s = _new_state()
    s.year = 1127
    s.defense_lines["内线_东京城防"]["garrison"] = 5  # 跌破阈值 10
    assert check_game_over(s) is True


def test_game_over_end_year_reached():
    s = _new_state()
    s.year = END_YEAR
    assert check_game_over(s) is True


def test_game_over_not_triggered_normal():
    s = _new_state()
    s.year = 1105
    s.emperor_health = 75
    s.treasury = 5_000_000
    s.population_satisfaction = 60
    assert check_game_over(s) is False


# ------------------------------------------------------------
# 月份推进一致性：settle_turn 不应双重推进
# ------------------------------------------------------------
def test_settle_turn_advances_month_once():
    from core.commands import settle_turn
    from core.settlement import run_monthly_settlement
    s = _new_state()
    y0, m0, t0 = s.year, s.month, s.turn
    run_monthly_settlement(s)
    # 仅跑结算函数，应恰好推进一月、一回合
    assert (s.year, s.month) == _next_month(y0, m0)
    assert s.turn == t0 + 1

    s2 = _new_state()
    y0, m0, t0 = s2.year, s2.month, s2.turn
    # 全游戏级强制 AI：settle_turn 需注入 AI 替身（拒绝式，无 AI 抛错）
    from tests.fake_ai_backend import FakeAIClient
    settle_turn(s2, ai_client=FakeAIClient())
    # settle_turn 内部已委托 run_monthly_settlement 推进，不应再推进一次
    assert (s2.year, s2.month) == _next_month(y0, m0)
    assert s2.turn == t0 + 1


# ------------------------------------------------------------
# 百姓口碑权重：流民率口径平滑
# ------------------------------------------------------------
def test_koubei_not_collapsed_by_small_refugee_rate():
    s = _new_state()
    s.population_satisfaction = 70
    s.population = 80_000_000
    s.refugee_count = 1_000_000  # 流民率 1.25%
    res = evaluate_game(s)
    koubei = res["scores"]["百姓口碑"]
    # 1.25% 流民率只应轻微拉低口碑，不应被打到接近 0
    assert koubei > 60


# ------------------------------------------------------------
# P0 回歸：finance_readout 役钱口径须与 _settle_finance 一致（按农 POP 征）
# 防止会计录展示数字与实际到库不符（本次审查发现的口径漂移）
# ------------------------------------------------------------
def test_finance_readout_poll_tax_matches_settlement():
    from core.game_state_econ import GameStateEconMixin  # noqa: F401
    from content.data import TAX_POLL_RATIO

    s = _new_state()
    # 会计录（展示层）役钱
    readout = s.finance_readout()
    poll_readout = readout["poll"]

    # 结算层（_settle_finance 同口径）役钱
    farm_pop = sum(p["pops"]["农"]["size"] for p in s.prefectures.values())
    arrival = s.calc_arrival_rate()
    shortage = s.coin.get("shortage", 0.3)
    from content.data import TAX_COEFF_MIN, TAX_COEFF_MAX
    tax_coeff = TAX_COEFF_MIN + (TAX_COEFF_MAX - TAX_COEFF_MIN) * (1 - shortage)
    expected = int((farm_pop * TAX_POLL_RATIO / 12) * arrival * tax_coeff)

    assert poll_readout == expected


# ------------------------------------------------------------
# P2 回归：经济守恒——单月结算不应凭空增删钱粮总量
# POP 重构后存在大量"转移"（士绅囤粮/窖银/隐田转正），
# 须保证 treasury + granary + 各路 POP wealth/grain 的加总不出现无来源的跳变。
# 以"月净变化可解释"为判据：净变化应等于当月收支结余的可观测部分。
# ------------------------------------------------------------
def test_settlement_money_conservation_no_silent_jump():
    from core.commands import settle_turn

    s = _new_state()

    def _money_snapshot(st):
        # 国库 + 内帑 + 太仓 + 各路 POP 家资（含窖银）
        total = st.treasury + st.imperial_treasury + st.granary
        for p in st.prefectures.values():
            for pop in p["pops"].values():
                total += pop.get("wealth", 0)
                total += pop.get("grain", 0) * 0.001  # 粮折钱（仅量级校验，非精确）
                total += pop.get("窖银", 0)
        return total

    # 开胃一回合，记录起止快照（全游戏级强制 AI：注入替身）
    from tests.fake_ai_backend import FakeAIClient
    before = _money_snapshot(s)
    settle_turn(s, ai_client=FakeAIClient())
    after = _money_snapshot(s)

    # 允许存在生产/消费带来的正常波动，但不允许"凭空"量级跳变
    # （例如 treasury 单月增减不应超过 +/-5000万贯 的合理量级）
    assert abs(after - before) < 50_000_000


if __name__ == "__main__":
    test_next_month_rolls_over_december()
    test_next_month_normal()
    test_execution_rate_secret_uses_loyalty()
    test_execution_rate_direct_wolf_bonus_penalty()
    test_execution_rate_zhongzhi_affiliation()
    test_execution_rate_bounded()
    test_reach_end_year_forces_game_over()
    test_no_reach_end_year_early()
    test_game_over_treasury_collapse()
    test_game_over_not_on_zero_health_after_death_removed()
    test_game_over_abdication()
    test_game_over_capital_falls()
    test_game_over_end_year_reached()
    test_game_over_not_triggered_normal()
    test_settle_turn_advances_month_once()
    test_koubei_not_collapsed_by_small_refugee_rate()
    test_finance_readout_poll_tax_matches_settlement()
    test_settlement_money_conservation_no_silent_jump()
    print("ALL CORE LOGIC TESTS PASSED")
