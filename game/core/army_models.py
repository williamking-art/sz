# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：实现已迁入 core.domains.military.army_models（第二十一包，2026-10-07）。
# 公开面上每个名字都从实现模块转发（含 `_` 开头私有名与 typing 绑定名）；
# ⚠️ 桩只保住『名字与对象』：打在桩上的 monkeypatch 不影响消费者，打在桩上的**重绑**也不改变实现侧同名绑定（第十七/十八包教训）。
"""宋祚 · army_models（兼容入口）。实现在 `core/domains/military/army_models.py`。"""
from __future__ import annotations
from core.domains.military.army_models import (  # noqa: F401
    ARMY_UNIT_INIT, ARMY_UNIT_SPLIT, ArmyUnit, CENTRAL_ARSENAL_INIT, CentralArsenal, ENFORCE_ARREARS_W, ENFORCE_BASE, ENFORCE_FLOOR, ENFORCE_MORALE_W, EQUIP_KEYS, EQUIP_STD, FRONTIER_MORALE_BONUS, FRONTIER_ROUTES, FRONTIER_TRAIN_BONUS, Optional, UNIT_TIER, _DEFENSE_LINE_OF, _army_power, _army_power_total, _defense_line_for, _firearm_power_mult, _org_names, _resolve_battle, _troops_weighted, annotations, branch_std, build_army_units, dataclass, deposit_workshop, distribute_arsenal, field, military_channels, reorganize_xiang_to_jin, unit_enforcement_mult, unit_monthly_pay, unit_tier_of,
)
__all__ = [
    "EQUIP_STD",
]
