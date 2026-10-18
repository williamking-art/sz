# -*- coding: utf-8 -*-
"""PM 投入配方平衡（2026-10-18）。

锁定：
1. 默认 PM ⇒ 配方**逐字段不变**（默认中性）；
2. 燃料替换：切木炭土炉 ⇒ 煤炭→木炭；切焦炭 ⇒ 煤炭×0.8；
3. 动力/组织：蒸汽追加煤炭 2%、工场追加木 1%；
4. 真实 `_settle_workshops`：默认耗煤炭，切木炭后改耗木炭。
"""
import os
import sys

import pytest

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from application.game_init import new_game  # noqa: E402
from core.foundation.ledger.building_bridge import capital_seat_id  # noqa: E402
from core.domains.economy.production_methods import (  # noqa: E402
    adjusted_recipe, relative_throughput_multiplier, switch_pm,
)
from core.settlement_econ import _settle_workshops  # noqa: E402


def _setup(route="京畿路"):
    s = new_game("史实")
    seat = capital_seat_id(s.prefectures[route], route)
    return s, route, seat


def test_default_pm_recipe_is_neutral():
    s, route, seat = _setup()
    for building, recipe in (
        ("冶铁作坊", {"铁": 1000.0, "煤炭": 300.0}),
        ("官窑瓷坊", {"黏土": 1000.0, "煤炭": 500.0}),
        ("丝坊", {"丝": 1000.0}),
        ("火药局", {"硝石": 500.0, "硫磺": 300.0, "木炭": 200.0}),
    ):
        out = adjusted_recipe(s, route, seat, building, recipe)
        assert out == pytest.approx(recipe), f"{building} 默认 PM 不应改配方：{out}"


def test_charcoal_substitutes_coal_for_iron_workshop():
    s, route, seat = _setup()
    assert switch_pm(s, route, seat, "冶铁作坊", "pm_smelting_charcoal")
    out = adjusted_recipe(s, route, seat, "冶铁作坊", {"铁": 1000.0, "煤炭": 300.0})
    assert out["铁"] == pytest.approx(1000.0)
    assert out.get("煤炭", 0.0) == pytest.approx(0.0)
    assert out["木炭"] == pytest.approx(300.0)
    assert relative_throughput_multiplier(s, route, seat, "冶铁作坊") == pytest.approx(1.0 / 1.5)


def test_charcoal_substitutes_coal_for_kiln():
    s, route, seat = _setup()
    assert switch_pm(s, route, seat, "官窑瓷坊", "pm_ceramics_charcoal")
    out = adjusted_recipe(s, route, seat, "官窑瓷坊", {"黏土": 1000.0, "煤炭": 500.0})
    assert out["黏土"] == pytest.approx(1000.0)
    assert out.get("煤炭", 0.0) == pytest.approx(0.0)
    assert out["木炭"] == pytest.approx(500.0)


def test_steam_power_adds_two_percent_coal():
    s, route, seat = _setup()
    s.steam_engine_unlocked = True       # 前置科技（生产开关，非本用例变量）
    assert switch_pm(s, route, seat, "冶铁作坊", "pm_power_steam")
    out = adjusted_recipe(s, route, seat, "冶铁作坊", {"铁": 1000.0, "煤炭": 300.0})
    assert out["煤炭"] == pytest.approx(300.0 + 1300.0 * 0.02)


def test_manufactory_adds_one_percent_wood():
    s, route, seat = _setup()
    assert switch_pm(s, route, seat, "冶铁作坊", "pm_org_manufactory")
    out = adjusted_recipe(s, route, seat, "冶铁作坊", {"铁": 1000.0, "煤炭": 300.0})
    assert out["木"] == pytest.approx(1300.0 * 0.01)


def _seed(s):
    for d in ("铁", "煤炭", "木炭"):
        s.resources.setdefault(d, {"stock": 0, "cap": 0})["stock"] = 10000


def _stocks(s):
    return {d: int(s.resources[d]["stock"]) for d in ("铁", "煤炭", "木炭")}


def test_real_workshop_consumes_switched_fuel():
    s, route, seat = _setup()
    wid = f"冶铁作坊_{route}_1"
    s.workshops = {wid: {"active": True, "name": "冶铁作坊", "seat": seat,
                         "recipe": {"铁": 1000, "煤炭": 300},
                         "output_dim": "熟铁", "yield": 800.0}}
    _seed(s)
    _settle_workshops(s, [])
    st = _stocks(s)
    assert st["铁"] == 9000 and st["煤炭"] == 9700 and st["木炭"] == 10000

    _seed(s)
    assert switch_pm(s, route, seat, "冶铁作坊", "pm_smelting_charcoal")
    _settle_workshops(s, [])
    st = _stocks(s)
    assert st["铁"] == 9000 and st["煤炭"] == 10000 and st["木炭"] == 9700