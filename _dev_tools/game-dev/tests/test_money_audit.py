# -*- coding: utf-8 -*-
"""批次 4：月度货币对账层（audit_step/reconcile/register_flow）——原零引用盲区。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core import money as M  # noqa: E402


def _s():
    return GameState("史实")


def test_register_flow_external_and_burn():
    s = _s()
    assert M.register_flow(s, "external", 100, "外贸") == 100
    assert M.register_flow(s, "burn", 50, "岁币") == 50
    assert M.register_flow(s, "external", 0) == 0
    with pytest.raises(ValueError):
        M.register_flow(s, "unknown", 1)
    flow = M.take_flow(s)
    assert flow["external_in"] == 100 and flow["burned"] == 50
    flow2 = M.take_flow(s)
    assert flow2["external_in"] == 0 and flow2["burned"] == 0


def test_reconcile_residual_formula():
    prev = {"M_ALL": 1000.0, "treasury": 1000.0}
    now = {"M_ALL": 1200.0, "treasury": 1200.0}
    r = M.reconcile(prev, now)
    assert abs(r["residual"] - 200.0) < 1e-6
    r2 = M.reconcile(prev, now, external_in=200.0)
    assert abs(r2["residual"]) < 1e-6
    now3 = {"M_ALL": 800.0, "treasury": 800.0}
    r3 = M.reconcile(prev, now3, burned=200.0)
    assert abs(r3["residual"]) < 1e-6


def test_audit_step_baseline_then_residual():
    s = _s()
    rec0 = M.audit_step(s)
    assert rec0["residual"] == 0.0
    assert isinstance(s.money_audit, dict) and "last" in s.money_audit
    s.treasury = int(s.treasury) + 50_000
    rec1 = M.audit_step(s)
    assert abs(rec1["residual"] - 50_000) < 1
    assert abs(s.money_audit["cum_residual"] - 50_000) < 1
    s.treasury = int(s.treasury) + 30_000
    M.register_flow(s, "external", 30_000, "白银流入")
    rec2 = M.audit_step(s)
    assert abs(rec2["residual"]) < 1
    assert abs(s.money_audit["cum_residual"] - 50_000) < 1


def test_describe_residual_readable():
    rec = {"residual": 12345.6, "deltas": {"treasury": 12345.6}}
    text = M.describe_residual(rec)
    assert "残差" in text and "造币" in text
    ok = M.describe_residual({"residual": 0.0, "deltas": {}})
    assert "通过" in ok


def test_audit_recent_capped():
    s = _s()
    for _ in range(30):
        M.audit_step(s)
    assert len(s.money_audit["recent"]) <= 24


def test_mint_distributes_net_without_remainder_loss():
    """P0-5：铸钱净增 _net 应足额入民间（尾差归最大府），并登记对账台账。"""
    from core.settlement_steps import _settle_mint
    from core.free_effect import _money_pools
    from content.data import COPPER_RESOURCE_DIM, MINT_NET_RATIO

    s = _s()
    s.price_level = 1.0
    s.resources.setdefault(COPPER_RESOURCE_DIM, {"stock": 0})
    s.resources[COPPER_RESOURCE_DIM]["stock"] = 100_000

    def pop_money():
        return sum(int(p.get("wealth", 0) or 0) for p in _money_pools(s))

    before = pop_money()
    log = []
    ok, msg = _settle_mint(s, log, amount=10_000)
    assert ok, msg
    net = int(10_000 * MINT_NET_RATIO)
    assert pop_money() == before + net, f"尾差丢失：Δ={pop_money() - before} 期望 {net}"
    flow = M.take_flow(s)
    assert flow["external_in"] >= net - 1
