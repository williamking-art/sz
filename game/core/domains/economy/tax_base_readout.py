# -*- coding: utf-8 -*-
"""应税产值分解（P-D 首批）—— **只读读数，不改税制**。

## 这个模块不解的问题

现行税制**没有按货/按类的税目**：工商税＝`Σ(工匠.size + 商人.size) × CRAFT_OUTPUT_PER_CAPITA × 税率`
（`core/settlement_finance.py:1397-1402`），盐课按销量、二税按田亩。全库无 `TAX_BY*`。
所以《物产新篇》那套「税种声明所征类目 → 货单自动推出」**在本项目没有可挂的地方**。

真按品目分征 = 改税基与 M0/M1 对账（与 `commerce_tax` 替代还是叠加？税基是产量×价还是成交额？谁纳？）
⇒ 另立待裁定 D8。**本模块只做第一层：把「按品目聚合的应税产值」算出来给人看**，
不写 `tax_breakdown`、不改 `monthly_tax`、不动任何账户。

## 口径（三条，缺一不可）

1. **产量**：取产地单元实测产出 `prefecture_entity.all_seats()[i]["demog"]["yields"][dim]`。
   - **只取正值**：`yields` 负值表示该产地单元**消耗/亏损**（如京畿盐为负），当产出会造出负产值
     （与 `material_holding.seat_yield_weights_of_circuit` 同口径）。
   - 🔴 **实测只有 9 个维有 yields**（茶/丝/麻/蔗/果/木/石/铁/盐）；其余 53 维（含全部成品维）
     **没有静态年产量源**（成品由作坊按月产出，无年度锚）。这些维一律进 `no_yield_dims`，
     **不记 0、不猜产量** —— 「没有年产量数据」与「年产 0」是两件事。
2. **单价**：`market_price._base_price(dim, state)` —— 全 mod 的成本/税基锚，且对已登记新材
   仍过 material_tech 解锁闸门（未解锁 → `None`）。`金`/`银`/`麦` 本来就没有基准价
   （金走比价、银走白银本位），故即使有产量也记 `undefined_dims`。
   🔴 **单位**：`MATERIAL_PRICE_BASE` 是「**钱（文）**/单位」，而国库/税课是「贯」
   ⇒ 本模块统一 `文 ÷ 1000 = 贯`（`WEN_PER_GUAN`），对外只给贯；同时保留 `value_wen` 可追溯。
3. **聚合**：按 `goods_category` 的**品目**汇总；未登记品目的维（运行时新维）进
   `uncategorized_dims`，同样不记 0。

## 只读

只调 `all_seats()`（静态缓存）与 `_base_price()`（只读）。**不写 state 任何字段**；
用例锁「跑完后 `prefectures`/`resources`/`treasury`/`tax_breakdown`/`statistics` 逐字不变」。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

__all__ = ["SCHEMA_VERSION", "survey_tax_base", "readout_tax_base"]

SCHEMA_VERSION = 1

#: 1 贯 = 1000 文。**本模块内唯一换算点**，勿在别处复制。
#: 依据：`content/data_constants.py:805` 自陈「每应役丁年纳 ≈0.327 贯（327 文）」；
#: 且 `MATERIAL_PRICE_BASE` 的注释是「**钱**/单位」（`data_constants.py:461`）＝文，
#: 而国库/税课口径是「贯」（`WON_PER_GUAN=10_000` 是万贯→贯，**不是**文→贯）。
#: 🔴 不换算就标「贯」＝读数撒谎 1000 倍（首版实测合计 7.6e10 被当成贯，实为文）。
WEN_PER_GUAN = 1000.0


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _yield_by_dim() -> Dict[str, float]:
    """全境各维年产出（**只累正值**）；读不到一律空（不臆造）。"""
    from core.foundation.ledger.prefecture_entity import all_seats

    out: Dict[str, float] = {}
    try:
        seats = all_seats()
    except Exception:                                            # noqa: BLE001
        log.warning("tax_base_readout: 产地实体不可读", exc_info=True)
        return out
    for s in seats or ():
        demog = (s or {}).get("demog") or {}
        yields = demog.get("yields")
        if not isinstance(yields, dict):
            continue
        for dim, raw in yields.items():
            v = _num(raw)
            if v is None or v <= 0:                              # 负产 = 消耗，不作产出
                continue
            key = str(dim)
            out[key] = out.get(key, 0.0) + v
    return out


def survey_tax_base(state: Any = None) -> Dict[str, Any]:
    """按品目聚合「产量 × 基准价」的应税产值（纯读）。

    返回：
      `by_category`   `{品目: {"value": float|None, "dims": {维: {yield, price, value, reason}}}}`
      `total_value`   可定价维之和（`None` 表示一项都不可定价）
      `dims_with_yield` / `dims_priced`  计数
      `undefined_dims`  有产量但无基准价（金/银/麦等）
      `no_yield_dims`   无静态年产量源（**成品维等；不是 0 产**）
      `uncategorized_dims`  未登记品目的维
      `readonly`       恒 `True`（本函数不写 state）
    """
    from content.data_constants import GOODS_DIMS
    from content.goods_category import CATEGORY_ORDER, category_of
    from core.market_price import _base_price

    yields = _yield_by_dim()
    all_dims = [str(d) for d in GOODS_DIMS]

    by_category: Dict[str, Dict[str, Any]] = {
        c: {"value": None, "dims": {}} for c in CATEGORY_ORDER
    }
    total = 0.0
    priced = 0
    undefined_dims: List[str] = []
    uncategorized: List[str] = []

    for dim in all_dims:
        y = yields.get(dim)
        if y is None or y <= 0:
            continue                                             # 无年产量源 → 后面统一列 no_yield_dims
        cat = category_of(dim)
        if cat is None:
            uncategorized.append(dim)
            continue
        try:
            price = _base_price(dim, state)
        except Exception:                                        # noqa: BLE001 — 定价失败不拖垮读数
            log.warning("tax_base_readout: 基准价不可读 dim=%s", dim, exc_info=True)
            price = None
        if price is None or price <= 0:
            undefined_dims.append(dim)
            by_category[cat]["dims"][dim] = {
                "yield": round(y, 4), "price": None, "value": None,
                "reason": "无基准价（金/银为货币口径；麦无锚）——缺失≠0",
            }
            continue
        value_wen = y * float(price)
        value_guan = value_wen / WEN_PER_GUAN
        priced += 1
        total += value_guan
        rec = by_category[cat]["dims"][dim] = {
            "yield": round(y, 4), "price": round(float(price), 4),
            "value": round(value_guan, 2),
            "value_wen": round(value_wen, 2),
            "reason": None,
        }
        agg = by_category[cat]["value"]
        by_category[cat]["value"] = round((agg or 0.0) + rec["value"], 2)

    no_yield = [d for d in all_dims if d not in yields]

    return {
        "schema_version": SCHEMA_VERSION,
        "by_category": by_category,
        "total_value": round(total, 2) if priced else None,
        "total_wen": round(total * WEN_PER_GUAN, 2) if priced else None,
        "dims_with_yield": len([d for d in all_dims if d in yields and (yields.get(d) or 0) > 0]),
        "dims_priced": priced,
        "undefined_dims": undefined_dims,
        "no_yield_dims": no_yield,
        "uncategorized_dims": uncategorized,
        "readonly": True,
        "reason": None if priced else "无可定价维（基准价或产量数据缺失）",
    }


def readout_tax_base(state: Any = None) -> Tuple[Optional[float], Optional[str], Dict[str, Any]]:
    """`readout_hub` 适配：返回 `(应税产值合计|None, reason|None, drill_down)`。

    口径：合计只含**有年产量且可定价**的维；`undefined_dims` / `no_yield_dims` 如实列在 drill 里，
    **不当 0**。单位：**贯**（`MATERIAL_PRICE_BASE` 为文，已按 `WEN_PER_GUAN` 折算）。
    """
    src = "core.domains.economy.tax_base_readout:survey_tax_base"
    try:
        rep = survey_tax_base(state)
    except Exception as e:                                       # noqa: BLE001
        log.warning("tax_base_readout: 应税产值分解失败", exc_info=True)
        return None, f"应税产值分解异常：{type(e).__name__}", {"drill": src}

    drill = {
        "drill": src,
        "可定价维数": rep["dims_priced"],
        "有年产量维数": rep["dims_with_yield"],
        "无年产量源的维数": len(rep["no_yield_dims"]),
        "有产量但无价（缺失≠0）": list(rep["undefined_dims"]),
        "无年产量源（非 0 产）": list(rep["no_yield_dims"])[:12],
        "未登记品目的维": list(rep["uncategorized_dims"]),
        "按品目": {c: v["value"] for c, v in rep["by_category"].items() if v["value"] is not None},
    }
    if rep["total_value"] is None:
        return None, rep["reason"] or "无可定价维", drill
    return float(rep["total_value"]), None, drill
