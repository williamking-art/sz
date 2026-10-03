# -*- coding: utf-8 -*-
"""B4-1 · 建材实物化本地市场的定向回归（规格 `market-civilian-economy` B4-1）

锁定的口径：
- **钱货双向守恒**：成交同时完成 `买方 wealth −paid` ＋ `卖方 wealth +paid`
  ＋ `卖方货 −q` ＋ `买方货 +q`；三方（材料来源／货款接收方／实物消耗）可对账；
- **无货不能买**：可售量为 0 → 成交 0、不扣钱，缺口如实记 `unmet_qty`；
- **可售量 ≤ 真实库存**：预留先扣，且成交后剩余**不得低于预留**；
- **替代必须显式**：默认一材不换；放行＋已声明才替代，且逐条留痕；
- **单位换算正确**：`MATERIAL_PRICE_BASE` 挂在库存单位上，成交单价按
  `units_per_stock` 换算到市场采购单位；
- **缺失不作 0**：存量缺槽／缺基准价／无来源 → `None` ＋ 明确原因；
- **非法输入拒绝**：负量、小数建材量、未知材料、不存在的持有人一律 `invalid`；
- **读数不改 state**：报价/可售量/价格函数是纯派生。
"""
import copy
import math
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.construction_cost import base_material_cost      # noqa: E402
from core.material_holding import MATERIAL_DIMS             # noqa: E402
from core.market import reset_trade_ledger                  # noqa: E402
from core.market_price import pref_good_key                 # noqa: E402
from core.material_market import (                          # noqa: E402
    CHANNELS, MATERIAL_SPECS, MATERIAL_SUBSTITUTES, MaterialReason,
    buy_material, convert_market_to_stock, convert_stock_to_market,
    issue_material, material_market_readout, material_price,
    material_spec, material_stock, material_supply, project_reservations,
    quote_material, register_material_spec, settle_material_purchase,
)

PREF = "京畿路"
TIMBER_PRICE = 50      # content.data_constants.MATERIAL_PRICE_BASE["木"]（钱/根）
STONE_PRICE = 30       # 同上（钱/方）


class _State:
    """最小可读 `state` 替身（只含本模块读取的既有槽位，无任何新增字段）。"""

    def __init__(self):
        self.turn = 1
        self.treasury = 100_000
        self.resources = {"木": {"stock": 1000, "cap": 5000},
                          "石": {"stock": 500, "cap": 5000},
                          "铁": {"stock": 200, "cap": 5000}}
        self.prefectures = {PREF: {"pops": {
            "士绅": {"size": 1000, "wealth": 20_000, "grain": 0, "goods": {}},
            "商人": {"size": 500, "wealth": 5_000, "grain": 0, "goods": {}},
        }}}
        self.dynamic_prices = {}
        self.statistics = {}
        self.projects = {}


def _state(turn=1, treasury=100_000, stock=None, pop_goods=None,
           pop_wealth=None, projects=None):
    s = _State()
    s.turn = turn
    s.treasury = treasury
    for dim, qty in (stock or {}).items():
        s.resources.setdefault(dim, {"stock": 0, "cap": 5000})["stock"] = qty
    for cls, g in (pop_goods or {}).items():
        s.prefectures[PREF]["pops"][cls]["goods"] = dict(g)
    for cls, w in (pop_wealth or {}).items():
        s.prefectures[PREF]["pops"][cls]["wealth"] = w
    if projects is not None:
        s.projects = dict(projects)
    return s


def _pop(s, cls):
    return s.prefectures[PREF]["pops"][cls]


def _money_total(s):
    """国库 + 各 POP wealth（建材成交**不得**凭空增减全系统钱量）。"""
    return s.treasury + sum(p.get("wealth", 0) for p in
                            s.prefectures[PREF]["pops"].values())


def _snapshot(s):
    return copy.deepcopy({
        "treasury": s.treasury, "resources": s.resources,
        "pops": s.prefectures[PREF]["pops"], "dynamic_prices": s.dynamic_prices,
        "projects": s.projects,
    })


