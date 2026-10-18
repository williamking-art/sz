# -*- coding: utf-8 -*-
"""M1b-3c：权限挂在职位上——任命即有，免职即无。"""
from types import SimpleNamespace

import pytest

from core import commands
from core.permission_model import (
    has_permission,
    permission_capture,
    permission_holders,
    resolve_actor,
)


def _state():
    return commands.new_game()


def _org(posts, holders, matter="官吏铨选"):
    return {
        "posts": [{"title": t} for t in posts],
        "holders": dict(holders),
        "matter_keys": [matter],
        "authority": [matter],
        "abolished": False,
    }


def test_lead_minister_holds_permission():
    s = _state()
    assert has_permission(s, "邓洵武", "官吏铨选") is True


def test_other_department_minister_lacks_permission():
    s = _state()
    assert has_permission(s, "王古", "官吏铨选") is False


def test_org_resolves_to_current_holder_not_department():
    s = _state()
    assert resolve_actor(s, "吏部") == "邓洵武"
    assert resolve_actor(s, {"org": "吏部"}) == "邓洵武"


def test_deputy_holds_permission_when_lead_vacant():
    s = SimpleNamespace(
        central_orgs={"X": _org(["主官", "副官"], {"主官": "", "副官": "邓洵武"})},
        factions={}, turn=0,
    )
    assert resolve_actor(s, "X") == "邓洵武"
    assert has_permission(s, "邓洵武", "官吏铨选") is True


def test_all_posts_vacant_means_permission_unheld():
    s = SimpleNamespace(
        central_orgs={"X": _org(["主官", "副官"], {"主官": "", "副官": ""})},
        factions={}, turn=0,
    )
    assert resolve_actor(s, "X") is None
    assert permission_holders(s, "官吏铨选") == []


def test_any_filled_post_carries_org_permission():
    s = SimpleNamespace(
        central_orgs={"X": _org(["主官", "副官"], {"主官": "邓洵武", "副官": "王古"})},
        factions={}, turn=0,
    )
    assert permission_holders(s, "官吏铨选") == ["王古", "邓洵武"]
    assert has_permission(s, "王古", "官吏铨选") is True


def test_appointment_grants_permission_and_dismissal_removes_it():
    org = _org(["主官"], {"主官": ""})
    s = SimpleNamespace(central_orgs={"X": org}, factions={}, turn=0)
    assert has_permission(s, "路人甲", "官吏铨选") is False
    org["holders"]["主官"] = "路人甲"
    assert has_permission(s, "路人甲", "官吏铨选") is True
    org["holders"]["主官"] = ""
    assert has_permission(s, "路人甲", "官吏铨选") is False


def test_same_person_multiple_posts_union_permissions():
    s = SimpleNamespace(
        central_orgs={
            "A": _org(["主官"], {"主官": "邓洵武"}, matter="官吏铨选"),
            "B": _org(["主官"], {"主官": "邓洵武"}, matter="赋税"),
        },
        factions={}, turn=0,
    )
    assert has_permission(s, "邓洵武", "官吏铨选") is True
    assert has_permission(s, "邓洵武", "赋税") is True


def test_permission_capture_by_faction():
    s = SimpleNamespace(
        central_orgs={"X": _org(["主官", "副官"], {"主官": "邓洵武", "副官": "王古"})},
        factions={}, turn=0,
    )
    assert permission_capture(s, "官吏铨选") == pytest.approx(
        {"新党": 0.5, "中立派": 0.5}
    )

