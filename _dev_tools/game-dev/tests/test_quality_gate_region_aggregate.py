# -*- coding: utf-8 -*-
"""质量放行门 · P2 政权级聚合与对账（2026-10-19）。

口径（实测）：国级 `external_regimes[国].population` 单位 = **万人**；
运行态 `provinces[*].population` 单位 = **人** ⇒ `Σ省人口 == 国人口 × 10000`。

本门钉住：
1. 七国对账全通过（`verify_aggregation` 为空）；
2. 单位常数 `REGIME_POP_UNIT = 10000`；
3. T1 人口未分解的国家 ⇒ `pop_total=None` + reason（**缺失≠0**），不回落 0；
4. 宋从 `prefectures` 真账聚合：T1=117、6 类 POP 为 Σ治所；
5. 反证：把某国国级人口改错 ⇒ 对账必须报错（门不是空转）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.foundation.ledger.region_registry import (  # noqa: E402
    REGIME_POP_UNIT, aggregate_regime, aggregate_song, verify_aggregation)

TIER1 = ("辽", "西夏", "吐蕃", "大理", "高丽", "日本", "安南")


def _state():
    from core.commands import new_game

    return new_game()


def test_pop_unit_constant():
    assert REGIME_POP_UNIT == 10000


def test_all_regimes_reconcile():
    s = _state()
    assert verify_aggregation(s) == [], verify_aggregation(s)


def test_province_sum_equals_country_times_unit():
    s = _state()
    for owner in TIER1:
        agg = aggregate_regime(s, owner)
        assert agg["reconcile_ok"] is True, (owner, agg)
        assert agg["province_pop_sum"] == agg["country_population_people"], (owner, agg)


def test_missing_t1_pop_is_none_with_reason():
    s = _state()
    for owner in ("吐蕃", "高丽", "日本", "安南"):
        agg = aggregate_regime(s, owner)
        assert agg["pop_total"] is None, (owner, agg["pop_total"])
        assert agg["pop_reason"], owner


def test_song_aggregates_from_prefectures():
    s = _state()
    song = aggregate_song(s)
    assert song["t1_count"] == 117 and song["t2_count"] == 20
    pop = song["pop_total"]
    assert isinstance(pop, dict) and pop.get("农", 0) > 0
    # Σ治所 必须与 aggregate_song 的 农 人口相等（同一真账）
    total = 0
    for pdata in s.prefectures.values():
        for srow in (pdata.get("seats") or {}).values():
            p = ((srow or {}).get("pops") or {}).get("农") or {}
            total += int(p.get("size") or 0)
    assert pop["农"] == total, (pop["农"], total)


def test_reconcile_detects_wrong_country_pop():
    s = _state()
    s.external_regimes["辽"]["population"] = 1  # 故意改错
    bad = verify_aggregation(s)
    assert any("辽" in b for b in bad), bad