# -*- coding: utf-8 -*-
"""产业链维表并轨（2026-10-18）。

链原料英文键（coal/iron_ore/clay/...）归一为 `RESOURCE_DIMS` 中文商品维；
仓储、需求、PM 规则从此使用同一套维名（不再出现「需求问 煤炭、仓里存 coal」）。
"""
import os
import sys

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from content.data_constants import RESOURCE_DIMS  # noqa: E402
from core import commands  # noqa: E402
from core.domains.economy.industry_chains import (  # noqa: E402
    CHAIN_DIM_ALIAS, _estimate_chain_input_demand, canonical_raw_dims,
    settle_industry_chains,
)


def test_canonical_raw_dims_maps_legacy_keys():
    out = canonical_raw_dims({
        "coal": 10, "iron_ore": 20, "clay": 3, "timber": 4,
        "silk_raw": 5, "hemp_raw": 6, "copper_ore": 7,
        "sugar_cane": 8, "hides_raw": 9, "stone": 2, "grain": 100,
    })
    assert out["煤炭"] == 10 and out["铁"] == 20 and out["黏土"] == 3
    assert out["木"] == 4 and out["丝"] == 5 and out["麻"] == 6
    assert out["铜"] == 7 and out["蔗"] == 8 and out["皮革"] == 9
    assert out["石"] == 2 and out["grain"] == 100
    assert not any(k in out for k in ("coal", "iron_ore", "clay", "timber"))


def test_sulfur_niter_splits_into_niter_and_sulfur():
    out = canonical_raw_dims({"sulfur_niter": 10})
    assert out["硝石"] == 6 and out["硫磺"] == 4


def test_chain_input_demand_uses_canonical_dims_only():
    demand = _estimate_chain_input_demand({
        "iron_ingots": 100, "copper_ingots": 50, "fine_china_pieces": 10,
        "gunpowder_jin": 20, "cloth_pi": 30, "paper": 5,
        "tanned_leather_jin": 10, "sugar_jin": 10,
        "four_treasures_pieces": 2, "timber_beams": 50,
    })
    legacy = set(CHAIN_DIM_ALIAS) | {"sulfur_niter"}
    assert not (set(demand) & legacy), f"仍残留英文维：{set(demand) & legacy}"
    allowed = set(RESOURCE_DIMS) | {"grain"}
    assert set(demand) <= allowed, f"出现未登记维：{set(demand) - allowed}"
    assert demand["煤炭"] > 0 and demand["铁"] > 0 and demand["黏土"] > 0


def test_settlement_ingests_canonical_dims_into_warehouses():
    s = commands.new_game()
    rep = settle_industry_chains(s, [])
    ss = rep["stock_settlement"]
    assert ss["mode"] == "warehouse_stock_to_stock", ss
    assert ss["input_coverage"] > 0
    assert "煤炭" in ss["inputs"] and "铁" in ss["inputs"]
    keys = set()
    for p in s.prefectures.values():
        for seat in (p.get("seats") or {}).values():
            for wh in ((seat or {}).get("warehouses") or {}).values():
                keys.update(((wh or {}).get("stocks") or {}).keys())
    assert {"煤炭", "铁", "黏土"} <= keys
    assert not ({"coal", "iron_ore", "clay"} & keys), "仓库仍有英文维残留"

def test_chain_demand_is_default_neutral_with_state():
    """给 state 时默认 PM 仍逐位等于无 state 的理论需求。"""
    outs = {"iron_ingots": 100.0, "fine_china_pieces": 10.0, "gunpowder_jin": 5.0}
    s = commands.new_game()
    assert _estimate_chain_input_demand(outs, s) == _estimate_chain_input_demand(outs)


def test_chain_demand_consumes_pm_fuel_switch():
    """并轨后产业链需求可直接消费 PM 燃料替换：切木炭 ⇒ 煤炭 0、木炭 > 0。"""
    from core.domains.economy.macro_climate import ALL_CIRCUITS_21
    from core.domains.economy.production_methods import switch_pm
    from core.foundation.ledger.building_bridge import capital_seat_id

    outs = {"iron_ingots": 100.0, "fine_china_pieces": 10.0}
    s = commands.new_game()
    base = _estimate_chain_input_demand(outs, s)
    assert base["煤炭"] > 0

    switched = 0
    for route in ALL_CIRCUITS_21:
        p = s.prefectures.get(route) or {}
        seat = capital_seat_id(p, route)
        if not seat:
            continue
        switched += int(bool(switch_pm(s, route, str(seat), "冶铁工场", "pm_smelting_charcoal")))
        switched += int(bool(switch_pm(s, route, str(seat), "官窑瓷坊", "pm_ceramics_charcoal")))
    assert switched > 0

    after = _estimate_chain_input_demand(outs, s)
    assert after.get("煤炭", 0.0) == 0.0, after
    assert after["木炭"] > 0, after