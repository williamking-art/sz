# -*- coding: utf-8 -*-
"""audit-core 5 项 P0 回归（2026-10-17）。

B-2 常平账不得覆盖官仓实物账；
B-5 配货必须把 resources 实搬到商人 goods 且 holding_report 闭合；
B-6 transfer_public_funds_to_pops 必须到治所真账、同步后 M_ALL 不变；
B-7 in_transit_batches/passenger_trips 存档往返；
B-8 derive_raw_production 纯派生，真实扣减每月一次。
"""
import os
import sys

import pytest

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from application.game_init import new_game
from core.foundation.ledger import money, pop_bridge
from core.foundation.ledger.grain_bridge import grain_add
from core.foundation.ledger.material_holding import (
    goods_amount, holding_report, merchant_goods, supply_goods_to_seats,
)
from core.foundation.ledger.spatial_warehouse_bridge import (
    advance_in_transit_batches, dispatch_spatial_transfer, warehouse_stock_add,
    warehouse_stock_get,
)
from core.foundation.ledger.storage_bridge import changping_add, changping_get
from core.settlement import run_monthly_settlement
from core.settlement_common import transfer_public_funds_to_pops
from core.save_load import save_game
from application.load_game import load_game
from core.domains.economy.mineral_deposit import (
    DIM_IRON, extract_circuit_minerals, get_circuit_minerals,
)
from core.domains.economy.industry_chains import derive_raw_production
from core.domains.economy.pop_livelihood import derive_pop_livelihood, settle_pop_livelihood


def _seat_sum_wealth(s, cls):
    return sum(int(((se.get("pops") or {}).get(cls) or {}).get("wealth", 0) or 0)
               for p in s.prefectures.values() for se in (p.get("seats") or {}).values())


def test_b2_changping_does_not_overwrite_public_granary():
    s = new_game()
    seat = "京畿路|开封府"
    warehouse_stock_add(s, seat, "public_granary", "grain", 12345.0)
    before_granary = warehouse_stock_get(s, seat, "public_granary", "grain")
    before_changping = changping_get(s, "京畿路")
    changping_add(s, "京畿路", 1000)
    assert warehouse_stock_get(s, seat, "public_granary", "grain") == before_granary, \
        "常平操作不得覆盖 public_granary 实物粮"
    assert changping_get(s, "京畿路") == before_changping + 1000


def test_b5_supply_moves_stock_into_empty_merchant_goods():
    s = new_game()
    dim = "木"
    s.resources.setdefault(dim, {"stock": 0, "cap": 5000})
    s.resources[dim]["stock"] = 1000
    before = 1000
    assert before > 0
    out = supply_goods_to_seats(s, dims=[dim])
    assert out.get(dim, 0) > 0, f"配货必须实际落商人 goods，实得 {out!r}"
    held = sum(int(goods_amount(merchant_goods(s, r), dim) or 0)
               for r in s.prefectures)
    after = int((s.resources.get(dim) or {}).get("stock", 0) or 0)
    assert held >= out[dim]
    assert after == before - out[dim], f"resources 应减少同样的搬运量：{before}->{after}"
    rep = holding_report(s)
    assert rep["ok"] is True, rep["dims"]
    assert rep["dims"][dim]["gap"] == 0
    # 幂等：第二次不得再膨胀或再扣
    out2 = supply_goods_to_seats(s, dims=[dim])
    assert out2.get(dim, 0) == 0
    assert int((s.resources.get(dim) or {}).get("stock", 0) or 0) == after


def test_b5_holding_report_rejects_unallocated_gap():
    s = new_game()
    s.resources.setdefault("木", {"stock": 0, "cap": 0})
    s.resources["木"]["stock"] = 1000
    rep = holding_report(s)
    assert rep["ok"] is False, "resources 有 1000 木但商人持有 0，不得判 ok"
    assert rep["dims"]["木"]["gap"] == 1000


