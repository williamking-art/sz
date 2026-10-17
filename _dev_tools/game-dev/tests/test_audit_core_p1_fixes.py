# -*- coding: utf-8 -*-
"""audit-core 第二批 P1 回归（2026-10-17）。"""
import os
import sys
import types

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from application.game_init import new_game
from core.foundation.ledger import money
from core.foundation.ledger.spatial_warehouse_bridge import (
    dispatch_spatial_transfer, warehouse_stock_add, warehouse_stock_get,
)
from core.domains.economy import mineral_deposit as md
from core.domains.economy.spatial_warehouse_readout import (
    merchant_warehouse_summary, public_depot_summary, public_granary_summary,
)
from core.domains.economy.stock_identity import (
    in_transit_by_dim, pending_stock_by_dim, stock_snapshot,
)
from core.settlement import run_monthly_settlement
from core.settlement_decree import _apply_decree_effect
from core.save_load import save_game
from application.load_game import load_game
from core.foundation.persistence import migrations as mig


def _seat_wh_sum(s, wh_type, dim=None):
    out = {}
    found = False
    for p in s.prefectures.values():
        for se in (p.get("seats") or {}).values():
            wh = (se.get("warehouses") or {}).get(wh_type)
            if not isinstance(wh, dict):
                continue
            found = True
            stocks = wh.get("stocks") or {}
            for d, v in stocks.items():
                if dim is not None and d != dim:
                    continue
                if isinstance(v, (int, float)):
                    out[d] = out.get(d, 0.0) + float(v)
    return (out if found else None)


def test_p1_2_mineral_deposits_survive_save_load_and_old_default():
    slot = 92
    path = os.path.join(os.path.expanduser("~"), "Documents", "宋祚", "saves",
                        f"slot_{slot}.json")
    s = new_game()
    before = md.get_circuit_minerals(s, "河北路")[md.DIM_IRON]["reserves"]
    md.extract_circuit_minerals(s, "河北路")
    after = md.get_circuit_minerals(s, "河北路")[md.DIM_IRON]["reserves"]
    save_game(s, slot)
    try:
        loaded = load_game(slot)
        assert md.get_circuit_minerals(loaded, "河北路")[md.DIM_IRON]["reserves"] == after
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    old = new_game()
    del old.mineral_deposits
    mig.ensure_mineral_deposits(old)
    assert old.mineral_deposits["河北路"][md.DIM_IRON]["reserves"] > 0


def test_p1_3_warehouse_missing_dim_is_none_and_explicit_zero_is_zero():
    s = new_game()
    seat = next(iter(s.prefectures["京畿路"]["seats"]))
    assert warehouse_stock_get(s, seat, "public_depot", "不存在的维度") is None
    assert warehouse_stock_get(s, seat, "不存在的仓位", "铁") is None
    warehouse_stock_add(s, seat, "public_depot", "铁", 0.0)
    assert warehouse_stock_get(s, seat, "public_depot", "铁") == 0.0


def test_p1_4_warehouse_readouts_use_seat_true_accounts():
    s = new_game()
    run_monthly_settlement(s)
    depot = _seat_wh_sum(s, "public_depot")
    granary = _seat_wh_sum(s, "public_granary", "grain")
    summary = public_depot_summary(s)
    assert summary["total_materials"] == round(sum(depot.values()), 2)
    pg = public_granary_summary(s)
    assert pg["total_grain"] == round(sum(granary.values()), 1)
    empty = types.SimpleNamespace(prefectures={})
    assert public_depot_summary(empty)["total_materials"] is None
    assert public_granary_summary(empty)["total_grain"] is None
    assert merchant_warehouse_summary(empty)["total_holdings"] is None


def test_p1_5_stock_identity_includes_warehouses_pending_and_spatial_transit():
    s = new_game()
    run_monthly_settlement(s)
    snap = stock_snapshot(s)
    assert "seat_warehouses" in snap["by_custody"]
    actual = _seat_wh_sum_all(s)
    assert snap["by_custody"]["seat_warehouses"] == actual

    s.pending_stock = {"京畿路": {"木": {"qty": 123, "owner": None,
                                        "owner_status": "归属待定",
                                        "evidence_ref": None}}}
    assert pending_stock_by_dim(s).get("木") == 123.0

    origin = next(iter(s.prefectures["京畿路"]["seats"]))
    target = next(iter(s.prefectures["两浙路"]["seats"]))
    warehouse_stock_add(s, origin, "public_depot", "铁", 300.0)
    dispatch_spatial_transfer(s, origin, target, "铁", 100.0, "state:treasury", "overland")
    assert in_transit_by_dim(s).get("铁") == 100.0


def _seat_wh_sum_all(s):
    out = {}
    found = False
    for p in s.prefectures.values():
        for se in (p.get("seats") or {}).values():
            for wh in ((se.get("warehouses") or {}).values()):
                if not isinstance(wh, dict):
                    continue
                found = True
                for d, v in (wh.get("stocks") or {}).items():
                    if isinstance(v, (int, float)):
                        out[d] = out.get(d, 0.0) + float(v)
    return out if found else None


def test_p1_9_imperial_treasury_decree_has_counterparty():
    s = new_game()
    m0 = money.m_all(s)
    imp0 = s.imperial_treasury
    log = []
    _apply_decree_effect(s, {"effects": {"imperial_treasury": -1000}}, log)
    assert money.m_all(s) == m0, "内帑负值不得无对手方销毁"
    assert s.imperial_treasury <= imp0
    m1 = money.m_all(s)
    _apply_decree_effect(s, {"effects": {"imperial_treasury": 500}}, [])
    assert money.m_all(s) == m1, "内帑正值必须从 POP 实征"
