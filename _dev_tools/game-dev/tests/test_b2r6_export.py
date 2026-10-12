# -*- coding: utf-8 -*-
"""B2-R6 · 外销与国内供给优先序的定向回归（规格 `market-civilian-economy` B2-R6）

锁定的口径（放行证据对应项）：
- **同一商品实物不能既内销又外销**：内销真成交扣过的货不在外销量里；
- **有真实剩余时**：钱货双向守恒（`goods −qty` / `wealth +income`）且来源登记为体外注入；
- **无剩余时**：明确报告"无可出口余货"，且语义是 **`0`（有记录）而非 `None`**；
- **缺失 ≠ 0 ≠ 1.0**：关键输入未记录 → `income is None`、`defined=False`；
- **非法输入拒绝**：负数/NaN/Inf/bool/空维度/非正单价/双卖不可能 ⇒ `ok=False` 且不改账；
- **与既有 §3.5 公式逐项等价**（接线是"换单点"不是调参）；
- POP 挂载律：钱货只落 POP `wealth`/`goods`，**不新建平行账本**。
"""
import math
import os
import sys
from types import SimpleNamespace

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.export_policy import (  # noqa: E402
    STAT_CUMULATIVE_KEY, STAT_MONTH_KEY, ExportReason, apply_export_decision,
    export_cumulative_readout, export_decision, export_month_readout,
    export_policy_params, export_unit_price, read_artisan_stock, summarize_export,
)
from core.market import trade_goods  # noqa: E402


def _state(turn=1):
    """最小 state：只需 statistics / turn（不建整局，避免测试与人口无关地耦合）。"""
    return SimpleNamespace(turn=turn, statistics={}, prefectures={})


def _artisan(stock=None, wealth=0):
    g = {} if stock is None else {"布": stock, "绸": stock}
    return {"size": 1000, "wealth": wealth, "goods": g}


# ============================================================ 与既有 §3.5 等价
def _legacy_qty_income(stock, month_prod, price, months=12, rate=0.3):
    """`settlement_granary.py:380-390` 现实现的逐字复刻（用于等价性对照）。"""
    cap = int(month_prod) * months
    if stock > cap and month_prod > 0:
        export = min(stock - cap, int(month_prod * rate))
        return export, int(export * price)
    return 0, 0


def test_equivalent_to_legacy_section_35_formula():
    """接线是"同一口径换单点"：与现实现逐项等价（不引入新的调参自由度）。"""
    grid = [(0, 100), (5, 100), (1200, 100), (1201, 100), (5000, 100),
            (0, 0), (999, 0), (1300, 1300), (20000, 1300)]
    for price in (1, 3):
        for stock, mp in grid:
            want_qty, want_income = _legacy_qty_income(stock, mp, price)
            d = export_decision(dim="布", stock=stock, month_prod=mp, price=price)
            assert d["ok"] and d["defined"], (stock, mp, price, d.get("detail"))
            assert d["qty"] == want_qty, (stock, mp, price, d["qty"], want_qty)
            assert d["income"] == want_income, (stock, mp, price, d["income"], want_income)


def test_policy_params_and_price_come_from_single_source():
    """策略参数与外销单价的**唯一口径源**是 content/data（参数不在本模块复制）。"""
    import content.data as cd
    p = export_policy_params()
    assert p["stock_months"] == float(cd.EXPORT_STOCK_MONTHS)
    assert p["export_rate"] == float(cd.EXPORT_RATE)
    assert export_unit_price("布") == float(cd.GOODS_PRICE["布"])
    assert export_unit_price("不存在的商品") is None      # 缺失 → None，不回落 0