def test_b6_transfer_public_funds_hits_seat_account_and_keeps_mall():
    s = new_game()
    m0 = money.m_all(s)
    before = _seat_sum_wealth(s, "官僚")
    got = transfer_public_funds_to_pops(s, 1000, {"官僚": 1.0}, "probe")
    assert got == 1000
    for p in s.prefectures.values():
        pop_bridge.sync_route_pops(p)
    assert _seat_sum_wealth(s, "官僚") == before + 1000, "到账必须落 seats 真账"
    assert money.m_all(s) == m0, "同步后 M_ALL 不得因写派生镜像而减少"


def test_b7_transit_batches_survive_save_load_and_arrive_conserved():
    slot = 93
    path = os.path.join(os.path.expanduser("~"), "Documents", "宋祚", "saves",
                        f"slot_{slot}.json")
    s = new_game()
    origin = next(iter(s.prefectures["京畿路"]["seats"]))
    target = next(iter(s.prefectures["两浙路"]["seats"]))
    warehouse_stock_add(s, origin, "public_depot", "铁", 500.0)
    dispatch = dispatch_spatial_transfer(
        s, origin, target, "铁", 300.0, "state:treasury", "overland")
    assert dispatch["ok"] is True
    before = list(getattr(s, "in_transit_batches", []) or [])
    assert len(before) == 1
    save_game(s, slot)
    try:
        loaded = load_game(slot)
        assert loaded is not None
        after = list(getattr(loaded, "in_transit_batches", []) or [])
        assert len(after) == 1, "在途批次必须随档往返"
        for key in ("batch_id", "origin_seat", "target_seat", "goods_dim", "gross_amount", "remaining_days"):
            assert after[0].get(key) == before[0].get(key)
        assert warehouse_stock_get(loaded, origin, "public_depot", "铁") == 200.0
        assert warehouse_stock_get(loaded, target, "public_depot", "铁") == 0.0
        arrived = advance_in_transit_batches(loaded, days=30)
        assert len(arrived) == 1
        assert warehouse_stock_get(loaded, origin, "public_depot", "铁") == 200.0
        assert warehouse_stock_get(loaded, target, "public_depot", "铁") == 300.0
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def test_b8_derive_raw_production_is_pure_and_monthly_extract_once():
    s = new_game()
    before = get_circuit_minerals(s, "河北路")[DIM_IRON]["reserves"]
    derive_raw_production(s, "河北路")
    assert get_circuit_minerals(s, "河北路")[DIM_IRON]["reserves"] == before, \
        "derive_raw_production 必须是纯派生，不得扣矿"
    derive_raw_production(s, "河北路")
    assert get_circuit_minerals(s, "河北路")[DIM_IRON]["reserves"] == before

    month = new_game()
    month_before = get_circuit_minerals(month, "河北路")[DIM_IRON]["reserves"]
    run_monthly_settlement(month)
    month_after = get_circuit_minerals(month, "河北路")[DIM_IRON]["reserves"]

    ref = new_game()
    ref_before = get_circuit_minerals(ref, "河北路")[DIM_IRON]["reserves"]
    extract_circuit_minerals(ref, "河北路", rate_mult=1.0, clerk_grip=0.45)
    ref_after = get_circuit_minerals(ref, "河北路")[DIM_IRON]["reserves"]
    assert month_before - month_after == ref_before - ref_after, \
        f"一月应只扣一次：month={month_before-month_after}, one_extract={ref_before-ref_after}"


def test_b8_same_turn_extract_is_idempotent():
    """同一 turn 内重复调用月度生计/提取只扣一次；纯派生读不扣矿。"""
    s = new_game()
    before = get_circuit_minerals(s, "河北路")[DIM_IRON]["reserves"]
    derive_pop_livelihood(s, "河北路")
    assert get_circuit_minerals(s, "河北路")[DIM_IRON]["reserves"] == before
    settle_pop_livelihood(s, [])
    mid = get_circuit_minerals(s, "河北路")[DIM_IRON]["reserves"]
    assert mid < before, "月度步应发生一次真实扣减"
    settle_pop_livelihood(s, [])
    assert get_circuit_minerals(s, "河北路")[DIM_IRON]["reserves"] == mid, \
        "同一 turn 重复调用不得二次扣减"
