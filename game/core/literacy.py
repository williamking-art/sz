# -*- coding: utf-8 -*-
"""宋祚 · 识字率（core/literacy.py）—— 新增设定（用户定稿 2026-09-19）

> **「既然现在没有识字率，就加入识字率这个设定」**
> **「识字率应该是各地 POP 自有的」**

## 挂载（POP 挂载律）
识字率是**各地各类 POP 自有**的社会属性，直接挂在 POP 上：

```
prefectures[路]["pops"][阶层]["literacy"]     # 0–100 的比率指标
```

它是**比率指标**（不是人口、不是钱粮），故不产生任何平行账本；逐路（每路 POP 结构不同）
逐类（各阶级识字水平天差地别）**互不相同**——这正是"同一道诏令在东南办得动、在边地办不动"
的弱关联来源。

派生读（**不落字段**）：
- 逐路：`route_literacy(state, route)` = 该路各类 POP 按 `size` 加权；
- 全国：`state.literacy` = 全部 POP 按 `size` 加权（`national_literacy`）。

## 口径（确定性、可解释、可测）
```
阶级基准（content.data.POP_LITERACY_BASE，史实锚点）：
    官僚 92 / 士绅 75 / 商人 32 / 工匠 22 / 兵 8 / 农 5

地区调制 region_mod = clamp(0.75 + 0.30×民心/100 − 0.20×动乱/100 + 0.20×art_mastery/100,
                            0.50, 1.35)
目标识字率 = clamp(阶级基准 × region_mod, 1, 98)
月度：literacy += (目标 − 当前) × 6%          # 缓动，不跳变（教育是慢变量）
```
只读边界：`literacy_target` / `route_literacy` / `national_literacy` / `pop_literacy` 纯派生；
**唯一写入点** `settle_literacy`（只写 `pops.*.literacy` 与派生值 `state.literacy`）。
"""
from __future__ import annotations
from core.numeric import parse_number as _num, clamp as _clamp

import logging
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger("literacy")

__all__ = ["POP_LITERACY_BASE", "literacy_target", "init_literacy", "settle_literacy",
           "route_literacy", "national_literacy", "pop_literacy"]

LITERACY_FLOOR = 1.0        # 再荒僻也有识几个字的人（僧道、行商、老吏）
LITERACY_CAP = 98.0         # 官僚/士绅不可能 100%
LITERACY_CONVERGE = 0.06    # 月度收敛率（教育慢变量）

MOD_BASE = 0.75
MOD_SUPPORT_W = 0.30        # 民心
MOD_UNREST_W = 0.20         # 动乱
MOD_ART_W = 0.20            # 文教（art_mastery）
MOD_LO, MOD_HI = 0.50, 1.35

# 阶级固有识字基准（史实锚点：士绅/官户为读书人，农户绝大多数不识字，兵丁略高于农）
POP_LITERACY_BASE: Dict[str, float] = {
    "官僚": 92.0, "士绅": 75.0, "商人": 32.0, "工匠": 22.0, "兵": 8.0, "农": 5.0,
}
_CLASSES: Tuple[str, ...] = tuple(POP_LITERACY_BASE)


def _region_mod(state, route: str, p: Optional[Dict[str, Any]] = None) -> float:
    """地区调制系数（0.50–1.35）：民心升、动乱降、文教投入升。"""
    p = p if isinstance(p, dict) else ((getattr(state, "prefectures", None) or {}).get(route) or {})
    support = _num(p.get("public_support"),
                   _num(getattr(state, "population_satisfaction", 50), 50.0))
    unrest = _num(p.get("unrest"), 15.0)
    art = _num(getattr(state, "art_mastery", 0), 0.0)
    mod = (MOD_BASE
           + MOD_SUPPORT_W * _clamp(support, 0.0, 100.0) / 100.0
           - MOD_UNREST_W * _clamp(unrest, 0.0, 100.0) / 100.0
           + MOD_ART_W * _clamp(art, 0.0, 100.0) / 100.0)
    return _clamp(mod, MOD_LO, MOD_HI)


