# -*- coding: utf-8 -*-
"""军令皇威差异：高皇威跳过执行侧事权，低皇威必须枢密院/掌调兵。"""
from core import commands, imperial_mandate
from core.commands import issue_military_order

TARGET = "京畿路"


def _state(prestige=55):
    s = commands.new_game()
    s.prestige = prestige
    return s


def test_military_dispatch_implemented():
    spec = imperial_mandate.spec("military_dispatch")
    assert spec is not None
    assert spec.implemented is True


def test_high_prestige_bypasses_executor_authority():
    s = _state(90)
    unit = s.army_units[0]
    assert imperial_mandate.can_direct(s, "military_dispatch") is True
    msg = issue_military_order(
        s, unit.unit_id, "地图调度", target=TARGET, executor="户部")
    assert "未成" not in msg
    assert int(s.prestige) == 85


def test_low_prestige_requires_military_authority():
    s = _state(55)
    unit = s.army_units[0]
    assert imperial_mandate.can_direct(s, "military_dispatch") is False
    msg = issue_military_order(
        s, unit.unit_id, "地图调度", target=TARGET, executor="户部")
    assert "未成" in msg
    assert int(s.prestige) == 55


def test_dispatch_alias_and_procedure_executor():
    s = _state(55)
    unit = s.army_units[0]
    msg = issue_military_order(
        s, unit.unit_id, "调度军令", target=TARGET, executor="枢密院")
    assert "未成" not in msg

