# -*- coding: utf-8 -*-
"""质量放行门 · 海运距离改走海路图（2026-10-18 用户：现在海运的距离怎么算）。

旧口径 = 大圆距离 × 1.2，不绕半岛（登州—密州直线 235km，实际须绕成山头）。
新口径 = 沿海岸线海路图最短路 + 两端河口加价。

本门钉住：
1. 段表自洽：端点都是真实治所、里程 > 0、每段有 note 依据；
2. 海路图**连通**（单一分量）；
3. 最长绕行不再被低估：登州→密州 > 500km、明州→泉州 > 900km；
4. 河口加价生效（杭州→明州 > 纯段里程和）；
5. 非海港 ⇒ None（不臆造直线）；
6. 路径每跳都是段表里的边；hops == len(path)-1；
7. 能力判定与 `sea_route` 同源（km/days 一致）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from content.data_constants import (  # noqa: E402
    SEA_INLET_EXTRA_KM, SEA_LANES)
from core.foundation.ledger.prefecture_entity import all_seats  # noqa: E402
from core.transport import sea_lanes_graph, sea_route  # noqa: E402

DENGRUO, MIZHOU = "京东东路|登州", "京东东路|密州"
MINGZHOU, QUANZHOU = "两浙路|明州", "福建路|泉州"
HANGZHOU = "两浙路|杭州"


def test_lane_table_is_sane():
    ids = {s["seat_id"] for s in all_seats()}
    assert SEA_LANES, "海路段表为空 ⇒ 门是空转"
    for lane in SEA_LANES:
        assert lane["a"] in ids and lane["b"] in ids, f"段端点不是真实治所：{lane}"
        assert float(lane.get("km") or 0) > 0, f"段里程非正：{lane}"
        assert lane.get("note"), f"段缺依据：{lane}"


def test_graph_is_connected():
    nodes, adj = sea_lanes_graph()
    assert len(nodes) >= 10, f"海港过少：{nodes}"
    seen = set()
    stack = [nodes[0]]
    while stack:
        u = stack.pop()
        if u in seen:
            continue
        seen.add(u)
        stack.extend(adj.get(u, {}))
    assert seen == set(nodes), f"海路图不连通：孤立 {sorted(set(nodes) - seen)}"


def test_long_detours_are_not_underestimated():
    r1 = sea_route(DENGRUO, MIZHOU)
    assert r1 and r1["km"] >= 500, f"登州—密州须绕成山头，应 >=500km（实算 {r1}）"
    r2 = sea_route(MINGZHOU, QUANZHOU)
    assert r2 and r2["km"] >= 900, f"明州—泉州应沿浙闽海岸 >=900km（实算 {r2}）"


def test_inlet_extra_applies():
    lane_sum = 0.0
    for lane in SEA_LANES:
        if {lane["a"], lane["b"]} == {HANGZHOU, MINGZHOU}:
            lane_sum = float(lane["km"])
    assert lane_sum > 0
    r = sea_route(HANGZHOU, MINGZHOU)
    expect = lane_sum + SEA_INLET_EXTRA_KM.get(HANGZHOU, 0) + SEA_INLET_EXTRA_KM.get(MINGZHOU, 0)
    assert abs(r["km"] - expect) < 1e-6, f"河口加价未生效：{r["km"]} vs {expect}"


def test_non_port_returns_none():
    assert sea_route("两浙路|越州", QUANZHOU) is None, "非海港不得臆造航线"
    assert sea_route("陕西路|熙州", QUANZHOU) is None


def test_path_edges_exist_and_hops():
    r = sea_route(MINGZHOU, QUANZHOU)
    _nodes, adj = sea_lanes_graph()
    path = r["path"]
    assert path[0] == MINGZHOU and path[-1] == QUANZHOU
    assert r["hops"] == len(path) - 1
    for a, b in zip(path, path[1:]):
        assert b in adj.get(a, {}), f"路径含不存在的航段：{a}->{b}"


def test_capability_uses_same_distance():
    from core.commands import new_game
    from core.transport import transport_capability

    s = new_game()
    r = sea_route(MINGZHOU, QUANZHOU)
    cap = transport_capability(s, MINGZHOU, QUANZHOU, "sea")
    assert cap["ok"], cap
    assert cap["km"] == r["km"] and cap["days"] == r["days"], f"{cap} vs {r}"
    assert cap["hops"] == r["hops"]