@pytest.fixture(autouse=True)
def _reset_trade_ledger():
    reset_trade_ledger()
    yield
    reset_trade_ledger()


@pytest.fixture
def _isolated_specs():
    """`register_material_spec` 会改模块级 `MATERIAL_SPECS`：用例后复原。"""
    before = copy.deepcopy(MATERIAL_SPECS)
    yield
    MATERIAL_SPECS.clear()
    MATERIAL_SPECS.update(before)


# ====================================================== 钱货双向守恒（三方对账）
def test_pop_buys_pop_is_two_leg_conservation():
    """民间买民间：钱与货**同时**转移，Σwealth 不变。"""
    s = _state(pop_goods={"商人": {"木": 200}}, pop_wealth={"士绅": 20_000})
    before_money = _money_total(s)
    r = buy_material(s, pref=PREF, dim="木", qty=50,
                     buyer="pop", buyer_pop="士绅",
                     carrier="pop", seller_pop="商人")
    assert r["ok"] is True and r["reason"] == MaterialReason.OK
    assert r["traded"] == 50
    assert r["paid"] == 50 * TIMBER_PRICE
    assert _pop(s, "士绅")["wealth"] == 20_000 - r["paid"]      # 买方付款
    assert _pop(s, "商人")["wealth"] == 5_000 + r["paid"]       # 货款接收方
    assert _pop(s, "士绅")["goods"]["木"] == 50            # 买方得货
    assert _pop(s, "商人")["goods"]["木"] == 150           # 卖方出货
    assert _money_total(s) == before_money, "总钱量被凭空增减"


def test_treasury_buys_from_civilian_vendor():
    """官府向民间商户买料：国库出钱、**商户收钱**，料入仓储（工程预留入库）。"""
    s = _state(pop_goods={"商人": {"木": 200}})
    r = buy_material(s, pref=PREF, dim="木", qty=50, buyer="treasury",
                     carrier="pop", seller_pop="商人")
    assert r["paid"] == 50 * TIMBER_PRICE
    assert s.treasury == 100_000 - r["paid"]
    assert _pop(s, "商人")["wealth"] == 5_000 + r["paid"]
    assert s.resources["木"]["stock"] == 1000 + 50
    assert r["seller"] == f"{PREF}|商人"


def test_civilian_buys_from_state_warehouse():
    """民间向官仓买料：货出仓储、**货款回国库**（钱货两条腿都有真实对手方）。"""
    s = _state()
    r = buy_material(s, pref=PREF, dim="木", qty=40, buyer="pop",
                     buyer_pop="士绅", carrier="warehouse")
    assert r["paid"] == 40 * TIMBER_PRICE
    assert s.resources["木"]["stock"] == 1000 - 40
    assert s.treasury == 100_000 + r["paid"]
    assert _pop(s, "士绅")["goods"]["木"] == 40


def test_self_dealing_treasury_buys_own_warehouse_is_rejected():
    """国库买官仓＝自购自卖：不构成市场，直接拒绝（防左手倒右手造钱造货）。"""
    s = _state()
    before = _snapshot(s)
    r = buy_material(s, pref=PREF, dim="木", qty=10, buyer="treasury",
                     carrier="warehouse")
    assert r["ok"] is False
    assert r["reason"] == MaterialReason.SELF_DEALING
    assert _snapshot(s) == before, "被拒绝的输入不得改动任何状态"


# ====================================================== 无货不能买 / 可售量上限
def test_no_stock_local_means_no_trade():
    s = _state(stock={"石": 0}, pop_goods={"商人": {"石": 0}})
    before = _snapshot(s)
    r = buy_material(s, pref=PREF, dim="石", qty=50, buyer="pop",
                     buyer_pop="士绅", carrier="pop", seller_pop="商人")
    assert r["traded"] == 0 and r["paid"] == 0
    assert r["reason"] == MaterialReason.NO_STOCK
    assert r["unmet_qty"] == 50, "缺口必须单独返回，不静默丢弃"
    assert _snapshot(s) == before


