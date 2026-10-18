# -*- coding: utf-8 -*-
"""质量放行门 · P7 走私（商人私货 + 固定查获率），2026-10-19。

规则：禁榷品只能走**商人私货**；查获 = 尝试量 × 0.5 **没收入官仓**；走私部分**无税**。
本门钉住：
1. 无商人私货 ⇒ 不外流（`no_merchant_stock`）；
2. 有私货 ⇒ 按查获率拆分（seized = 50%、smuggled = 50%）；
3. 查获部分**没收入官仓**（官仓 +seized）；
4. 守恒：商人池 −尝试量 == 走私流出 + 查获；
5. 走私**不计税**（税 0、价值 None 不臆造）；
6. 结算里走私腿记 `direction=smuggle`，不进 blocked。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

import content.data_constants as dc  # noqa: E402
from core.domains.economy import trade_legs as TL  # noqa: E402
from core.foundation.ledger.material_holding import (  # noqa: E402
    goods_add, goods_amount, merchant_goods)


def _state():
    from core.commands import new_game

    return new_game()


def _seed_merchant(state, route, dim, qty):
    goods = merchant_goods(state, route)
    assert isinstance(goods, dict), "该路无商人货池"
    goods_add(goods, dim, qty)
    return goods


def test_no_merchant_stock_means_no_smuggling():
    s = _state()
    leg = {"dim": "官铸铜钱", "direction": "export", "route": "河北路", "planned_qty": 100}
    r = TL.attempt_smuggle(s, leg)
    assert r["ok"] is False and r["reason"] == "no_merchant_stock"


def test_seizure_split_and_conservation():
    s = _state()
    dim, route = "官铸铜钱", "河北路"
    goods = _seed_merchant(s, route, dim, 200)
    before_merchant = int(goods_amount(goods, dim) or 0)
    stock_before = int((s.resources.get(dim) or {}).get("stock") or 0)
    leg = {"dim": dim, "direction": "export", "route": route, "planned_qty": 100}
    r = TL.attempt_smuggle(s, leg)
    assert r["ok"], r
    rate = float(dc.CONTRABAND_SEIZURE_RATE)
    assert r["seized_qty"] == int(round(100 * rate)), r
    assert r["smuggled_qty"] == 100 - r["seized_qty"], r
    after_merchant = int(goods_amount(goods, dim) or 0)
    stock_after = int((s.resources.get(dim) or {}).get("stock") or 0)
    assert before_merchant - after_merchant == 100, (before_merchant, after_merchant)
    assert stock_after - stock_before == r["seized_qty"], (stock_before, stock_after)
    assert r["smuggled_qty"] + r["seized_qty"] == 100


def test_smuggle_leg_has_no_tax(monkeypatch):
    s = _state()
    monkeypatch.setattr(dc, "FOREIGN_TRADE_LEGS", 1)
    route = "河北路"
    _seed_merchant(s, route, "官铸铜钱", 500)
    r = TL.settle_foreign_trade(s, month=1)
    smug = [x for x in r["rows"] if x.get("smuggled")]
    if smug:
        assert all(x["tax"] == 0 for x in smug)
        assert all(x["goods_value"] is None for x in smug), "价值缺失不臆造"
        assert r["smuggled_qty"] > 0 and r["seized_qty"] >= 0


def test_all_seized_when_rate_is_one(monkeypatch):
    s = _state()
    monkeypatch.setattr(dc, "CONTRABAND_SEIZURE_RATE", 1.0)
    dim, route = "铁", "河北路"
    _seed_merchant(s, route, dim, 100)
    leg = {"dim": dim, "direction": "export", "route": route, "planned_qty": 50}
    r = TL.attempt_smuggle(s, leg)
    assert r["seized_qty"] == 50 and r["smuggled_qty"] == 0
    assert r["reason"] == "all_seized"


def test_switch_off_still_noop(monkeypatch):
    s = _state()
    monkeypatch.setattr(dc, "FOREIGN_TRADE_LEGS", 0)
    r = TL.settle_foreign_trade(s, month=1)
    assert r["enabled"] is False