# ============================================================ 同一批货不重复出售
def test_same_units_never_sold_domestically_and_exported():
    """**同一商品实物不能既内销又外销**（B2-R6 核心放行证据）。

    夹具：工匠池 1000 单位；内销经 `trade_goods` 真成交扣掉 600；
    随后外销判定只能在这**剩下的 400** 上做，且外销量不得超过它。
    """
    st = _state()
    artisan = _artisan(stock=1000)
    buyer = {"size": 10, "wealth": 10_000, "goods": {}}

    before = int(artisan["goods"]["布"])
    r = trade_goods(st, dim="布", qty=600, price=1, buyer=buyer, seller=artisan,
                    purpose="resale", trade_id=None)
    assert r["traded"] == 600, "夹具前提：内销应真成交 600"
    after_domestic = int(artisan["goods"]["布"])
    assert after_domestic == before - 600, "内销必须扣卖方（B1 真成交）"

    d = export_decision(dim="布", stock=after_domestic, month_prod=20,
                        price=1, domestic_sold_qty=600, stock_before_domestic=before)
    assert d["export"] is True
    assert d["ledger"]["exported_qty"] <= after_domestic, "外销量超出内销后的真实库存"
    assert d["ledger"]["no_double_sale"] is True
    # 守恒恒等式：内销 + 外销 ≤ 内销前存量（同一单位不会被卖两次）
    assert 600 + d["qty"] <= before
    assert d["income"] == d["qty"]                                  # 布 1 贯/单位

    out = apply_export_decision(st, d, seller=artisan, log=[])
    assert out["applied"] is True
    assert int(artisan["goods"]["布"]) == after_domestic - d["qty"]
    # 实物恒等式：内销 600 ＋ 外销 d.qty ＋ 池内剩余 == 内销前存量（无重复出售、无凭空货）
    assert 600 + (after_domestic - int(artisan["goods"]["布"])) + int(artisan["goods"]["布"]) \
        == before


def test_export_quantity_capped_by_real_post_domestic_stock():
    """外销量在结构上被"内销后真实库存"夹住（`min(..., stock)` 那一位不可绕过）。"""
    d = export_decision(dim="绸", stock=30, month_prod=10_000, price=3,
                        stock_months=0, export_rate=1.0)   # 极端：上限远大于库存
    assert d["export"] is True
    assert d["qty"] == 30 <= d["ledger"]["stock_after_domestic"]
    assert d["ledger"]["stock_left_after_export"] == 0


# ============================================================ 钱货守恒 + 来源登记
def test_real_surplus_conserves_goods_and_money_and_registers_source():
    """有真实剩余：货 −qty、钱 +income、来源登记为体外注入（不是内部划转）。"""
    st = _state()
    artisan = _artisan(stock=5000, wealth=1234)
    d = export_decision(dim="布", stock=5000, month_prod=100, price=1, pref="京畿路")
    assert d["export"] and d["qty"] > 0 and d["income"] > 0
    assert d["flow_registration"]["kind"] == "external"
    assert "外销变现·布" in d["flow_registration"]["reason"]

    goods_before = int(artisan["goods"]["布"])
    wealth_before = int(artisan["wealth"])
    out = apply_export_decision(st, d, seller=artisan, log=[])

    assert out["applied"] is True and out["registered"] is True
    assert int(artisan["goods"]["布"]) == goods_before - d["qty"]      # 货出
    assert int(artisan["wealth"]) == wealth_before + d["income"]      # 钱入
    assert d["income"] == d["qty"] * int(d["price"])                  # 钱货同价守恒
    flow = getattr(st, "_money_flow_month", {})
    assert flow["external_in"] == d["income"], "外销钱必须登记为体外注入"
    assert any("外销变现" in n for n in flow["notes"])
    assert st.statistics[STAT_CUMULATIVE_KEY] == d["income"], "累计键只在真实外销时累加"
    assert d["route_key"] == "京畿路|布", "路级键复用 pref_good_key 口径（B2-R2）"


def test_domestic_priority_blocks_export_when_committed_demand_unmet():
    """**国内有效需求优先**：有未满足的国内需求 ⇒ 货留国内，本月外销 0（有记录）。"""
    d = export_decision(dim="布", stock=5000, month_prod=100, price=1,
                        domestic_commitment_qty=5000)
    assert d["defined"] is True
    assert d["export"] is False
    assert d["income"] == 0, "有记录地确无外销，不是 None"
    assert d["reason"] == ExportReason.DOMESTIC_PRIORITY
    assert "国内" in d["reason_text"]
    assert d["ledger"]["reserved_for_domestic"] == 5000