def test_sellable_never_exceeds_real_stock_after_reserve():
    """预留先扣，且成交后剩余**不得低于预留**（预留不复制库存）。"""
    s = _state(stock={"石": 100})
    r = buy_material(s, pref=PREF, dim="石", qty=200, buyer="pop",
                     buyer_pop="士绅", carrier="warehouse", reserved=30)
    assert r["traded"] == 70, "成交不得超过 真实库存 − 预留"
    assert s.resources["石"]["stock"] == 30
    assert r["unmet_qty"] == 130
    # 再买一次：可售量已归零 ⇒ 无货不能买
    r2 = buy_material(s, pref=PREF, dim="石", qty=10, buyer="pop",
                      buyer_pop="士绅", carrier="warehouse", reserved=30)
    assert r2["traded"] == 0 and r2["reason"] == MaterialReason.NO_STOCK
    assert s.resources["石"]["stock"] == 30, "预留份额被吃掉"


def test_purchasing_power_is_the_second_cap():
    """三重上限：购买力不足时按实成交，不透支。"""
    s = _state(pop_goods={"商人": {"木": 1000}}, pop_wealth={"士绅": 120})
    r = buy_material(s, pref=PREF, dim="木", qty=100, buyer="pop",
                     buyer_pop="士绅", carrier="pop", seller_pop="商人")
    assert r["traded"] == 2 and r["paid"] == 100
    assert _pop(s, "士绅")["wealth"] == 20
    assert r["unmet_qty"] == 98
    assert r["reason"] == MaterialReason.NO_MONEY


# ====================================================== 替代必须显式
def test_substitution_not_performed_unless_explicitly_allowed():
    """默认 `allow_substitutes=None` ⇒ **一材不换**，缺口如实记账。"""
    s = _state(stock={"石": 10, "木": 500})
    r = settle_material_purchase(s, pref=PREF, materials={"石": 100},
                                 buyer="treasury", carrier="warehouse")
    assert r["substitutions"], "替代被评估过，必须留下痕迹（未放行＝未采用）"
    assert all(x["accepted"] is False for x in r["substitutions"])
    assert all(x["reason"] == "not_allowed" for x in r["substitutions"])
    assert r["totals"]["substitute_qty"] == 0
    assert r["totals"]["covered"] == 0.0
    assert r["totals"]["unmet"] > 0, "未放行替代时缺口必须如实记 unmet"


def test_substitution_only_for_declared_and_allowed_material():
    """放行未声明的替代材 ⇒ 仍不换（声明表是硬闸门）。"""
    s = _state(stock={"石": 0, "木": 500, "铁": 500})
    r = settle_material_purchase(s, pref=PREF, materials={"石": 60},
                                 buyer="treasury", carrier="warehouse",
                                 allow_substitutes=["铁"])     # stone↔iron 未声明
    assert all(x["accepted"] is False for x in r["substitutions"])
    assert r["totals"]["traded"] == 0


def test_explicit_substitution_records_acceptability():
    """显式放行 ⇒ 按**接受度**折算当量，并逐条留痕（可审计）。"""
    s = _state(stock={"石": 10, "木": 500})
    acc = MATERIAL_SUBSTITUTES["石"][0]["acceptability"]      # 1 材折抵 0.6 方
    r = settle_material_purchase(s, pref=PREF, materials={"石": 100},
                                 buyer="treasury", carrier="warehouse",
                                 allow_substitutes=["木"])
    sub = r["substitutions"][0]
    assert sub["accepted"] is True
    assert sub["provided_dim"] == "木"
    assert sub["acceptability"] == acc
    shortfall = 100 - r["lines"][0]["traded"]          # 主材缺口 90 方
    assert sub["qty"] == math.ceil(shortfall / acc)     # 需 150 材木折抵
    assert sub["covered"] == pytest.approx(shortfall, abs=1e-6)
    assert r["lines"][0]["covered"] == pytest.approx(shortfall, abs=1e-6)
    # 覆盖后不应再有缺口；替代材数量**不并入 traded**（不同单位）
    assert r["totals"]["unmet"] == 0
    assert r["totals"]["traded"] == 10
    assert r["totals"]["substitute_qty"] == 150
    assert r["ok"] is True


