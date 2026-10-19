# -*- coding: utf-8 -*-
"""质量放行门 · 舆图运行期 overlay 读数（M3，2026-10-19）。

原则：底图静态、归属运行期；overlay **只读** `state.regions`，不写 state、不重建 geojson。

本门钉住：
1. 行数 == `len(state.regions)`，T1/T2 计数与 regions 一致；
2. 开局 `owner_changed == 0`（owner 与静态底图一致 ⇒ 视觉零变更）；
3. 宋 T1 = 117、外邦 T1 = 67（`occupied` = 本朝以外）；
4. 调用前后 `state` **逐字不变**（只读）；
5. `transition` 只在 `transition_until > 当前月` 时为真；
6. 属性齐全（region_id/level/name/owner/parent）。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.domains.diplomacy.map_overlay import map_overlay, overlay_summary  # noqa: E402


def _state():
    from core.commands import new_game

    return new_game()


def test_rows_match_regions():
    s = _state()
    rows = map_overlay(s)
    assert len(rows) == len(s.regions), (len(rows), len(s.regions))
    t1 = sum(1 for r in rows if r["level"] == "T1")
    t2 = sum(1 for r in rows if r["level"] == "T2")
    assert t1 == 184 and t2 == 41, (t1, t2)


def test_start_state_has_no_owner_change():
    s = _state()
    assert overlay_summary(s)["owner_changed"] == 0, "开局 overlay 必须与底图一致"


def test_song_and_foreign_split():
    s = _state()
    rows = map_overlay(s)
    song_t1 = [r for r in rows if r["owner"] == "宋" and r["level"] == "T1"]
    assert len(song_t1) == 117, len(song_t1)
    assert all(not r["occupied"] for r in song_t1)
    foreign = [r for r in rows if r["owner"] != "宋"]
    assert len(foreign) == 88, len(foreign)
    assert all(r["occupied"] for r in foreign)


def test_read_only():
    s = _state()
    before = copy.deepcopy((s.regions, s.prefectures, int(s.treasury)))
    map_overlay(s)
    overlay_summary(s)
    after = (s.regions, s.prefectures, int(s.treasury))
    assert after == before, "overlay 不得写 state"


def test_transition_semantics():
    s = _state()
    from core.civil_building import abs_month_index

    now = abs_month_index(s)
    rid = next(iter(s.regions))
    s.regions[rid]["transition_until"] = int(now) + 3
    row = next(r for r in map_overlay(s) if r["region_id"] == rid)
    assert row["transition"] is True and row["transition_until"] == now + 3
    s.regions[rid]["transition_until"] = int(now) - 1
    row = next(r for r in map_overlay(s) if r["region_id"] == rid)
    assert row["transition"] is False


def test_properties_complete():
    s = _state()
    for r in map_overlay(s):
        assert r["region_id"] and r["level"] in ("T1", "T2")
        assert r["name"] and r["owner"] and r["parent"]