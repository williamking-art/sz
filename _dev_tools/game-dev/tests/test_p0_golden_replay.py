# -*- coding: utf-8 -*-
"""P0 golden replay：同种子 new_game + 12 月结算快照；行为变化必须显式更新基线。"""
from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

BASELINE = Path(__file__).with_name("testdata") / "p0_golden_12m.json"


def _snapshot(s) -> dict:
    def num(v):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        return round(float(v), 4)

    routes = {}
    pop_size = pop_wealth = pop_grain = 0.0
    for route, pdata in (getattr(s, "prefectures", None) or {}).items():
        p = (pdata or {}).get("pops") or {}
        sz = num(p.get("size")) or 0.0
        routes[str(route)] = {
            "pops_size": round(sz, 4),
            "seats": len(((pdata or {}).get("seats") or {})),
            "treasury": num(((pdata or {}).get("treasury"))),
        }
        pop_size += sz
        pop_wealth += num(p.get("wealth")) or 0.0
        pop_grain += num(p.get("grain")) or 0.0
    army_troops = sum(int(getattr(u, "troops", 0) or 0)
                      for u in (getattr(s, "army_units", None) or []))
    return {
        "year": s.year, "month": s.month, "turn": s.turn, "era_name": s.era_name,
        "treasury": num(s.treasury), "imperial_treasury": num(getattr(s, "imperial_treasury", None)),
        "granary": num(getattr(s, "granary", None)),
        "pops_size": round(pop_size, 4), "pops_wealth": round(pop_wealth, 4),
        "pops_grain": round(pop_grain, 4), "army_troops": army_troops,
        "finance": {k: num(v) for k, v in sorted((getattr(s, "finance", None) or {}).items())},
        "routes": dict(sorted(routes.items())),
    }


def test_golden_12m_snapshot():
    from core.commands import new_game
    from core.settlement import run_monthly_settlement

    random.seed(20261021)
    s = new_game("史实")
    for _ in range(12):
        run_monthly_settlement(s)
    snap = _snapshot(s)

    if os.environ.get("P0_GOLDEN_WRITE") == "1":
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(snap, ensure_ascii=False, indent=1, sort_keys=True),
                            encoding="utf-8")
        pytest.skip("已写入 golden 基线")
    assert BASELINE.is_file(), "缺 golden 基线；用 P0_GOLDEN_WRITE=1 生成"
    assert snap == json.loads(BASELINE.read_text(encoding="utf-8")), \
        "12 月结算与 golden 基线不一致：行为变化必须显式更新基线并说明原因"
