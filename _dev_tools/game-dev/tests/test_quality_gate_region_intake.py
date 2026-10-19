# -*- coding: utf-8 -*-
"""质量放行门 · P5.5 攻占接收口径（2026-10-19）。

Jev 裁定：**只计人口/土地，税产冻结**（A 0.614 / B 0.262 / C 0.124）。

本门钉住：
1. 无占领地 ⇒ `population=None`（缺失≠0）、`t1_count=0`；
2. 占辽 南京道 ⇒ 人口 **114.0 万**（= 该省 1,140,000），**treasury 仍 0**（税产冻结）；
3. 占宋 京畿路 ⇒ 人口来自 seats 真账；`land=None` + `land_missing_regions` 列出（宋座无土地字段，**不假造**）；
4. `frozen_regions` 覆盖全部被占地（税产不立即归占领方）；
5. 和议归还 ⇒ intake 回到 0。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.domains.diplomacy.regime_intake import regime_intake  # noqa: E402
from core.domains.diplomacy.regime_transfer import (  # noqa: E402
    revert_change, transfer_regions)
from core.foundation.ledger.region_registry import regions_by_owner  # noqa: E402


def _state():
    from core.commands import new_game

    return new_game()


def test_no_territory_is_none():
    s = _state()
    got = regime_intake(s, "金")
    assert got["t1_count"] == 0
    assert got["population_people"] is None and got["population_reason"]


def test_absorb_liao_province_counts_people_not_tax():
    s = _state()
    out = transfer_regions(s, "辽", "金", ["辽_p0"], create_to=True, reason="接收")
    assert out["ok"], out
    got = regime_intake(s, "金")
    assert got["t1_count"] == 3
    assert got["population_wan"] == 114.0, got
    assert got["tax_output_frozen"] is True
    assert int(s.external_regimes["金"].get("treasury") or 0) == 0


def test_absorb_song_seats_uses_real_ledger_and_flags_missing_land():
    s = _state()
    seats = [r for r in regions_by_owner(s, "宋")
             if r["level"] == "T1"
             and (r.get("prefecture_ref") or {}).get("route") == "京畿路"]
    transfer_regions(s, "宋", "金", [r["region_id"] for r in seats],
                     create_to=True, reason="接收宋地")
    got = regime_intake(s, "金")
    assert got["t1_count"] == len(seats)
    assert got["population_people"] and got["population_people"] > 0
    assert got["land"] is None
    assert len(got["land_missing_regions"]) == len(seats)
    assert set(got["frozen_regions"]) >= {r["region_id"] for r in seats}


def test_frozen_covers_all_occupied():
    s = _state()
    out = transfer_regions(s, "辽", "金", ["辽_p1"], create_to=True, reason="冻结")
    got = regime_intake(s, "金")
    moved_t1 = [m for m in out["moved"] if s.regions[m]["level"] == "T1"]
    assert set(got["frozen_regions"]) >= set(moved_t1), got


def test_revert_clears_intake():
    s = _state()
    out = transfer_regions(s, "辽", "金", ["辽_p0"], create_to=True, reason="归还")
    assert regime_intake(s, "金")["t1_count"] == 3
    assert revert_change(s, out["change_id"])["ok"]
    got = regime_intake(s, "金")
    assert got["t1_count"] == 0 and got["population_people"] is None, got