# -*- coding: utf-8 -*-
"""皇威权柄（2026-10-18 用户设定）。

皇威高于阈值时，皇帝获得对**特定程序化命令**的直行权柄：
言出即行，跳过执行侧权限与程序；但仍校验**目标合法性/物理约束**，
并支付可调的皇威代价。

- 本模块只维护「权柄表」与判定/扣费，不实现具体命令；
- `appoint`（任免）已由 `personnel_order` 接线；
- `military_dispatch`（调兵）等先登记为 `implemented=False`，避免假接线；
- 阈值/代价都是**可调数值**，最终放到平衡表，不在代码里写死。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

__all__ = [
    "DirectActionSpec", "ACTION_SPECS", "spec", "threshold",
    "prestige_cost", "can_direct", "charge_direct_cost",
    "direct_actions",
]


@dataclass(frozen=True)
class DirectActionSpec:
    key: str
    label: str
    threshold: int
    prestige_cost: int = 0
    implemented: bool = False
    note: str = ""


# 权柄表：阈值/代价可调；implemented=False = 只登记、未接线。
ACTION_SPECS: Dict[str, DirectActionSpec] = {
    "appoint": DirectActionSpec(
        "appoint", "任免", 80, 2, True, "任免官职（已接 personnel_order）"
    ),
    "military_dispatch": DirectActionSpec(
        "military_dispatch", "调兵", 85, 5, True, "军令（已接 issue_military_order）"
    ),
    "fiscal_directive": DirectActionSpec(
        "fiscal_directive", "财政直令", 85, 3, False, "待接财政入口"
    ),
    "justice": DirectActionSpec(
        "justice", "刑狱", 80, 2, False, "待接刑狱入口"
    ),
    "party_ban": DirectActionSpec(
        "party_ban", "党禁", 90, 8, True, "党禁（已接 party_ban_order）"
    ),
}


def spec(action: str) -> Optional[DirectActionSpec]:
    return ACTION_SPECS.get(str(action or "").strip())


def threshold(action: str) -> Optional[int]:
    item = spec(action)
    return item.threshold if item else None


def prestige_cost(action: str) -> int:
    item = spec(action)
    return item.prestige_cost if item else 0


def can_direct(state, action: str) -> bool:
    """皇威 > 阈值，且该权柄已接线 ⇒ 可直行。"""
    item = spec(action)
    if not item or not item.implemented:
        return False
    try:
        prestige = int(getattr(state, "prestige", 0) or 0)
    except (TypeError, ValueError):
        return False
    return prestige > item.threshold


def charge_direct_cost(state, action: str) -> int:
    """支付直行皇威代价（可调）；返回实际名义代价。"""
    cost = prestige_cost(action)
    if cost <= 0:
        return 0
    if hasattr(state, "change_prestige"):
        state.change_prestige(-cost)
    else:
        state.prestige = max(0, int(getattr(state, "prestige", 0) or 0) - cost)
    return cost


def direct_actions(only_implemented: bool = True) -> List[DirectActionSpec]:
    items = list(ACTION_SPECS.values())
    if only_implemented:
        items = [x for x in items if x.implemented]
    return items

