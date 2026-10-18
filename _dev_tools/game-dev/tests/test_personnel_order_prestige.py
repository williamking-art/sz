# -*- coding: utf-8 -*-
"""人事令：皇威 >80 当场任免；≤80 走流程（下一回合生效）。"""
from core import commands
from core.personnel_order import (
    PENDING_KEY,
    issue_personnel_order,
    settle_personnel_orders,
)

SEAT = "京畿路|开封府"


def _state():
    return commands.new_game()


def _appoint(s, name="测试官", executor="吏部"):
    return issue_personnel_order(
        s, action="appoint_circuit", executor=executor,
        circuit="京畿路", role_key="cao",
        official_data={"name": name, "faction": "中立派"},
    )


def _dismiss(s, executor="吏部"):
    return issue_personnel_order(
        s, action="dismiss_circuit", executor=executor,
        circuit="京畿路", role_key="cao", reason="测试罢免",
    )


def test_prestige_above_80_appoints_immediately():
    s = _state()
    s.prestige = 81
    out = _appoint(s, "甲")
    assert out["ok"] is True and out["immediate"] is True
    assert s.circuit_officials["京畿路"]["officials"]["cao"]["name"] == "甲"
    assert s.statistics.get(PENDING_KEY, []) == []


def test_prestige_at_80_queues_order():
    s = _state()
    s.prestige = 80
    out = _appoint(s, "乙")
    assert out["ok"] is True and out["immediate"] is False
    assert out["due_turn"] == 1
    assert len(s.statistics.get(PENDING_KEY, [])) == 1


def test_queued_order_applies_next_turn():
    s = _state()
    s.prestige = 80
    _appoint(s, "丙")
    s.turn = 1
    res = settle_personnel_orders(s)
    assert res["applied"] == 1
    assert s.circuit_officials["京畿路"]["officials"]["cao"]["name"] == "丙"
    assert s.statistics["personnel_order_ledger"]


def test_direct_bypasses_executor_permission_but_target_must_exist():
    s = _state()
    s.prestige = 90
    out = _appoint(s, "丁", executor={"org": "户部"})
    assert out["ok"] is True and out["immediate"] is True
    assert s.circuit_officials["京畿路"]["officials"]["cao"]["name"] == "丁"
    assert s.statistics.get(PENDING_KEY, []) == []

    bad = issue_personnel_order(
        s, action="appoint_circuit", executor={"org": "户部"},
        circuit="不存在", role_key="cao",
        official_data={"name": "戊", "faction": "中立派"},
    )
    assert bad["ok"] is False


def test_low_prestige_also_rejects_illegal_executor():
    s = _state()
    s.prestige = 80
    out = _appoint(s, "戊", executor={"org": "户部"})
    assert out["ok"] is False
    assert s.statistics.get(PENDING_KEY, []) == []


def test_immediate_dismiss_at_high_prestige():
    s = _state()
    s.prestige = 90
    _appoint(s, "己")
    out = _dismiss(s)
    assert out["ok"] is True and out["immediate"] is True
    assert s.circuit_officials["京畿路"]["officials"]["cao"].get("vacant") is True


def test_queued_dismiss_applies_next_turn():
    s = _state()
    s.prestige = 90
    _appoint(s, "庚")
    s.prestige = 80
    out = _dismiss(s)
    assert out["immediate"] is False
    s.turn = 1
    res = settle_personnel_orders(s)
    assert res["applied"] == 1
    assert s.circuit_officials["京畿路"]["officials"]["cao"].get("vacant") is True


def test_settle_is_idempotent():
    s = _state()
    s.prestige = 80
    _appoint(s, "辛")
    s.turn = 1
    first = settle_personnel_orders(s)
    second = settle_personnel_orders(s)
    assert first["applied"] == 1
    assert second["applied"] == 0
    assert len(s.statistics["personnel_order_ledger"]) == 1


def test_lost_authority_fails_queued_order():
    s = _state()
    s.prestige = 80
    _appoint(s, "壬")
    s.central_orgs["吏部"]["abolished"] = True
    s.turn = 1
    res = settle_personnel_orders(s)
    assert res["failed"] == 1
    ledger = list(s.statistics["personnel_order_ledger"].values())
    assert ledger and ledger[0]["status"] == "failed"


def test_threshold_boundary_80_vs_81():
    s80 = _state()
    s80.prestige = 80
    assert _appoint(s80, "癸")["immediate"] is False
    s81 = _state()
    s81.prestige = 81
    assert _appoint(s81, "子")["immediate"] is True


def test_direct_action_charges_prestige():
    s = _state()
    s.prestige = 90
    out = _appoint(s, "丑")
    assert out["ok"] is True
    assert out["prestige_cost"] == 2
    assert s.prestige == 88


def test_registry_declares_military_dispatch_as_pending():
    from core import imperial_mandate
    s = _state()
    s.prestige = 99
    military = imperial_mandate.spec("military_dispatch")
    assert military is not None
    assert military.threshold == 85
    assert military.implemented is False
    assert imperial_mandate.can_direct(s, "military_dispatch") is False


def test_unknown_action_not_direct():
    from core import imperial_mandate
    s = _state()
    s.prestige = 100
    assert imperial_mandate.can_direct(s, "not_an_action") is False

