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
    check_emperor_death, check_reach_end_year, check_game_over,
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
# 皇帝死亡与收束年
# ------------------------------------------------------------
def test_emperor_death_at_zero_health():
    s = _new_state()
    s.emperor_health = 0
    dead, _ = check_emperor_death(s)
    assert dead is True


def test_emperor_death_not_triggered_early_when_healthy():
    s = _new_state()
    s.year = 1110
    s.emperor_health = 80
    dead, _ = check_emperor_death(s)
    assert dead is False  # 早期健康良好不应崩殂


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


def test_game_over_emperor_death():
    s = _new_state()
    s.emperor_health = 0
    assert check_game_over(s) is True
    assert s.emperor_alive is False


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
    settle_turn(s2)
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


if __name__ == "__main__":
    test_next_month_rolls_over_december()
    test_next_month_normal()
    test_execution_rate_secret_uses_loyalty()
    test_execution_rate_direct_wolf_bonus_penalty()
    test_execution_rate_zhongzhi_affiliation()
    test_execution_rate_bounded()
    test_emperor_death_at_zero_health()
    test_emperor_death_not_triggered_early_when_healthy()
    test_reach_end_year_forces_game_over()
    test_no_reach_end_year_early()
    test_game_over_treasury_collapse()
    test_game_over_emperor_death()
    test_game_over_abdication()
    test_game_over_capital_falls()
    test_game_over_end_year_reached()
    test_game_over_not_triggered_normal()
    test_settle_turn_advances_month_once()
    test_koubei_not_collapsed_by_small_refugee_rate()
    print("ALL CORE LOGIC TESTS PASSED")
