# -*- coding: utf-8 -*-
"""A G-4 P0（Jev A 0.554 货主口径）：逐路资金缺口只读报告。"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


def _fp(s) -> str:
    txt = json.dumps(s.prefectures, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()


def test_capital_gap_report_readonly_and_counts():
    from core.commands import new_game
    from core.domains.economy.owner_candidates_shadow import capital_gap_report

    s = new_game("史实")
    before = _fp(s)
    rep = capital_gap_report(s)
    assert _fp(s) == before, "缺口报告不得改 prefectures"
    assert rep["read_only"] is True
    assert rep["workshops"] == 128
    assert rep["route_count"] >= 1
    assert rep["total_need"] is not None and rep["total_need"] > 0
    for r in rep["routes"]:
        assert r["need"] is None or r["need"] == r["procure_need"] + r["wage_need"]
        assert r["coverage"] is None or 0 <= r["coverage"] <= 1
        assert r["shortfall"] is None or r["shortfall"] >= 0


def test_capital_gap_unknown_type_makes_route_none():
    from core.domains.economy.owner_candidates_shadow import capital_gap_report

    class S:
        pass

    s = S()
    s.prefectures = {"路A": {"name": "路A", "seats": {}}}
    s.workshops = {"谜之坊_路A_0": {"name": "谜之坊", "active": True}}
    s.treasury = 100
    rep = capital_gap_report(s)
    assert rep["total_need"] is None
    assert rep["routes"][0]["need"] is None
    assert rep["routes"][0]["unreadable"]
