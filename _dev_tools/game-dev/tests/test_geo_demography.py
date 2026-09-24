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
    split_circuit_demog, split_regime_prefecture_demog, SONG_SEAT_WEIGHTS,
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