def test_unrecorded_domestic_commitment_is_warned_not_silently_zero():
    """承诺需求未记录时按 0 计算，但**必须留痕**（缺失≠0）。"""
    d = export_decision(dim="布", stock=5000, month_prod=100, price=1,
                        domestic_commitment_qty=None)
    assert d["export"] is True
    assert any("未记录" in w for w in d["warnings"]), d["warnings"]


# ============================================================ 无余货 ⇒ 0（不是 None）
def test_no_surplus_is_recorded_zero_not_none():
    """库存未超上限：**语义为 0 且有记录**，reason 明确报"无可出口余货"。"""
    d = export_decision(dim="布", stock=500, month_prod=100, price=1)
    assert d["defined"] is True
    assert d["income"] == 0 and d["income"] is not None
    assert d["export"] is False
    assert d["reason"] == ExportReason.NO_SURPLUS
    assert "无可出口余货" in d["reason_text"]


def test_no_stock_and_no_production_are_distinct_recorded_zeros():
    """库存为 0 与本月无产出：**两个不同的已定义 0**，都不得读成 None。"""
    d0 = export_decision(dim="布", stock=0, month_prod=100, price=1)
    assert (d0["reason"], d0["income"], d0["defined"]) == (ExportReason.NO_STOCK, 0, True)
    dp = export_decision(dim="布", stock=5000, month_prod=0, price=1)
    assert (dp["reason"], dp["income"], dp["defined"]) == (ExportReason.NO_PRODUCTION, 0, True)


def test_zero_export_month_is_recorded_zero_and_cumulative_stays_unrecorded():
    """本月"确无余货"写 0；**累计**键不被写成 0（累计 0 ＝ 整局从未外销，口径不同）。"""
    st = _state()
    artisan = _artisan(stock=10)
    d = export_decision(dim="布", stock=10, month_prod=100, price=1)
    out = apply_export_decision(st, d, seller=artisan, log=[])
    assert out["applied"] is False and out["qty"] == 0

    month = export_month_readout(st)
    assert month["state"] == "recorded_zero" and month["income"] == 0 and month["defined"]
    assert STAT_MONTH_KEY in st.statistics
    assert STAT_CUMULATIVE_KEY not in st.statistics, "无外销时不得凭空造一个累计 0"
    cum = export_cumulative_readout(st)
    assert cum["income"] is None and cum["state"] == "unrecorded"
    assert st.statistics["export_decisions"][ExportReason.NO_SURPLUS] == 1


def test_undefined_inputs_yield_none_not_zero():
    """关键输入未记录 → `income is None` + `defined=False`（绝不回落 0/1.0）。"""
    for kwargs, reason in (
        ({"dim": "布", "stock": None, "month_prod": 100, "price": 1},
         ExportReason.UNDEFINED_STOCK),
        ({"dim": "布", "stock": 5000, "month_prod": None, "price": 1},
         ExportReason.UNDEFINED_PRODUCTION),
        ({"dim": "布", "stock": 5000, "month_prod": 100, "price": None},
         ExportReason.UNDEFINED_PRICE),
    ):
        d = export_decision(**kwargs)
        assert d["ok"] is True
        assert d["defined"] is False
        assert d["income"] is None, f"{reason} 不得回落 0"
        assert d["reason"] == reason
        assert d["flow_registration"] is None
        assert "未定义" in (d["detail"] or "") or "不等于 0" in d["reason_text"]


def test_undefined_policy_params_are_not_silently_defaulted():
    """策略参数不可读 → 未定义，**不回落默认值**（避免凭默认值伪造结论）。"""
    import content.data as cd
    old = cd.EXPORT_STOCK_MONTHS
    try:
        cd.EXPORT_STOCK_MONTHS = None
        d = export_decision(dim="布", stock=5000, month_prod=100, price=1)
        assert d["defined"] is False
        assert d["reason"] == ExportReason.UNDEFINED_PARAMS
        assert d["income"] is None
    finally:
        cd.EXPORT_STOCK_MONTHS = old
    assert export_decision(dim="布", stock=5000, month_prod=100, price=1)["export"] is True


