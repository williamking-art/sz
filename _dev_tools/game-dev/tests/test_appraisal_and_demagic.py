# -*- coding: utf-8 -*-
"""三年磨勘考课 × 天道 score、以及"去魔数"真动态性测试（P0 修复批 · 2026-10-17）。

覆盖两条真实退化：
1. 接入 `score` 后**下考不可达**（民怨 70/80/100 全判中考）⇒ 罢黜 / 祠禄冷冻机制失效；
2. `dynamic_treasury_crisis_line` 读的字段**全库无写入方** ⇒ 恒等于 5,000,000，
   "去魔数"是空转（旧用例靠测试自己往 statistics 里塞字段才通过）。
"""
import pytest

from application.game_init import new_game
from core.ai.tiandao_facade import TianDaoFacade
from core.domains.administration.official_appraisal import run_triennial_appraisal
from core.settlement import run_monthly_settlement


# =============================================================================
# 1. 考课分档：下考必须可达（旧规则：民怨 >60 ⇒ 下考）
# =============================================================================
def test_appraisal_promotes_when_peaceful():
    state = new_game("史实")
    log = []
    res = run_triennial_appraisal(state, log=log)
    assert res["promoted_circuits"], "民和政平时应有上考擢升"
    assert res["demoted_circuits"] == []
    assert log


def test_appraisal_demotes_when_unrest_high():
    """民怨 80 全路 ⇒ 必须出现下考殿罚 / 祠禄冷冻（旧实现全员中考，永不黜落）。"""
    state = new_game("史实")
    state.statistics["organic_unrest_pool"] = {c: 80.0 for c in state.prefectures}
    log = []
    res = run_triennial_appraisal(state, log=log)

    assert res["demoted_circuits"], "民怨 80 竟无人判下考 —— score 档位不可达"
    assert res["sinecure_assigned"] > 0, "下考应触发祠禄冷冻"
    assert res["administrative_efficiency"] < 1.0
    assert any(("殿罚" in m) or ("黜降" in m) or ("祠禄" in m) for m in log), \
        f"下考未落日志：{log}"


def test_appraisal_grade_thresholds_monotonic():
    """民怨越高，评等不得**变好**（回归保护：旧实现 20→上考 / 70→中考）。"""
    state = new_game("史实")
    levels = ["下考", "中考", "上考"]
    scores = []
    for unrest in (0.0, 30.0, 60.0, 90.0):
        ctx = {"tax_completion": 0.75, "unrest": unrest, "official_integrity": 0.6}
        scores.append(TianDaoFacade.appraisal_score(ctx, levels)["score"])
    assert scores == sorted(scores, reverse=True), f"评等未随民怨单调下降：{scores}"


# =============================================================================
# 2. 去魔数：安全垫线必须有真实写入方
# =============================================================================
def test_monthly_expense_reading_is_actually_written():
    """跑一次真实月度结算后，`last_monthly_expense` 必须被写入（旧实现零写入方）。"""
    state = new_game("史实")
    assert "last_monthly_expense" not in (state.statistics or {}), "新局不应预置该读数"
    run_monthly_settlement(state)
    expense = (state.statistics or {}).get("last_monthly_expense")
    assert expense is not None, "结算后仍未写入月度支出 —— 动态安全垫线是假动态"
    assert expense > 0
    assert TianDaoFacade.crisis_line_source(state)["source"] == "dynamic"


def test_crisis_line_clamps_and_falls_back():
    assert TianDaoFacade.dynamic_treasury_crisis_line(None) == 5_000_000
    state = new_game("史实")
    assert TianDaoFacade.dynamic_treasury_crisis_line(state) == 5_000_000
    state.statistics["last_monthly_expense"] = 800_000
    assert TianDaoFacade.dynamic_treasury_crisis_line(state, 3) == 2_400_000
    state.statistics["last_monthly_expense"] = 5_000_000
    assert TianDaoFacade.dynamic_treasury_crisis_line(state, 3) == 10_000_000
    state.statistics["last_monthly_expense"] = 100_000
    assert TianDaoFacade.dynamic_treasury_crisis_line(state, 3) == 1_000_000
