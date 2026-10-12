# -*- coding: utf-8 -*-
"""M39a 航道治所级表 —— 定向回归。

口径（Jev 2026-10-13 choose A 0.690）：真账＝治所级表 `SEAT_WATERWAY`（首府承载）；
路级 `waterway_tier_route` = 该路已登记治所中的**最高档** ⇒ 与原史料表**逐路相等**（零行为变化）。

锁定边界：
  1. 首府承载：21 路各自首府登记，档位与源表一致；
  2. **零行为变化**：`waterway_tier(route)` 对全部 21 路与源表相等（含影子模块改走派生后）；
  3. 缺失≠0：非首府治所、未知道路、未知治所 ⇒ `None`（不回落"有"/"弱"）；
  4. 不臆造：无治所实体的路**不登记**；
  5. 对账：`survey_waterway()` 失配为 0。
"""

import pytest

from core.domains.economy import trade_shadow, waterway_seats as ws


def test_first_21_routes_capital_registered():
    """每路首府都登记，且档位 == 源表档位。"""
    n = 0
    for tier, routes in trade_shadow.ROUTE_WATERWAY.items():
        for route in routes:
            sid = ws.capital_seat_id(route)
            assert sid, f"{route} 首府判不出（治所实体缺失？）"
            assert ws.waterway_tier_seat(sid) == tier, f"{route} 首府档位不符"
            n += 1
    assert n == 21


def test_route_derived_equals_source_for_all_routes():
    """**零行为变化**：路级派生值 == 史料源表值（逐路）。"""
    for tier, routes in trade_shadow.ROUTE_WATERWAY.items():
        for route in routes:
            assert ws.waterway_tier_route(route) == tier


def test_trade_shadow_waterway_tier_unchanged():
    """影子模块的公开函数改走派生后，结果必须与源表逐路一致。"""
    for tier, routes in trade_shadow.ROUTE_WATERWAY.items():
        for route in routes:
            assert trade_shadow.waterway_tier(route) == tier
    assert trade_shadow.waterway_tier("不存在路") is None


def test_non_capital_seat_is_none():
    """非首府治所**未登记** ⇒ None（缺失≠0；不把路级档位复制给所有治所）。"""
    from core.foundation.ledger.prefecture_entity import seats_of
    checked = 0
    for route in ("京畿路", "两浙路"):
        cap = ws.capital_seat_id(route)
        for ent in seats_of(route, include_merged=False):
            sid = ent.get("seat_id")
            if sid != cap:
                assert ws.waterway_tier_seat(sid) is None
                checked += 1
    assert checked > 0, "应至少有一个非首府治所可检"


def test_unknown_entries_are_none():
    assert ws.waterway_tier_seat("不存在|治所") is None
    assert ws.waterway_tier_route("不存在路") is None


def test_survey_has_no_mismatch():
    rep = ws.survey_waterway()
    assert rep["路由数"] == 21
    assert rep["失配"] == []


def test_no_fabrication_when_seat_entities_missing(monkeypatch):
    """无治所实体的路 ⇒ **不登记**（不臆造地点）。"""
    monkeypatch.setattr(ws, "capital_seat_id", lambda route: None)
    assert ws.rebuild_seat_table() == {}


def test_fallback_when_seat_module_unavailable(monkeypatch):
    """治所级模块不可用 ⇒ `waterway_tier` 回落源表（可选层不得卡流程）。"""
    import builtins
    real_import = builtins.__import__

    def _boom(name, *a, **kw):
        if "waterway_seats" in name:
            raise ImportError("simulated")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", _boom)
    assert trade_shadow.waterway_tier("京畿路") == "强"      # 回落源表仍然正确
