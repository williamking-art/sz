# -*- coding: utf-8 -*-
"""A P1 影子（Jev A 0.974）：按现有池的贪心资金分配计划，只读不扣钱。"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


def _fp(s) -> str:
    txt = json.dumps(s.prefectures, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()


def test_plan_is_readonly_and_conserves_pool():
    from core.commands import new_game
    from core.domains.economy.owner_candidates_shadow import plan_capital_allocation

    s = new_game("史实")
    before = _fp(s)
    treasury_before = s.treasury
    rep = plan_capital_allocation(s)
    assert _fp(s) == before and s.treasury == treasury_before, "分配计划不得改钱/state"
    t = rep["totals"]
    assert t["funded"] + t["partial"] + t["unfunded"] + t["undefined"] == 128
    for r in rep["routes"]:
        assert r["items"]
        if r["pool"] is None:
            assert all(i["status"] == "undefined" for i in r["items"])
        else:
            assert sum(int(i["allocated"] or 0) for i in r["items"]) <= r["pool"]


def test_plan_unknown_type_is_undefined():
    from core.domains.economy.owner_candidates_shadow import plan_capital_allocation

    class S:
        pass

    s = S()
    s.prefectures = {"路A": {"name": "路A", "seats": {}}}
    s.workshops = {"谜之坊_路A_0": {"name": "谜之坊"}}
    s.treasury = 100
    rep = plan_capital_allocation(s)
    assert rep["totals"]["undefined"] == 1
    assert rep["totals"]["allocated"] == 0
