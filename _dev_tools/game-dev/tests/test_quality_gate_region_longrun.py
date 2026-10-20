# -*- coding: utf-8 -*-
"""质量放行门 · 外邦人口长局守恒（2026-10-20）。

背景：外邦省份人口每月演化，此前只在开局分解一次州府 ⇒ 60 月回放实测 7 条失配。
修复：结算末尾按省**精确重摊**州府（尾差归最大省）+ 国级人口尾差归最大省。

本门（12 月，测速友好）钉住：
1. 每月末 `verify_pop_conservation` == []（Σ州府 == 省，逐类三层字段）；
2. 每月末 `verify_aggregation` == []（Σ省人口 == 国人口×10000，精确）；
3. 每月末 `verify_region_invariants` == []；
4. 跑完 `regions` 数量与 T1/T2 计数不变（无块丢失）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.foundation.ledger.region_registry import (  # noqa: E402
    verify_aggregation, verify_pop_conservation, verify_region_invariants)

MONTHS = 12


def _state():
    from core.commands import new_game

    return new_game()


def test_longrun_conservation():
    from core.settlement import run_monthly_settlement

    s = _state()
    base = (len(s.regions),
            sum(1 for r in s.regions.values() if r["level"] == "T1"),
            sum(1 for r in s.regions.values() if r["level"] == "T2"))
    for i in range(MONTHS):
        run_monthly_settlement(s)
        assert verify_pop_conservation(s) == [], f"第 {i+1} 月人口守恒违规：{verify_pop_conservation(s)[:2]}"
        assert verify_aggregation(s) == [], f"第 {i+1} 月国级对账违规：{verify_aggregation(s)[:2]}"
        assert verify_region_invariants(s) == [], f"第 {i+1} 月行政区不变量违规"
    now = (len(s.regions),
           sum(1 for r in s.regions.values() if r["level"] == "T1"),
           sum(1 for r in s.regions.values() if r["level"] == "T2"))
    assert now == base, (now, base)