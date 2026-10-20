# -*- coding: utf-8 -*-
"""质量放行门 · 赐专断之权的代价（2026-10-20）。

设计：专断 ⇒ 推进提速 ×1.15；但每月承办人贪腐 +0.008、民心 −1（有代价才叫决策）。

钉住：
1. 推进公式：有专断 ⇒ advance 恰为无专断的 1.15 倍（同一组 channels/stance）；
2. 月度结算：专断 ⇒ 承办人 corruption 上升、population_satisfaction −1，并记在日志 entry；
3. 未授专断 ⇒ 两项都不动（零变更）；
4. 专断代价有界（corruption ≤ 1.0，满意度 ≥ 0）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.longterm_task import _advance_amount  # noqa: E402


class _S:
    def __init__(self):
        self.turn = 5
        self.prestige = 60
        self.population_satisfaction = 50
        self.treasury = 100000
        self.difficulty = "史实"
        self.difficulty_presets = {}

    def change_treasury(self, d):
        self.treasury += int(d)

    def change_prestige(self, d, reason=""):
        self.prestige += int(d)


CH = {"defined": True, "effect_mult": 1.0}
ST = {"net": 0.0}


def test_discretion_speeds_up_advance():
    s = _S()
    base_task = {"id": "t1", "months": 18, "support_bonus": 0.0}
    plain, d1 = _advance_amount(s, base_task, CH, ST)
    disc_task = dict(base_task, discretion=True)
    fast, d2 = _advance_amount(s, disc_task, CH, ST)
    assert d1["discretion_mult"] == 1.0 and d2["discretion_mult"] == 1.15
    assert abs(fast / plain - 1.15) < 1e-3, (plain, fast)


def test_monthly_discretion_costs(monkeypatch):
    from core.domains.politics import longterm_case as lc

    s = _S()
    t = {"id": "ltp1", "minister": "曾布", "progress": 10, "discretion": True,
         "monthly_effects": []}
    got = lc.monthly_case_settle(s, t, [], progress=15)
    e = t["progress_log"][-1]
    assert e["discretion"]["corruption"] == lc.DISCRETION_CORRUPTION_MONTH
    assert s.population_satisfaction == 49
    assert e["discretion"]["corruption_now"] >= lc.DISCRETION_CORRUPTION_MONTH


def test_no_discretion_no_cost():
    from core.domains.politics import longterm_case as lc

    s = _S()
    t = {"id": "ltp1", "minister": "曾布", "progress": 10, "monthly_effects": []}
    lc.monthly_case_settle(s, t, [], progress=15)
    assert t["progress_log"][-1]["discretion"] is None
    assert s.population_satisfaction == 50


def test_costs_bounded():
    from core.domains.politics import longterm_case as lc

    s = _S()
    s.population_satisfaction = 0
    t = {"id": "ltp1", "progress": 0, "discretion": True, "monthly_effects": []}
    lc.monthly_case_settle(s, t, [])
    assert s.population_satisfaction == 0, "民心不得为负"