def test_invalid_acceptability_is_rejected_not_defaulted():
    """接受度非法（>1）⇒ 该条替代被拒并如实标注，**不按 1.0 兜底**。"""
    saved = MATERIAL_SUBSTITUTES["石"]
    MATERIAL_SUBSTITUTES["石"] = ({"to": "木", "acceptability": 3.0,
                                      "reason": "非法接受度用例"},)
    try:
        s = _state(stock={"石": 0, "木": 500})
        r = settle_material_purchase(s, pref=PREF, materials={"石": 30},
                                     buyer="treasury", carrier="warehouse",
                                     allow_substitutes=["木"])
        sub = r["substitutions"][0]
        assert sub["accepted"] is False
        assert sub["reason"] == "invalid_acceptability"
        assert r["totals"]["substitute_qty"] == 0
    finally:
        MATERIAL_SUBSTITUTES["石"] = saved


def test_quote_lists_declared_substitutes_without_enabling_them():
    q = quote_material(_state(), pref=PREF, dim="石")
    assert q["substitutes"], "必须列出已声明的替代材"
    assert all(x["declared"] is True and x["enabled"] is False
               for x in q["substitutes"])


# ====================================================== 单位与换算
def test_declared_units_are_explicit_and_consistent():
    for dim in ("木", "石", "铁"):
        spec = material_spec(dim)
        assert spec["unit"], f"{dim} 必须声明采购单位"
        assert spec["stock_unit"], f"{dim} 必须声明库存单位"
        assert spec["source"], f"{dim} 必须声明来源"
        assert spec["units_per_stock"] > 0


def test_unit_conversion_scales_price_and_stock_consistently(_isolated_specs):
    """非 1 换算系数：1 库存单位 = 2 采购单位 ⇒ 单价与扣货都按该系数折算。"""
    assert register_material_spec(
        "test梁", name="试验梁", unit="根", stock_unit="材",
        units_per_stock=2.0, source="测试夹具")["ok"] is True
    s = _state(stock={"test梁": 100})
    px = material_price(s, pref=PREF, dim="test梁", gov_price=100.0)
    # 基准价 100 钱/**材**（库存单位）；1 材 = 2 根（采购单位）⇒ 1 根 = 50 钱
    assert px["price_per_stock"] == pytest.approx(100.0)
    assert px["unit_price"] == pytest.approx(100.0 / 2.0)
    r = buy_material(s, pref=PREF, dim="test梁", qty=10, buyer="pop",
                     buyer_pop="士绅", carrier="warehouse", gov_price=100.0)
    assert r["traded"] == 10
    assert r["paid"] == 10 * 50             # 10 根 × 50 钱/根
    # 换算方向：`units_per_stock=2` ＝**1 库存单位(材) = 2 市场单位(根)**，
    # 故 10 根 = 5 材，100 − 5 = 95。
    assert s.resources["test梁"]["stock"] == 95
    assert convert_stock_to_market("test梁", 100) == pytest.approx(200.0)
    assert convert_market_to_stock("test梁", 200) == pytest.approx(100.0)


def test_pop_seller_stock_round_trips_through_unit_conversion(_isolated_specs):
    """POP 卖方的持货槽同样按**库存单位**写回（非 1:1 系数时不失真）。"""
    assert register_material_spec(
        "test石", name="试验石", unit="块", stock_unit="方",
        units_per_stock=2.0, source="测试夹具")["ok"] is True
    s = _state(pop_goods={"商人": {"test石": 100}})
    r = buy_material(s, pref=PREF, dim="test石", qty=20, buyer="pop",
                     buyer_pop="士绅", carrier="pop", seller_pop="商人",
                     gov_price=30.0)          # 30 钱/方 ⇒ 15 钱/块
    assert r["traded"] == 20
    assert r["paid"] == 20 * 15
    # 20 块 = 10 方 ⇒ 商户持货 100 方 → 90 方；货款进其 wealth
    assert _pop(s, "商人")["goods"]["test石"] == 90
    assert _pop(s, "商人")["wealth"] == 5_000 + r["paid"]
    assert _pop(s, "士绅")["goods"]["test石"] == 20


