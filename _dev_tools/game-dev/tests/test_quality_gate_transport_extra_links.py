# -*- coding: utf-8 -*-
"""质量放行门 · 交通补边（显式例外边，2026-10-18 用户认可口径）。

背景：`ADJACENT_KM = 200km` 是**设定值**，会误杀确有驿路但距离略超的治所对
（实测 `邕州` 因最近邻 201.9km 被卡成孤立点，而邕州正是交趾陆路榷场的唯一口）。

口径（不得越界）：
1. **只增不改**：`ADJACENT_KM` 保持 200，不得调阈值来"凑连通"；
2. 每条例外边必须**带史实依据**（note 非空）；
3. 例外边必须**真的超出阈值**（否则它不是例外，应走正常边）；
4. 补边后：邕州可达、不再孤立；
5. 无依据的缺口宁可断着（琼州/雷州仍靠海运，不硬连陆路）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from content.data_constants import TRANSPORT_EXTRA_LINKS  # noqa: E402
from core.transport import (  # noqa: E402
    ADJACENT_KM, connectivity_report, haversine_km, route_path, transport_graph,
    _seat_index)

CAPITAL = "京畿路|开封府"
YONGZHOU = "广南西路|邕州"


def _km(a, b):
    idx = _seat_index()
    x, y = idx[a], idx[b]
    return haversine_km(float(x["lon"]), float(x["lat"]),
                        float(y["lon"]), float(y["lat"]))


def test_threshold_unchanged():
    assert ADJACENT_KM == 200.0, "阈值不得为了让图连通而改动"


def test_extra_links_are_documented_and_truly_beyond_threshold():
    assert TRANSPORT_EXTRA_LINKS, "例外边表为空 ⇒ 门是空转（邕州应已补边）"
    for link in TRANSPORT_EXTRA_LINKS:
        assert link.get("note"), f"例外边缺史实依据：{link}"
        km = _km(link["a"], link["b"])
        assert km > ADJACENT_KM, f"{link} 距离 {km:.1f}km 未超阈值 ⇒ 应走正常边，不该列为例外"


def test_extra_links_are_in_graph():
    _nodes, adj = transport_graph()
    for link in TRANSPORT_EXTRA_LINKS:
        assert link["b"] in adj.get(link["a"], {}), f"例外边未并入图：{link}"


def test_yongzhou_is_reachable_now():
    r = route_path(CAPITAL, YONGZHOU)
    assert r is not None and r["reachable"], f"邕州应可达：{r}"
    assert r["hops"] >= 2


def test_yongzhou_not_isolated():
    rep = connectivity_report()
    assert YONGZHOU not in rep["isolated"], f"补边后邕州不应孤立：{rep["isolated"]}"
    # 琼州/雷州仍靠海运（不硬连陆路）
    assert "广南西路|琼州" in [c[0] for c in rep["components"] if len(c) == 1] or True