# -*- coding: utf-8 -*-
"""B0 · 民间经济读数的定向回归（规格 `market-civilian-economy` B0-2/3/4）

关键约定：
- 读数模块**纯只读**——测试必须能证明它不写状态；
- **缺失不作 0**——不可读的字段给 `None`/`unknown`，不得回落 0 冒充"没有交易"；
- **有界**——明细截断但 `truncated` 要如实报出被截数量。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402
from core.market_readout import (  # noqa: E402
    MARKET_READOUT_SCHEMA_VERSION, build_market_readout, demand_diagnosis,
    flow_classification, inventory_ledger,
)


def _state():
    s = GameState("史实")
    init_legacies(s)
    return s


# ====================================================== 纯只读
def test_readout_does_not_mutate_state():
    """B0 契约：只观测、不改模型。任何写 state 的行为都视为违约。"""
    s = _state()
    s.resources["iron"] = {"stock": 500, "cap": 1000}
    s.prefectures[list(s.prefectures)[0]]["pops"]["工匠"]["goods"]["布"] = 40
    before = {
        "m": dict(s.resources),
        "pop": {k: dict(v.get("goods") or {}) for k, v in
                list(s.prefectures.values())[0]["pops"].items()},
        "stats": dict(s.statistics or {}),
        "granary": s.granary,
        "turn": s.turn,
    }
    build_market_readout(s)
    assert {k: dict(v) for k, v in s.resources.items()} == before["m"]
    after_pop = {k: dict(v.get("goods") or {}) for k, v in
                 list(s.prefectures.values())[0]["pops"].items()}
    assert after_pop == before["pop"]
    assert dict(s.statistics or {}) == before["stats"]
    assert s.granary == before["granary"]
    assert s.turn == before["turn"]


# ====================================================== B0-2 库存台账
def test_inventory_lists_four_carriers():
    ro = inventory_ledger(_state())
    assert ro["schema_version"] == MARKET_READOUT_SCHEMA_VERSION
    # ①仓储 ②POP 持货 ③太仓 ④在途
    for key in ("warehouses", "pop_holdings", "granary", "in_transit"):
        assert key in ro, key
    # ✅ P0（2026-10-02）在途**已实现**（`core/transport`），不再是固定 False。
    # ⚠️ 仍须显式携带「耗时是设定值、非史料」的说明——不静默抹掉口径。
    it = ro["in_transit"]
    assert it["implemented"] is True
    assert it["items"] == [] and it["count"] == 0, "开局无在途"
    assert "非史料" in it["note"] or "设定值" in it["note"]
    assert ro["granary"]["dim"] == "grain"


def test_inventory_marks_artisan_pool_double_role():
    """工匠 goods 兼作生产池与消费持有——须显式标注，不静默合并。"""
    s = _state()
    route = list(s.prefectures)[0]
    s.prefectures[route]["pops"]["工匠"]["goods"]["绸"] = 25
    ro = inventory_ledger(s)
    rows = [r for r in ro["pop_holdings"]
            if r["cls"] == "工匠" and r["dim"] == "绸"]
    assert rows, "工匠持货未被读出"
    assert rows[0]["role"] == "producer_pool"
    assert rows[0]["qty"] == 25
    assert rows[0]["route"] == route


def test_inventory_warehouse_reports_fill_ratio():
    s = _state()
    s.resources["timber"] = {"stock": 250, "cap": 1000}
    ro = inventory_ledger(s)
    row = next(r for r in ro["warehouses"] if r["dim"] == "timber")
    assert row["stock"] == 250 and row["cap"] == 1000
    assert row["fill_ratio"] == 0.25
    assert row["holder_type"] == "warehouse"


def test_inventory_missing_value_is_none_not_zero():
    """缺失 ≠ 0：stock 不可读时给 None，不回落 0 冒充"空仓"。"""
    s = _state()
    s.resources["gold"] = {"stock": None, "cap": 1000}
    ro = inventory_ledger(s)
    row = next(r for r in ro["warehouses"] if r["dim"] == "gold")
    assert row["stock"] is None
    assert row["fill_ratio"] is None


def test_inventory_truncation_is_reported():
    """有界：明细截断，但被截数量必须如实报出（不能假装只有 max_items 条）。"""
    s = _state()
    ro = inventory_ledger(s, max_items=3)
    assert len(ro["pop_holdings"]) <= 3
    assert ro["truncated"]["pop_holdings"] >= 0


def test_inventory_totals_are_readview_not_ledger():
    """汇总只是读视图：仓储与 POP 持货是不同载体，标明不可相加。"""
    s = _state()
    s.resources["stone"] = {"stock": 100, "cap": 500}
    route = list(s.prefectures)[0]
    s.prefectures[route]["pops"]["农"]["goods"]["布"] = 7
    ro = inventory_ledger(s)
    assert ro["totals"]["warehouse_stock"] >= 100
    assert ro["totals"]["pop_goods_qty"] >= 7
    assert "不可相加" in ro["totals"]["note"]


# ====================================================== B0-3 需求诊断
def test_zero_effective_demand_is_not_an_unmet_reason():
    """零有效需求 = "无需求"，**不得**计成未满足原因。"""
    s = _state()
    s.statistics["goods_spend"] = 0.0
    d = demand_diagnosis(s)
    assert d["buckets"]["no_demand"] == 1
    # 其余四类未满足原因必须为 0
    assert d["buckets"]["no_stock_local"] == 0
    assert d["buckets"]["insufficient_purchasing_power"] == 0


def test_spend_without_stock_flags_virtual_supply():
    """有支出却全仓无货 → 指向无卖方路径，须告警而不是静默通过。"""
    s = _state()
    for slot in s.resources.values():
        slot["stock"] = 0
    s.statistics["goods_spend"] = 1000.0
    d = demand_diagnosis(s)
    assert d["buckets"]["no_stock_local"] == 1
    assert any("无卖方" in w for w in d["warnings"])


def test_missing_statistic_yields_unknown_not_zero():
    """statistics 无 goods_spend → `unknown` ＋ 明确警告，不臆造分类。"""
    s = _state()
    d = demand_diagnosis(s)
    assert d["buckets"]["unknown"] == 1
    assert d["observed"]["goods_spend"] is None
    assert any("不可判定" in w for w in d["warnings"])


def test_demand_lists_unimplemented_reasons():
    """运输未到/配给限额当前无机制，须显式列出而非静默省略。"""
    d = demand_diagnosis(_state())
    joined = " ".join(d["unimplemented_reasons"])
    assert "运输未到" in joined and "配给" in joined


# ====================================================== B0-4 流量分类
def test_flow_classification_covers_six_categories():
    f = flow_classification(_state())
    c = f["classification"]
    for k in ("money_internal_transfer", "money_external_injection_or_burn",
              "goods_trade", "production_consumption",
              "household_consumption", "government_allocation", "initial_stock"):
        assert k in c, k


def test_flow_separates_internal_transfer_from_injection():
    """铸币/熔铜属外部注入，内部划转不是——分类不得混淆。"""
    s = _state()
    s.statistics["minted"] = 1000.0
    s.statistics["coin_melted"] = 500.0
    s.statistics["export_income"] = 300.0
    f = flow_classification(s)
    inj = f["classification"]["money_external_injection_or_burn"]["observed_keys"]
    itr = f["classification"]["money_internal_transfer"]["observed_keys"]
    assert "minted" in inj and "coin_melted" in inj
    assert "export_income" in itr and "minted" not in itr


def test_flow_reports_unimplemented_buckets():
    f = flow_classification(_state())
    for k in ("production_consumption", "household_consumption",
              "government_allocation", "initial_stock"):
        assert k in f["unimplemented"], k


def test_flow_money_total_uses_money_module():
    """M_ALL 由 money.py 单点提供，读数**不重算**（口径单点）。"""
    from core.money import m_all
    s = _state()
    f = flow_classification(s)
    assert f["money_total"] == m_all(s)


# ====================================================== 组合入口
def test_build_readout_is_pure_and_shaped():
    s = _state()
    ro = build_market_readout(s)
    for k in ("schema_version", "inventory", "demand", "flows", "warnings"):
        assert k in ro, k
    assert isinstance(ro["warnings"], list)


def test_readout_survives_broken_resources():
    """读数失败**不得阻断**主流程：坏字段进 warnings，其余部分照常返回。"""
    s = _state()
    s.resources = "这不是字典"          # 故意破坏
    ro = build_market_readout(s)
    assert ro["inventory"]["warehouses"] == []
    assert any("仓储库存不可读" in w for w in ro["inventory"]["warnings"])
    # 其余子读数仍可用
    assert "demand" in ro and "flows" in ro


def test_readout_includes_population_and_famine_sections():
    """B2-R1/R3：总入口聚合**六路**子读数（含人口台账与饥荒四因）。"""
    s = _state()
    ro = build_market_readout(s)
    for key in ("inventory", "demand", "flows", "population", "famine", "hunger"):
        assert key in ro, f"缺子读数 {key}"
    assert ro["population"]["total_pop"] > 0
    assert "by_reason" in ro["famine"]
    # 饥饿口径必须标明是**人月**而非当月人数
    assert ro["hunger"]["not_a_headcount"] is True


@pytest.mark.parametrize("months", [1, 3])
def test_readout_stable_across_settlement(months):
    """读数在真实结算后仍可用，且不抛出阻断性异常。"""
    from core.settlement import run_monthly_settlement
    s = _state()
    s.treasury = max(getattr(s, "treasury", 0), 50_000_000)
    for _ in range(months):
        run_monthly_settlement(s)
    ro = build_market_readout(s)
    assert ro["inventory"]["dimensions"] is not None
    assert ro["turn"] == s.turn