def test_fractional_material_qty_is_rejected_not_rounded():
    s = _state(stock={"木": 100})
    before = _snapshot(s)
    r = buy_material(s, pref=PREF, dim="木", qty=1.5, buyer="pop",
                     buyer_pop="士绅", carrier="warehouse")
    assert r["ok"] is False and r["reason"] == MaterialReason.INVALID
    assert _snapshot(s) == before


def test_market_unit_price_matches_construction_cost_unit_price():
    """口径单点：市场成交单价与 `construction_cost.base_material_cost` 同价。"""
    s = _state()
    px = material_price(s, pref=PREF, dim="木")
    cost = base_material_cost(materials={"木": 10.0}, state=s)
    assert cost["unresolved"] is False
    assert cost["lines"][0]["price"] == pytest.approx(
        px["price_per_stock"], rel=1e-6)
    assert cost["total"] == pytest.approx(10 * px["unit_price"], rel=1e-6)


# ====================================================== 缺失 ≠ 0
def test_missing_stock_slot_is_none_not_zero():
    """仓储槽位缺失 ⇒ 存量 `None`（**不是 0**），且拒绝成交。"""
    s = _state()
    del s.resources["石"]
    assert material_stock(s, "石") is None
    sup = material_supply(s, pref=PREF, dim="石")
    assert sup["known"] is False and sup["stock"] is None and sup["sellable"] is None
    assert sup["reason"] == MaterialReason.UNKNOWN_STOCK
    r = buy_material(s, pref=PREF, dim="石", qty=10, buyer="pop",
                     buyer_pop="士绅", carrier="warehouse")
    assert r["ok"] is False and r["reason"] == MaterialReason.UNKNOWN_STOCK
    assert r["paid"] == 0


def test_pop_without_goods_slot_is_unknown_not_zero():
    """旧档 POP 缺 `goods` 槽 ⇒ 未定义，不按"没有货"也不按"有货"处理。"""
    s = _state()
    del _pop(s, "商人")["goods"]
    sup = material_supply(s, pref=PREF, dim="木", carrier="pop")
    assert sup["stock"] is None and sup["known"] is False
    r = buy_material(s, pref=PREF, dim="木", qty=10, buyer="pop",
                     buyer_pop="士绅", carrier="pop", seller_pop="商人")
    assert r["ok"] is False and r["reason"] == MaterialReason.UNKNOWN_STOCK


def test_material_without_source_cannot_trade():
    """砖：无来源（未建模）⇒ 一律拒绝，**不凭空产出、不按 0 价成交**。"""
    s = _state(stock={"brick": 500})
    q = quote_material(s, pref=PREF, dim="brick", qty=10)
    assert q["tradeable"] is False
    assert q["reason"] == MaterialReason.NO_SOURCE
    before = _snapshot(s)
    r = settle_material_purchase(s, pref=PREF, materials={"brick": 10},
                                 buyer="treasury", carrier="warehouse")
    assert r["ok"] is False
    assert r["reason"] == MaterialReason.NO_SOURCE
    assert _snapshot(s) == before


def test_missing_base_price_is_not_zero_price():
    """缺基准价 ⇒ 价格 `None`，不回落 0（0 价会变成"凭空送货"）。"""
    s = _state()
    px = material_price(s, pref=PREF, dim="不存在之物")
    assert px["unit_price"] is None and px["price_per_stock"] is None


