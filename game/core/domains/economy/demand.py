# -*- coding: utf-8 -*-
"""B2-1/2/3 · 需求分层与价格敏感（**口径单点**，规格 `market-civilian-economy`）

对应用户定论（2026-10-01）：**民间消费 ＝ 阶层需求 × 财富余量，两者相乘非相加**。

```text
余量释放   = clamp((人均wealth − 温饱线(cls)) / 余量尺度, 0, 1)
品类需求   = 阶层偏好 × 余量释放 × 价格敏感
耐用品抑制 = 持有达目标库存则不再买（不该每月重复消费）
替代降级   = 首选品买不起 → 按接受度改买替代品
```

**数值全部在 `content.data_constants`**（`SUBSISTENCE_LINE` 等），
改数**不需要改本模块**——标定与实现在此分离。

## 三条纪律

- **纯函数优先**：本模块不写 `state`；需要写时由调用方（结算步）显式落账；
- **缺失 ≠ 0**：某品类未配置基本线 → `None`（不是 0 条需求）；
- **不臆造**：温饱线以上的余量、替代接受度都按配置读，**不猜测**玩家意图。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = [
    "demand_release", "basic_need", "durable_gap",
    "price_sensitivity", "resolve_purchase_plan",
]


def _num(v: Any, default: Optional[float] = None) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):
        return default
    return f


def _cfg(name: str, default: Any = None) -> Any:
    from content import data as _d
    val = getattr(_d, name, None)
    return default if val is None else val


def demand_release(cls: str, per_capita_wealth: Optional[float]) -> Optional[float]:
    """余量释放 = `clamp((人均wealth − 温饱线) / 余量尺度, 0, 1)`。

    - `per_capita_wealth` 不可读 → `None`（**不臆造 0**，调用方须显式处理）；
    - 温饱线**未给该阶层配置** → 返回 `1.0`（无门槛 = 现状口径，不擅自加门槛）；
    - 温饱线以下 → `0.0`（**不买**，不是"少买"）。
    """
    per = _num(per_capita_wealth)
    if per is None:
        return None
    line_map = _cfg("SUBSISTENCE_LINE", {}) or {}
    if cls not in line_map:
        return 1.0
    line = _num(line_map.get(cls))
    if line is None:
        return 1.0
    scale = _num(_cfg("SUBSISTENCE_SCALE", 30.0), 30.0) or 30.0
    return max(0.0, min(1.0, (per - line) / scale))


def basic_need(cls: str, dim: str, pop_size: int) -> Optional[float]:
    """基本需求（人均·月）；未配置 → `None`（**不是 0 条需求**）。"""
    basket = _cfg("BASIC_NEED_BASKET", {}) or {}
    if dim not in basket:
        return None
    per = _num(basket.get(dim))
    if per is None:
        return None
    return per * max(0, int(pop_size))


def durable_gap(dim: str, pop_size: int, held: Optional[float]) -> Optional[float]:
    """耐用品**缺口**＝目标库存 − 现持有（<=0 表示已够，不必再买）。"""
    target_map = _cfg("DURABLE_TARGET_STOCK", {}) or {}
    if dim not in target_map:
        return None
    tgt = _num(target_map.get(dim))
    if tgt is None:
        return None
    want = tgt * max(0, int(pop_size))
    have = _num(held, 0.0) or 0.0
    return max(0.0, want - have)


def price_sensitivity(base_price: Optional[float], price: Optional[float],
                      tolerate: Optional[float] = None) -> float:
    """价格敏感系数 ∈ (0,1]：涨价 → 购买意愿递减；跌价 → 不超过 1（**不放大购买**）。

    线性相对涨幅折算（0.5 容忍度时：涨 50% → 系数 0.5；持平 → 1.0）。
    """
    b = _num(base_price)
    p = _num(price)
    if b is None or p is None or b <= 0:
        return 1.0
    tol = _num(tolerate, 0.5)
    if tol is None or tol <= 0:
        tol = 0.5
    rise = (p - b) / b
    if rise <= 0:
        return 1.0
    return max(0.0, 1.0 - rise / tol)


def resolve_purchase_plan(*, cls: str, pop_size: int, per_capita_wealth: Optional[float],
                          pref: Dict[str, float], held: Optional[Dict[str, float]] = None,
                          prices: Optional[Dict[str, float]] = None,
                          base_prices: Optional[Dict[str, float]] = None,
                          budget: Optional[float] = None,
                          ) -> Dict[str, Any]:
    """综合出某阶层本月的**购买计划**（纯计算，不落账）。

    返回 `{release, items: [{dim, qty, reason, kind}], unmet: {dim: qty},
             basics_unmet: {dim: qty}, no_demand: bool, reason}`。

    `items[].kind ∈ {basic, durable}`：
    - `basic`：按收入比例的基本消费（受余量释放与价格敏感约束）；
    - `durable`：耐用品缺口（已达目标则不再买）。
    """
    rel = demand_release(cls, per_capita_wealth)
    out: Dict[str, Any] = {
        "cls": cls, "release": rel, "items": [], "unmet": {},
        "basics_unmet": {}, "no_demand": False, "reason": "ok",
    }
    if rel is None:
        out.update(no_demand=True, reason="per_capita_wealth_unreadable")
        return out
    if rel <= 0:
        # 温饱线以下：不买任何商品（但**基本需求未满足要记录**，不是"没需求"）
        for dim in (pref or {}):
            need = basic_need(cls, dim, pop_size)
            if need:
                out["basics_unmet"][dim] = need
        out.update(reason="below_subsistence")
        return out

    prices = prices or {}
    base_prices = base_prices or {}
    held = held or {}

    # ---- 耐用品：已达目标库存则不买 ----
    for dim, _share in (pref or {}).items():
        gap = durable_gap(dim, pop_size, held.get(dim))
        if gap is None or gap <= 0:
            continue
        out["items"].append({"dim": dim, "qty": gap, "kind": "durable",
                             "reason": "耐用品缺口"})

    # ---- 基本需求：按余量释放 × 价格敏感，达不到记 unmet ----
    for dim, _share in (pref or {}).items():
        need = basic_need(cls, dim, pop_size)
        if not need:
            continue
        sens = price_sensitivity(base_prices.get(dim), prices.get(dim))
        want = need * rel * sens
        if budget is not None:
            px = _num(prices.get(dim))
            if px and px > 0:
                want = min(want, max(0.0, _num(budget, 0.0)) / px)
        got = min(want, max(0.0, need))
        short = need - got
        if short > 0:
            out["basics_unmet"][dim] = short
        if got > 0:
            out["items"].append({"dim": dim, "qty": got, "kind": "basic",
                                 "reason": "基本需求"})

    if not out["items"]:
        out.update(no_demand=True, reason="no_target_demand")
    return out


def substitute_for(dim: str) -> Optional[str]:
    """首选品买不起时的**替代品**（按接受度最高的候选）。"""
    tol = _cfg("SUBSTITUTE_TOLERANCE", {}) or {}
    cands = tol.get(dim) or {}
    if not isinstance(cands, dict) or not cands:
        return None
    best = None
    best_v = 0.0
    for sub, v in cands.items():
        f = _num(v, 0.0) or 0.0
        if f > best_v:
            best_v, best = f, sub
    return best if best_v > 0 else None