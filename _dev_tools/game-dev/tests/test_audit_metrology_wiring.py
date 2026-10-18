# -*- coding: utf-8 -*-
"""M324 度量衡效果接线回归（2026-10-17）。"""
import copy
import os
import re
import sys

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from application.game_init import new_game
from core.domains.administration import institution
from core.domains.economy import land_tenure
from core.foundation.ledger.spatial_warehouse_bridge import (
    dispatch_spatial_transfer, warehouse_stock_add,
)
from core.foundation.metrology import (
    MetrologyEngine, active_effects, SYSTEM_SONG_TRADITIONAL,
    SYSTEM_SONG_UNIFIED, SYSTEM_MODERN_METRIC,
)
from core.settlement import run_monthly_settlement


def _set_system(s, system_id):
    institution.set_param(s, "metrology_system_id", float(system_id))


def _run_one_month_with_custom_workshop(system_id):
    s = new_game()
    s.workshops = {
        "probe_ws": {"name": "探针坊", "recipe": {}, "output_dim": "绸",
                     "yield": 100, "active": True},
    }
    _set_system(s, system_id)
    run_monthly_settlement(s)
    return s, int(s.statistics.get("workshop_finished_goods", 0) or 0)


def test_metrology_active_effects_mapping():
    s = new_game()
    assert active_effects(s)["manufacturing_mult"] == 1.0
    _set_system(s, 1)
    assert active_effects(s)["manufacturing_mult"] == 1.10
    assert active_effects(s)["logistics_loss_reduction"] == 0.10
    _set_system(s, 2)
    assert active_effects(s)["manufacturing_mult"] == 1.30
    assert active_effects(s)["tax_leakage_resistance"] == 0.15
    # 非法值按传统 0 处理
    _set_system(s, 1.5)
    assert active_effects(s)["manufacturing_mult"] == 1.0
    assert MetrologyEngine.get_active_system(s) == SYSTEM_SONG_TRADITIONAL


def test_workshop_manufacturing_multiplier_from_monthly_settlement():
    _, out0 = _run_one_month_with_custom_workshop(0)
    _, out1 = _run_one_month_with_custom_workshop(1)
    _, out2 = _run_one_month_with_custom_workshop(2)
    assert out0 == 100, out0
    assert out1 == 110, out1
    assert out2 == 130, out2
    assert out0 < out1 < out2


def _transport_net(system_id):
    s = new_game()
    # 2026-10-18：时效已分档（京畿→两浙陆路 36 天 > 1 个月），本用例需「单月内到货」，
    # 故改走同路短途（开封府→郑州，62km ⇒ 近程基准 15 天）。
    seats = list(s.prefectures["京畿路"]["seats"])
    origin, target = seats[0], seats[1]
    warehouse_stock_add(s, origin, "public_granary", "grain", 1000.0)
    disp = dispatch_spatial_transfer(
        s, origin, target, "grain", 1000.0, "state:treasury", "overland")
    assert disp["ok"] is True
    _set_system(s, system_id)
    log = run_monthly_settlement(s)
    line = next((str(x) for x in log if "本月运抵" in str(x)), "")
    m = re.search(r"本月运抵 ([\d.]+) 实物", line)
    assert m, line
    return float(m.group(1)), int(disp["days"])


def test_logistics_loss_reduction_from_monthly_settlement():
    net0, days = _transport_net(0)
    net1, _d1 = _transport_net(1)
    net2, _d2 = _transport_net(2)
    loss = 500 * 0.020 * days          # 运 1000 石陆路：porters=500、0.02 石/人·日
    assert abs(net0 - (1000.0 - loss)) < 1e-6, (net0, loss, days)
    assert net0 < net1 < net2
    assert abs(net1 - (1000.0 - loss * 0.90)) < 1e-6, net1
    assert abs(net2 - (1000.0 - loss * 0.75)) < 1e-6, net2


def test_fangtian_survey_tax_leakage_resistance():
    base = new_game()
    outs = []
    for sid in (0, 1, 2):
        s = copy.deepcopy(base)
        _set_system(s, sid)
        res = land_tenure.apply_fangtian_survey(s, "京畿路", intensity=0.25)
        assert res["ok"] is True, res
        outs.append(res["cleared_land"])
    assert outs[0] > 0
    assert outs[0] < outs[1] < outs[2], outs


def test_clerk_grip_resistance_from_monthly_settlement():
    base = new_game()
    grips = []
    for sid in (0, 1, 2):
        s = copy.deepcopy(base)
        _set_system(s, sid)
        run_monthly_settlement(s)
        grips.append(float(s.statistics.get("clerks_grip", 0) or 0))
    assert grips[0] > grips[1] > grips[2], grips


def test_apply_reform_gentry_unrest_spike_once():
    s = new_game()
    s.treasury = 1_000_000
    before = float(s.population_satisfaction)
    ok, msg, effects = MetrologyEngine.apply_reform(s, SYSTEM_SONG_UNIFIED)
    assert ok, msg
    assert float(s.population_satisfaction) == max(0.0, before - 2.0)
    after_first = float(s.population_satisfaction)
    # 再切到公制：一次性再加 6，不做持续累计
    ok2, msg2, _ = MetrologyEngine.apply_reform(s, SYSTEM_MODERN_METRIC)
    assert ok2, msg2
    assert float(s.population_satisfaction) == max(0.0, after_first - 6.0)