# ====================================================== 拒绝式非法输入
@pytest.mark.parametrize("bad,reason", [
    ({"木": -5}, MaterialReason.INVALID),
    ({"木": 1.5}, MaterialReason.INVALID),
    ({"木": "十"}, MaterialReason.INVALID),
    # 🔴 「未知物料」＝**未注册进 `MATERIAL_SPECS` 的维**（如「砖」——见规格：brick 三重缺失）。
    # 「木」已注册，是**合法建材维**；无来源时的正确 reason 是 `no_stock_local`，
    # 与「未知物料」是两回事，不可用「木」代测 UNKNOWN。
    ({"砖": 10}, MaterialReason.UNKNOWN_MATERIAL),
])
def test_invalid_materials_are_rejected_without_state_change(bad, reason):
    s = _state()
    before = _snapshot(s)
    r = settle_material_purchase(s, pref=PREF, materials=bad)
    assert r["ok"] is False and r["reason"] == reason
    assert _snapshot(s) == before


@pytest.mark.parametrize("kwargs", [
    {"pref": "", "materials": {"木": 1}},
    {"pref": None, "materials": {"木": 1}},
    {"pref": PREF, "materials": None},
    {"pref": PREF, "materials": {}}, {"pref": PREF, "materials": "木"},
    {"pref": PREF, "materials": {"木": 1}, "budget": -1},
    {"pref": PREF, "materials": {"木": 1}, "buyer": "外邦"},
    {"pref": PREF, "materials": {"木": 1}, "carrier": "仓库"},
    {"pref": PREF, "materials": {"木": 1}, "allow_substitutes": "木"},
])
def test_bad_arguments_are_rejected(kwargs):
    s = _state()
    before = _snapshot(s)
    r = settle_material_purchase(s, **kwargs)
    assert r["ok"] is False and r["reason"] == MaterialReason.INVALID
    assert r["detail"], "拒绝必须给出可读原因"
    assert _snapshot(s) == before


def test_missing_holder_is_rejected_not_invented():
    s = _state()
    before = _snapshot(s)
    r = buy_material(s, pref=PREF, dim="木", qty=10, buyer="pop",
                     buyer_pop="不存在阶层", carrier="warehouse")
    assert r["ok"] is False and r["reason"] == MaterialReason.NO_BUYER
    r2 = buy_material(s, pref=PREF, dim="木", qty=10, buyer="pop",
                      buyer_pop="士绅", carrier="pop", seller_pop="不存在阶层")
    assert r2["ok"] is False and r2["reason"] == MaterialReason.NO_SELLER
    assert _snapshot(s) == before


def test_zero_demand_is_not_unmet():
    s = _state()
    r = settle_material_purchase(s, pref=PREF, materials={"木": 0},
                                 buyer="treasury", carrier="warehouse")
    assert r["reason"] == MaterialReason.NO_DEMAND
    assert r["totals"]["unmet"] == 0


# ====================================================== 读数不改 state
def test_readonly_functions_do_not_touch_state():
    s = _state(pop_goods={"商人": {"木": 200}},
               projects={"p1": {"status": "building",
                                "_mat_left_木": 30.0, "_mat_left_石": 10.0}})
    before = _snapshot(s)
    _ = material_stock(s, "木")
    _ = material_supply(s, pref=PREF, dim="木", reserved="projects")
    _ = material_price(s, pref=PREF, dim="木")
    _ = quote_material(s, pref=PREF, dim="木", qty=10)
    _ = quote_material(s, pref=PREF, dim="石")
    _ = project_reservations(s)
    _ = material_market_readout(s, pref=PREF)
    assert _snapshot(s) == before, "只读读数不得改动任何状态"


# ====================================================== 幂等 / 预留派生 / 预算
def test_same_trade_id_in_same_turn_is_idempotent():
    """同回合同 trade_id ⇒ 幂等，不二次转移（防回合重试重复成交）。"""
    s = _state(pop_goods={"商人": {"木": 200}})
    args = dict(pref=PREF, dim="木", qty=50, buyer="treasury",
                carrier="pop", seller_pop="商人", trade_id="mat:t1:0")
    r1 = buy_material(s, **args)
    snap = _snapshot(s)
    r2 = buy_material(s, **args)
    assert r1["traded"] == 50
    assert r2["reason"] == MaterialReason.DUPLICATE
    assert r2["traded"] == r1["traded"], "重复调用返回首次结果，不二次转移"
    assert _snapshot(s) == snap


