# -*- coding: utf-8 -*-
"""D 数值接线 4/10（Jev C 0.455）：tax_collection_stance strict/lenient ⇒ 田赋应征额 ×1.03/×0.97。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


class _S:
    pass


def test_factor_defaults_and_mapping():
    from core.settlement_finance import _tax_stance_factor

    assert _tax_stance_factor(_S()) == 1.0
    s = _S()
    s._tiandao_observe = {"decisions": {"tax_collection_stance": "strict"}}
    assert _tax_stance_factor(s) == 1.03
    s._tiandao_observe = {"decisions": {"tax_collection_stance": "lenient"}}
    assert _tax_stance_factor(s) == 0.97
    for v in ("moderate", None, "unknown", {"verdict": "moderate"}):
        s._tiandao_observe = {"decisions": {"tax_collection_stance": v}}
        assert _tax_stance_factor(s) == 1.0, v


def test_land_tax_assessed_scaled_by_stance():
    from core.commands import new_game
    from core.settlement_finance import _settle_land_tax_color

    def run(stance):
        s = new_game("史实")
        s._tiandao_observe = {"decisions": {"tax_collection_stance": stance}}
        return _settle_land_tax_color(s, [])

    strict = run("strict")
    moderate = run("moderate")
    lenient = run("lenient")
    assert strict["assessed"] > moderate["assessed"] > lenient["assessed"], (
        strict["assessed"], moderate["assessed"], lenient["assessed"])
