# -*- coding: utf-8 -*-
"""商人 POP 自主投资（P8，2026-10-18）。

三层：**档位**（天道 posture）→ **规则**（比例/门槛/成本，程序算）→ **执行**（守恒转移）。

🔴 纪律：
- 天道只给档位（进取/稳健/保守），**不给数值**；非法档位回落「稳健」；
- 钱**守恒转移**：商人 wealth → 同 seat 工匠 wealth（造船/造车工钱），不凭空增币；
- 资产落 `state.carriage["private"]`（既有载具账），不另开平行账本；
- 边际成本递增：船队越大，每艘船越贵（`INVEST_FLEET_COST_GROWTH^n`）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = ["merchant_posture", "posture_rules", "plan_investments", "apply_investment",
           "settle_merchant_investment"]


def merchant_posture(state) -> str:
    """读天道档位；缺失/非法 ⇒ 「稳健」（回落中性，不伪造进取）。"""
    from content.data_constants import MERCHANT_POSTURE_FALLBACK, MERCHANT_POSTURES

    # 🔴 只读**已接线**的 agent 槽位：merchant_decide 专用契约尚未接入（落地稿 §25 N-4），
    # 现在从 economy_decide（`_economy_ai`，始终唤醒）取 posture 字段；都没有 ⇒ 稳健。
    slot = getattr(state, "_economy_ai", None)
    posture = None
    if isinstance(slot, dict):
        posture = slot.get("posture") or (slot.get("merchant") or {}).get("posture")
    if posture in MERCHANT_POSTURES:
        return str(posture)
    return str(MERCHANT_POSTURE_FALLBACK)


def posture_rules(posture: Optional[str]) -> Dict[str, float]:
    """档位 → 投资规则；非法 ⇒ 回落中性档。"""
    from content.data_constants import MERCHANT_POSTURE_FALLBACK, MERCHANT_POSTURES

    key = posture if posture in MERCHANT_POSTURES else MERCHANT_POSTURE_FALLBACK
    return dict(MERCHANT_POSTURES[key])


def _iter_merchant_pops(state):
    """遍历州府级商人 POP：yield (route, seat, pop)。"""
    prefs = getattr(state, "prefectures", None) or {}
    for route, pdata in prefs.items():
        seats = (pdata or {}).get("seats") or {}
        for seat_id, srow in seats.items():
            pops = (srow or {}).get("pops") or {}
            pop = pops.get("商人")
            if isinstance(pop, dict):
                yield route, seat_id, pop


def _fleet_cost(base_cost: int, have: int) -> int:
    """边际成本递增：第 n 件成本 = base × growth^n。"""
    from content.data_constants import INVEST_FLEET_COST_GROWTH

    growth = float(INVEST_FLEET_COST_GROWTH or 1.0)
    # 边际成本按**规模档**递增（每 100 件一档、最多 20 档）——
    # 不能按存量件数直接取幂（50000 件会 OverflowError）。
    steps = min(20, max(0, int(have)) // 100)
    return int(round(float(base_cost) * (growth ** steps)))


def plan_investments(state) -> List[Dict[str, Any]]:
    """**纯函数**：按档位给每个商人 POP 生成投资提案（不改 state）。"""
    from content.data_constants import (POP_INVEST_MAX_PROPOSALS, POP_INVEST_MIN_CAPITAL,
                                        PRIVATE_BOAT_COST, PRIVATE_CART_COST)

    rules = posture_rules(merchant_posture(state))
    cap = int(getattr(state, "carriage", {}).get("private", {}).get("small_boat", 0) or 0)
    cart_have = int(getattr(state, "carriage", {}).get("private", {}).get("cart", 0) or 0)
    plans: List[Dict[str, Any]] = []
    for route, seat_id, pop in _iter_merchant_pops(state):
        wealth = pop.get("wealth")
        if not isinstance(wealth, (int, float)) or isinstance(wealth, bool):
            continue
        budget = float(wealth) * float(rules.get("invest_ratio") or 0)
        if float(wealth) < float(POP_INVEST_MIN_CAPITAL or 0) or budget <= 0:
            continue
        boat_cost = _fleet_cost(int(PRIVATE_BOAT_COST), cap)
        cart_cost = _fleet_cost(int(PRIVATE_CART_COST), cart_have)
        if budget >= boat_cost and rules.get("boat_share", 0) > 0:
            plans.append({"kind": "buy_boat", "route": route, "seat": seat_id,
                          "cost": boat_cost, "asset": "small_boat", "qty": 1,
                          "share": rules.get("boat_share")})
        elif budget >= cart_cost and rules.get("cart_share", 0) > 0:
            plans.append({"kind": "buy_cart", "route": route, "seat": seat_id,
                          "cost": cart_cost, "asset": "cart", "qty": 1,
                          "share": rules.get("cart_share")})
        elif rules.get("scope_share", 0) > 0:
            plans.append({"kind": "expand_scope", "route": route, "seat": seat_id,
                          "cost": 0, "asset": None, "qty": 1,
                          "share": rules.get("scope_share")})
        if len(plans) >= int(POP_INVEST_MAX_PROPOSALS or 40):
            break
    return plans


def apply_investment(state, plan: Dict[str, Any]) -> Dict[str, Any]:
    """执行提案：商人 wealth → 同 seat 工匠 wealth（工钱），资产 +1（**守恒**）。"""
    from core.foundation.ledger.pop_bridge import pop_obj_add

    route = plan.get("route")
    seat_id = plan.get("seat")
    cost = int(plan.get("cost") or 0)
    prefs = getattr(state, "prefectures", None) or {}
    srow = ((prefs.get(route) or {}).get("seats") or {}).get(seat_id) or {}
    pops = srow.get("pops") or {}
    merchant = pops.get("商人")
    artisan = pops.get("工匠")
    if not isinstance(merchant, dict):
        return {"ok": False, "reason": "no_merchant_pop"}
    wealth = merchant.get("wealth")
    if not isinstance(wealth, (int, float)) or float(wealth) < cost:
        return {"ok": False, "reason": "insufficient_wealth"}
    if cost > 0:
        paid = pop_obj_add(state, merchant, "wealth", -cost)
        if paid is None:
            merchant["wealth"] = float(wealth) - cost
        if isinstance(artisan, dict):
            got = pop_obj_add(state, artisan, "wealth", cost)
            if got is None:
                artisan["wealth"] = float(artisan.get("wealth") or 0) + cost
        else:
            state.treasury = int(getattr(state, "treasury", 0) or 0) + cost
    asset = plan.get("asset")
    if asset:
        carriage = getattr(state, "carriage", None)
        if not isinstance(carriage, dict):
            carriage = {}
            state.carriage = carriage
        private = carriage.setdefault("private", {})
        private[asset] = int(private.get(asset, 0) or 0) + int(plan.get("qty") or 1)
    journal = getattr(state, "merchant_investments", None)
    if not isinstance(journal, list):
        journal = []
        state.merchant_investments = journal
    record = {"route": route, "seat": seat_id, "kind": plan.get("kind"),
              "cost": cost, "asset": asset, "posture": merchant_posture(state)}
    journal.append(record)
    return {"ok": True, **record}


def settle_merchant_investment(state) -> Dict[str, Any]:
    """跑一轮投资（默认**不在结算里自动调用**，由 P8 接线时开关控制）。"""
    plans = plan_investments(state)
    done, failed = [], []
    for plan in plans:
        r = apply_investment(state, plan)
        (done if r.get("ok") else failed).append(r)
    return {"posture": merchant_posture(state), "planned": len(plans),
            "done": len(done), "failed": len(failed), "items": done}