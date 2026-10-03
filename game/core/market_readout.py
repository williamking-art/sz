# -*- coding: utf-8 -*-
"""B0 · 民间经济读数（**纯派生、只读**，不改任何模拟行为）

对应规格 `specs/market-civilian-economy` 的 **B0-2 / B0-3 / B0-4**。
B0 阶段的契约是"**先看见，不改模型**"——本模块只做观测与诊断，不写 `state`、不参与结算。

## 为什么需要它（实测背景）

台账见同目录 `b0-inventory-ledger.md`：

1. 库存有**四个载体**（`state.resources` 仓储／`pop["goods"]` 持有／
   `state.granary` 太仓／在途未实现），语义各异，**不可合并成一个字典**；
2. 宋境 POP 购买走 `settlement_granary.py:280-285`——**扣钱后凭空给货**，
   与 `_settle_econ` 的真扣货路径（外邦）语义不同；
3. 因此"到底有没有成交、谁卖给了谁、库存怎么变的"**当前无任何读数**，
   `statistics` 里也无商品类键（只有 `export_income` 一个外销口径）。

## 三条纪律

- **纯只读**：不写 `state`、不改 `statistics`、不抛异常阻断结算；
- **缺失不作 0**：读不到的字段给 `None` 并在 `warnings` 说明，
  **不用 0 冒充"没有交易"**（AGENTS.md §3.3）；
- **有界**：明细最多 `max_items` 项，汇总另有 `totals`——面板不会被拖垮。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = [
    "MARKET_READOUT_SCHEMA_VERSION",
    "build_market_readout",
    "inventory_ledger",
    "demand_diagnosis",
    "flow_classification",
]

# B2-R1/R3 人口与饥荒读数（延迟导入避免循环依赖；模块无副作用，仅纯派生函数）
from core.population_readout import (  # noqa: E402
    famine_attribution, hunger_person_months, population_ledger,
)

#: 读数结构版本（供存档/面板判断读数是否同构）
MARKET_READOUT_SCHEMA_VERSION = 1

#: 六类 POP（权威键序见 `content.data.GRAIN_CONSUME_PER_CAPITA`；勿在此另立一份）
_POP_CLASSES = ("农", "士绅", "工匠", "商人", "官僚", "兵")

#: 仓储资源维度的缺省上限；仅用于"未配置 cap"时标注，不臆造容量
_NO_CAP = None


def _num(v: Any) -> Optional[float]:
    """安全取数：非数值/缺失 → `None`（**不回落 0**，缺失≠0）。"""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):   # NaN / inf
        return None
    return f


def _int(v: Any) -> Optional[int]:
    f = _num(v)
    return None if f is None else int(round(f))


# ====================================================== B0-2 · 库存台账读数
def inventory_ledger(state, *, max_items: int = 60) -> Dict[str, Any]:
    """逐载体/地点/持有人/商品列出当前库存，并给出恒等式可重建所需的口径。

    返回：
      `{"schema_version", "warehouses", "pop_holdings", "granary",
        "in_transit", "dimensions", "warnings"}`

    **只报当前值**：期初/生产/输入等流量项由 `flow_classification` 从
    `statistics`/日志取；本函数负责"此刻各持有人手上有什么"。
    """
    warnings: List[str] = []

    # ---- ① 全国/官仓仓储：state.resources[dim]["stock"/"cap"]
    warehouses: List[Dict[str, Any]] = []
    resources = getattr(state, "resources", None)
    if not isinstance(resources, dict):
        warnings.append("state.resources 缺失或非 dict：仓储库存不可读")
    else:
        for dim, slot in resources.items():
            if not isinstance(slot, dict):
                warnings.append(f"resources[{dim}] 非 dict，跳过")
                continue
            stock = _int(slot.get("stock"))
            cap = _int(slot.get("cap"))
            warehouses.append({
                "holder_type": "warehouse",      # 官仓/仓储（非民间可售）
                "holder_id": "state.resources",
                "route": None,                   # 全国口径，无单一所在路
                "dim": dim,
                "purpose": "storage",            # 仓储；预留/官用待 B1 细分
                "stock": stock,
                "cap": cap,
                "fill_ratio": (None if (cap in (None, 0) or stock is None)
                               else round(stock / cap, 4)),
            })
    warehouses.sort(key=lambda r: (-(r["stock"] or 0), str(r["dim"])))

    # ---- ② POP 手持商品：pop[阶层]["goods"][dim]
    # ⚠️ 工匠条目**兼作生产池/待售货**（台账 §1-②）；`role` 字段显式标注，不静默合并。
    pop_holdings: List[Dict[str, Any]] = []
    prefectures = getattr(state, "prefectures", None)
    if not isinstance(prefectures, dict):
        warnings.append("state.prefectures 缺失：POP 持货不可读")
    else:
        for route, pref in prefectures.items():
            pops = pref.get("pops") if isinstance(pref, dict) else None
            if not isinstance(pops, dict):
                continue
            for cls in _POP_CLASSES:
                pop = pops.get(cls)
                goods = pop.get("goods") if isinstance(pop, dict) else None
                if not isinstance(goods, dict):
                    continue
                # 2026-10-03：只遍历**商品维**（`goods` 另含 `治所→{dim:n}` 州府桶，
                # 桶是 dict，不应出现在逐维持仓清单里）。
                from core.material_holding import commodity_dims
                for dim in commodity_dims(goods):
                    q = _int(goods.get(dim))
                    if q is None:
                        warnings.append(f"{route}/{cls}.goods[{dim}] 非数值，未计入")
                        continue
                    pop_holdings.append({
                        "holder_type": "pop",
                        "holder_id": f"{route}/{cls}",
                        "route": route,
                        "cls": cls,
                        "dim": dim,
                        # 工匠既是生产者又是消费者，此处标出双重角色供 B1 拆分
                        "role": ("producer_pool" if cls == "工匠" else "consumer_holding"),
                        "qty": q,
                    })
    pop_holdings.sort(key=lambda r: (-(r["qty"] or 0), str(r["holder_id"]), str(r["dim"])))

    # ---- ③ 太仓（粮食专用，独立于 ①②）
    granary = {
        "holder_type": "granary",
        "holder_id": "state.granary",
        "dim": "grain",
        "stock": _int(getattr(state, "granary", None)),
        "stats": dict(getattr(state, "granary_stats", {}) or {}) or None,
    }

    # ---- ④ 在途（P0 · 2026-10-02 已实现）：建材跨州府运输批次
    # 此前固定返回 `implemented: False`（跨路贸易尚未建模）。
    # 现由 `core/transport` 提供真实读数；⚠️ 耗时按平地常数推算（**设定值、非史料**），
    #    路况修正表为空（无可靠史料，不臆造）——该说明随读数一并透出。
    try:
        from core.transport import transit_report
        in_transit = transit_report(state)
    except Exception as _tr_e:  # noqa: BLE001
        # 🔴 缺失≠0：读不出就如实说读不出，**不回落 implemented=False 冒充"没有在途"**
        in_transit = {"implemented": None, "items": None, "count": None,
                      "note": f"在途读数不可用：{_tr_e!r}"}

    # ---- 汇总（读视图，不重复持货）
    wh_total = sum(r["stock"] for r in warehouses if r["stock"] is not None)
    pop_total = sum(r["qty"] for r in pop_holdings if r["qty"] is not None)
    return {
        "schema_version": MARKET_READOUT_SCHEMA_VERSION,
        "warehouses": warehouses[:max_items],
        "pop_holdings": pop_holdings[:max_items],
        "granary": granary,
        "in_transit": in_transit,
        "dimensions": sorted({r["dim"] for r in warehouses} | {r["dim"] for r in pop_holdings}),
        "totals": {
            "warehouse_stock": wh_total,
            "pop_goods_qty": pop_total,
            "note": "汇总为读视图；仓储与 POP 持货是**不同载体**，不可相加当总量",
        },
        "truncated": {"warehouses": max(0, len(warehouses) - max_items),
                      "pop_holdings": max(0, len(pop_holdings) - max_items)},
        "warnings": warnings,
    }


# ====================================================== B0-3 · 需求诊断四分解
def demand_diagnosis(state) -> Dict[str, Any]:
    """把"想买没买到"拆成**四类互斥原因**；并把**零有效需求**单列。

    口径（tasks B0-3）：**先形成有效需求**，只对未满足部分归因。
    涨价造成的买不起归入**购买力不足**（它是成因/诊断标签），
    **不另计一类**，否则与"没钱"重复计数。

    判据（全部基于当前可读字段；不可读者进 `unknown`）：
      · 有效需求 == 0            → `no_demand`（**不是**未满足原因）
      · 卖方可售 == 0 且有需求   → `no_stock_local`
      · 在途 > 0 但本地可售 == 0 → `not_arrived`
      · 支付量 < 期望量          → `insufficient_purchasing_power`
      · 其余受限（配给/市场容量）→ `rationed_or_capacity`
    """
    warnings: List[str] = []
    stats = getattr(state, "statistics", None) or {}

    # 宋境商品成交当前**未按原因分类**记录（settlement_granary 只记总支出），
    # 故此处给出的是**可判定的部分 ＋ 明确的不可判定说明**，不臆造分类。
    spend = _num(stats.get("goods_spend"))            # 若后续 B1 补充该键即生效
    export_income = _num(stats.get("export_income"))
    resources = getattr(state, "resources", None) or {}
    any_stock = any((_int((s or {}).get("stock")) or 0) > 0
                    for s in resources.values() if isinstance(s, dict))

    buckets = {
        "no_demand": 0,                 # 有效需求为 0（单列，非未满足原因）
        "no_stock_local": 0,
        "not_arrived": 0,
        "insufficient_purchasing_power": 0,
        "rationed_or_capacity": 0,
        "unknown": 0,                   # 现有实现未记录原因 → 不可判定
    }
    if spend is None:
        warnings.append(
            "statistics 无 `goods_spend` 键：宋境商品支出未按原因分类，"
            "四分解目前**不可判定**（B1 成交改造时补齐记录键）")
        buckets["unknown"] = 1
    else:
        if spend <= 0:
            # 有效需求为 0 → "无需求"。这是**单列**的一类，
            # 不得计成任何未满足原因（否则"没人买"会被误读成"买不到"）。
            buckets["no_demand"] = 1
        elif not any_stock:
            # 有支出但仓储无货 → 高度指向"凭空给货"（须在 B1 修）
            buckets["no_stock_local"] = 1
            warnings.append(
                "仓储全空却发生商品支出：指向 `settlement_granary.py:280-285` "
                "的无卖方路径（须在 B1 修）")

    return {
        "schema_version": MARKET_READOUT_SCHEMA_VERSION,
        "buckets": buckets,
        "observed": {"goods_spend": spend, "export_income": export_income,
                     "warehouse_any_stock": any_stock},
        "unimplemented_reasons": [
            "运输未到（在途未实现，台账 §2.4）",
            "配给/市场容量限制（当前无此机制）",
        ],
        "warnings": warnings,
    }


# ====================================================== B0-4 · 流量分类读数
def flow_classification(state) -> Dict[str, Any]:
    """把本月的钱/物流量分成六类（B0-4），并显式区分**内部转移**与**外部注入/销毁**。

    分类（tasks B0-4）：货币转移／外部注入或销毁／商品交易／生产耗料／
    消费耗用／官府调拨／初始存量。
    """
    warnings: List[str] = []
    stats = getattr(state, "statistics", None) or {}

    # 可从 statistics 直接读到的（现有键）
    known = {k: _num(stats.get(k)) for k in (
        "export_income", "goods_spend", "project_runtime_yield",
        "project_runtime_grain", "minted", "coin_melted",
    )}

    # 内部转移 vs 外部注入：M_ALL 口径由 money.py 单点提供，此处**不重算**
    try:
        from core.money import m_all as _m_all
        money_total = _m_all(state)
    except Exception as exc:                      # noqa: BLE001 — 读数失败不阻断
        money_total = None
        warnings.append(f"M_ALL 不可读：{exc}")

    return {
        "schema_version": MARKET_READOUT_SCHEMA_VERSION,
        "classification": {
            "money_internal_transfer": {
                "note": "民间↔民间、官↔民间 内部划转：ΣM_ALL 不变",
                "observed_keys": ["export_income", "project_runtime_yield",
                                  "project_runtime_grain"],
            },
            "money_external_injection_or_burn": {
                "note": "铸币/熔铜等改变 M_ALL 的外部项",
                "observed_keys": ["minted", "coin_melted"],
            },
            "goods_trade": {"note": "商品成交", "observed_keys": ["goods_spend"]},
            "production_consumption": {"note": "生产耗料与成品",
                                       "observed_keys": []},
            "household_consumption": {"note": "消费耗用（含折旧）",
                                      "observed_keys": []},
            "government_allocation": {"note": "官府调拨/征发",
                                      "observed_keys": []},
            "initial_stock": {"note": "初始存量（不参与月度恒等式）",
                              "observed_keys": []},
        },
        "observed": known,
        "money_total": money_total,
        "unimplemented": ["production_consumption", "household_consumption",
                          "government_allocation", "initial_stock"],
        "warnings": warnings,
    }


# ====================================================== 组合入口
def build_market_readout(state, *, max_items: int = 60) -> Dict[str, Any]:
    """B0 总入口：库存台账 ＋ 需求诊断 ＋ 流量分类。

    **纯派生只读**；任一子读数失败不抛异常，改为在 `warnings` 留痕（缺失不作 0）。
    """
    out: Dict[str, Any] = {
        "schema_version": MARKET_READOUT_SCHEMA_VERSION,
        "year": _int(getattr(state, "year", None)),
        "month": _int(getattr(state, "month", None)),
        "turn": _int(getattr(state, "turn", None)),
    }
    warnings: List[str] = []
    for key, fn in (("inventory", inventory_ledger),
                    ("demand", demand_diagnosis),
                    ("flows", flow_classification),
                    # B2-R1/R3：人口台账与饥荒四因（纯派生只读，失败不阻断）
                    ("population", population_ledger),
                    ("famine", famine_attribution),
                    ("hunger", hunger_person_months)):
        try:
            out[key] = fn(state) if key == "inventory" else fn(state)
        except Exception as exc:                  # noqa: BLE001 — 读数不可阻断主流程
            out[key] = {"error": str(exc)}
            warnings.append(f"{key} 读数失败：{exc}")
    out["warnings"] = warnings
    return out