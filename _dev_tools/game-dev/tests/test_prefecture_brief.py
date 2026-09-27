# -*- coding: utf-8 -*-
"""P0 · 地方档案（州府级）派生断言：守恒 / 治安正极性 / 隐田脱敏。

对应方案 `_dev_tools/game-docs/analysis/地方档案面板方案_2026-09-27.md` §4 验证项 10、11。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState                      # noqa: E402
from core.region_brief import (                            # noqa: E402
    build_prefecture_brief, build_region_brief, _security,
)

_DIMS = ("population", "households", "land", "grain_year", "tax_month")


def _new_state():
    return GameState("史实")


def test_prefecture_brief_conserves_route_totals():
    """**Σ府 == 路级**（守恒）：府级只做份额分配，不得新增账本、不得丢量。"""
    s = _new_state()
    routes = {r["name"]: r for r in build_region_brief(s)["routes"]}
    pb = build_prefecture_brief(s)
    assert pb["prefectures"], "府级行不得为空"
    assert pb["audit"]["violations"] == [], f"守恒被破坏：{pb['audit']['violations'][:3]}"

    agg = {}
    for row in pb["prefectures"]:
        bucket = agg.setdefault(row["route"], {k: 0.0 for k in _DIMS})
        for k in _DIMS:
            bucket[k] += float(row[k])
    for route, sums in agg.items():
        assert route in routes, f"府级出现了未知路：{route}"
        for k, got in sums.items():
            want = float(routes[route][k])
            tol = 0.05 if k == "tax_month" else 0.5
            assert abs(got - want) <= tol, f"{route}.{k}: Σ府={got} ≠ 路级={want}"


def test_security_is_positive_polarity():
    """治安 = 100 − 动乱（**越高越好**）；用户 2026-09-27 纠正极性口径。"""
    s = _new_state()
    rows = build_region_brief(s)["routes"]
    assert rows
    for r in rows:
        assert abs(r["security"] - (100.0 - r["unrest"])) < 0.05, r["name"]
        assert r["security"] == _security(r["unrest"])
        assert isinstance(r["security_label"], str) and r["security_label"]
    # 边界：动乱 0 → 治安 100（太平）；动乱 100 → 治安 0（不靖）
    assert _security(0) == 100.0 and _security(100) == 0.0
    assert _security(0) > _security(60)          # 正极性：越少动乱治安越高


def test_hidden_land_not_exposed_before_survey():
    """**未清丈只下发约值**：真值不得出现在读数里；清丈（隐匿率<0.2）后才给真数。"""
    s = _new_state()
    row = build_region_brief(s)["routes"][0]
    assert row["surveyed"] is False, "开局隐田率应高于清丈门槛"
    assert "hidden_land" not in row, "未清丈不得下发隐田真值（脱敏）"
    assert row["hidden_land_band"], "应给档位词"
    assert isinstance(row["hidden_land_est"], int) and row["hidden_land_est"] >= 0

    p = s.prefectures[row["name"]]
    p["land"] = 10_000_000
    p["hidden_land"] = 100_000                   # 隐匿率 ≈ 0.99% < 0.2 → 视为已清丈
    row2 = next(r for r in build_region_brief(s)["routes"] if r["name"] == row["name"])
    assert row2["surveyed"] is True
    assert row2["hidden_land"] == 100_000, "清丈后应给真数"
