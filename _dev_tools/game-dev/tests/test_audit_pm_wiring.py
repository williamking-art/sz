# -*- coding: utf-8 -*-
"""M317/M318 生产方式（PM）相对倍率接线回归（2026-10-17）。"""
import os
import sys

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from application.game_init import new_game
from core.domains.economy.production_methods import (
    BUILDING_DEFAULT_PMS, relative_throughput_multiplier, switch_pm,
)
from core.domains.economy.seat_goods_readout import route_of_workshop
from core.foundation.ledger.building_bridge import capital_seat_id
from core.settlement import run_monthly_settlement

ROUTE = "京畿路"
BUILDING = "造船作坊"
WID = "造船作坊_京畿路_1"


def _seat_of(s, route):
    p = s.prefectures[route]
    return capital_seat_id(p, route) or next(iter(p["seats"]))


def _with_probe_workshop(upgrade=False):
    s = new_game()
    s.workshops = {WID: {"name": BUILDING, "recipe": {}, "output_dim": "绸",
                         "yield": 100, "active": True}}
    seat = _seat_of(s, ROUTE)
    if upgrade:
        assert switch_pm(s, ROUTE, seat, BUILDING, "pm_org_manufactory") is True
    return s, seat


def test_relative_multiplier_default_is_exactly_one():
    s, seat = _with_probe_workshop(False)
    assert BUILDING in BUILDING_DEFAULT_PMS
    assert relative_throughput_multiplier(s, ROUTE, seat, BUILDING) == 1.0
    # 未知建筑同样中性
    assert relative_throughput_multiplier(s, ROUTE, seat, "不存在作坊") == 1.0


def test_relative_multiplier_upgrade_and_restore():
    s, seat = _with_probe_workshop(False)
    assert switch_pm(s, ROUTE, seat, BUILDING, "pm_org_manufactory") is True
    assert abs(relative_throughput_multiplier(s, ROUTE, seat, BUILDING) - 1.8) < 1e-9
    assert switch_pm(s, ROUTE, seat, BUILDING, "pm_org_craft_guild") is True
    assert relative_throughput_multiplier(s, ROUTE, seat, BUILDING) == 1.0


def test_invalid_pm_config_is_neutral():
    s, seat = _with_probe_workshop(False)
    key = f"{ROUTE}:{seat}:{BUILDING}"
    s.statistics.setdefault("seat_production_methods", {})[key] = {
        "base": "not_a_pm", "power": "also_missing",
        "ownership": "pm_ownership_state", "organization": "pm_org_craft_guild",
    }
    assert relative_throughput_multiplier(s, ROUTE, seat, BUILDING) == 1.0


def _monthly_output(upgrade):
    s, _seat = _with_probe_workshop(upgrade)
    run_monthly_settlement(s)
    return int(s.statistics.get("workshop_finished_goods", 0) or 0)


def test_pm_wiring_from_monthly_settlement_default_upgrade_restore():
    out_default = _monthly_output(False)
    out_upgrade = _monthly_output(True)
    assert out_default == 100, out_default
    assert out_upgrade == 180, out_upgrade
    assert out_upgrade > out_default

    # 切回默认后真实月结复原
    s, seat = _with_probe_workshop(False)
    assert switch_pm(s, ROUTE, seat, BUILDING, "pm_org_manufactory") is True
    assert switch_pm(s, ROUTE, seat, BUILDING, "pm_org_craft_guild") is True
    run_monthly_settlement(s)
    assert int(s.statistics.get("workshop_finished_goods", 0) or 0) == 100
