# -*- coding: utf-8 -*-
"""批次 4：geo_admin.validate_geo 与 demography 拆分恒等式——原零测试盲区。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.geo_admin import (  # noqa: E402
    CIRCUIT_INFO, CIRCUIT_BOUNDS, PREFECTURE_ADMIN, REGIME_GEO, validate_geo,
)
from content.demography import (  # noqa: E402
    split_circuit_demog, split_circuit_demog_scoped,
    split_regime_prefecture_demog, SONG_SEAT_WEIGHTS,
)
from content.data import PREFECTURE_LIST, PREFECTURE_INFO  # noqa: E402


def test_validate_geo_clean():
    problems = validate_geo()
    assert problems == [], f"geo 一致性问题：{problems}"


def test_circuit_keys_aligned():
    assert set(CIRCUIT_INFO) == set(CIRCUIT_BOUNDS)
    assert set(PREFECTURE_ADMIN) == set(PREFECTURE_LIST)


def test_regime_polygons_closed():
    for key, geo in REGIME_GEO.items():
        if geo.get("use_parts"):
            continue
        poly = geo.get("polygon") or []
        assert len(poly) >= 4 and poly[0] == poly[-1], f"{key} 疆域未闭合"


def test_split_circuit_demog_conserves_totals():
    """拆分恒等式：Σ子分量 == 父级分量（人口/户/田/粮/税）。"""
    circuit = "京畿路"
    base = PREFECTURE_INFO.get(circuit)
    assert base, "京畿路 应在 PREFECTURE_INFO"
    members = [m[0] for m in CIRCUIT_INFO[circuit]["members"]]
    area_map = {n: 1.0 for n in members}
    out = split_circuit_demog(circuit, area_map)
    assert set(out) == set(members)
    for dim in ("population", "households", "land", "grain", "monthly_tax"):
        if base.get(dim) is None:
            continue
        s = sum(out[n].get(dim, 0) or 0 for n in members)
        assert abs(s - base[dim]) <= 1, f"{dim}: Σ{s} vs 父级 {base[dim]}"


def test_split_circuit_demog_unknown_or_empty():
    assert split_circuit_demog("不存在的路", {"a": 1.0}) == {}
    assert split_circuit_demog("京畿路", {}) == {}


def test_split_regime_prefecture_demog_shape():
    """政权拆分：有输出时键齐全且人口非负。"""
    from content.geo_admin import REGIME_DEMOG, REGIME_PREFECTURES
    if not REGIME_DEMOG:
        pytest.skip("无 REGIME_DEMOG")
    reg = next(iter(REGIME_DEMOG))
    prefs = REGIME_PREFECTURES.get(reg, {})
    if not prefs:
        pytest.skip("无 REGIME_PREFECTURES")
    rname = next(iter(prefs))
    names = list(prefs[rname])
    area_map = {n: 1.0 for n in names}
    out = split_regime_prefecture_demog(reg, area_map)
    assert out, f"{reg}/{rname} 应有拆分结果"
    for n, row in out.items():
        assert row["name"] == n and row["regime"] == reg
        assert (row.get("population") or 0) >= 0


def test_song_seat_weights_only_known_seats():
    for seat in SONG_SEAT_WEIGHTS:
        # 悬空键被忽略；这里只断言权重为正
        assert SONG_SEAT_WEIGHTS[seat] > 0


# ============================================================
# 省级归入口径（用户 2026-09-29 裁决）：无地图府块的治所按历史数据归入省级
# ============================================================
def _scoped_fixture():
    """用真有省级归入的路（荆湖北路·澧州）构造 area_map。"""
    circuit = "荆湖北路"
    members = [str(m[0]) for m in CIRCUIT_INFO[circuit]["members"]]
    blocked = [n for n in members if n != "澧州"]
    area_map = {n: 2.0 for n in blocked}
    return circuit, blocked, area_map, ["澧州"]


def test_split_scoped_default_matches_legacy():
    """`merged_seats=()` 时必须与旧函数**完全同行为**（残留为空）——不改既有口径。"""
    circuit, _b, area_map, _m = _scoped_fixture()
    by_seat, residual = split_circuit_demog_scoped(circuit, area_map)
    assert residual == {}
    assert by_seat == split_circuit_demog(circuit, area_map)


def test_split_scoped_keeps_merged_share_at_circuit_level():
    """省级归入的份额**不从邻府分得、也不摊给邻府**：Σ府块 + 残留 == 路级总量。"""
    circuit, blocked, area_map, merged = _scoped_fixture()
    base = PREFECTURE_INFO[circuit]
    by_seat, residual = split_circuit_demog_scoped(circuit, area_map, merged)
    assert set(by_seat) == set(blocked), "省级归入的治所不得出现在府块里"
    assert residual["merged_seats"] == ["澧州"]
    for dim in ("population", "households", "land", "grain", "monthly_tax"):
        if base.get(dim) is None:
            continue
        s = sum(by_seat[n].get(dim, 0) or 0 for n in blocked)
        assert s + int(residual.get(dim) or 0) == int(base[dim]), \
            f"{dim} 不守恒：Σ府块 {s} + 省级残留 {residual.get(dim)} ≠ {base[dim]}"
        assert int(residual.get(dim) or 0) > 0, f"{dim} 应有留在省级的份额"
    for dim, val in (base.get("yields") or {}).items():
        s = sum((by_seat[n].get("yields") or {}).get(dim, 0) or 0 for n in blocked)
        assert s + int((residual.get("yields") or {}).get(dim) or 0) == int(val), \
            f"yields.{dim} 不守恒"
    # 府块 yields 的键是**货品名**，不得出现 {"yields": …} 双层嵌套（回归 2026-09-29 实测缺陷）
    for n in blocked:
        assert "yields" not in (by_seat[n].get("yields") or {}), \
            f"{n} 的 yields 出现双层嵌套键"


def test_split_scoped_neighbor_share_is_not_inflated():
    """同面积下：把 澧州 记为省级归入后，邻府所得必须**严格少于**全量摊派。"""
    circuit, blocked, area_map, merged = _scoped_fixture()
    legacy = split_circuit_demog(circuit, area_map)
    scoped, _res = split_circuit_demog_scoped(circuit, area_map, merged)
    dim = "population"
    assert sum(scoped[n][dim] for n in blocked) < sum(legacy[n][dim] for n in blocked)


def test_split_scoped_unknown_or_empty():
    assert split_circuit_demog_scoped("不存在的路", {"a": 1.0}, ["b"]) == ({}, {})
    assert split_circuit_demog_scoped("京畿路", {}, ["b"]) == ({}, {})
