# -*- coding: utf-8 -*-
"""党禁令：高皇威直行/低皇威入队/幂等。"""
from core import commands
from core.party_ban_order import (
    LEDGER_KEY, PENDING_KEY, can_ban_immediately,
    issue_party_ban_order, settle_party_ban_orders,
)


def _state(prestige=50):
    s = commands.new_game()
    s.prestige = prestige
    return s


def test_high_prestige_immediate():
    s = _state(95)
    assert can_ban_immediately(s) is True
    out = issue_party_ban_order(
        s, faction="旧党", level="轻", executor="李清臣",
        decree_id="d1")
    assert out["ok"] is True
    assert out["immediate"] is True
    assert s.factions["旧党"]["ban"]["status"] == "active"
    assert int(s.prestige) == 87
    assert out["order"]["status"] == "applied"
    assert not s.statistics.get(PENDING_KEY)


def test_low_prestige_queues_then_applies():
    s = _state(50)
    assert can_ban_immediately(s) is False
    out = issue_party_ban_order(
        s, faction="旧党", level="中", executor="李清臣",
        decree_id="d2")
    assert out["ok"] is True
    assert out["immediate"] is False
    assert out["order"]["status"] == "pending"
    assert out["order"]["due_turn"] == 1
    assert s.statistics[PENDING_KEY]
    s.turn = 1
    res = settle_party_ban_orders(s)
    assert res["applied"] == 1
    assert s.factions["旧党"]["ban"]["status"] == "active"
    assert out["order"]["status"] == "applied"
    assert not s.statistics[PENDING_KEY]


def test_threshold_is_strict():
    s = _state(90)
    assert can_ban_immediately(s) is False
    out = issue_party_ban_order(s, faction="旧党", level="轻")
    assert out["immediate"] is False
    assert out["order"]["status"] == "pending"


def test_direct_order_idempotent():
    s = _state(95)
    a = issue_party_ban_order(s, faction="旧党", level="轻", decree_id="same")
    b = issue_party_ban_order(s, faction="旧党", level="轻", decree_id="same")
    assert a["immediate"] is True
    assert b.get("duplicate") is True
    assert int(s.prestige) == 87
    assert s.statistics[LEDGER_KEY][a["order"]["order_id"]]["status"] == "applied"


def test_invalid_faction_or_level():
    s = _state(95)
    assert issue_party_ban_order(s, faction="不存在", level="轻")["ok"] is False
    assert issue_party_ban_order(s, faction="旧党", level="超重")["ok"] is False

