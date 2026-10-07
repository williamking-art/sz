# -*- coding: utf-8 -*-
"""B2-R5 · 农民与商人市场参与：收入来源读数与市场再进入判定的定向回归

对应规格 `specs/market-civilian-economy` §4 B2-R5「放行证据」：

1. **长局分别观察各 POP 收入来源** → `income_source_readout` 覆盖五类来源
   （售粮 / 工资工钱 / 运输仓储服务 / 作坊农业岗位 / 官府给付赈济），
   且 `capacity`（容量）与 `realized`（实发）**分列**、读不到即 `None` ＋ 原因。
2. **消费退出不会被误报成饥饿** → `consumption_exit_vs_hunger` 两口径并列，
   各自单一来源（`demand_release` / `food_insecure_headcount`），互不推导。
3. **重新获得收入后需求能响应** → `market_reentry` 口径**完全委托**
   `core.domains.economy.demand.demand_release` / `resolve_purchase_plan`（本模块不改 `demand.py`）。

锁定的项目硬约束：
- **POP 挂载律**：读数是**派生视图**，不改 `state`、不改 `statistics`、
  **不新建与 POP 平行的收入账本**（state 属性集合不得增加）。
- **缺失 ≠ 0 ≠ 1.0**：缺字段 → `None` ＋ 原因；**分母为 0 不除零**。
- **非法输入拒绝式**：未知路/阶层、负数/非有限收入、非正 `max_rows` → `ValueError`。
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

from core.demand import demand_release, resolve_purchase_plan  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.income_readout import (  # noqa: E402
    INCOME_SOURCES, POP_CLASSES, SOURCE_KEYS, build_income_readout,
    consumption_exit_vs_hunger, income_source_readout, market_reentry,
    purchasing_power_readout,
)
from core.legacy_mechanic import init_legacies  # noqa: E402
from core.market import sellable_stock  # noqa: E402
from core.settlement_common import food_insecure_headcount  # noqa: E402

#: 任务书要求覆盖的五类收入来源（顺序即 `INCOME_SOURCES` 展示序）
REQUIRED_SOURCES = (
    "grain_sale", "wage_labor", "logistics_service",
    "workshop_agriculture_job", "public_grant_relief",
)


def _state(months: int = 0):
    s = GameState("史实")
    init_legacies(s)
    for _ in range(months):
        s.treasury = max(s.treasury, 50_000_000)
        from core.settlement import run_monthly_settlement
        run_monthly_settlement(s)
    return s


def _route(s, i=0):
    return list(s.prefectures)[i]


def _rows(d, route):
    return next(r for r in d["by_route"] if r["route"] == route)


# ---------------------------------------------------------------- 状态快照

_SNAP_KEYS = ("prefectures", "statistics", "granary_stats", "economy_history",
              "treasury", "imperial_treasury", "grain_price", "dynamic_prices",
              "workshops", "_money_flow_month", "population_satisfaction")


def _snapshot(s):
    """深快照权威字段 ＋ `state` 属性集合（用于验证"不写 state / 不新建账本"）。"""
    snap = {k: copy.deepcopy(getattr(s, k, None)) for k in _SNAP_KEYS}
    snap["__attrs__"] = set(vars(s))
    return snap


# ============================================================== 1 · 收入来源拆分

def test_five_income_sources_are_covered_with_chinese_labels():
    """五类收入来源齐全且各带中文标签（任务书点名项逐条覆盖）。"""
    assert tuple(k for k, _l, _p in INCOME_SOURCES) == REQUIRED_SOURCES
    assert set(SOURCE_KEYS) == set(REQUIRED_SOURCES)
    labels = {k: lab for k, lab, _p in INCOME_SOURCES}
    assert labels["grain_sale"] == "售粮收入"
    assert "工资" in labels["wage_labor"] and "工钱" in labels["wage_labor"]
    assert "运输" in labels["logistics_service"] and "仓储" in labels["logistics_service"]
    assert "作坊" in labels["workshop_agriculture_job"]
    assert "官府" in labels["public_grant_relief"] and "赈济" in labels["public_grant_relief"]


def test_every_route_class_row_has_all_five_source_slots():
    """每个 (路, 阶层) 都给出全部五类来源，并按路/按阶层分开。"""
    s = _state()
    d = income_source_readout(s, routes=[_route(s, 0)], classes=["农", "商人", "工匠"])
    by_c = _rows(d, _route(s, 0))["by_class"]
    assert set(by_c) == {"农", "商人", "工匠"}
    for cls, row in by_c.items():
        assert set(row["sources"]) == set(REQUIRED_SOURCES)
        for k, slot in row["sources"].items():
            assert slot["key"] == k
            assert slot["label"]
            assert slot["code_path"], f"{k} 缺实现落点标注"
            assert "available" in slot and "capacity" in slot
            assert "realized" in slot


def test_farmer_sale_capacity_applies_safety_floor_and_others_do_not():
    """农售粮容量扣**安全垫**（可售＝grain−2×need），非农扣一份口粮（grain−need）。"""
    s = _state()
    r = _route(s, 0)
    pops = s.prefectures[r]["pops"]
    d = income_source_readout(s, routes=[r], classes=["农", "士绅"])
    by_c = _rows(d, r)["by_class"]

    from content.data import GRAIN_CONSUME_PER_CAPITA as G
    for cls, mult in (("农", 2), ("士绅", 1)):
        pop = pops[cls]
        need = int(pop["size"] * G.get(cls, 0.5))
        want = max(0, int(pop["grain"]) - mult * need)
        cap = by_c[cls]["sources"]["grain_sale"]["capacity"]
        assert cap["monthly_need_stone"] == need
        assert cap["saleable_grain_stone"] == want, f"{cls} 可售粮口径不符"
        slot = by_c[cls]["sources"]["grain_sale"]
        assert slot["capacity_bound"] == "upper_bound"
        assert slot["capacity"]["farmer_safety_floor"] is (cls == "农")


def test_grain_sale_value_upper_bound_uses_route_grain_price():
    """售粮容量上限用**本路**粮价（路级价格域 B2-R2），不是全国价。"""
    s = _state()
    r = _route(s, 0)
    s.prefectures[r]["grain_price"] = 2.5
    d = income_source_readout(s, routes=[r], classes=["农"])
    cap = _rows(d, r)["by_class"]["农"]["sources"]["grain_sale"]["capacity"]
    assert cap["grain_price"] == 2.5
    assert cap["grain_price_source"] == "prefectures[路].grain_price"
    if cap["saleable_value_upper_bound"] is not None:
        assert cap["saleable_value_upper_bound"] == pytest.approx(
            cap["saleable_grain_stone"] * 2.5)


def test_artisan_workshop_capacity_reads_sellable_goods_pool():
    """工匠的作坊/岗位容量＝本路**可售成品池**（`sellable_stock` 单点口径）。"""
    s = _state()
    r = _route(s, 0)
    art = s.prefectures[r]["pops"]["工匠"]
    art["goods"] = {"布": 100, "绸": 0}
    d = income_source_readout(s, routes=[r], classes=["工匠"])
    slot = _rows(d, r)["by_class"]["工匠"]["sources"]["workshop_agriculture_job"]
    pool = slot["capacity"]["goods_pool_by_dim"]
    assert pool["布"]["sellable_qty"] == sellable_stock(seller=art, dim="布") == 100
    assert pool["绸"]["sellable_qty"] == 0
    assert slot["capacity_bound"] == "upper_bound"


def test_realized_is_none_with_reason_when_no_authoritative_record():
    """无权威记录键 ⇒ `realized=None` **且必带 reason**（不得回落 0 冒充"没赚到"）。"""
    s = _state()
    d = income_source_readout(s, routes=[_route(s, 0)])
    for row in _rows(d, _route(s, 0))["by_class"].values():
        if row is None:
            continue
        for k, slot in row["sources"].items():
            assert slot["realized"] is None, f"{k} 凭空给出了实发额"
            assert slot["reason"], f"{k} 的 realized 为 None 却没有说明原因"
            assert slot["record_key"] is None


def test_national_evidence_is_marked_cumulative_and_not_attributable():
    """全国累加证据单列，且**不得**被当成按路/按阶层实发额。"""
    s = _state()
    d = income_source_readout(s, routes=[_route(s, 0)])
    ev = d["national_evidence"]
    assert ev["window"] == "cumulative-national"
    for k, item in ev["items"].items():
        assert item["per_route"] is False and item["per_class"] is False, k
        if not item["present"]:
            assert item["value"] is None, f"{k} 未记录却给了数值"
    # 已确认是累加键：跑两个月后必然出现且不为 None（首月粮市可能无买方）
    s2 = _state(2)
    d2 = income_source_readout(s2, routes=[_route(s2, 0)])
    it = d2["national_evidence"]["items"]["grain_market_trade"]
    assert it["present"] is True and it["value"] is not None


def test_unwired_channel_is_reported_as_undecidable_not_zero():
    """运输/仓储服务收入**已定义但未接线** ⇒ 如实不可判定（`None`），不报 0。"""
    s = _state()
    d = income_source_readout(s, routes=[_route(s, 0)], classes=["商人"])
    slot = _rows(d, _route(s, 0))["by_class"]["商人"]["sources"]["logistics_service"]
    assert slot["available"] is None
    assert slot["realized"] is None
    assert slot["capacity"]["value_upper_bound"] is None
    assert "无调用方" in slot["reason"] or "未接线" in slot["reason"]
    # 不得把漕运**粮量**（石）当运费收入
    assert slot["capacity"]["pref_changping_stock"] is not None
    assert "石" in slot["reason"] and "不得当作钱" in slot["reason"]


# ============================================================== 2 · 消费退出 ≠ 饥饿

def test_consumption_exit_is_not_reported_as_hunger():
    """可选品 0 成交是**消费退出**，饥饿人数只能来自 `food_insecure_headcount`。"""
    s = _state()
    r = _route(s, 0)
    # 把农户压到温饱线以下（人均远低于 0.15 贯），并确保**有粮吃**（不得饿）
    s.prefectures[r]["pops"]["农"].update({"size": 1000, "wealth": 10, "grain": 100000})
    s.prefectures[r]["grain_price"] = 1.0
    ch = consumption_exit_vs_hunger(s, routes=[r])
    row = ch["by_class"]["农"]
    assert row["consumption_exit"] is True, "温饱线以下应是消费退出"
    assert row["hunger_headcount"] == 0, "有粮却被报成饥饿 ⇒ 消费退出被误报"
    assert row["coexist"] is False
    assert row["misreport_risk"] is True, "该场景正是消费退出被误报成饥饿的高风险点"
    assert "不得" in row["misreport_note"]
    # 饥饿口径来源必须唯一指向 food_insecure_headcount
    assert "food_insecure_headcount" in row["hunger_source"]


def test_consumption_exit_and_hunger_are_mutually_independent():
    """两个口径互不推导：有释放但买不起粮、无释放却没饿，两者都能单独成立。"""
    s = _state()
    r = _route(s, 0)
    pops = s.prefectures[r]["pops"]
    # 粮价 100 贯/石 ⇒ 吃饱需 50 贯/人；士绅温饱线仅 20 贯/人
    # ⇒ 存在"过得了消费闸门、却买不起口粮"的窗口（消费不退出 ≠ 不饿）
    s.grain_price = 100.0
    s.prefectures[r]["grain_price"] = 100.0
    pops["士绅"].update({"size": 1000, "wealth": 30_000, "grain": 0})   # 30 贯/人
    # 农：极穷但有粮 ⇒ 消费退出=True，饥饿=0
    pops["农"].update({"size": 1000, "wealth": 10, "grain": 100_000})
    ch = consumption_exit_vs_hunger(s, routes=[r])
    gentry, farm = ch["by_class"]["士绅"], ch["by_class"]["农"]
    assert gentry["consumption_exit"] is False, "30 贯/人 > 温饱线 20 ⇒ 不该判消费退出"
    assert gentry["hunger_headcount"] > 0, "买不起口粮的士绅应被判缺粮"
    assert farm["consumption_exit"] is True
    assert farm["hunger_headcount"] == 0
    assert gentry["coexist"] is False and farm["coexist"] is False


def test_hunger_headcount_matches_single_source_of_truth():
    """读数的 `hunger_headcount` 与 `food_insecure_headcount` 单点**逐路对账**。"""
    s = _state(2)
    r = _route(s, 0)
    pops = s.prefectures[r]["pops"]
    s.grain_price = 1.7                      # `famine_attribution` 读的是 state 级粮价
    s.prefectures[r]["grain_price"] = 1.7
    pops["兵"].update({"size": 500, "wealth": 0, "grain": 0})
    expect = food_insecure_headcount(pops, 1.7).get("兵", 0)
    ch = consumption_exit_vs_hunger(s, routes=[r])
    assert ch["by_class"]["兵"]["hunger_headcount"] == expect
    assert ch["hunger_evidence"]["grain_price"] == 1.7
    assert ch["hunger_evidence"]["grain_price_readable"] is True
    assert ch["hunger_evidence"]["capped_per_route"] is True


def test_zero_goods_spend_never_becomes_hunger():
    """`goods_spend=0`（可选品零成交）**只**进可选品证据，不影响饥饿读数。"""
    s = _state()
    r = _route(s, 0)
    s.prefectures[r]["pops"]["农"].update({"size": 1000, "wealth": 10, "grain": 100000})
    s.prefectures[r]["grain_price"] = 1.0
    s.statistics["goods_spend"] = 0.0
    s.statistics["goods_traded"] = {"布": 0, "绸": 0}
    ch = consumption_exit_vs_hunger(s, routes=[r])
    assert ch["optional_market_evidence"]["goods_spend"] == 0.0
    assert ch["optional_market_evidence"]["record_window"] == "cumulative-national"
    assert "不是" in ch["optional_market_evidence"]["zero_means"]
    assert ch["by_class"]["农"]["hunger_headcount"] == 0
    assert ch["by_class"]["农"]["consumption_exit"] is True


# ============================================================== 3 · 市场再进入

def _small_farmer_state():
    """构造小农局：温饱线以下但有粮有地，便于验证"获得收入后需求响应"。"""
    s = _state()
    r = _route(s, 0)
    s.prefectures[r]["grain_price"] = 1.0
    s.prefectures[r]["pops"]["农"].update(
        {"size": 1000, "wealth": 100, "grain": 100_000})   # 人均 0.1 贯 < 0.15
    s.prefectures[r]["pops"]["工匠"]["goods"] = {"布": 10_000, "绸": 10_000}
    return s


def test_no_income_is_not_assessed_instead_of_guessed():
    """未给注入收入 ⇒ `not_assessed`，**不臆造**响应与否。"""
    s = _small_farmer_state()
    d = market_reentry(s, routes=[_route(s, 0)], classes=["农"])
    row = _rows(d, _route(s, 0))["by_class"]["农"]
    assert row["verdict"] == "not_assessed"
    assert row["blocking"] == "income_not_specified"
    assert d["income_coin_assumed"] is None


def test_restored_income_makes_optional_demand_respond():
    """重新获得收入（售粮/工钱）⇒ 温饱线闸门越过 ⇒ 可选品需求**能响应**。"""
    s = _small_farmer_state()
    r = _route(s, 0)
    before = _rows(market_reentry(s, routes=[r], classes=["农"], income=0), r)["by_class"]["农"]
    assert before["release_now"] == 0.0
    assert before["verdict"] == "still_withheld"
    assert before["blocking"] == "below_subsistence"

    after = _rows(market_reentry(s, routes=[r], classes=["农"], income=1_000), r)["by_class"]["农"]
    assert after["release_after"] > after["release_now"] == 0.0
    assert after["verdict"] == "responsive"
    assert after["blocking"] is None
    assert after["plan_after"]["item_kinds"], "越过温饱线后应产出购买项"
    assert after["plan_now"]["item_kinds"] == []
    # 口径必须与 core.demand 完全一致（不另立算法）
    want = demand_release("农", (100 + 1000) / 1000.0)
    assert after["release_after"] == pytest.approx(want)


def test_income_alone_cannot_cross_subsistence_line():
    """收入不够越过温饱线时仍 `still_withheld` ⇒ 不谎报"有收入就能买"。"""
    s = _small_farmer_state()
    r = _route(s, 0)
    row = _rows(market_reentry(s, routes=[r], classes=["农"], income=10), r)["by_class"]["农"]
    assert row["verdict"] == "still_withheld"
    assert row["blocking"] == "below_subsistence"
    assert row["release_after"] == 0.0


def test_already_released_class_is_not_counted_as_rescued_by_income():
    """本就买得起的阶层标 `already_released`，不冒充"被收入救回市场"。"""
    s = _state()
    r = _route(s, 0)
    s.prefectures[r]["pops"]["士绅"].update({"size": 1000, "wealth": 5_000_000,
                                             "grain": 10_000})
    s.prefectures[r]["pops"]["工匠"]["goods"] = {"布": 100_000, "绸": 100_000}
    d = market_reentry(s, routes=[r], classes=["士绅"], income=1_000)
    row = _rows(d, r)["by_class"]["士绅"]
    assert row["release_now"] > 0
    assert row["verdict"] == "already_released"
    assert row["blocking"] is None


def test_supply_blocker_is_separated_from_income_blocker():
    """有收入但本路**无货** ⇒ `supply_blocked=True`，使收入问题与供给问题可分辨。"""
    s = _state()
    r = _route(s, 0)
    s.prefectures[r]["pops"]["农"].update({"size": 1000, "wealth": 100, "grain": 100_000})
    s.prefectures[r]["pops"]["工匠"]["goods"] = {}          # 本路无货
    row = _rows(market_reentry(s, routes=[r], classes=["农"], income=1_000), r)["by_class"]["农"]
    assert row["supply_blocked"] is True
    assert "布" in row["supply_blocker_dims"]
    assert any("无货" in n for n in row["notes"]), "须提示供给侧阻塞，不能全赖购买力"


def test_reentry_uses_route_level_buy_price():
    """再进入判定读**本路**买入价（`effective_buy_price`），不拿全国价冒充。"""
    s = _small_farmer_state()
    r = _route(s, 0)
    s.dynamic_prices = {f"{r}|布": 200.0}
    row = _rows(market_reentry(s, routes=[r], classes=["农"], income=1_000), r)["by_class"]["农"]
    # 高价使基本需求被价格敏感压低，但**闸门已越过** ⇒ 仍是 responsive
    assert row["release_after"] > 0
    assert row["verdict"] == "responsive"


# ============================================================== 4 · 纯只读 / 不新建账本

def test_all_readouts_do_not_write_state_or_statistics():
    """四个读数 ＋ 组合入口都不写 state / statistics（**纯派生只读**）。"""
    s = _state(2)
    before = _snapshot(s)
    r = _route(s, 0)
    income_source_readout(s, routes=[r])
    purchasing_power_readout(s, routes=[r])
    market_reentry(s, routes=[r], income=50_000)
    consumption_exit_vs_hunger(s, routes=[r])
    build_income_readout(s, routes=[r], income=50_000)
    after = _snapshot(s)
    assert after["__attrs__"] == before["__attrs__"], "读数在 state 上新建了属性（疑为新账本）"
    for k in _SNAP_KEYS:
        assert after[k] == before[k], f"读数改写了 state.{k}"


def test_build_income_readout_is_flagged_read_only_and_has_all_sections():
    """组合入口四段齐全、`read_only=True`、无异常。"""
    s = _state(1)
    d = build_income_readout(s, routes=[_route(s, 0)], income=10_000)
    assert d["read_only"] is True
    for k in ("income_sources", "purchasing_power", "reentry", "consumption_vs_hunger"):
        assert k in d and "error" not in d[k], f"{k} 读数失败：{d.get('warnings')}"
    assert d["warnings"] == []


def test_demand_module_is_not_reexported_with_own_algorithm():
    """本模块只**读** `core.demand`：口径来源须显式标注为 `core.demand.*`。"""
    s = _state()
    r = _route(s, 0)
    pp = _rows(purchasing_power_readout(s, routes=[r]), r)["by_class"]["农"]
    assert pp["release_source"] == "core.domains.economy.demand.demand_release"
    row = _rows(market_reentry(s, routes=[r], classes=["农"], income=1_000), r)["by_class"]["农"]
    assert row["release_source"] == "core.domains.economy.demand.demand_release"


def test_release_matches_demand_release_exactly():
    """余量释放与 `core.domains.economy.demand.demand_release` **完全同源**（数值逐条相等）。"""
    s = _state(1)
    r = _route(s, 0)
    d = purchasing_power_readout(s, routes=[r])
    for cls, row in _rows(d, r)["by_class"].items():
        if row is None:
            continue
        if row["per_capita_wealth"] is None:
            assert row["release"] is None
        else:
            assert row["release"] == demand_release(cls, row["per_capita_wealth"])


# ============================================================== 5 · 缺失 ≠ 0 ≠ 1.0

def test_missing_wealth_is_none_not_zero():
    """POP 缺 `wealth` 键 ⇒ `None` ＋ release 不可判定，**不回落 0**。"""
    s = _state()
    r = _route(s, 0)
    del s.prefectures[r]["pops"]["农"]["wealth"]
    d = income_source_readout(s, routes=[r], classes=["农"])
    row = _rows(d, r)["by_class"]["农"]
    assert row["wealth"] is None
    assert row["per_capita_wealth"] is None
    assert "不除零" in row["per_capita_note"]
    pp = _rows(purchasing_power_readout(s, routes=[r], classes=["农"]), r)["by_class"]["农"]
    assert pp["wealth"] is None and pp["release"] is None
    assert pp["above_subsistence"] is None


def test_missing_grain_price_yields_none_not_zero_hunger():
    """粮价不可读 ⇒ 饥饿维度 `None` ＋ 原因，**不作 0**。"""
    s = _state()
    r = _route(s, 0)
    s.grain_price = None
    s.prefectures[r]["grain_price"] = None
    ch = consumption_exit_vs_hunger(s, routes=[r])
    row = ch["by_class"]["农"]
    assert row["hunger_headcount"] is None
    assert row["hunger_unavailable_reason"] == "grain_price_unreadable"
    assert row["coexist"] is None and row["misreport_risk"] is None
    assert ch["hunger_evidence"]["grain_price_readable"] is False
    assert any("grain_price" in w for w in ch["warnings"])
    pp = _rows(purchasing_power_readout(s, routes=[r], classes=["农"]), r)["by_class"]["农"]
    assert pp["food_purchasing_ability_stone"] is None


def test_missing_statistics_key_is_flagged_not_zero():
    """`statistics` 缺 `goods_spend` ⇒ `present=False` 且值为 `None`。"""
    s = _state()
    s.statistics.pop("goods_spend", None)
    s.statistics.pop("goods_traded", None)
    ch = consumption_exit_vs_hunger(s, routes=[_route(s, 0)])
    ev = ch["optional_market_evidence"]
    assert ev["present"] is False
    assert ev["goods_spend"] is None and ev["goods_traded"] is None


def test_missing_pop_class_row_is_none_and_warned():
    """该路缺某阶层记录 ⇒ 行给 `None` ＋ warning，**不当 0 人**。"""
    s = _state()
    r = _route(s, 0)
    del s.prefectures[r]["pops"]["商人"]
    d = income_source_readout(s, routes=[r], classes=["商人", "农"])
    row = _rows(d, r)["by_class"]
    assert row["商人"] is None
    assert row["农"] is not None
    assert any("商人" in w and "缺失" in w for w in d["warnings"])


def test_missing_prefectures_reports_warning_not_empty_zero():
    """`state.prefectures` 缺失 ⇒ 读数返回 `None`/警告，不回落全 0。"""
    s = _state()
    s.prefectures = None
    d = income_source_readout(s)
    assert d["by_route"] == []
    assert d["warnings"] and "prefectures" in d["warnings"][0]
    pp = purchasing_power_readout(s)
    assert pp["by_class_totals"] == {} and pp["warnings"]


# ============================================================== 6 · 分母为 0

def test_zero_size_does_not_divide_and_release_stays_none():
    """`size=0` ⇒ 人均财富 `None`、release `None`、再进入 `not_assessed`
    —— **不除零**、不回落 0/1.0。"""
    s = _state()
    r = _route(s, 0)
    s.prefectures[r]["pops"]["农"].update({"size": 0, "wealth": 0, "grain": 0})
    pp = _rows(purchasing_power_readout(s, routes=[r], classes=["农"]), r)["by_class"]["农"]
    assert pp["per_capita_wealth"] is None
    assert pp["release"] is None
    assert pp["above_subsistence"] is None
    # 口粮需求为 0 ⇒ 自给率 None（不是"完全自给 1.0"）
    assert pp["monthly_grain_need_stone"] == 0
    assert pp["grain_self_sufficiency"] is None
    row = _rows(market_reentry(s, routes=[r], classes=["农"], income=1_000), r)["by_class"]["农"]
    assert row["verdict"] == "not_assessed"
    assert row["blocking"] == "per_capita_wealth_unreadable"
    assert row["release_after"] is None


def test_class_totals_per_capita_is_none_when_no_population():
    """全路 size 都为 0 ⇒ 汇总人均财富 `None`（不造 0，也不造 1.0）。"""
    s = _state()
    r = _route(s, 0)
    s.prefectures[r]["pops"]["农"].update({"size": 0, "wealth": 0})
    d = purchasing_power_readout(s, routes=[r], classes=["农"])
    tot = d["by_class_totals"]["农"]
    assert tot["per_capita_wealth"] is None
    assert "不除零" in tot["per_capita_note"]


def test_purchasing_power_never_returns_infinite_or_nan():
    """读数不得产出 NaN/inf（否则 JSON 非法、前端解析直接崩）。"""
    s = _state(1)
    r = _route(s, 0)
    s.prefectures[r]["grain_price"] = float("inf")
    s.prefectures[r]["pops"]["农"]["wealth"] = float("nan")
    d = purchasing_power_readout(s, routes=[r])
    for row in _rows(d, r)["by_class"].values():
        if row is None:
            continue
        for k, v in row.items():
            if isinstance(v, float):
                assert math.isfinite(v), f"{k} 产出非有限值 {v}"


# ============================================================== 7 · 拒绝式输入

@pytest.mark.parametrize("bad_routes", ["京畿路", ["不存在的路"]])
def test_unknown_route_is_rejected(bad_routes):
    """未知路/传字符串 ⇒ `ValueError`（不静默纠正、不回落默认）。"""
    s = _state()
    with pytest.raises(ValueError):
        income_source_readout(s, routes=bad_routes)
    with pytest.raises(ValueError):
        purchasing_power_readout(s, routes=bad_routes)
    with pytest.raises(ValueError):
        market_reentry(s, routes=bad_routes, income=1)
    with pytest.raises(ValueError):
        consumption_exit_vs_hunger(s, routes=bad_routes)


def test_unknown_class_is_rejected():
    s = _state()
    with pytest.raises(ValueError):
        income_source_readout(s, classes=["不存在阶层"])
    with pytest.raises(ValueError):
        income_source_readout(s, classes="农")


@pytest.mark.parametrize("bad_income", [-1, float("nan"), float("inf"), "100", True])
def test_invalid_income_is_rejected(bad_income):
    """负数/非有限/非数值收入 ⇒ `ValueError`。

    `market_reentry` 是**拒绝式**入口，直接抛；
    `build_income_readout` 是**组合**入口，按设计不抛，改为把错误留在
    `warnings` ＋ 子读数 `error`（读数不得阻断调用方）。
    """
    s = _state()
    with pytest.raises(ValueError):
        market_reentry(s, routes=[_route(s, 0)], income=bad_income)
    d = build_income_readout(s, routes=[_route(s, 0)], income=bad_income)
    assert "error" in d["reentry"], "组合入口须把拒绝结果显式留痕"
    assert any("reentry" in w for w in d["warnings"])


@pytest.mark.parametrize("bad_max", [0, -3, "x"])
def test_invalid_max_rows_is_rejected(bad_max):
    s = _state()
    with pytest.raises(ValueError):
        income_source_readout(s, max_rows=bad_max)


def test_max_rows_truncation_is_reported_honestly():
    """超出 `max_rows` ⇒ 截断并如实报 `truncated`，不静默丢路。"""
    s = _state()
    all_routes = list(s.prefectures)
    d = income_source_readout(s, max_rows=2)
    assert len(d["by_route"]) == 2
    assert d["truncated"]["routes"] == len(all_routes) - 2
    assert {r["route"] for r in d["by_route"]} == set(all_routes[:2])


def test_pop_classes_constant_is_not_duplicated():
    """阶层表不另立一份（POP 挂载律：只 6 类 POP）。"""
    assert POP_CLASSES == ("农", "士绅", "工匠", "商人", "官僚", "兵")
    from content.data import GRAIN_CONSUME_PER_CAPITA
    assert tuple(GRAIN_CONSUME_PER_CAPITA.keys()) == POP_CLASSES


# ============================================================== 8 · 组合口径自洽

def test_resolve_purchase_plan_agrees_with_reentry_row():
    """`reentry` 的 `plan_after` 与直接调 `core.demand.resolve_purchase_plan` 一致。"""
    s = _small_farmer_state()
    r = _route(s, 0)
    income = 1_000
    row = _rows(market_reentry(s, routes=[r], classes=["农"], income=income), r)["by_class"]["农"]
    pop = s.prefectures[r]["pops"]["农"]
    from core.market_price import effective_buy_price
    from content.data import GOODS_DEMAND
    dims = list(GOODS_DEMAND.get("农", {}))
    prices = {d: effective_buy_price(dim=d, state=s, pref=r)["price"] for d in dims}
    base = {d: effective_buy_price(dim=d, state=None, pref=r, use_dynamic=False)["price"]
            for d in dims}
    plan = resolve_purchase_plan(
        cls="农", pop_size=pop["size"],
        per_capita_wealth=(pop["wealth"] + income) / float(pop["size"]),
        pref=GOODS_DEMAND["农"], held=pop.get("goods") or {},
        prices=prices, base_prices=base, budget=pop["wealth"] + income)
    assert row["plan_after"]["release"] == plan["release"]
    assert row["plan_after"]["no_demand"] == plan["no_demand"]
    assert row["plan_after"]["reason"] == plan["reason"]


def test_long_run_state_readout_stays_consistent():
    """长局（12 月）读数不崩、不产生非有限值（长局观察是 B2-R5 放行手段）。"""
    s = _state(12)
    d = build_income_readout(s, income=100_000)
    assert d["warnings"] == []
    assert d["consumption_vs_hunger"]["by_class"]["农"]["consumption_exit"] is not None
    pp = d["purchasing_power"]["by_class_totals"]
    assert pp["农"]["size"] > 0
    assert set(d["income_sources"]["source_keys"]) == set(REQUIRED_SOURCES)
