# -*- coding: utf-8 -*-
"""审查修复回归：钱守恒 / 家产来源 / 一条鞭 / AI 待批队列 / 异步无嵌套。"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "game"))


def _state():
    from core.game_state import GameState
    return GameState("史实")


def test_transfer_money_pair():
    s = _state()
    road = next(iter(s.prefectures))
    t0 = s.treasury
    w0 = s.prefectures[road]["pops"]["官僚"]["wealth"]
    moved = s.transfer_money("treasury", f"pop:{road}:官僚", 10_000)
    assert moved == 10_000
    assert s.treasury == t0 - 10_000
    assert s.prefectures[road]["pops"]["官僚"]["wealth"] == w0 + 10_000


def test_change_treasury_no_underflow():
    s = _state()
    s.treasury = 100
    s.change_treasury(-500)
    assert s.treasury == 0


def test_estate_growth_drains_bureaucrat():
    from core.estate_mechanic import settle_minister_estate
    s = _state()
    s._economy_ai = {"景气": "中"}
    pool0 = sum(p["pops"]["官僚"]["wealth"] for p in s.prefectures.values())
    e0 = sum(e["wealth"] for e in s.minister_estate.values())
    settle_minister_estate(s, [])
    pool1 = sum(p["pops"]["官僚"]["wealth"] for p in s.prefectures.values())
    e1 = sum(e["wealth"] for e in s.minister_estate.values())
    # 官僚池减少 ≈ 家产净增（奢侈/窖藏另计，池必不增）
    assert pool1 <= pool0
    assert e1 != e0 or pool1 == pool0  # 有变化时必有来源


def test_single_whip_no_mint():
    from core.settlement_steps import _settle_land_local
    s = _state()
    s.single_whip = True
    money0 = s.treasury + sum(
        p["pops"][k]["wealth"] for p in s.prefectures.values()
        for k in ("农", "士绅"))
    _settle_land_local(s, [])
    money1 = s.treasury + sum(
        p["pops"][k]["wealth"] for p in s.prefectures.values()
        for k in ("农", "士绅"))
    # 折银只做民间→国库划转，钱组合计不增（允许欠税科目记账造成的微小差）
    assert money1 <= money0 + 1


def test_ai_pending_queue_strict():
    from ai.client_utils import _tool_dispatch
    s = _state()
    calls = [{
        "id": "c1",
        "function": {
            "name": "secret_order",
            "arguments": '{"title":"试密","summary":"测","longterm":false}',
        },
    }]
    _tool_dispatch(s, calls, minister_name="测试臣")
    assert s.get_ai_pending("pending"), "密令应入待批队列"
    assert not s.pending_secret_decrees, "批红前不得写入密令队列"
    from core.commands import approve_ai_action, reject_ai_action
    aid = s.get_ai_pending("pending")[0]["id"]
    msg = approve_ai_action(s, aid)
    assert "批红" in msg
    assert s.pending_secret_decrees
    assert not s.get_ai_pending("pending")


def test_military_increase_rejected_without_money():
    from core.commands import approve_ai_action
    s = _state()
    s.treasury = 0
    aid = s.enqueue_ai_action(
        "military_dispatch", "禁军·增募", "测",
        {"army": "禁军", "action": "增募", "scale": 3}, proposer="x")
    msg = approve_ai_action(s, aid)
    assert "驳回" in msg
    assert s.pop_ai_pending(aid)["status"] == "rejected"


def test_async_settlement_no_nested_submit():
    """run_settlement_ai 的 worker 不得再 submit 到同一 _EXECUTOR（防死锁）。"""
    import inspect
    import core.async_ai as m
    src = inspect.getsource(m.run_settlement_ai)
    assert "_EXECUTOR.submit(_call_guarded" not in src
    assert "as_completed" not in src


def test_paper_pay_no_copper_mint():
    """一体发钞：俸禄以交子支付时兵 POP 铜钱不得增加。

    回归：原实现同月既发行等额交子、又无条件给兵/官僚 POP 记铜钱，
    且国库不支出（effective_cash_out=0）→ 一笔俸禄记两次且凭空造币。
    """
    from core.settlement_steps import _settle_finance
    s = _state()
    s.pay_system["mode"] = "一体发钞"
    soldier0 = sum(p["pops"]["兵"]["wealth"] for p in s.prefectures.values())
    jz0 = s.jiaozi["issued"]
    _settle_finance(s, [])
    soldier1 = sum(p["pops"]["兵"]["wealth"] for p in s.prefectures.values())
    assert s.jiaozi["issued"] > jz0, "一体发钞应发行交子"
    assert soldier1 == soldier0, "俸禄已付交子，兵 POP 铜钱不得再增（否则双发造币）"


def test_cash_pay_credits_soldiers():
    """对照：非一体发钞时兵 POP 铜钱应随俸禄增加（门控未误伤正常路径）。"""
    from core.settlement_steps import _settle_finance
    s = _state()
    s.pay_system["mode"] = "钱粮并给"
    soldier0 = sum(p["pops"]["兵"]["wealth"] for p in s.prefectures.values())
    _settle_finance(s, [])
    soldier1 = sum(p["pops"]["兵"]["wealth"] for p in s.prefectures.values())
    assert soldier1 > soldier0


def test_fixed_finance_transfer_no_mint():
    """御笔直发「移库」：来源不足时按可付额截断，钱总量不得增加。

    回归：原实现先给目标全额入账、再扣来源，而 change_* 内部 max(0, …)
    会截断来源 → 差额凭空产生。
    """
    from core.commands_decree import _run_fixed
    s = _state()
    s.treasury = 1_000
    s.imperial_treasury = 0
    _run_fixed(s, "fixed_finance",
               {"amount": 5_000, "target": "内藏", "source": "国库"})
    assert s.treasury + s.imperial_treasury == 1_000, "移库总额须守恒"
    assert s.imperial_treasury == 1_000, "内帑应按国库可付额入账"


def test_fixed_finance_relief_debits_treasury():
    """州郡赈济为「国库列支」：国库应减少，州郡府库等额增加（成对划转）。

    回归：原实现写作 change_treasury(+amt)，赈济反给国库加钱（符号反）。
    """
    from core.commands_decree import _run_fixed
    s = _state()
    s.treasury = 100_000
    local0 = sum(int(p.get("local_treasury", 0) or 0)
                 for p in s.prefectures.values())
    _run_fixed(s, "fixed_finance", {"amount": 30_000, "target": "州郡"})
    local1 = sum(int(p.get("local_treasury", 0) or 0)
                 for p in s.prefectures.values())
    assert s.treasury == 70_000
    assert local1 - local0 == 30_000, "州郡府库应等额增收（守恒）"


def test_changping_trade_conserves_grain_and_money():
    """常平仓粜籴守恒：政府仓 ↔ 本路民间 POP 成对划转，粮/钱两账 ΣΔ==0。

    回归：原实现只动 changping_stock / local_treasury（对手方未建模）→
    平粜放出的粮凭空消失、回收的钱凭空产生；平籴反之（粮凭空产生、付钱灭失）。
    """
    from core.settlement_steps import _changping_trade
    s = _state()
    road = next(iter(s.prefectures))
    p = s.prefectures[road]
    p["changping_stock"] = 100_000
    p["local_treasury"] = 100_000
    _price = 2.0

    def _books():
        g = sum(int(pp.get("grain", 0) or 0) for pp in p["pops"].values())
        m = sum(int(pp.get("wealth", 0) or 0) for pp in p["pops"].values())
        return g + int(p["changping_stock"]), m + int(p["local_treasury"])

    g0, m0 = _books()

    _g, _m = _changping_trade(p, road, 30_000, "sell", _price, [], "t")
    assert _g > 0 and _m > 0, "平粜应成交易"
    g1, m1 = _books()
    assert g1 == g0, "平粜：粮总量须守恒（原实现凭空消失）"
    assert m1 == m0, "平粜：钱总量须守恒（原实现凭空产生）"

    _g2, _m2 = _changping_trade(p, road, 20_000, "buy", _price, [], "t")
    assert _g2 > 0 and _m2 > 0, "平籴应成交易"
    g2, m2 = _books()
    assert g2 == g1, "平籴：粮总量须守恒（原实现凭空产生）"
    assert m2 == m1, "平籴：钱总量须守恒（原实现灭失）"


def test_levy_and_return_men_conserves_population():
    """整军征补/裁汰的人丁守恒：兵额增减必与民户（农/流民）成对划转。

    回归：原诏令整军只 add_troops（增兵无人口来源），而 _settle_finance 随后
    以 Σbranches 重聚合兵 POP、并把 ΣPOP 写回 population → 一句诏令凭空
    产生数万「人」（每军最多 +50% 员额）。
    """
    from core.settlement_steps import _levy_men, _return_men
    s = _state()
    road = next(iter(s.prefectures))
    p = s.prefectures[road]

    def _total():
        return (sum(int(pp.get("size", 0) or 0) for pp in p["pops"].values())
                + int(p.get("refugees", 0) or 0))

    t0 = _total()
    got = _levy_men(s, road, 5_000)
    assert got > 0, "农户/流民充足时应能征补"
    # 民户（农户 + 流民）减少恰为征得人数；这 got 人转入兵额（真账由 Σbranches 承载）
    assert _total() == t0 - got, "征补：民户应等量减少（人守恒）"

    _return_men(s, road, got)
    assert _total() == t0, "裁汰：人丁还民后民户总数应复原"
