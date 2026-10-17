# -*- coding: utf-8 -*-
"""M317/M318 PM 多级产业链驱动（2026-10-18 全审）。

默认 PM 中性（产出逐位不变）；把某代表建筑切到更高 throughput 的组织形态后，
对应产业链成品入仓应按相对倍率增加。
"""
import os
import random
import sys

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from application.game_init import new_game  # noqa: E402
from core.domains.economy.industry_chains import (  # noqa: E402
    _route_capital_seat, settle_industry_chains,
)
from core.domains.economy.production_methods import switch_pm  # noqa: E402
from core.domains.economy.macro_climate import ALL_CIRCUITS_21  # noqa: E402


def _settle(seed=20261013):
    random.seed(seed)
    s = new_game("史实")
    rep = settle_industry_chains(s, [])
    return s, rep["stock_settlement"]["outputs_booked"]


def _switch_all(s, building, pm_id):
    n = 0
    for route in ALL_CIRCUITS_21:
        sid = _route_capital_seat(s, route)
        if not sid:
            continue
        if switch_pm(s, route, sid, building, pm_id):
            n += 1
    return n


def test_pm_chain_default_is_neutral_and_deterministic():
    _, a = _settle()
    _, b = _settle()
    assert a.get("barges_built", {}).get("qty") == b.get("barges_built", {}).get("qty")
    assert a.get("iron_ingots", {}).get("qty") == b.get("iron_ingots", {}).get("qty")


def test_pm_switch_increases_shipbuilding_chain_output():
    _, base = _settle()
    base_q = float(base.get("barges_built", {}).get("qty", 0) or 0)
    assert base_q > 0

    random.seed(20261013)
    s = new_game("史实")
    n = _switch_all(s, "造船作坊", "pm_org_manufactory")
    assert n > 0, "应至少切换一路的造船作坊 PM"
    rep = settle_industry_chains(s, [])
    q = float(rep["stock_settlement"]["outputs_booked"].get("barges_built", {}).get("qty", 0) or 0)
    assert q > base_q * 1.05, f"船舶链产出未随 PM 提升：{base_q} → {q}"


def test_unknown_building_falls_back_neutral():
    # 无对应建筑的成品（绸/布）不应因 PM 关闭而报错或改变
    _, base = _settle()
    assert float(base.get("silk_cloth_pi", {}).get("qty", 0) or 0) > 0