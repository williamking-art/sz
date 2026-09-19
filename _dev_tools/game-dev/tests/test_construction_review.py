# -*- coding: utf-8 -*-
"""营建闭环回归（立项 -> 工程推进 -> 完工落成 -> adoption/维持费生效）。"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.asset_context import node_adoption_coverage  # noqa: E402
from core.construction import can_build, propose_project, resolve_blueprint  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.settlement_steps import _settle_projects, _settle_upkeep  # noqa: E402


def _s():
    s = GameState("史实")
    s.treasury = 10 ** 9
    return s


def _run_to_operating(s, pid, limit=20):
    for m in range(limit):
        _settle_projects(s, [])
        if s.projects[pid].get("status") == "operating":
            return m + 1
    return None


def test_resolve_blueprint_by_key_and_name():
    bp = resolve_blueprint("", key="C1_gunpowder")
    assert bp and bp["_name"] == "火药局"
    assert resolve_blueprint("火药局")["_key"] == "C1_gunpowder"
    assert resolve_blueprint("根本不存在的建筑") is None


def test_region_prerequisite_blocks_wrong_route():
    s = _s()
    cap = next((x for x, p in s.prefectures.items() if "京畿" in str(p.get("type"))), None)
    other = next((x for x, p in s.prefectures.items() if "京畿" not in str(p.get("type"))), None)
    assert cap and other
    ok_cap, errs_cap = can_build(s, cap, "国子监印书局", "I0_block")
    ok_other, errs_other = can_build(s, other, "国子监印书局", "I0_block")
    assert ok_cap, errs_cap
    assert not ok_other and any("地利" in e for e in errs_other)
    t0, b0 = s.treasury, dict(s.prefectures[other].get("buildings") or {})
    can_build(s, other, "国子监印书局", "I0_block")
    assert s.treasury == t0 and (s.prefectures[other].get("buildings") or {}) == b0


def test_unknown_blueprint_refused():
    s = _s()
    r = next(iter(s.prefectures))
    res = propose_project(s, r, "根本没有这座建筑")
    assert res["ok"] is False and res["errors"]


def test_propose_project_creates_proposed_entry():
    s = _s()
    r = next(iter(s.prefectures))
    res = propose_project(s, r, "水利")
    assert res["ok"], res["errors"]
    p = s.projects[res["pid"]]
    assert p["status"] == "proposed" and p["fund_cost"] == res["cost"] > 0
    assert 1 <= res["months"] <= 6
    assert p["speed"] == max(1, int(round(100.0 / res["months"])))


def test_propose_refuses_duplicate_and_bad_tech_treasury():
    s = _s()
    r = next(iter(s.prefectures))
    assert propose_project(s, r, "水利")["ok"]
    dup = propose_project(s, r, "水利")
    assert dup["ok"] is False and any("已有" in e for e in dup["errors"])
    s.tech["unlocked"] = []
    bad = propose_project(s, r, "火药局", "C1_gunpowder")
    assert bad["ok"] is False and any("科技前置" in e for e in bad["errors"])
    s2 = _s()
    s2.treasury = 1
    bad2 = propose_project(s2, next(iter(s2.prefectures)), "水利")
    assert bad2["ok"] is False and any("国库不足" in e for e in bad2["errors"])
    assert not any(str(p.get("name")) == "水利" for p in s2.projects.values())


def test_completion_lands_building_into_prefecture():
    s = _s()
    r = next(iter(s.prefectures))
    res = propose_project(s, r, "水利", levels=1)
    assert res["ok"], res["errors"]
    assert (s.prefectures[r].get("buildings") or {}) == {}
    assert _run_to_operating(s, res["pid"]) is not None
    assert s.prefectures[r]["buildings"]["水利"] == 1


def test_completion_enables_upkeep_and_adoption():
    s = _s()
    r = next(iter(s.prefectures))
    s.tech["unlocked"] = list(s.tech.get("unlocked") or []) + ["C1_gunpowder"]
    cov0 = round(node_adoption_coverage(s, "C1_gunpowder"), 6)
    s.treasury = 10 ** 9
    paid0 = _settle_upkeep(s, [])
    res = propose_project(s, r, "火药局", "C1_gunpowder", levels=4)
    assert res["ok"], res["errors"]
    assert _run_to_operating(s, res["pid"]) is not None
    assert s.prefectures[r]["buildings"]["火药局"] == 4
    s.treasury = 10 ** 9
    assert _settle_upkeep(s, []) > paid0
    assert round(node_adoption_coverage(s, "C1_gunpowder"), 6) > cov0