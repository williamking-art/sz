# -*- coding: utf-8 -*-
"""D 数值接线 5/10（Jev C 0.339，近平手自证）：
should_waive_ancient_arrears=True ⇒ 暂停本月欠税追缴 + 核销 10% 欠税存量。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


class _S:
    pass


def test_waiver_defaults_false():
    from core.settlement_finance import _arrears_waiver_active

    assert _arrears_waiver_active(_S()) is False


def test_waiver_true_only_when_defined_true():
    from core.settlement_finance import _arrears_waiver_active

    s = _S()
    s._tiandao_observe = {"decisions": {"should_waive_ancient_arrears": True}}
    assert _arrears_waiver_active(s) is True
    s._tiandao_observe = {"decisions": {
        "should_waive_ancient_arrears": {"verdict": True, "defined": True}}}
    assert _arrears_waiver_active(s) is True
    for dec in (False, {"verdict": False, "defined": True},
                {"verdict": True, "defined": False}, {"error": "x"}):
        s._tiandao_observe = {"decisions": {"should_waive_ancient_arrears": dec}}
        assert _arrears_waiver_active(s) is False, dec


def test_settlement_waives_10pct_and_skips_collection():
    from core.commands import new_game
    from core.settlement_finance import _settle_finance

    s = new_game("史实")
    for p in s.prefectures.values():
        p["pops"]["农"]["欠税"] = 1_000_000
    before = sum(int(p["pops"]["农"].get("欠税", 0) or 0) for p in s.prefectures.values())
    s._tiandao_observe = {"decisions": {"should_waive_ancient_arrears": True}}
    log = []
    _settle_finance(s, log)
    after = sum(int(p["pops"]["农"].get("欠税", 0) or 0) for p in s.prefectures.values())
    assert after < before, (before, after)
    assert any("蠲免" in line for line in log), log[-5:]
