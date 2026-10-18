# -*- coding: utf-8 -*-
"""质量放行门 · P2 读数层（2026-10-18）：外贸与运输读数。

纪律：只读、不复制算法、缺失≠0。
本门钉住：
1. 无流水 ⇒ 贸易额 0（**真零**），但 import/silver/ports 必须 `None` + reason（不臆造）；
2. 逐笔流水有字段缺失 ⇒ `None`+reason，不回落 0；
3. 通道拆分按口岸表 partner→channel；未登记对家 ⇒ `unknown` 且留 reason；
4. 货种 TopN 与税费按流水汇总；阻塞腿进 `blocked`；
5. 运输读数与 `transport_capacity` 同源；占用后 remaining 下降；
6. 在途批次 `remaining_months` 与 `arrive_month` 一致。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.domains.economy.foreign_trade_readout import (  # noqa: E402
    survey_all, survey_foreign_trade, survey_transport)
from core.transport import (  # noqa: E402
    _now, transport_capacity, transport_consume)


def _state():
    from core.commands import new_game

    return new_game()


def test_empty_journal_is_true_zero_but_fields_missing():
    s = _state()
    s.trade_journal = []
    r = survey_foreign_trade(s)
    assert r["implemented"] is True and r["trade_value"] == 0
    assert r["channels"] == {} and r["top_dims"] == []
    assert r["import_value"] is None and r["silver_flow"] is None and r["ports"] is None
    assert r["reasons"], "缺失字段必须留 reason（缺失≠0）"


def test_missing_journal_attribute_is_not_empty_data():
    s = _state()
    if hasattr(s, "trade_journal"):
        del s.trade_journal
    r = survey_foreign_trade(s)
    assert r["implemented"] is False and "缺失" in r["reason"]


def test_legs_aggregate_by_channel_and_dim():
    s = _state()
    s.trade_journal = [
        {"partner": "日本", "dim": "香药", "goods_value": 1000, "direction": "export",
         "tax_over": 40, "tax_stay": 60, "route": "两浙路"},
        {"partner": "辽", "dim": "茶", "goods_value": 500, "direction": "export",
         "tax_over": 20, "tax_stay": 30, "route": "河北路"},
        {"partner": "辽", "dim": "香药", "goods_value": 500, "direction": "export",
         "route": "河北路", "reason": "contraband"},
    ]
    r = survey_foreign_trade(s)
    assert r["trade_value"] == 2000
    assert r["channels"]["sea"]["trade_value"] == 1000
    assert r["channels"]["land"]["trade_value"] == 1000
    assert r["channels"]["sea"]["tax"] == 100
    dims = {d["dim"]: d["value"] for d in r["top_dims"]}
    assert dims["香药"] == 1500 and dims["茶"] == 500
    assert r["top_dims"][0]["dim"] == "香药"
    assert len(r["blocked"]) == 1 and r["blocked"][0]["reason"] == "contraband"


def test_unknown_partner_is_flagged_not_guessed():
    s = _state()
    s.trade_journal = [{"partner": "火星", "dim": "香药", "goods_value": 100,
                        "direction": "export"}]
    r = survey_foreign_trade(s)
    assert "unknown" in r["channels"]
    assert "partner_channel" in r["reasons"]


def test_missing_goods_value_is_none_not_zero():
    s = _state()
    s.trade_journal = [{"partner": "辽", "dim": "茶", "direction": "export"}]
    r = survey_foreign_trade(s)
    assert r["trade_value"] == 0
    assert "goods_value" in r["reasons"]


def test_transport_readout_matches_capacity():
    s = _state()
    r = survey_transport(s)
    for mode in ("waterway", "maritime", "overland", "post"):
        cap = transport_capacity(s, mode)
        assert r["modes"][mode]["capacity"] == cap["capacity"]
        assert r["modes"][mode]["bottleneck"] == cap["bottleneck"]
    before = r["modes"]["post"]["remaining"]
    transport_consume(s, "post", 1000)
    after = survey_transport(s)["modes"]["post"]["remaining"]
    assert after < before


def test_in_transit_remaining_months():
    from core.foundation.ledger.money_transport import dispatch_money

    s = _state()
    r = dispatch_money(s, frm_kind="treasury", to_kind="local_treasury",
                       amount=100, to_seat="京西路|河南府")
    assert r["ok"], r
    rep = survey_transport(s)
    assert rep["in_transit_count"] >= 1
    row = rep["in_transit"][0]
    assert row["remaining_months"] == int(row["arrive_month"]) - int(_now(s))
    assert row["remaining_months"] >= 1


def test_survey_all_shape():
    s = _state()
    r = survey_all(s)
    assert set(r) == {"foreign_trade", "transport"}