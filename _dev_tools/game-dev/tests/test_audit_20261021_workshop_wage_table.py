# -*- coding: utf-8 -*-
"""A G-4 首批（Jev A 0.536）：作坊岗位/工价表 + 影子工资义务（不接钱）。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


def test_jobs_table_unknown_returns_none_not_zero():
    from content.data_workshop_jobs import jobs_of, wage_of

    assert jobs_of("未知坊", 1) is None
    assert jobs_of("酒坊", 0) is None
    assert wage_of("未知坊", 1) is None
    assert jobs_of("酒坊", 2) == 160_000
    assert wage_of("酒坊", 1) == 120_000.0


def test_workshop_wage_obligation_uses_table():
    from core.commands import new_game
    from core.domains.economy.workshop_fund_shadow import wage_obligation, workshop_shadow

    s = new_game("史实")
    wid = next(iter(s.workshops))
    w = wage_obligation(s, wid)
    assert w["jobs"] is not None and w["obligation"] is not None
    assert w["rate"] == 1.5
    sh = workshop_shadow(s, wid)
    assert sh["status"] == "shadow_ready", sh
    assert "wage" not in sh["missing"]


def test_survey_shadow_ready_all_four_types():
    from core.commands import new_game
    from core.domains.economy.workshop_fund_shadow import survey_workshop_fund_shadow

    s = new_game("史实")
    rep = survey_workshop_fund_shadow(s)
    assert rep["workshops"] == 128
    assert rep["shadow_ready"] == rep["workshops"], rep
    assert rep["conservation"]["ok"] is True
