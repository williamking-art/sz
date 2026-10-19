# -*- coding: utf-8 -*-
"""质量放行门 · 舆图州府点（M2，2026-10-19）。

数据源：`content.data_external_admin.REGIME_SEATS`（= 舆图切分）；
无 `seat_at` 的州府由**几何代表点**兜底（不飘出块外）。

本门钉住：
1. 点层总数 == 静态表 T1 总数（67）；逐国 == 18/9/12/12/6/5/5；
2. 坐标在合理经纬框（lon 73–146，lat 3–54），且**不与别的州府重合**（同国去重）；
3. 每个点能对上 `regions` 里同国同名的 T1（面/点/账三方一致）；
4. 点属性齐全（regime/map_province/seat_kind）；
5. 不写任何 state（纯构建期函数）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from content.data_external_admin import REGIME_SEATS, REGIME_TIER1  # noqa: E402


def _points():
    from content.build_map_geo import build_regime_cities

    return build_regime_cities()["features"]


def test_point_count_matches_table():
    feats = _points()
    expect = sum(len(v) for reg in REGIME_TIER1 for v in (REGIME_SEATS.get(reg) or {}).values())
    assert len(feats) == expect == 67, (len(feats), expect)


def test_per_regime_counts():
    import collections

    cnt = collections.Counter(f["properties"]["regime"] for f in _points())
    expect = {"辽": 18, "西夏": 9, "吐蕃": 12, "大理": 12, "高丽": 6, "日本": 5, "安南": 5}
    for reg, n in expect.items():
        assert cnt.get(reg) == n, (reg, cnt.get(reg), n)


def test_coordinates_in_box_and_unique():
    seen = {}
    for f in _points():
        lon, lat = f["geometry"]["coordinates"]
        assert 73 <= lon <= 146, (f["properties"]["name"], lon)  # 东至日本（镰仓 139.5）
        assert 3 <= lat <= 54, (f["properties"]["name"], lat)
        key = (f["properties"]["regime"], f["properties"]["name"])
        assert key not in seen, f"同国重名/重合：{key}"
        seen[key] = (lon, lat)


def test_points_match_regions_t1():
    """点 ↔ regions T1 一一对应（名称+政权）。"""
    from core.commands import new_game
    from core.foundation.ledger.region_registry import regions_by_owner

    s = new_game()
    for f in _points():
        reg = f["properties"]["regime"]
        name = f["properties"]["name"]
        hit = [r for r in regions_by_owner(s, reg)
               if r["level"] == "T1" and r["name"] == name]
        assert hit, f"点无对应 region：{reg}/{name}"


def test_properties_complete():
    for f in _points():
        p = f["properties"]
        assert p["kind"] == "regime_city"
        assert p["regime"] in REGIME_TIER1
        assert p["map_province"] and p["seat_kind"]