# -*- coding: utf-8 -*-
"""质量放行门 · 天道档位化第一批：灾情严重度（2026-10-19）。

用户：「能用天道裁决的就用天道裁决」；Jev 边界 A（只改情境强度类，0.644）。

钉住：
1. **是否成灾**仍由频次模型（roll >= 0.03 ⇒ 不成灾，不看天道）；
2. 天道档位 → 严重度：轻1 / 中3 / 重4 / 极重5；
3. 天道可指定受灾路；未指定 ⇒ 程序在最内层随机（保留混沌）；
4. 天道缺档 ⇒ 程序 1–5 均匀兜底且 `source` 明确（不许静默取中值）；
5. provider 可注入档位（优先于兜底）；
6. 非法档位被拒（不崩、走兜底）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.domains.events import disaster_tier as dt  # noqa: E402


class _S:
    def __init__(self, severity=None, region=None, note=""):
        self._disaster_ai = {}
        if severity:
            self._disaster_ai = {"severity": severity, "region": region, "note": note}


def test_frequency_gate_keeps_deterministic():
    s = _S(severity="极重")
    got = dt.resolve_disaster(s, roll=0.99)
    assert got["occur"] is False and got["severity"] == 0


def test_tier_mapping():
    for tier, level in (("轻", 1), ("中", 3), ("重", 4), ("极重", 5)):
        got = dt.resolve_disaster(_S(severity=tier), roll=0.0)
        assert got["occur"] and got["severity"] == level, (tier, got)
        assert got["source"] == "天道"


def test_region_from_heaven():
    got = dt.resolve_disaster(_S(severity="重", region="河北"), roll=0.0)
    assert got["region"] == "河北"
    assert got["note"] == ""


def test_missing_tier_falls_back_with_source():
    got = dt.resolve_disaster(_S(), roll=0.0)
    assert got["occur"] and 1 <= got["severity"] <= 5
    assert "兜底" in got["source"]


def test_provider_injection():
    dt.register_disaster_provider(lambda st: {"severity": "中", "region": "陕西", "note": "provider"})
    try:
        got = dt.resolve_disaster(_S(), roll=0.0)
        assert got["severity"] == 3 and got["region"] == "陕西"
        assert "provider" in got["source"]
    finally:
        dt._PROVIDERS.clear()


def test_invalid_tier_rejected_to_fallback():
    s = _S()
    s._disaster_ai = {"severity": "巨大无比"}
    got = dt.resolve_disaster(s, roll=0.0)
    assert got["occur"] and "兜底" in got["source"]