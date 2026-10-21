# -*- coding: utf-8 -*-
"""E 最小切片（Jev A 0.901）：行政区划只读覆盖盘点——只清点、不改 state。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


def test_coverage_report_counts_and_read_only():
    from core.commands import new_game
    from core.foundation.ledger.region_registry import coverage_report

    s = new_game("史实")
    before = json.dumps(s.regions, ensure_ascii=False, sort_keys=True, default=str)
    rep = coverage_report(s)
    after = json.dumps(s.regions, ensure_ascii=False, sort_keys=True, default=str)
    assert before == after, "覆盖盘点不得改 regions"
    assert rep["report_only"] is True
    assert rep["counts"]["total"] == len(s.regions)
    assert rep["counts"]["song_registered_t1"] == \
        sum(len((p or {}).get("seats") or {}) for p in s.prefectures.values())
    assert 0.0 <= rep["counts"]["song_coverage"] <= 1.0
    assert rep["counts"]["by_level"].get("T1", 0) > 0
    assert rep["counts"]["by_level"].get("T2", 0) > 0


def test_coverage_report_surfaces_data_gaps():
    from core.commands import new_game
    from core.foundation.ledger.region_registry import coverage_report

    s = new_game("史实")
    rep = coverage_report(s)
    gaps = rep["data_gaps"]
    assert isinstance(gaps["missing_province_pops"], list)
    assert isinstance(gaps["unallocated_provinces"], list)
    # 缺失省人口只报告、不臆造：每条都应有 owner/province
    for row in gaps["missing_province_pops"]:
        assert row.get("owner") is not None and row.get("province")
    assert rep["ok"] is True, rep["issues"]
