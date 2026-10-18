# -*- coding: utf-8 -*-
"""质量放行门 · P6 榷场（陆路互市开关 + 榷税拆分），2026-10-18。

规则：战时闭场、态度过低闭场；榷税 **过税 40% → 沿途路府库、住税 60% → 交易地府库**。
本门钉住：
1. 战和/态度决定陆路开闭，且**海路不受影响**；
2. 闭场时陆路腿被 blocked（reason 明确）且**不动库存**；
3. 榷税 40:60 拆分并合计等于税额（守恒）；
4. 缺 `local_treasury` ⇒ 不入账且给 reason（不臆造通道）；
5. 总开关关闭时一切不变（P5 回归保护）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

import content.data_constants as dc  # noqa: E402
from core.domains.economy import trade_legs as TL  # noqa: E402


def _state():
    from core.commands import new_game

    return new_game()


def test_war_closes_land_market():
    s = _state()
    assert TL.land_market_open(s, "辽")["open"] is True
    s._at_war = {"辽": True}
    r = TL.land_market_open(s, "辽")
    assert r["open"] is False and r["reason"] == "at_war"


def test_low_attitude_closes_market():
    s = _state()
    s.external_regimes["辽"]["attitude"] = dc.LAND_MARKET_MIN_ATTITUDE - 1
    r = TL.land_market_open(s, "辽")
    assert r["open"] is False and "low_attitude" in r["reason"]
    s.external_regimes["辽"]["attitude"] = dc.LAND_MARKET_MIN_ATTITUDE + 10
    assert TL.land_market_open(s, "辽")["open"] is True


def test_unmodeled_partner_defaults_open_with_reason():
    s = _state()
    r = TL.land_market_open(s, "假想国")
    assert r["open"] is True and r["reason"] == "partner_unmodeled"


def test_closed_land_leg_is_blocked_and_stock_untouched(monkeypatch):
    s = _state()
    monkeypatch.setattr(dc, "FOREIGN_TRADE_LEGS", 1)
    # 全部陆路对家均闭场，才能断言「陆路不动库存」
    s._at_war = {"辽": True, "西夏": True, "吐蕃": True, "大理": True, "交趾": True}
    s.resources["茶"] = {"stock": 1000, "cap": 10 ** 9}
    r = TL.settle_foreign_trade(s, month=1, dry_run=False)
    assert r["blocked"] > 0
    closed = [x for x in r["rows"] if str(x.get("j", {}).get("reason", "")).startswith("market_closed")]
    assert closed, "闭场的陆路腿必须带 market_closed 归因"
    assert all(x["channel"] == "land" for x in closed)
    assert float(s.resources["茶"]["stock"]) == 1000, "陆路全闭场时不得动库存"


def test_sea_legs_unaffected_by_war(monkeypatch):
    s = _state()
    monkeypatch.setattr(dc, "FOREIGN_TRADE_LEGS", 1)
    s._at_war = {"辽": True}
    r = TL.settle_foreign_trade(s, month=1, dry_run=False)
    assert r["blocked"] > 0
    sea_rows = [x for x in r["rows"] if x.get("channel") == "sea"]
    assert sea_rows, "海路腿必须仍存在"
    assert not any(str(x.get("j", {}).get("reason", "")).startswith("market_closed")
                   for x in sea_rows), "海路不应受陆路榷场战和影响"


def test_land_tariff_splits_40_60_conserved():
    s = _state()
    before = int(s.prefectures["河北路"]["local_treasury"])
    out = TL.settle_land_tariff(s, {"route": "河北路"}, 1000)
    assert out["ok"]
    assert out["over_tax"] == 400 and out["stay_tax"] == 600
    assert out["over_tax"] + out["stay_tax"] == 1000
    assert int(s.prefectures["河北路"]["local_treasury"]) == before + 1000


def test_land_tariff_refuses_when_no_treasury_field():
    s = _state()
    s.prefectures["河北路"].pop("local_treasury", None)
    out = TL.settle_land_tariff(s, {"route": "河北路"}, 500)
    assert out["ok"] is False and out["reason"] == "no_local_treasury"


def test_switch_off_keeps_p5_behavior():
    s = _state()
    assert dc.FOREIGN_TRADE_LEGS == 0
    s._at_war = {"辽": True}
    r = TL.settle_foreign_trade(s, month=1)
    assert r["enabled"] is False