def test_project_reservation_reduces_sellable():
    """`reserved="projects"`：在营工程的未领申领占用同一批货。"""
    s = _state(stock={"木": 100}, pop_goods={"商人": {"木": 100}},
               projects={"p1": {"status": "building", "_mat_left_木": 40.0,
                                "_mat_left_石": 10.0},
                         "p2": {"status": "proposed", "_mat_left_木": 99.0}})
    assert project_reservations(s) == {"木": 40, "石": 10}
    assert project_reservations(s, "石") == {"石": 10}
    sup = material_supply(s, pref=PREF, dim="木", carrier="pop",
                          reserved="projects")
    assert sup["reserved"] == 40 and sup["sellable"] == 60
    r = buy_material(s, pref=PREF, dim="木", qty=100, buyer="treasury",
                     carrier="pop", reserved="projects")
    assert r["traded"] == 60, "可售量必须先扣工程预留"
    assert _pop(s, "商人")["goods"]["木"] == 40


def test_budget_caps_purchase_and_reports_unused():
    s = _state(pop_goods={"商人": {"木": 1000}})
    r = settle_material_purchase(s, pref=PREF, materials={"木": 100},
                                 budget=500, buyer="treasury",
                                 carrier="pop", seller_pop="商人")
    assert r["totals"]["paid"] <= 500
    assert r["totals"]["budget_unused"] == pytest.approx(500 - r["totals"]["paid"])
    assert r["money"]["payer"] == "state.treasury"
    assert r["money"]["receiver"] == f"{PREF}|商人"
    # 官府购料**落进仓储**（工程预留入库）⇒ 现有 `_settle_projects` 仍从仓储扣料
    bought = r["totals"]["traded"]
    assert s.resources["木"]["stock"] == 1000 + bought


# ====================================================== 官仓领料（B4-6 不双计）
def test_warehouse_issue_has_no_money_leg():
    """官仓领料＝内部调拨：**没有货款**，只记基准估价（与市场购料分别记账）。"""
    s = _state(stock={"木": 1000})
    before = _snapshot(s)
    r = issue_material(s, pref=PREF, dim="木", qty=100)
    assert r["channel"] == CHANNELS[1]
    assert r["traded"] == 100 and r["paid"] == 0
    assert r["value"] == pytest.approx(100 * TIMBER_PRICE)
    assert s.treasury == before["treasury"], "领料不得动钱"
    assert s.resources["木"]["stock"] == 900
    assert r["seller"] == "state.resources" and r["buyer"] == "state.treasury"


def test_settle_routes_treasury_warehouse_to_issue():
    s = _state(stock={"木": 1000})
    r = settle_material_purchase(s, pref=PREF, materials={"木": 50},
                                 buyer="treasury", carrier="warehouse")
    assert r["channel"] == CHANNELS[1]
    assert r["totals"]["paid"] == 0
    assert r["money"]["receiver"].startswith("无（官仓领料")
    assert any("不双计" in w for w in r["warnings"])


# ====================================================== 价格：路级动态键
def test_price_uses_route_level_dynamic_key():
    s = _state()
    key = pref_good_key(PREF, "木")
    assert key == f"{PREF}|木"
    px = material_price(s, pref=PREF, dim="木")
    assert px["dynamic_key"] == key
    assert px["price_kind"] == "base" and px["price_per_stock"] == TIMBER_PRICE
    # 成交后回写**路级**动态成交均价（不改基准表）
    buy_material(s, pref=PREF, dim="木", qty=10, buyer="pop",
                 buyer_pop="士绅", carrier="warehouse")
    assert key in s.dynamic_prices
    assert s.dynamic_prices[key] == pytest.approx(TIMBER_PRICE)


