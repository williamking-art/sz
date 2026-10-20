# -*- coding: utf-8 -*-
"""2026-10-20 全审必修/应修回归（P0-1 / P0-2 / P0-3 / P1-20 / P1-21 / R-N-3）。

口径（报告 `_dev_tools/game-docs/reviews/宋祚全审报告_2026-10-20.md`）：
- P0-1：外贸进口付款必须走治所级桥（写单治所+刷镜像），熔铜必须逐治所真账扣减；
  `new_game` + 12 月**月际对账残差**必须≈0（修前 +13,470,432/12 月）。
- P0-2：陆路榷税必须由该路商人 POP 付款，不得只入府库。
- P0-3：长期案卷授权只登额度、月结才实扣（不得双扣/账外余额）。
- P1-20/21：`change_treasury/granary` 返回实际生效 Δ；太仓恒等式不得用 assert。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core import money as M  # noqa: E402
from core.commands import new_game  # noqa: E402
from core.domains.economy.trade_legs import (  # noqa: E402
    _pay_import, _seat_merchant_pops, settle_land_tariff)
from core.domains.politics.longterm_case import (  # noqa: E402
    authorize_case, case_readout, monthly_case_settle)
from core.pop_bridge import survey_pops  # noqa: E402
from core.settlement import run_monthly_settlement  # noqa: E402


def _seat_wealth(s, route: str) -> float:
    return sum(float(p.get("wealth") or 0) for p in _seat_merchant_pops(s, route))


# ---------------------------------------------------------------- P0-1
def test_new_game_12m_cum_residual_is_zero():
    """P0-1 主验收：修前 12 月 cum_residual=+13,470,432（外贸进口货款被熔铜「复活」）。"""
    s = new_game("史实")
    for _ in range(12):
        run_monthly_settlement(s)
    cum = float((s.money_audit or {}).get("cum_residual") or 0.0)
    assert abs(cum) < 1.0, f"12 月累计对账残差 {cum:+,.0f} 贯（存在无对手方的造币/销毁）"
    sv = survey_pops(s)
    assert sv["字段失配"] == [], sv["字段失配"][:5]


def test_pay_import_deducts_real_money_and_keeps_mirror():
    s = new_game("史实")
    route = "京畿路"
    money0 = M.pop_money(s)
    seat0 = _seat_wealth(s, route)
    paid = _pay_import(s, route, "米", 1000.0, 10.0)
    assert paid > 0
    cost = int(round(paid * 10.0))
    assert abs((M.pop_money(s) - money0) + cost) < 1.0, "治所在途：M_ALL 应立减货款"
    assert abs((_seat_wealth(s, route) - seat0) + cost) < 1.0
    assert survey_pops(s)["字段失配"] == [], "桥接写后镜像必须即时一致"


def test_melt_does_not_resurrect_seat_deductions():
    """治所级直写（旧写法）留下的镜像滞后，不得被熔铜步按镜像重铺「复活」。"""
    from core.settlement_finance import _settle_coin_melt

    s = new_game("史实")
    route = "京畿路"
    pops = _seat_merchant_pops(s, route)
    assert pops
    seat = pops[0]
    w0 = float(seat.get("wealth") or 0)
    seat["wealth"] = w0 - 5000          # 只改真账、故意不刷镜像
    route_before = _seat_wealth(s, route)
    _settle_coin_melt(s, [])
    route_after = _seat_wealth(s, route)
    assert route_after < route_before, "熔铜只能减、不得把已扣的钱抹回"
    assert route_before - route_after >= 0
    assert survey_pops(s)["字段失配"] == [], "熔铜后必须刷镜像"


# ---------------------------------------------------------------- P0-2
def test_land_tariff_has_payer():
    s = new_game("史实")
    route = "京畿路"
    pdata = s.prefectures[route]
    local0 = float(pdata.get("local_treasury") or 0)
    wealth0 = _seat_wealth(s, route)
    out = settle_land_tariff(s, {"route": route, "channel": "land"}, 10000)
    assert out["ok"] and out["credited"] > 0
    credited = int(out["credited"])
    assert abs((float(pdata["local_treasury"]) - local0) - credited) < 1
    assert abs((_seat_wealth(s, route) - wealth0) + credited) < 1, "必须有付款方（商人 POP）"
    assert survey_pops(s)["字段失配"] == []


def test_land_tariff_short_payer_does_not_mint():
    s = new_game("史实")
    route = "京畿路"
    pdata = s.prefectures[route]
    for p in _seat_merchant_pops(s, route):
        p["wealth"] = 100              # 故意只剩 100 贯/治所（合计 400）
    from core.foundation.ledger.pop_bridge import refresh_route_class
    refresh_route_class(pdata, "商人")
    total_payer = sum(int(p.get("wealth") or 0) for p in _seat_merchant_pops(s, route))
    local0 = float(pdata.get("local_treasury") or 0)
    out = settle_land_tariff(s, {"route": route, "channel": "land"}, 10000)
    credited = int(out.get("credited") or 0)
    assert credited == min(10000, total_payer) and out.get("short", 0) > 0
    assert abs((float(pdata["local_treasury"]) - local0) - credited) < 1


# ---------------------------------------------------------------- P0-3
def test_longterm_authorize_no_double_charge():
    s = new_game("史实")
    task = {"id": "ltp-probe", "task_name": "整饬海防", "progress": 0}
    treasury0 = int(s.treasury)
    out = authorize_case(s, task, budget=300000, monthly_cost=20000)
    assert out["ok"] and int(s.treasury) == treasury0, "授权只登额度，不即时扣库"
    assert task["case_no"] and task["opened_turn"] == int(s.turn)
    for _ in range(3):
        monthly_case_settle(s, task, [])
    assert int(s.treasury) == treasury0 - 3 * 20000, "月结是唯一真实扣款点"
    assert task["budget"]["remaining"] == 300000 - 3 * 20000
    auth = case_readout(s, task)["authorization"]
    assert auth["budget_total"] == 300000 and auth["monthly_cost"] == 20000


def test_longterm_unauthorized_readout_is_none():
    task = {"id": "ltp-x", "task_name": "未授权案卷", "progress": 0}
    s = new_game("史实")
    assert case_readout(s, task)["authorization"] is None


# ---------------------------------------------------------------- P1-20/21
def test_change_treasury_returns_actual_delta():
    s = new_game("史实")
    s.treasury = 100
    got = s.change_treasury(-100000)
    assert got == -100, "穿底时返回实际生效 Δ（旧实现返回 None，调用方会按请求额记账）"
    assert s.treasury == 0
    s.treasury = 500
    assert s.change_treasury(200) == 200 and s.treasury == 700


def test_change_granary_returns_actual_delta():
    s = new_game("史实")
    s.granary = 50
    s.granary_cap = 100
    assert s.change_granary(100000) == 50 and s.granary == 100
    assert s.change_granary(-30) == -30 and s.granary == 70


# ---------------------------------------------------------------- R-N-3
def test_transport_dropped_is_recorded_in_statistics(monkeypatch):
    import core.transport as T
    import content.data_constants as DC

    s = new_game("史实")
    T.transport_queue(s).clear()
    monkeypatch.setattr(DC, "TRANSPORT_QUEUE_MAX_STONE", 10)
    monkeypatch.setattr(T, "transport_consume", lambda *a, **k: {
        "ok": False, "taken": 0.0, "short": 25.0, "remaining": 0.0, "kind": "goods"})
    out = T.transport_ship_or_queue(s, "overland", 25.0)
    assert out["dropped"] == 15.0 and out["queued"] == 10.0
    assert out["status"] == "dropped"
    assert float(s.statistics.get("transport_queue_dropped") or 0) == 15.0


def test_transport_missing_cap_does_not_drop(monkeypatch):
    import core.transport as T
    import content.data_constants as DC

    s = new_game("史实")
    T.transport_queue(s).clear()
    monkeypatch.setattr(DC, "TRANSPORT_QUEUE_MAX_STONE", 0)
    monkeypatch.setattr(T, "transport_consume", lambda *a, **k: {
        "ok": False, "taken": 0.0, "short": 77.0, "remaining": 0.0, "kind": "goods"})
    out = T.transport_ship_or_queue(s, "overland", 77.0)
    assert out["dropped"] == 0.0 and out["queued"] == 77.0, "上限缺失不得静默全丢"
    assert out["status"] == "queued"
