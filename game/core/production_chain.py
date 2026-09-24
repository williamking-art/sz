# -*- coding: utf-8 -*-
"""宋祚 · 宋侧产出链（批 4 · 外邦省域产业链设计 §11 S1/S2）。

**S1 原料产出链**：按路 `yields`（年额）÷ 12 × 建筑等级乘数 → 全局 `state.resources`
（单一真账，消费侧零改动）。消除「原料只出不进」缺口（设计 §0.3）。

**S2 商品单通道**：`_settle_granary` 的 POP 直产段（工匠 size→布/绸）并入本模块的
作坊 PM 口径——**成品唯一产出通道是作坊**；直产删除后带**不断供护栏**（供给不足
立即回退到旧直产，保证成交率 ≥ 改造前 90%）。

纪律：
- 产量是唯一增量；只写 `state.resources[dim]["stock"]`，不碰钱/POP wealth；
- 旧档缺 yields 键 → `setdefault` 幂等跳过，不抛异常；
- `test_pop_identity._STEPS` 镜像须同步新步（调用侧在 settlement.py 接线时登记）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

__all__ = ["settle_production_chain", "PRODUCTION_BUILDING_MULT"]

# 建筑等级 → 产出乘数（与外邦 LV_OUTPUT_BONUS 同口径：1 + 0.05×(lv−1)）
PRODUCTION_BUILDING_MULT = 0.05
_BUILDING_LV_MAX = 5


def _building_mult(p: dict) -> float:
    """该路建筑等级综合乘数（取 POP 建筑最高等级；无建筑 → 1.0）。"""
    best_lv = 1
    for entry in (p.get("buildings") or {}).values():
        lv = 1
        if isinstance(entry, dict):
            try:
                lv = int(entry.get("lv", 1) or 1)
            except (TypeError, ValueError):
                lv = 1
        else:
            try:
                lv = int(entry or 1)
            except (TypeError, ValueError):
                lv = 1
        best_lv = max(best_lv, min(_BUILDING_LV_MAX, lv))
    return 1.0 + PRODUCTION_BUILDING_MULT * max(0, best_lv - 1)


def settle_production_chain(state, log: Optional[list] = None) -> Dict[str, int]:
    """S1 原料产出链：各路 `yields` 年额 ÷ 12 × 建筑乘数 → `state.resources`。

    返回 `{dim: 本月产量}`（诊断用）；产量封顶后溢出截断（不超 cap）。
    """
    logs = log if isinstance(log, list) else []
    produced: Dict[str, int] = {}
    resources = getattr(state, "resources", None)
    if not isinstance(resources, dict):
        return produced
    from content.data import RAW_DIMS
    for name, p in (getattr(state, "prefectures", None) or {}).items():
        if not isinstance(p, dict):
            continue
        yields = p.get("yields") or {}
        if not isinstance(yields, dict):
            continue
        mult = _building_mult(p)
        for dim in RAW_DIMS:
            annual = yields.get(dim)
            if annual is None:
                continue
            try:
                annual = float(annual)
            except (TypeError, ValueError):
                continue
            if annual <= 0:
                continue
            q = int(annual / 12.0 * mult)
            if q <= 0:
                continue
            slot = resources.setdefault(dim, {"stock": 0, "cap": 50_000})
            cap = int(slot.get("cap", 50_000) or 50_000)
            stock = int(slot.get("stock", 0) or 0)
            add = min(q, max(0, cap - stock))
            if add > 0:
                slot["stock"] = stock + add
                produced[dim] = produced.get(dim, 0) + add
    if produced:
        top = sorted(produced.items(), key=lambda kv: -kv[1])[:4]
        logs.append("[产出链] 诸路原料入仓：" + "、".join(f"{d}+{q}" for d, q in top))
    return produced


def goods_direct_production_backup(artisan: dict, merchant: dict,
                                   prod_mult: float = 1.0) -> Dict[str, int]:
    """S2 不断供护栏：旧直产口径（工匠 size→布/绸 + 商人贩运）备用。

    仅在作坊单通道供给不足时调用，保证商品成交率 ≥ 改造前 90%。
    返回 `{gdim: 本月补产}`。
    """
    added: Dict[str, int] = {}
    if isinstance(artisan, dict):
        for gdim in list(artisan.get("goods", {}) or {}):
            _add = int(artisan.get("size", 0) * (0.10 if gdim == "绸" else 0.20) * prod_mult)
            if _add > 0:
                artisan.setdefault("goods", {})[gdim] = (
                    int(artisan["goods"].get(gdim, 0) or 0) + _add)
                added[gdim] = added.get(gdim, 0) + _add
    if isinstance(merchant, dict):
        for gdim in list(merchant.get("goods", {}) or {}):
            _add = int(merchant.get("size", 0) * 0.10 * prod_mult)
            if _add > 0:
                merchant.setdefault("goods", {})[gdim] = (
                    int(merchant["goods"].get(gdim, 0) or 0) + _add)
                added[gdim] = added.get(gdim, 0) + _add
    return added
