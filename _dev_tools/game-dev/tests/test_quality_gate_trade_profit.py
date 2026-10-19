# -*- coding: utf-8 -*-
"""质量放行门 · V3 风格利润驱动贸易路线量（2026-10-19）。

V3 口径：路线量按**利润空间**增缩（逐步、不瞬变）；亏损路线**关停**。
本门钉住：
1. 报价含买价/卖价/关税/运费，毛利 = 卖 − 买 − 税 − 运；
2. 出口看外邦付费倍率、进口看到岸倍率，方向不能弄反；
3. 目标量 = 基准量 × clamp(毛利比 / 目标毛利, 0, 上限)；亏损 ⇒ 0；
4. `step_volume` **渐变**：单月增幅 ≤ 25%、降幅 ≤ 30%；
5. 亏损路线多步后归零；
6. `plan_legs(advance=False)` 不写 state（可复现）；
7. 开关关闭 ⇒ 零行为变更。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

import content.data_constants as dc  # noqa: E402
from core.domains.economy import trade_legs as TL  # noqa: E402


def _state():
    from core.commands import new_game

    return new_game()


def _leg(partner="三佛齐", dim="香药", direction="import", channel="sea", price=800):
    return {"partner": partner, "dim": dim, "direction": direction,
            "channel": channel, "unit_price": price, "route": "广南东路"}


def test_quote_arithmetic():
    s = _state()
    q = TL.quote_route(s, _leg())
    assert q["ok"], q
    assert abs(q["margin"] - (q["sell_price"] - q["buy_price"] - q["tariff"] - q["freight"])) < 0.02
    assert q["tariff"] > 0 and q["freight"] > 0


def test_direction_uses_right_price_side():
    s = _state()
    imp = TL.quote_route(s, _leg(direction="import"))
    exp = TL.quote_route(s, _leg(direction="export", dim="精品瓷器", price=450))
    # 进口买价 = 基准 × 进口倍率（<1）；卖价 = 本路价
    assert abs(imp["buy_price"] - 800 * dc.PARTNER_IMPORT_FACTORS["三佛齐"]) < 0.02, imp
    # 出口卖价 = 基准 × 出口倍率（>1）
    assert abs(exp["sell_price"] - 450 * dc.PARTNER_PRICE_FACTORS["三佛齐"]) < 0.02, exp


def test_unprofitable_route_targets_zero():
    s = _state()
    # 构造亏损：把进口倍率抬到 1.6（买贵）
    leg = _leg(partner="日本", dim="香药", direction="import")
    old = dict(dc.PARTNER_IMPORT_FACTORS)
    try:
        dc.PARTNER_IMPORT_FACTORS["日本"] = 1.6
        q = TL.quote_route(s, leg)
        assert q["margin"] < 0, q
        assert TL.target_volume(q, 20) == 0
    finally:
        dc.PARTNER_IMPORT_FACTORS.clear()
        dc.PARTNER_IMPORT_FACTORS.update(old)


def test_profitable_route_target_scales_with_margin():
    s = _state()
    q = TL.quote_route(s, _leg())
    t = TL.target_volume(q, 20)
    assert t > 0
    assert t <= 20 * dc.TRADE_MAX_MULT + 1e-9


def test_step_volume_is_gradual():
    s = _state()
    leg = _leg()
    q = TL.quote_route(s, leg)
    v1 = TL.step_volume(s, leg, q, 20)["volume"]
    v2 = TL.step_volume(s, leg, q, 20)["volume"]
    assert v2 >= v1
    assert v2 <= v1 * (1 + dc.TRADE_VOLUME_GROWTH) + max(dc.TRADE_VOLUME_FLOOR, 1) + 1e-9


def test_loss_shrinks_to_zero_over_steps():
    s = _state()
    leg = _leg(partner="日本", dim="香药", direction="import")
    old = dict(dc.PARTNER_IMPORT_FACTORS)
    try:
        dc.PARTNER_IMPORT_FACTORS["日本"] = 1.6
        q = TL.quote_route(s, leg)
        s.trade_routes = {TL.route_key(leg): {"volume": 100.0}}
        vols = []
        for _ in range(20):
            vols.append(TL.step_volume(s, leg, q, 20)["volume"])
        assert vols[-1] == 0.0, vols[-5:]
        assert all(vols[i] >= vols[i + 1] for i in range(len(vols) - 1)), vols[:6]
    finally:
        dc.PARTNER_IMPORT_FACTORS.clear()
        dc.PARTNER_IMPORT_FACTORS.update(old)


def test_plan_without_advance_does_not_mutate():
    s = _state()
    before = copy.deepcopy(getattr(s, "trade_routes", None))
    legs = TL.plan_legs(s, 1, advance=False)
    assert legs, "应有可走路线（有利润）"
    assert getattr(s, "trade_routes", None) == before, "advance=False 不得写路线账"


def test_switch_off_is_noop(monkeypatch):
    s = _state()
    monkeypatch.setattr(dc, "FOREIGN_TRADE_LEGS", 0)
    r = TL.settle_foreign_trade(s, 1)
    assert r["enabled"] is False