def test_undefined_decision_is_not_written_as_zero_in_month_record():
    """未定义判定登记进本月读数时**不得**把 income 变成 0（缺失≠0）。"""
    st = _state()
    artisan = _artisan(stock=5000)
    d = export_decision(dim="布", stock=5000, month_prod=100, price=None)
    out = apply_export_decision(st, d, seller=artisan, log=[])
    assert out["applied"] is False
    m = export_month_readout(st)
    assert m["income"] is None and m["defined"] is False and m["state"] == "undefined"
    assert m["undefined_count"] == 1
    assert st.statistics[STAT_MONTH_KEY]["income"] is None


# ============================================================ 非法输入拒绝
def test_invalid_inputs_are_rejected_without_touching_books():
    """拒绝式校验：负数/NaN/Inf/bool/空维度/非正单价/双卖不可能 ⇒ ok=False 且不改账。"""
    bad = [
        dict(dim="", stock=10, month_prod=1, price=1),
        dict(dim=None, stock=10, month_prod=1, price=1),
        dict(dim="布", stock=-1, month_prod=1, price=1),
        dict(dim="布", stock=10, month_prod=-5, price=1),
        dict(dim="布", stock=10, month_prod=1, price=0),
        dict(dim="布", stock=10, month_prod=1, price=-2),
        dict(dim="布", stock=float("nan"), month_prod=1, price=1),
        dict(dim="布", stock=float("inf"), month_prod=1, price=1),
        dict(dim="布", stock=10, month_prod=float("nan"), price=1),
        dict(dim="布", stock=10, month_prod=True, price=1),
        dict(dim="布", stock=10, month_prod=1, price=1, domestic_sold_qty=-1),
        dict(dim="布", stock=10, month_prod=1, price=1, export_rate=-0.1),
        dict(dim="布", stock=10, month_prod=1, price=1,
             domestic_sold_qty=900, stock_before_domestic=100),
    ]
    for kwargs in bad:
        d = export_decision(**kwargs)
        assert d["ok"] is False, f"未拒绝：{kwargs}"
        assert d["defined"] is False and d["income"] is None
        assert d["export"] is False and d["qty"] == 0
        assert d["detail"], f"拒绝必须说明原因：{kwargs}"
        assert d["statistics_patch"] == {}, "被拒决策不得产出统计建议"


def test_rejected_decision_never_moves_goods_or_money():
    """被拒决策喂给执行入口：**钱货都不动**（不留单边账）。"""
    st = _state()
    artisan = _artisan(stock=1000, wealth=50)
    before_goods = int(artisan["goods"]["布"])
    out = apply_export_decision(st, export_decision(dim="布", stock=-1, month_prod=1,
                                                    price=1),
                                 seller=artisan, log=[])
    assert out["applied"] is False
    assert int(artisan["goods"]["布"]) == before_goods
    assert int(artisan["wealth"]) == 50
    assert not hasattr(st, "_money_flow_month") or st._money_flow_month["external_in"] == 0


def test_apply_never_invents_a_goods_slot():
    """卖家无该商品槽位 ⇒ 拒绝，**不新建槽位**（缺失≠0，也不得凭空造货）。"""
    st = _state()
    seller = {"size": 1, "wealth": 0, "goods": {}}
    d = export_decision(dim="布", stock=5000, month_prod=100, price=1)
    out = apply_export_decision(st, d, seller=seller, log=[])
    assert out["applied"] is False
    assert seller["goods"] == {}


