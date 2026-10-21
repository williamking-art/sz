# -*- coding: utf-8 -*-
"""G 首批（Jev B 0.821）：影子产出 vs 正式 yields 的只读 A/B 基线。"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


def _state_fingerprint(s) -> str:
    txt = json.dumps(s.prefectures, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()


def test_shadow_comparison_is_read_only_and_reports_three_states():
    from core.commands import new_game
    from core.domains.production.crop_shadow import shadow_output_comparison

    s = new_game("史实")
    before = _state_fingerprint(s)
    rep = shadow_output_comparison(s)
    assert _state_fingerprint(s) == before, "A/B 基线不得改 prefectures"
    assert rep["read_only"] is True
    assert rep["route_count"] > 0
    assert rep["row_count"] == rep["route_count"] * len(rep["crops"])
    assert rep["both_defined"] >= 0
    assert rep["shadow_none_formal_positive"] >= 0
    # 严格三态：both + shadow_none_formal_positive + formal_none_shadow_positive ≤ row_count
    # （其余为两边都 None 的缺数据行）
    assert (rep["both_defined"] + rep["shadow_none_formal_positive"]
            + rep["formal_none_shadow_positive"]) <= rep["row_count"]
    for row in rep["sample"]:
        if row["shadow_output"] is None or row["formal_yield"] is None:
            assert row["delta"] is None


def test_shadow_comparison_matches_manual_crop_output():
    from core.commands import new_game
    from core.domains.production import crop_shadow as cs

    s = new_game("史实")
    route, p = next(iter(s.prefectures.items()))
    lv = 1
    staffed = 100_000
    expected = cs.crop_output(route, "丝", lv, staffed)
    rep = cs.shadow_output_comparison(s)
    row = next(r for r in rep["sample"] if r["route"] == route and r["crop"] == "丝")
    if row["level"] == lv and row["staffed"] == staffed:
        assert row["shadow_output"] == expected
