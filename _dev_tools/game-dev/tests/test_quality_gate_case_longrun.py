# -*- coding: utf-8 -*-
"""质量放行门 · 带案卷的长局结算（2026-10-20）。

背景：60 月回放发现——事务议毕即被移出在办队列 ⇒ 案卷结算从第 13 月起静默失效
（专款停扣、日志停写）。修复：结案事务移入 longterm_cases_archive，结算/读数/邸报
统一走 iter_case_tasks；结案后 _closed ⇒ 不再扣款、不再落效果。

本门（12 月）钉住：
1. 案卷跑满进度后被移出在办队列，但**仍在归档**且案卷读数可查；
2. 结案后专款不再扣（余额停在结案时）；
3. 没告成（待支持）不发 outcome_effects；
4. 专断代价**按案封顶**（民心累计 -10、贪腐累计 +0.08）；
5. 每月守恒（人口/国级对账/行政区不变量）不破。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.foundation.ledger.region_registry import (  # noqa: E402
    verify_aggregation, verify_pop_conservation, verify_region_invariants)

MONTHS = 12


def _setup():
    from core.commands import new_game
    from core.commands_decree import authorize_longterm_case

    s = new_game()
    task = {"id": "ltp_case", "task_name": "整饬海防", "case_no": "#426",
            "minister": "曾布", "progress": 60.0, "months": 6,
            "monthly_effects": [], "outcome_effects": [{"key": "prestige", "amount": 9}],
            "fail_effects": []}
    s.longterm_public.append(task)
    assert authorize_longterm_case(s, "ltp_case", budget=100000,
                                   discretion=True, monthly_cost=1000)["ok"]
    return s, task


def test_longrun_case_archived_and_closed():
    from core.domains.politics.longterm_case import iter_case_tasks
    from core.settlement import run_monthly_settlement

    s, task = _setup()
    for i in range(MONTHS):
        run_monthly_settlement(s)
        assert verify_pop_conservation(s) == [], "第 %d 月人口守恒违规" % (i + 1)
        assert verify_aggregation(s) == [], "第 %d 月国级对账违规" % (i + 1)
        assert verify_region_invariants(s) == []

    assert task.get("_closed") is True, "议毕后应结案"
    in_queue = any(isinstance(t, dict) and t.get("id") == "ltp_case" for t in s.longterm_public)
    in_archive = any(isinstance(t, dict) and t.get("id") == "ltp_case"
                     for t in s.longterm_cases_archive)
    assert not in_queue and in_archive, (in_queue, in_archive)
    assert task in iter_case_tasks(s)


def test_closed_case_stops_burning_budget():
    from core.settlement import run_monthly_settlement

    s, task = _setup()
    for _ in range(MONTHS):
        run_monthly_settlement(s)
    remain = task["budget"]["remaining"]
    for _ in range(3):
        run_monthly_settlement(s)
    assert task["budget"]["remaining"] == remain, "结案后不得再扣专款"
    assert task.get("_outcome_applied") is not True, "待支持不得发达成奖励"


def test_discretion_cost_capped():
    from core.domains.politics.longterm_case import (DISCRETION_CORRUPTION_CAP,
                                                     DISCRETION_SATISFACTION_CAP,
                                                     monthly_case_settle)

    class _S:
        def __init__(self):
            self.prestige = 60
            self.population_satisfaction = 80
            self.treasury = 100000
            self.turn = 1

        def change_treasury(self, d):
            self.treasury += int(d)

        def change_prestige(self, d, reason=""):
            self.prestige += int(d)

    s = _S()
    t = {"id": "ltp1", "minister": "曾布", "progress": 10, "discretion": True,
         "monthly_effects": []}
    for _ in range(40):
        monthly_case_settle(s, t, [])
    assert s.population_satisfaction == 80 - DISCRETION_SATISFACTION_CAP
    used = t["_discretion_used"]
    assert abs(used["corruption"] - DISCRETION_CORRUPTION_CAP) < 1e-9