def test_write_before_recheck_blocks_whole_trade():
    """写前复核：决策后池子被别处抽走 ⇒ **整笔不发生**（货不动、钱不动）。"""
    st = _state()
    artisan = _artisan(stock=5000, wealth=0)
    d = export_decision(dim="布", stock=5000, month_prod=100, price=1)
    artisan["goods"]["布"] = 1          # 决策后、外部抽走库存
    out = apply_export_decision(st, d, seller=artisan, log=[])
    assert out["applied"] is False
    assert int(artisan["goods"]["布"]) == 1 and int(artisan["wealth"]) == 0
    assert STAT_CUMULATIVE_KEY not in st.statistics
    assert "写前复核" in (out["detail"] or "")


# ============================================================ POP 挂载律 / 纯读
def test_no_parallel_ledger_is_created():
    """POP 挂载律：只动 POP `goods`/`wealth` ＋ statistics/货币流水，**不新建存量账本**。"""
    st = _state()
    artisan = _artisan(stock=5000, wealth=10)
    keys_before = set(artisan)
    d = export_decision(dim="布", stock=5000, month_prod=100, price=1)
    apply_export_decision(st, d, seller=artisan, log=[])
    assert set(artisan) == keys_before, "不得给 POP 增删字段（另起账本）"
    new_state_attrs = {k for k in vars(st) if k not in {"turn", "statistics", "prefectures"}}
    # 🔴 **有理由的例外（2026-10-13 登记）**：`stock_flow` 是 `core.domains.economy.stock_flow`
    #   的**登记式测量仪器**——按月记 `{custody: {dim: {in,out,by_reason}}}`，**不持 custody 真账、
    #   不参与任何结算判定、不 gate 任何玩法**，仅供"逐月库存恒等式"取证与回归断言。
    #   它与本用例要禁的「**与 POP 平行的玩法账本**」性质不同 ⇒ 显式放行；其余新增属性仍会被拒。
    assert new_state_attrs <= {"_money_flow_month", "stock_flow"}, new_state_attrs


def test_decision_is_pure_and_readouts_do_not_write():
    """决策与读数是**纯派生**：调用前后 state 一字未改。"""
    st = _state()
    artisan = _artisan(stock=5000)
    st.prefectures = {"京畿路": {"pops": {"工匠": artisan}}}
    snap = dict(st.statistics)
    export_decision(dim="布", stock=5000, month_prod=100, price=1, pref="京畿路")
    summarize_export([export_decision(dim="布", stock=5000, month_prod=1, price=1)])
    export_month_readout(st)
    export_cumulative_readout(st)
    read_artisan_stock(st, "京畿路", "布")
    assert st.statistics == snap


def test_read_artisan_stock_missing_is_none_not_zero():
    """读数：缺 `goods` 槽/缺该维度键 ⇒ `None`（未记录），**不回落 0**。"""
    st = _state()
    st.prefectures = {"甲": {"pops": {"工匠": {"goods": {"绸": 5}}}}}
    assert read_artisan_stock(st, "甲", "绸") == 5
    assert read_artisan_stock(st, "甲", "布") is None       # 无该维度键
    assert read_artisan_stock(st, "乙", "布") is None       # 无该路
    st.prefectures = {"甲": {"pops": {"工匠": {"size": 1}}}}  # 无 goods 槽
    assert read_artisan_stock(st, "甲", "布") is None


def test_month_record_merges_multiple_routes_in_same_turn():
    """同月多路/多商品的本月读数**累加**（turn 变了则另起一条，不跨月串账）。"""
    st = _state(turn=7)
    a1, a2 = _artisan(stock=5000), _artisan(stock=5000)
    d1 = export_decision(dim="布", stock=5000, month_prod=100, price=1, pref="甲")
    d2 = export_decision(dim="绸", stock=5000, month_prod=100, price=3, pref="乙")
    apply_export_decision(st, d1, seller=a1, log=[])
    apply_export_decision(st, d2, seller=a2, log=[])
    m = export_month_readout(st)
    assert m["turn"] == 7 and m["income"] == d1["income"] + d2["income"]
    assert m["qty"] == d1["qty"] + d2["qty"]
    assert set(m["by_dim"]) == {"甲|布", "乙|绸"}

    st.turn = 8
    d0 = export_decision(dim="布", stock=10, month_prod=100, price=1, pref="甲")
    apply_export_decision(st, d0, seller=a1, log=[])
    assert export_month_readout(st)["income"] == 0, "新月从 0 起，不继承上月"
    assert st.statistics[STAT_CUMULATIVE_KEY] == d1["income"] + d2["income"], "累计不因 0 重置"


