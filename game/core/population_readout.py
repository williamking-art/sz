# -*- coding: utf-8 -*-
"""B2-R1 · 人口与粮食归因读数（**纯派生、只读**，规格 `market-civilian-economy` B2-R1）

## 为什么有这个模块

`tasks.md` §4 B2-R1 指控（**已实测核实**）：

1. `statistics["grain_hungry"]` 在 `settlement_granary.py:528` 是
   `get(...) + _famine_total`——**逐月累加**。同一个人在缺粮期每月被计一次，
   所以它是**饥饿人月（person-month）**，**不是**"某月有多少人挨饿"。
   原基线报告把它当"持续攀升的饥饿人口"，是**口径误读**。
2. 农缺粮走 `settlement_granary.py:523-527`：
   `pop["size"] -= _flee` 且 `p["refugees"] += _flee`（1:1 派生，用户 2026-10-01 定稿）。
   ⇒ **逃荒是"农 → 流民池"的转移，不是凭空消灭**；而 `ΣPOP` 口径**不含流民**，
   所以只看 ΣPOP 会误判为"人口崩落"。

## 本模块提供

按回合/路/POP 拆分**可重建**的四类去向，使人口恒等式可核对：
`ΣPOP(t) + Σ流民(t)` 与 `ΣPOP(0) + Σ流民(0) + Σ死亡/其他去向` 的差额可归因。

**纪律**：不写 `state`、不改 `statistics`；缺失给 `None`／如实标注，**不回落 0**
（流民池字段缺失 ≠ 没有流民）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from core.foundation.common.numeric import finite_number as _num

__all__ = [
    "POP_CLASSES", "POPAGE_SCHEMA_VERSION",
    "population_ledger", "hunger_person_months", "famine_attribution",
]

#: 6 类 POP（POP 挂载律：人只落这 6 类的 `size`）
POP_CLASSES = ("农", "士绅", "工匠", "商人", "官僚", "兵")

#: 读数结构版本
POPAGE_SCHEMA_VERSION = 1


def population_ledger(state, *, include_routes: bool = True) -> Dict[str, Any]:
    """人口台账：按阶层/路拆分 ΣPOP 与流民池，并给出**转移口径**对照。

    返回 `{schema_version, by_class:{cls:size}, total_pop, total_refugees,
           pop_plus_refugees, by_route:[{route, size, refugees}],
           missing_refugee_field:[route], note}`。
    `missing_refugee_field` 列出**没有 `refugees` 键**的路——按"缺失≠0"如实标注，
    不当作"该路无流民"。
    """
    by_class = {c: 0 for c in POP_CLASSES}
    by_route: List[Dict[str, Any]] = []
    missing_ref = []
    total_ref = 0
    for route, pref in (getattr(state, "prefectures", None) or {}).items():
        if not isinstance(pref, dict):
            continue
        pops = pref.get("pops")
        if not isinstance(pops, dict):
            continue
        r_size = 0
        for cls in POP_CLASSES:
            pop = pops.get(cls)
            if not isinstance(pop, dict):
                continue
            n = int(_num(pop.get("size"), 0) or 0)
            by_class[cls] += n
            r_size += n
        if "refugees" in pref:
            rf = int(_num(pref.get("refugees"), 0) or 0)
            total_ref += rf
        else:
            rf = None
            missing_ref.append(route)
        if include_routes:
            by_route.append({"route": route, "size": r_size, "refugees": rf})

    total_pop = sum(by_class.values())
    return {
        "schema_version": POPAGE_SCHEMA_VERSION,
        "by_class": by_class,
        "total_pop": total_pop,
        "total_refugees": total_ref,
        "pop_plus_refugees": total_pop + total_ref,
        "by_route": by_route,
        "missing_refugee_field": missing_ref,
        "note": ("逃荒为『农 → 流民池』转移（settlement_granary.py:523-527，1:1）；"
                 "ΣPOP 口径不含流民，比较人口规模须用 pop_plus_refugees。"),
    }


def hunger_person_months(state) -> Dict[str, Any]:
    """`statistics["grain_hungry"]` 的**正确口径**：饥饿**人月**，非当月人数。

    返回 `{person_months, unit:"person-month", is_cumulative:True,
           not_a_headcount:True, note}`。
    若该键缺失 → `person_months=None`（**不作 0**：未记录≠无人饥饿）。
    """
    stats = getattr(state, "statistics", None)
    if not isinstance(stats, dict) or "grain_hungry" not in stats:
        return {"person_months": None, "unit": "person-month", "is_cumulative": True,
                "not_a_headcount": True, "note": "statistics 缺 grain_hungry 键（未记录）"}
    v = _num(stats.get("grain_hungry"))
    return {
        "person_months": None if v is None else int(v),
        "unit": "person-month",
        "is_cumulative": True,
        "not_a_headcount": True,
        "note": ("逐月累加（settlement_granary.py:528 `get(...) + _famine_total`）；"
                 "同一人缺粮多月会被重复计入，**不可**当作某月受灾人口数。"),
    }


def famine_attribution(state) -> Dict[str, Any]:
    """饥荒触发因素归因（`settlement_common.food_insecure_headcount` 的口径）。

    区分**四因**（B2-R3 要求"饥饿因粮/钱/运/库存可诊断"）：
    `own_grain_short`（自有粮不足）／`purchasing_power_short`（有钱但买不起粮）／
    `stock_short`（本路无粮可买）／`transport`（断运：本路无存粮且无常平仓可调）。
    判据优先级：**断运/无粮 → 没钱 → 自有粮不足**，便于定位可修复环节。
    本函数只做**当月**判定，不累加。

    返回 `{by_class:{cls:{own_grain, need, shortfall_headcount, reason}},
           total_shortfall, note}`。缺粮人数缺 `food_insecure_headcount` 时给 `None`。
    """
    out = {
        "schema_version": POPAGE_SCHEMA_VERSION,
        "by_class": {},
        "by_reason": {},
        "total_shortfall": 0,
        "note": ("当月判定（非累加）；`own_grain_short` 与 `purchasing_power_short` "
                 "按 `food_insecure_headcount` 单点口径，二者不可混记。"),
        "per_route_capped": True,
        "capped_note": ("⚠️ `food_insecure_headcount` 受 `FLEE_CAP_PER_ROUTE`（每路逃荒封顶）"
                        "约束，结算内亦按路分别调用；故 `total_shortfall` 是**逐路封顶后**"
                        "的求和，**不等于**全国真实缺粮人数，**不可**与 `grain_hungry`"
                        "（未封顶的累加人月）比大小。"),
    }
    stats = getattr(state, "statistics", None)
    price = _num(getattr(state, "grain_price", None))
    if price is None or price <= 0:
        out["note"] += " grain_price 不可读 → 无法判定购买力维度。"
        return out
    try:
        from core.settlement_common import food_insecure_headcount
    except Exception:                                    # noqa: BLE001
        out["note"] += " `food_insecure_headcount` 不可用。"
        return out
    for route, pref in (getattr(state, "prefectures", None) or {}).items():
        if not isinstance(pref, dict):
            continue
        pops = pref.get("pops")
        if not isinstance(pops, dict):
            continue
        # B2-R3 四因诊断：
        #   ① own_grain_short        自有粮不足
        #   ② purchasing_power_short 有粮但没钱买
        #   ③ stock_short            太仓与本路**皆无粮可调**（确实无货）
        #   ④ transport              断运（太仓有粮但 `canal_block` 阻断，运不进来）
        # 判据优先级：断运 / 无货 → 没钱 → 自有粮不足（从"外部约束"到"内部约束"），
        # 便于定位**可修复的环节**（运力/库存 vs 收入）。
        _cp = int(_num(pref.get("changping_stock"), 0) or 0)
        _local = int(_num(pref.get("grain"), 0) or 0)
        # 运力判据用**真字段** `state.canal_block`（漕运阻断百分比，0~100）：
        # 阻断越高运力越低。`changping_stock` 是**存量**不是运力，二者不可混用。
        _block = _num(getattr(state, "canal_block", None))
        _transport_ok = (_block is None) or (_block < 100)
        _granary_total = int(_num(getattr(state, "granary", 0), 0) or 0)
        try:
            hungry_map = food_insecure_headcount(pops, price)
        except Exception:                                # noqa: BLE001
            out["note"] += " food_insecure_headcount 执行失败（按不可判定处理）。"
            return out
        for cls in POP_CLASSES:
            pop = pops.get(cls)
            if not isinstance(pop, dict):
                continue
            hungry = int(_num(hungry_map.get(cls), 0) or 0)
            own = int(_num(pop.get("grain"), 0) or 0)
            if hungry <= 0:
                continue
            # 判据优先级（从外部约束到内部约束）：
            #  ① transport   —— 太仓有粮可调拨，但本路**运力/常平仓不可用**
            #                   （断运：不是没粮，是粮进不来）
            #  ② stock_short —— 太仓与本路**都无粮可调**（确实无货）
            #  ③ purchasing_power_short —— 有粮可买但买不起
            #  ④ own_grain_short —— 自有粮不足
            if _cp <= 0 and not _transport_ok and _granary_total > 0:
                reason = "transport"          # 断运：太仓有粮但本路调不进
            elif _cp <= 0 and _local <= 0 and _granary_total <= 0:
                reason = "stock_short"        # 太仓与本路皆空：确实无货
            elif own <= 0:
                reason = "purchasing_power_short"   # 有粮可买但买不起
            else:
                reason = "own_grain_short"
            slot = out["by_class"].setdefault(
                cls, {"own_grain": 0, "shortfall_headcount": 0, "reason": reason})
            slot["own_grain"] += own
            slot["shortfall_headcount"] += hungry
            slot["reason"] = reason
            out["by_reason"][reason] = out["by_reason"].get(reason, 0) + hungry
            out["total_shortfall"] += hungry
    del stats
    return out