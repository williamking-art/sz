# -*- coding: utf-8 -*-
"""宋祚 · 蓝图前置校验（core/construction.py）—— **只读纯函数**

定位（2026-09-19 用户指正后调整）：**不是**营建通道。营建（建筑从蓝图到落地的
"扣费 + 落等级"）应走**既有工程系统**（`state.projects` + `_settle_projects` 五态状态机）
与统一立项端口（`core.asset_context`）。

本模块只回答一个问题：**这座蓝图此刻能不能在这条路开工**，供工程立项/面板/AI 共用：
- 蓝图登记（`BUILDING_BLUEPRINTS` 优先，回落 `BUILDING_STD`）
- 科技前置（`need_node` 是否已解锁）
- **地利前置**（`requires_region` vs 该路路型）—— 仿明末 `requires_region_tags`
- 造价可支（国库）

**不含任何写操作**：不扣费、不写 `prefectures[*]["buildings"]`、不碰 `state.projects`。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from content.data import (
    BUILDING_BLUEPRINTS, BUILDING_COST_GROWTH, BUILDING_STD,
    blueprint_region_ok,
)
from core.numeric import parse_number as _num

log = logging.getLogger("construction")

__all__ = ["resolve_blueprint", "blueprint_cost", "can_build"]


def resolve_blueprint(name: str, key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """按**蓝图键**或**中文名**解析蓝图（科技蓝图优先，回落 `BUILDING_STD`）；未登记 None。"""
    k = str(key or "").strip()
    if k and k in BUILDING_BLUEPRINTS:
        bp = dict(BUILDING_BLUEPRINTS[k])
        bp.setdefault("_key", k)
        bp.setdefault("_name", bp.get("name", k))
        return bp
    n = str(name or "").strip()
    if not n:
        return None
    for k2, bp2 in BUILDING_BLUEPRINTS.items():
        if str(bp2.get("name")) == n:
            out = dict(bp2)
            out.setdefault("_key", k2)
            out.setdefault("_name", n)
            return out
    if n in BUILDING_STD:
        out = dict(BUILDING_STD[n])
        out.setdefault("_key", n)
        out.setdefault("_name", n)
        return out
    return None


def blueprint_cost(bp: Dict[str, Any], levels: int = 1) -> int:
    """造价（贯）：基础建筑按 `base_cost` × 等级增长；科技蓝图取 `cost.silver`。"""
    lv = max(1, int(levels or 1))
    if "base_cost" in bp:
        base = float(bp.get("base_cost", 0) or 0)
        return int(sum(base * (BUILDING_COST_GROWTH ** i) for i in range(lv)))
    return int(_num((bp.get("cost") or {}).get("silver"), 0.0)) * lv


def can_build(state, route: str, name: str,
              key: Optional[str] = None) -> Tuple[bool, List[str]]:
    """营建前置校验（**只读**）；返回 `(可否, 原因列表)`。

    依次检查：蓝图登记 / 路存在 / 科技前置未解锁 / **地利不合** / 国库不足。
    调用方（工程立项 / 面板 / AI）据返回值决定是否允许开工，**不得跳过本校验**。
    """
    errs: List[str] = []
    bp = resolve_blueprint(name, key)
    if bp is None:
        return False, [f"蓝图未登记：{name or key}（无图纸可依，不得静默开工）"]
    prefs = getattr(state, "prefectures", None) or {}
    p = prefs.get(str(route))
    if not isinstance(p, dict):
        return False, [f"路不存在：{route}"]

    need_node = bp.get("need_node")
    if need_node:
        tech = getattr(state, "tech", None) or {}
        if str(need_node) not in set(tech.get("unlocked") or []):
            errs.append(f"科技前置未解锁：{need_node}")

    if not blueprint_region_ok(p.get("type"), bp.get("_key") or ""):
        need = bp.get("requires_region") or ()
        errs.append(f"地利不合：该蓝图须 {('/'.join(map(str, need)))}，"
                    f"而 {route} 为「{p.get('type')}」")

    cost = blueprint_cost(bp, 1)
    if cost > 0 and int(getattr(state, "treasury", 0) or 0) < cost:
        errs.append(f"国库不足：需 {cost:,} 贯")
    return (not errs), errs
