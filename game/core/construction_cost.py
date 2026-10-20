# -*- coding: utf-8 -*-
"""B4 · 营造造价、工期与赶工预算（**口径单点**，规格 `market-civilian-economy` B4）

对应用户定论（2026-10-01）：
1. **造价挂材料**——`基准造价 = Σ(材料量 × 单价)`，单一真源，
   消除 `cost_coin` 与 `cost_material` 两套分离声明；
2. **加大投入缩短工期**——`工期倍率 = k^α`（凹函数 α≈0.5），总额封顶＝基准造价；
3. **赶工预算独立**——溢价不占基准预算，**未用余额退回出资方**。

本模块为**纯函数**，不写 `state`；结算侧（`settlement_tech._settle_projects`）
按本模块口径改读月度应付，**不再**自行按 `cost_coin × 供给率` 重复计全额。

## 边界

- **单件价格取 `effective_buy_price`**（官定>动态>基准），保证与 B2-5 价格口径一致；
- **凹函数加速**：投入 ×2 → 工期 ÷1.4（α=0.5），边际提速递减；
- **总额封顶**：任何加速下累计付款 ≤ 基准造价；
- **赶工退款**：未用完的赶工预算**必须**能算出应退额（不静默消失）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional
from core.foundation.common.numeric import finite_number as _num

__all__ = [
    "ACCEL_ALPHA", "base_material_cost", "accel_speed_mult",
    "monthly_due", "rush_budget_spent", "rush_refund",
    "plan_construction_cost",
]

#: 加速指数（凹函数）；0.5 ⇒ 投入 ×2 → 工期 ÷1.41
ACCEL_ALPHA = 0.5


def _unit_price(dim: str, state=None) -> Optional[float]:
    from core.market_price import effective_buy_price
    r = effective_buy_price(dim=dim, state=state)
    return _num(r.get("price"))


def base_material_cost(*, materials: Dict[str, float], state=None) -> Dict[str, Any]:
    """**基准造价 = Σ(材料量 × 单价)**（B4-3 单一真源）。

    返回 `{total, lines:[{dim, qty, price, cost}], missing_price:[dim],
             unresolved:bool}`。
    - 单价不可读（该维度无基准价）→ 列入 `missing_price` �� `unresolved=True`，
      **不按 0 计价**（缺失≠0，那会低估造价）。
    """
    total = 0.0
    lines = []
    missing = []
    for dim, qty in (materials or {}).items():
        q = _num(qty, 0.0) or 0.0
        if q <= 0:
            continue
        px = _unit_price(dim, state=state)
        if px is None or px <= 0:
            missing.append(dim)
            continue
        cost = q * px
        total += cost
        lines.append({"dim": dim, "qty": q, "price": px, "cost": round(cost, 4)})
    return {"total": round(total, 4), "lines": lines, "missing_price": missing,
            "unresolved": bool(missing)}


def accel_speed_mult(intensity: Optional[float]) -> float:
    """投入强度 → 工期倍率：`k^α`（凹函数）。

    - `intensity` 不可读或 ≤0 → `1.0`（不加速，不臆造）；
    - 单调递增且边际递减（α=0.5）。
    """
    k = _num(intensity, 1.0)
    if k is None or k <= 0:
        return 1.0
    return max(0.1, min(3.0, math.pow(k, ACCEL_ALPHA)))


def monthly_due(*, base_total: float, months: int,
                intensity: Optional[float] = None) -> float:
    """本月应付工程款 = `(基准造价/基准工期) × 投入强度 × 工期倍率`，
    且**累计不超过基准造价**（`paid_so_far` 由调用方核）。

    `months` 为基准工期；`intensity` 缺省 1.0。
    """
    base_total_f = _num(base_total, 0.0) or 0.0
    m = max(1, int(months))
    k = _num(intensity, 1.0) or 1.0
    mult = accel_speed_mult(k)
    # 加速时不按比例多付总额——总额封顶；此处只调"何时付完"（提前付，不超付）
    per_month_base = base_total_f / m
    return round(min(base_total_f, per_month_base * k * mult), 4)


def rush_budget_spent(*, base_total: float, intensity: float) -> float:
    """赶工溢价＝`基准造价 × (工期倍率 − 1) × 溢价系数`（B4-5，独立于基准预算）。

    溢价不占基准预算；未用部分由 `rush_refund` 退还。
    """
    base = _num(base_total, 0.0) or 0.0
    mult = accel_speed_mult(intensity)
    if mult <= 1.0:
        return 0.0
    # 溢价系数：取 0.5（凹函数已含边际递减，溢价不过陡）
    return round(base * (mult - 1.0) * 0.5, 4)


def rush_refund(*, rush_granted: float, rush_used: float) -> float:
    """赶工预算未用余额应退额 ＝ `granted − used`（下限 0，不静默消失）。"""
    g = _num(rush_granted, 0.0) or 0.0
    u = _num(rush_used, 0.0) or 0.0
    return round(max(0.0, g - u), 4)


def plan_construction_cost(*, materials: Dict[str, float], months: int,
                           intensity: float = 1.0, state=None) -> Dict[str, Any]:
    """规划一次营造：基准造价 ＋ 基准工期 ＋ 加速后工期 ＋ 赶工溢价。

    返回 `{base_total, months, base_monthly, speed_mult, effective_months,
             rush_premium, total_commitment, missing_price, unresolved}`。
    """
    base = base_material_cost(materials=materials, state=state)
    total = base["total"]
    m = max(1, int(months))
    mult = accel_speed_mult(intensity)
    eff_months = max(1, int(math.ceil(m / mult))) if mult > 0 else m
    rush = rush_budget_spent(base_total=total, intensity=intensity)
    return {
        "base_total": total,
        "months": m,
        "base_monthly": round(total / m, 4),
        "speed_mult": round(mult, 4),
        "effective_months": eff_months,
        "rush_premium": rush,
        "total_commitment": round(total + rush, 4),
        "missing_price": base["missing_price"],
        "unresolved": base["unresolved"],
    }