def test_readout_reports_every_registered_material():
    s = _state(stock={"木": 10})
    out = material_market_readout(s, pref=PREF)
    dims = {r["dim"] for r in out["rows"]}
    assert dims == set(MATERIAL_SPECS)
    row = next(r for r in out["rows"] if r["dim"] == "brick")
    assert row["tradeable"] is False and row["reason"] == MaterialReason.NO_SOURCE
    assert out["warnings"] == []


# ====================================================== 读数登记不双计
def test_statistics_are_recorded_once_per_applied_trade():
    s = _state(pop_goods={"商人": {"木": 500}})
    r = settle_material_purchase(s, pref=PREF, materials={"木": 20},
                                 buyer="treasury", carrier="pop",
                                 seller_pop="商人", trade_prefix="mt1")
    assert r["totals"]["paid"] == 20 * TIMBER_PRICE
    assert s.statistics["material_paid"] == pytest.approx(20 * TIMBER_PRICE)
    assert s.statistics["material_qty_by_dim"]["木"] == 20
    # 同回合重复调用被幂等拦截：不得二次登记读数
    again = settle_material_purchase(s, pref=PREF, materials={"木": 20},
                                     buyer="treasury", carrier="pop",
                                     seller_pop="商人", trade_prefix="mt1")
    assert again["reason"] == MaterialReason.DUPLICATE
    assert again["totals"]["paid"] == 0
    assert s.statistics["material_paid"] == pytest.approx(20 * TIMBER_PRICE)
    assert _pop(s, "商人")["goods"]["木"] == 480


def test_brick_alternative_is_rejected_without_source():
    """砖未注册来源 ⇒ 不能拿来替代石料（B4-2：科技 ≠ 免费材料）。"""
    s = _state(stock={"石": 0, "木": 500, "brick": 999})
    r = settle_material_purchase(s, pref=PREF, materials={"石": 30},
                                 buyer="treasury", carrier="warehouse",
                                 allow_substitutes=["brick"])
    assert r["totals"]["substitute_qty"] == 0
    assert r["totals"]["unmet"] > 0


def test_same_pop_cannot_buy_from_itself():
    s = _state(pop_goods={"商人": {"木": 100}})
    before = _snapshot(s)
    r = buy_material(s, pref=PREF, dim="木", qty=10, buyer="pop",
                     buyer_pop="商人", carrier="pop", seller_pop="商人")
    assert r["ok"] is False and r["reason"] == MaterialReason.INVALID
    assert _snapshot(s) == before


# ====================================================== 真实 GameState 冒烟
def test_works_on_real_game_state():
    """真实 `GameState`：仓储槽位/POP 结构可被读，缺货如实报"无货"而非崩。"""
    from core.game_state import GameState
    from core.legacy_mechanic import init_legacies

    s = GameState("史实")
    init_legacies(s)
    pref = next(iter(s.prefectures))
    q = quote_material(s, pref=pref, dim="木", qty=10)
    assert q["supply"]["known"] is True
    assert q["price"]["unit_price"] == pytest.approx(TIMBER_PRICE)
    assert q["unit"] == "材" and q["stock_unit"] == "根"
    # 开局仓储为空 ⇒ 如实报"无货"，**不虚拟供给**
    assert (q["supply"]["sellable"] or 0) >= 0
    assert q["tradeable"] is False
    # 放入真实库存后即可成交（钱货两腿都落在既有槽位）
    s.resources["木"]["stock"] = 200
    before_treasury = s.treasury
    r = buy_material(s, pref=pref, dim="木", qty=20, buyer="pop",
                     buyer_pop="士绅", carrier="warehouse")
    assert r["applied"] is True and r["traded"] == 20
    assert s.resources["木"]["stock"] == 180
    assert s.treasury == before_treasury + r["paid"]
    out = material_market_readout(s, pref=pref)
    assert len(out["rows"]) == len(MATERIAL_SPECS)