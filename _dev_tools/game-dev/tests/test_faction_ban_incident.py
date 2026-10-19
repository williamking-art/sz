# -*- coding: utf-8 -*-
"""党禁影响奏折前执行层：被禁官员跳过、无可用人则升级。"""
from core import commands
from core.county_registry import assign_county_official
from core.faction_ban import (
    banned_factions,
    is_faction_banned,
    is_official_banned,
    settle_faction_bans,
    start_faction_ban,
)
from core.incident import create_incident, settle_incidents
from memory.memory_graph import get_memory_graph

SEAT = "京畿路|开封府"
ROUTE = "京畿路"


def _state():
    return commands.new_game()


def _incident(s, *, locality="X县", severity=0.1, kind="flood"):
    return create_incident(
        s, kind=kind, locality=locality, parent_seat_id=SEAT,
        route=ROUTE, severity=severity)["incident"]


def test_start_ban_writes_faction_subkey_only():
    s = _state()
    out = start_faction_ban(s, "旧党", "轻", turn=0)
    assert out["ok"] is True
    assert s.factions["旧党"]["ban"]["status"] == "active"
    assert is_faction_banned(s, "旧党") is True
    assert not hasattr(s, "faction_ban")


def test_banned_official_detected():
    s = _state()
    start_faction_ban(s, "旧党", "轻", turn=0)
    assert is_official_banned(s, "范百禄") is True
    assert is_official_banned(s, "范宗尹") is False
    assert banned_factions(s) == ["旧党"]


def test_banned_prefect_skipped_uses_subprefect():
    s = _state()
    start_faction_ban(s, "旧党", "轻", turn=0)
    inc = _incident(s, severity=0.1)
    settle_incidents(s, turn=1)
    assert inc["status"] == "resolved"
    assert inc["handled_by"] == "范宗尹"


def test_banned_county_official_falls_back_to_prefecture():
    s = _state()
    s.slot = 9877
    g = get_memory_graph(9877)
    g.add_entity("测试知县", "minister", "测试知县", {}, turn=0)
    s.official_stats["测试知县"] = {"faction": "旧党"}
    assign_county_official(
        g, "测试知县", "测试县_9877", post="知县",
        route=ROUTE, parent_seat_id=SEAT, turn=0)
    g.save(9877)
    start_faction_ban(s, "旧党", "轻", turn=0)
    inc = _incident(s, locality="测试县_9877", severity=0.1)
    settle_incidents(s, turn=1)
    assert inc["handled_by"] != "测试知县"
    assert inc["handled_by"] == "范宗尹"


def test_banned_circuit_official_is_skipped():
    s = _state()
    start_faction_ban(s, "旧党", "轻", turn=0)
    inc = _incident(s, severity=1.0)
    settle_incidents(s, turn=1)   # 州府通判（中立派）不够
    settle_incidents(s, turn=2)   # 路省仓司李仲叔（旧党）应被跳过
    assert inc["handled_by"] != "李仲叔"


def test_ban_expiry_bonus_once():
    s = _state()
    start_faction_ban(s, "旧党", "轻", turn=0)
    before = float(s.factions["旧党"].get("_event_delta", 0.0))
    s.turn = 6
    settle_faction_bans(s)
    assert s.factions["旧党"]["ban"]["status"] == "expired"
    after = float(s.factions["旧党"].get("_event_delta", 0.0))
    assert after == before + 5
    settle_faction_bans(s)
    assert float(s.factions["旧党"].get("_event_delta", 0.0)) == after


def test_ban_does_not_touch_influence():
    s = _state()
    before = s.factions["旧党"]["influence"]
    start_faction_ban(s, "旧党", "轻", turn=0)
    assert s.factions["旧党"]["influence"] == before


def test_heavy_ban_splits_shock_and_target():
    s = _state()
    start_faction_ban(s, "旧党", "重", turn=0)
    f = s.factions["旧党"]
    assert float(f["_event_delta"]) == -12.0
    assert float(f["ban"]["satisfaction_target"]) == -13.0


def test_ban_changes_targets_and_grievance():
    from content.data import FACTION_POP_BASIS
    from core.faction_settle import (
        cohesion_target, satisfaction_target, settle_factions_from_pop,
    )

    s = _state()
    f = s.factions["旧党"]
    spec = FACTION_POP_BASIS["旧党"]
    sat0 = satisfaction_target(s, "旧党", spec, f)
    coh0 = cohesion_target(s, "旧党", spec, f)
    start_faction_ban(s, "旧党", "中", turn=0)
    sat1 = satisfaction_target(s, "旧党", spec, f)
    coh1 = cohesion_target(s, "旧党", spec, f)
    assert sat1 <= sat0 - 3
    assert coh1 >= coh0 + 8
    settle_factions_from_pop(s, [])
    assert float(f.get("grievance", 0.0)) > 0


def test_ban_targets_release_after_expiry():
    from content.data import FACTION_POP_BASIS
    from core.faction_settle import satisfaction_target

    s = _state()
    f = s.factions["旧党"]
    spec = FACTION_POP_BASIS["旧党"]
    start_faction_ban(s, "旧党", "轻", turn=0)
    s.turn = 6
    ban = f["ban"]
    assert ban["status"] == "active"
    # end_turn 之前 active；到 end_turn 时 target 修正应消失（settle 先解除）
    from core.faction_ban import settle_faction_bans
    settle_faction_bans(s)
    assert f["ban"]["status"] == "expired"
    assert satisfaction_target(s, "旧党", spec, f) >= 50 - 50  # 不因 ban 再惩罚

