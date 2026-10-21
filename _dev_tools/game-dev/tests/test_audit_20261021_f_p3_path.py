# -*- coding: utf-8 -*-
"""F P3 首批（Jev A 0.909）：只读投影「旨意→承办人→经济动作→前置资源」，不改钱。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


def test_projection_finance_reform_read_only():
    from core.commands import new_game
    from core.settlement_decree import project_economic_action_path

    s = new_game("史实")
    before = (s.treasury, s.granary, dict(s.finance or {}))
    decree = {"decree_id": "D1", "executor": "王安石",
              "effects": {"finance_rates": {"collection_rate": 0.05}}}
    path = project_economic_action_path(s, decree)
    assert path["action"] == "finance_reform"
    assert path["executor"] == "王安石"
    assert path["defined"] is True
    assert path["retry_key"].startswith("D1:王安石:")
    assert "finance" in path["preconditions"]
    assert (s.treasury, s.granary, dict(s.finance or {})) == before, "投影不得改钱/改率"
    assert "finance_undefined" not in path["rejection_reasons"]


def test_projection_missing_executor_and_no_effect():
    from core.commands import new_game
    from core.settlement_decree import project_economic_action_path

    s = new_game("史实")
    p = project_economic_action_path(s, {"decree_id": "D2", "effects": {}})
    assert p["defined"] is False
    assert "no_effect" in p["rejection_reasons"]
    assert "no_executor" in p["rejection_reasons"]
    assert p["authorized"] is None


def test_projection_uses_first_addressee_as_executor():
    from core.commands import new_game
    from core.settlement_decree import project_economic_action_path

    s = new_game("史实")
    lead = None
    for row in (s.central_orgs or {}).values():
        if isinstance(row, dict) and row.get("lead"):
            lead = row["lead"]
            break
    if not lead:
        return
    p = project_economic_action_path(s, {"decree_id": "D3", "addressees": [lead],
                                         "effects": {"treasury": 1}})
    assert p["executor"] == lead
    assert p["action"] == "fiscal"
