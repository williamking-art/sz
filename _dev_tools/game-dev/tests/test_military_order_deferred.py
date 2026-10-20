# -*- coding: utf-8 -*-
"""低皇威军令走流程：入枢密院待次月批红；高皇威仍直行。"""
from core import commands
from core.commands import issue_military_order
from core.military_order import settle_military_orders


def _state(prestige):
    s = commands.new_game()
    s.prestige = prestige
    return s


def test_low_prestige_defers_until_next_turn():
    s = _state(55)
    unit = s.army_units[0]
    before = unit.training
    msg = issue_military_order(
        s, unit.unit_id, "整编", scale=3, executor="枢密院", defer=True)
    assert "待 1 回合" in msg
    assert unit.training == before
    pending = [a for a in s.ai_pending_actions
               if a.get("kind") == "military_dispatch"
               and a.get("payload", {}).get("defer")]
    assert len(pending) == 1
    assert pending[0]["payload"]["due_turn"] == 1
    s.turn = 1
    out = settle_military_orders(s)
    assert out["applied"] == 1
    assert unit.training > before
    assert pending[0]["status"] == "approved"


def test_high_prestige_ignores_defer_and_is_immediate():
    s = _state(90)
    unit = s.army_units[0]
    before = unit.training
    msg = issue_military_order(
        s, unit.unit_id, "整编", scale=3, executor="户部", defer=True)
    assert "已入枢密院议" not in msg
    assert unit.training > before
    assert int(s.prestige) == 85
    assert not [a for a in s.ai_pending_actions
                if a.get("kind") == "military_dispatch"
                and a.get("payload", {}).get("defer")]

