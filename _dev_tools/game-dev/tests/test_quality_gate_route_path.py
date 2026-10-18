# -*- coding: utf-8 -*-
"""质量放行门 · 多跳路由（G-3 P5a）。

用户 2026-10-18 批准「水运资格表走 A」后，先补**路由**（P5 的前置）：
`transport.route_days` 只判相邻（≤200km），超过即 None；跨路调拨需要**最短路**。

本门钉住：
1. 相邻对：`route_path` 的天数必须与既有 `route_days` 一致；
2. 远端对：可达、端点正确、**每一跳都 ≤ ADJACENT_KM**、天数 = ceil(km/KM_PER_MONTH)；
3. 不连通 ⇒ **显式 reachable=False**（不是 None、不回落 0、不臆造直线）；
4. 未知治所 ⇒ None；同点 ⇒ 0 天；对称性；缓存一致；
5. 连通性报告自洽（Σ分量 == 节点数，孤立点如实报）。
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.transport import (  # noqa: E402
    ADJACENT_KM, KM_PER_MONTH, connectivity_report, haversine_km, route_days,
    route_path, transport_graph)

CAPITAL = "京畿路|开封府"
NEAR = "京西路|河南府"
FAR_A = "两浙路|台州"
FAR_B = "陕西路|熙州"
UNKNOWN = "不存在路|不存在州"


def _km(sid_a: str, sid_b: str) -> float:
    idx = transport_graph()  # 只为触发索引构建
    from core.transport import _seat_index

    idx2 = _seat_index()
    a, b = idx2[sid_a], idx2[sid_b]
    return haversine_km(float(a["lon"]), float(a["lat"]), float(b["lon"]), float(b["lat"]))


def _adjacent_pairs(limit=8):
    _nodes, adj = transport_graph()
    out = []
    for a, nbrs in adj.items():
        for b in nbrs:
            out.append((a, b))
            if len(out) >= limit:
                return out
    return out


def test_adjacent_days_match_route_days():
    """相邻对：新路由与既有 route_days 的天数必须一致（不另立口径）。"""
    pairs = _adjacent_pairs(6)
    assert pairs, "邻接图没有任何边 ⇒ 门是空转"
    for a, b in pairs:
        r = route_path(a, b)
        assert r and r["reachable"] and r["hops"] == 1, f"{a}->{b}: {r}"
        assert r["days"] == route_days(a, b), f"{a}->{b} 天数不一致：{r["days"]} vs {route_days(a, b)}"


def test_far_route_is_multi_hop_and_each_hop_adjacent():
    """远端：多跳、端点正确、每跳 ≤ 阈值、天数 = ceil(km/月里程)。"""
    r = route_path(FAR_A, FAR_B)
    assert r and r["reachable"], f"远端应可达：{r}"
    path = r["path"]
    assert path[0] == FAR_A and path[-1] == FAR_B, path
    assert r["hops"] == len(path) - 1 >= 2, f"应多跳：{r}"
    for a, b in zip(path, path[1:]):
        km = _km(a, b)
        assert km <= ADJACENT_KM + 1e-6, f"跳距超阈值：{a}->{b} {km:.1f}km"
    total = sum(_km(a, b) for a, b in zip(path, path[1:]))
    assert abs(total - r["km"]) < 1.0, f"里程不一致：{total} vs {r["km"]}"
    assert r["days"] == max(1, math.ceil(total / KM_PER_MONTH))


def test_unknown_seat_returns_none():
    assert route_path(UNKNOWN, CAPITAL) is None
    assert route_path(CAPITAL, UNKNOWN) is None
    assert route_path("", CAPITAL) is None


def test_same_seat_zero_days():
    r = route_path(CAPITAL, CAPITAL)
    assert r == {"reachable": True, "path": [CAPITAL], "km": 0.0, "days": 0, "hops": 0}


def test_symmetry_and_cache_consistency():
    a = route_path(CAPITAL, NEAR)
    b = route_path(NEAR, CAPITAL)
    assert a["days"] == b["days"] and a["km"] == b["km"]
    again = route_path(CAPITAL, NEAR)
    assert again == a, "缓存前后结果不一致"


def test_disconnected_is_explicit_not_instant():
    """不连通的治所必须显式 reachable=False（不得 None、不得 0 天）。"""
    rep = connectivity_report()
    comps = rep["components"]
    if len(comps) < 2:
        return  # 全图连通时不适用
    a, b = comps[0][0], comps[1][0]
    r = route_path(a, b)
    assert r is not None, "已知治所不得返回 None（None 只表示未知）"
    assert r["reachable"] is False, f"跨分量应不可达：{r}"
    assert r["days"] is None and r["path"] == []


def test_connectivity_report_is_self_consistent():
    rep = connectivity_report()
    total = sum(len(c) for c in rep["components"])
    assert total == rep["node_count"], f"Σ分量 {total} != 节点数 {rep["node_count"]}"
    assert rep["isolated"] == [c[0] for c in rep["components"] if len(c) == 1]
    assert rep["connected"] == (len(rep["components"]) <= 1)