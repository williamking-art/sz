# -*- coding: utf-8 -*-
"""质量放行门 · P3 季节通航窗口（2026-10-18）。

规则：封冻停航（等下一窗口）、枯水减载、汛期降速/抬风险、飓风抬风险、雪封降速。
本门钉住：
1. 北方内河 11–2 月停航，`deferred_to` 指向 3 月；
2. 枯水月载重 < 1、速度 < 1；
3. 海运夏季风险 > 1（飓风）但不停航；
4. 陆路冬季降速（雪封）；
5. `month` 缺失 ⇒ `open=None`（**不臆断**通航）；
6. 驿传不受季节影响（快马/急递）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from content.data_constants import SEASON_RULES  # noqa: E402
from core.transport import route_season  # noqa: E402


def test_rules_cover_all_modes():
    for mode in ("waterway", "maritime", "overland", "post"):
        assert mode in SEASON_RULES, mode


def test_waterway_closed_in_winter_with_deferred_month():
    for m in (11, 12, 1, 2):
        r = route_season("waterway", m)
        assert r["open"] is False, m
        assert r["deferred_to"] == 3, r
    assert route_season("waterway", 3)["open"] is True


def test_low_water_reduces_capacity():
    r = route_season("waterway", 3)
    assert 0 < r["capacity_mult"] < 1
    assert 0 < r["speed_mult"] <= 1


def test_maritime_monsoon_risk_not_closure():
    r = route_season("maritime", 7)
    assert r["open"] is True
    assert r["risk_mult"] > 1


def test_overland_snow_slows_but_open():
    r = route_season("overland", 1)
    assert r["open"] is True and r["speed_mult"] < 1


def test_missing_month_is_unknown_not_open():
    r = route_season("waterway", None)
    assert r["open"] is None and r["reason"] == "month_missing"


def test_post_unaffected():
    for m in range(1, 13):
        r = route_season("post", m)
        assert r["open"] is True and r["speed_mult"] == 1.0 and r["risk_mult"] == 1.0