def test_summarize_refuses_to_partial_sum_undefined():
    """汇总：只要有未定义/被拒决策，收入即 `None`（不许部分求和伪装确定值）。"""
    ok = export_decision(dim="布", stock=5000, month_prod=100, price=1)
    bad = export_decision(dim="布", stock=5000, month_prod=100, price=None)
    s = summarize_export([ok, bad])
    assert s["income"] is None and s["defined"] is False and s["undefined_count"] == 1
    assert s["qty"] == ok["qty"]
    assert s["by_reason"][ExportReason.EXPORTED] == 1


def test_fresh_state_month_readout_is_unrecorded_not_zero():
    """未接线的旧档/新局：本月读数是 `unrecorded`（None），**不是 0**。"""
    m = export_month_readout(_state())
    assert m["income"] is None and m["state"] == "unrecorded" and m["defined"] is False


def test_mixed_defined_and_undefined_month_is_not_partially_summed():
    """同月既有已定义判定又有未定义判定：收入**不可判定**（None），
    不得出现"income=0 却 defined=False"或部分求和伪装确定值。"""
    st = _state(turn=3)
    a1, a2 = _artisan(stock=5000), _artisan(stock=5000)
    apply_export_decision(st, export_decision(dim="布", stock=5000, month_prod=100,
                                              price=1, pref="甲"),
                          seller=a1, log=[])
    apply_export_decision(st, export_decision(dim="绸", stock=5000, month_prod=100,
                                              price=None, pref="乙"),
                          seller=a2, log=[])
    m = export_month_readout(st)
    assert m["income"] is None and m["defined"] is False
    assert m["state"] == "undefined" and m["undefined_count"] == 1
    assert m["reasons"] == [ExportReason.EXPORTED, ExportReason.UNDEFINED_PRICE]


def test_register_flow_failure_does_not_roll_back_goods():
    """台账登记失败必须**可见**（沿用 `register_money_flow` 契约），但不回滚钱货主流程。"""
    st = _state()
    artisan = _artisan(stock=5000, wealth=0)
    d = export_decision(dim="布", stock=5000, month_prod=100, price=1)
    out = apply_export_decision(st, d, seller=artisan, log=[], register_flow=True)
    assert out["applied"] is True
    assert out["registered"] is True
    assert all(math.isfinite(float(v)) for v in (artisan["wealth"],))


def test_real_game_state_pool_starts_empty_and_reports_recorded_zero():
    """接真实整局形状：工匠池开局为空 ⇒ 判定为**有记录的 0**（不是 None、不是凭空有货）。

    这是 B2-R6 放行证据"无剩余时明确报告无可出口余货"在真实数据上的落点：
    B1 之前池子靠虚拟直产虚胖，B1 之后真实为空 ⇒ 读数必须是**可解释的 0**。
    """
    from core.game_state import GameState
    from core.legacy_mechanic import init_legacies

    s = GameState("史实")
    init_legacies(s)
    route = next(iter(s.prefectures))
    artisan = s.prefectures[route]["pops"]["工匠"]
    stock = read_artisan_stock(s, route, "布")
    assert stock == 0, f"夹具前提：真实工匠池开局为空，实得 {stock!r}"

    d = export_decision(dim="布", stock=stock, month_prod=100, price=1, pref=route)
    assert d["defined"] is True and d["income"] == 0
    out = apply_export_decision(s, d, seller=artisan, log=[])
    assert out["applied"] is False and int(artisan["wealth"]) > 0, "钱未被凭空增加"
    m = export_month_readout(s)
    assert m["state"] == "recorded_zero" and m["income"] == 0
    assert export_cumulative_readout(s)["income"] is None, "累计键仍未登记（未记录≠0）"
