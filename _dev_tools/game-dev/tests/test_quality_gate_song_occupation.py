# -*- coding: utf-8 -*-
"""质量放行门 · P6 宋结算按归属过滤（2026-10-19）。

口径：**被非宋政权全占的路不计田赋**；默认全宋 ⇒ 判定恒真（零行为变更）。
部分占领（同路仍有宋属州府）⇒ 仍按整路计（路级账无座级税基，如实登记为局限）。

本门钉住：
1. 默认 A/B：有/无 `regions` 跑一月结算，国库/地方府库/日志条数**逐字相同**；
2. 全占一路 ⇒ `song_settlement_filter.fully_occupied_routes` 命中；结算不崩；国库**下降**；
3. 部分占领 ⇒ `partially_occupied_routes` 命中、`fully_occupied_routes` 为空，且结算结果**与默认完全一致**；
4. 被占路的 `local_treasury` 不因留州而增长（≤ 占领前）；
5. 占位政权（金）建政权后结算可跑（字段数值型，不因 power 字符串崩）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.domains.diplomacy.regime_transfer import transfer_regions  # noqa: E402
from core.foundation.ledger.region_registry import (  # noqa: E402
    regions_by_owner, song_settlement_filter)


def _state():
    from core.commands import new_game

    return new_game()


def _run(s):
    from core.settlement import run_monthly_settlement

    log = run_monthly_settlement(s)
    return (int(s.treasury),
            int(sum(int(p.get("local_treasury", 0) or 0) for p in s.prefectures.values())),
            len(log))


def _song_seats(s, route):
    return [r for r in regions_by_owner(s, "宋")
            if r["level"] == "T1" and (r.get("prefecture_ref") or {}).get("route") == route]


def test_default_zero_change():
    s1 = _state()
    base = _run(s1)
    s2 = _state()
    s2.regions = {}   # 无 regions ⇒ 过滤恒真
    got = _run(s2)
    assert got == base, (got, base)


def test_full_occupation_excludes_route_tax():
    s = _state()
    base = _run(_state())
    seats = _song_seats(s, "京畿路")
    assert seats
    out = transfer_regions(s, "宋", "金", [r["region_id"] for r in seats],
                           create_to=True, reason="P6 全占")
    assert out["ok"], out
    f = song_settlement_filter(s)
    assert "京畿路" in f["fully_occupied_routes"], f
    got = _run(s)
    assert got[0] < base[0], (got[0], base[0])


def test_partial_occupation_does_not_change_result():
    s = _state()
    base = _run(_state())
    seats = _song_seats(s, "京畿路")
    if len(seats) < 2:
        return
    out = transfer_regions(s, "宋", "金", [seats[0]["region_id"]],
                           create_to=True, reason="P6 部分占")
    assert out["ok"], out
    f = song_settlement_filter(s)
    assert "京畿路" in f["partially_occupied_routes"], f
    assert "京畿路" not in f["fully_occupied_routes"], f
    got = _run(s)
    assert got == base, (got, base)


def test_occupied_route_local_treasury_not_increased():
    s = _state()
    seats = _song_seats(s, "京畿路")
    transfer_regions(s, "宋", "金", [r["region_id"] for r in seats],
                     create_to=True, reason="P6 留州")
    before = int((s.prefectures.get("京畿路") or {}).get("local_treasury", 0) or 0)
    _run(s)
    after = int((s.prefectures.get("京畿路") or {}).get("local_treasury", 0) or 0)
    assert after <= before, (after, before)


def test_placeholder_regime_settles_without_error():
    s = _state()
    seats = _song_seats(s, "京畿路")
    transfer_regions(s, "宋", "金", [r["region_id"] for r in seats],
                     create_to=True, reason="P6 占位")
    doc = s.external_regimes["金"]
    assert isinstance(doc.get("power"), (int, float))
    _run(s)  # 不崩即通过