def literacy_target(state, route: str, cls: str,
                    p: Optional[Dict[str, Any]] = None) -> float:
    """该路该阶级的**目标识字率**（0–100；纯派生，不写状态）。"""
    base = POP_LITERACY_BASE.get(cls)
    if base is None:
        return 0.0
    return round(_clamp(base * _region_mod(state, route, p), LITERACY_FLOOR, LITERACY_CAP), 2)


def pop_literacy(state, route: str, cls: str) -> Optional[float]:
    """该路该阶级的识字率读数（缺失 → None，不伪造）。"""
    p = (getattr(state, "prefectures", None) or {}).get(route)
    if not isinstance(p, dict):
        return None
    pop = ((p.get("pops") or {}).get(cls))
    if not isinstance(pop, dict) or pop.get("literacy") is None:
        return None
    return round(_num(pop.get("literacy")), 2)


def route_literacy(state, route: str) -> Optional[float]:
    """该路识字率 = 各类 POP 按 `size` 加权（**派生读，不落字段**）。"""
    p = (getattr(state, "prefectures", None) or {}).get(route)
    if not isinstance(p, dict):
        return None
    pops = p.get("pops") or {}
    num = den = 0.0
    for cls, pop in pops.items():
        if not isinstance(pop, dict) or pop.get("literacy") is None:
            continue
        size = max(0.0, _num(pop.get("size")))
        num += _num(pop.get("literacy")) * size
        den += size
    if den <= 0:
        return None
    return round(num / den, 2)


def national_literacy(state) -> Optional[float]:
    """全国识字率 = 全部 POP 按 `size` 加权（**派生读**；无读数 → None）。"""
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return None
    num = den = 0.0
    for route, p in prefs.items():
        if not isinstance(p, dict):
            continue
        for cls, pop in (p.get("pops") or {}).items():
            if not isinstance(pop, dict) or pop.get("literacy") is None:
                continue
            size = max(0.0, _num(pop.get("size")))
            num += _num(pop.get("literacy")) * size
            den += size
    if den <= 0:
        return None
    return round(num / den, 2)


def init_literacy(state) -> int:
    """幂等补齐**各地各类 POP** 的 `literacy`（旧档/新局皆可）；返回补齐的 POP 条目数。

    首值 = 该路该阶级的**目标值**（开局即稳定点，不出现"首月突跳"）。
    """
    fixed = 0
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return 0
    for route, p in prefs.items():
        if not isinstance(p, dict):
            continue
        pops = p.get("pops")
        if not isinstance(pops, dict):
            continue
        for cls, pop in pops.items():
            if not isinstance(pop, dict) or cls not in POP_LITERACY_BASE:
                continue
            if pop.get("literacy") is None:
                pop["literacy"] = literacy_target(state, route, cls, p)
                fixed += 1
    nat = national_literacy(state)
    if nat is not None:
        state.literacy = nat
    return fixed


def settle_literacy(state, log: Optional[list] = None) -> Dict[str, Any]:
    """月度识字率结算步（各地各类 POP 缓动趋近目标；**唯一写入点**）。

    教育是慢变量：每月只走 6% 的差距，故赈济/安民不会立刻"提高识字率"，
    但持续的太平与文教投入会。返回 `{"pops": n, "changed": k, "national": x}`。
    """
    out: Dict[str, Any] = {"pops": 0, "changed": 0, "national": None}
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return out
    for route, p in prefs.items():
        if not isinstance(p, dict):
            continue
        pops = p.get("pops")
        if not isinstance(pops, dict):
            continue
        for cls, pop in pops.items():
            if not isinstance(pop, dict) or cls not in POP_LITERACY_BASE:
                continue
            target = literacy_target(state, route, cls, p)
            cur = pop.get("literacy")
            if cur is None:
                pop["literacy"] = target
                out["changed"] += 1
                continue
            new = _clamp(_num(cur) + (target - _num(cur)) * LITERACY_CONVERGE,
                         LITERACY_FLOOR, LITERACY_CAP)
            if abs(new - _num(cur)) > 1e-9:
                pop["literacy"] = round(new, 2)
                out["changed"] += 1
            out["pops"] += 1
    nat = national_literacy(state)
    if nat is not None:
        state.literacy = out["national"] = nat
    if isinstance(log, list) and out["changed"] and nat is not None:
        log.append(f"[文教] 全国识字率 {nat:.1f}（本月 {out['changed']} 处 POP 缓动）")
    return out
