# -*- coding: utf-8 -*-
"""宋祚 · 利益集团派生指标（core/faction_metrics.py）—— **只读纯函数**

依据：`faction_pop_optimization_plan_2026-09-19`（集团模型与派生 / 政策传导顺序）。

## 挂载口径（2026-09-19 用户定稿）
- **立场跟派系，不跟地域**（地域只是出身）：集团切片 = 该 POP 类的**基数人数 × 立场占比**
  （`state.faction_split`，见 core/faction_split.py），**不按路切**；
- 集团人数 = Σ_路 Σ_类 (基数 × split)；资源按"占父 POP 人数比例"折算；
- `officials`/`clerks` 是**人数**子池（无独立 wealth），故子池集团按人数比例折算资源。

## 纪律
1. **只读**：不写 `state.factions` / POP / 国库；写入由 `core/faction_settle.py` 单点负责；
2. 粮价取既有口径 `prefectures[路]["grain_price"]`（回落 `state.grain_price`），不新造价格变量；
3. **重叠不重复扣**：同一 POP 可被多个网络引用，本模块只读；写入由 applier 的 path 唯一性保证。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from content.data import FACTION_POP_BASIS
from core.faction_basis import basis_routes
from core.faction_split import split_of
from core.numeric import clamp as _clamp, parse_number as _num

log = logging.getLogger("faction_metrics")

__all__ = [
    "local_grain_price", "pop_pool_size", "pop_pool_share", "faction_slice",
    "national_totals", "faction_power", "all_faction_power",
    "POWER_W_POP", "POWER_W_RES", "POWER_W_VOICE", "POWER_W_INST", "POWER_W_MIL",
    "POWER_W_COH",
]

# 影响力权重（文档口径 + 声量项；和 = 1.00）
POWER_W_POP = 0.25
POWER_W_RES = 0.20
POWER_W_VOICE = 0.25     # 朝堂声量（宰执/台谏/近侍席位）——人数 ≠ 话语权
POWER_W_INST = 0.15
POWER_W_MIL = 0.10
POWER_W_COH = 0.05


def local_grain_price(state, route: Optional[str]) -> float:
    """该路粮价（贯/石）：既有 `prefectures[路]["grain_price"]` → `state.grain_price` → 1.0。"""
    prefs = getattr(state, "prefectures", None)
    if isinstance(prefs, dict) and route:
        p = prefs.get(route)
        if isinstance(p, dict) and p.get("grain_price") is not None:
            v = _num(p.get("grain_price"))
            if v > 0:
                return v
    v = _num(getattr(state, "grain_price", 1.0), 1.0)
    return v if v > 0 else 1.0


def pop_pool_size(pop: Any, pool: Optional[str]) -> float:
    """基数人数：子池用子池人数（`officials`/`clerks`/`clan`），否则父 POP `size`。"""
    if not isinstance(pop, dict):
        return 0.0
    if pool:
        return max(0.0, _num(pop.get(pool)))
    return max(0.0, _num(pop.get("size")))


def pop_pool_share(pop: Any, pool: Optional[str]) -> float:
    """子池人数 ÷ 父 POP 人数（无子池 → 1.0）。"""
    if not pool:
        return 1.0
    if not isinstance(pop, dict):
        return 0.0
    size = max(0.0, _num(pop.get("size")))
    if size <= 0:
        return 0.0
    return _clamp(_num(pop.get(pool)) / size, 0.0, 1.0)


def faction_slice(state, spec: Any, name: str = "") -> Dict[str, Any]:
    """集团基本盘的 POP 切片汇总（**只读**；按立场占比切，不按地域）。

    `resources = wealth + grain × 逐路粮价`；集团对该 POP 的资源按"人数占比"折算。
    """
    name = name or str((spec or {}).get("_name") or "")
    routes = basis_routes(spec)                      # routes=None → 全部路
    classes = list((spec or {}).get("pop_classes") or [])
    pool = (spec or {}).get("pool")
    prefs = getattr(state, "prefectures", None) or {}

    population = wealth = grain = grain_value = 0.0
    units: List[Dict[str, Any]] = []
    for route in routes:
        p = prefs.get(route)
        if not isinstance(p, dict):
            continue
        pops = p.get("pops") or {}
        if not isinstance(pops, dict):
            continue
        price = local_grain_price(state, route)
        for cls in classes:
            pop = pops.get(cls)
            if not isinstance(pop, dict):
                continue
            # 立场只落在「官」身上：官僚类未显式声明子池时，一律取 officials 子池
            # （官僚 POP 的 size 含吏，吏不预党争；见 content/data.py 的身份子池）。
            use_pool = pool or ("officials" if cls == "官僚" else None)
            base = pop_pool_size(pop, use_pool)
            if base <= 0:
                continue
            share = _clamp(_num(split_of(state, cls).get(name, 0.0)), 0.0, 1.0)
            if share <= 0:
                continue
            sz = base * share
            frac = sz / max(1e-9, _num(pop.get("size")))     # 占父 POP 人数比
            w = max(0.0, _num(pop.get("wealth"))) * frac
            g = max(0.0, _num(pop.get("grain"))) * frac
            population += sz
            wealth += w
            grain += g
            grain_value += g * price
            units.append({"route": route, "pop_class": cls, "pool": use_pool,
                          "base": round(base, 2), "share": round(share, 4),
                          "size": round(sz, 2), "wealth": round(w, 2),
                          "grain": round(g, 2), "grain_price": price})
    return {
        "name": name, "routes": routes, "pop_classes": classes, "pool": pool,
        "population": round(population, 2), "wealth": round(wealth, 2),
        "grain": round(grain, 2), "grain_value": round(grain_value, 2),
        "resources": round(wealth + grain_value, 2),
        "units": units, "complete": bool(routes) and bool(classes),
    }


def national_totals(state) -> Dict[str, Any]:
    """全国口径（influence 分母：人口 / 资源 / officials / troops；**父 POP 全额**）。"""
    prefs = getattr(state, "prefectures", None)
    pop_total = res_total = officials_total = troops_total = 0.0
    by_class: Dict[str, float] = {}
    if not isinstance(prefs, dict):
        return {"population": 0.0, "resources": 0.0, "by_class": by_class,
                "officials": 0.0, "troops": 0.0}
    for route, p in prefs.items():
        if not isinstance(p, dict):
            continue
        pops = p.get("pops") or {}
        if not isinstance(pops, dict):
            continue
        price = local_grain_price(state, route)
        for cls, pop in pops.items():
            if not isinstance(pop, dict):
                continue
            sz = max(0.0, _num(pop.get("size")))
            w = max(0.0, _num(pop.get("wealth")))
            g = max(0.0, _num(pop.get("grain")))
            pop_total += sz
            res_total += w + g * price
            by_class[cls] = by_class.get(cls, 0.0) + sz
            if cls == "官僚":
                officials_total += max(0.0, _num(pop.get("officials")))
            if cls == "兵":
                troops_total += sz
    return {"population": round(pop_total, 2), "resources": round(res_total, 2),
            "by_class": by_class, "officials": round(officials_total, 2),
            "troops": round(troops_total, 2)}


def _class_slice_population(state, spec: Any, name: str, cls: str) -> float:
    """该集团在**指定阶级**上的切片人数（只取该类，避免把士绅人数算进"制度杠杆"）。"""
    sub = dict(spec or {})
    sub["pop_classes"] = [cls]
    sub["pool"] = (spec or {}).get("pool") if cls == "官僚" else None
    return faction_slice(state, sub, name)["population"]


def _institutional_access(state, spec: Any, nat: Dict[str, Any], name: str = "") -> float:
    """制度杠杆：本集团**官僚部分**占全国 officials 的比例（非官僚集团 → 0）。"""
    classes = list((spec or {}).get("pop_classes") or [])
    if "官僚" not in classes:
        return 0.0
    den = _num(nat.get("officials"))
    if den <= 0:
        return 0.0
    return _clamp(_class_slice_population(state, spec, name, "官僚") / den, 0.0, 1.0)


def _military_leverage(state, spec: Any, nat: Dict[str, Any], name: str = "") -> float:
    """军事杠杆：本集团**兵系**占全国兵额的比例（非兵集团 → 0）。"""
    classes = list((spec or {}).get("pop_classes") or [])
    if "兵" not in classes:
        return 0.0
    den = _num(nat.get("troops"))
    if den <= 0:
        return 0.0
    return _clamp(_class_slice_population(state, spec, name, "兵") / den, 0.0, 1.0)


def faction_power(state, name: str, spec: Any = None) -> Dict[str, Any]:
    """集团影响力（0–100，由 POP + **声量**派生）。

    `power = .25人口份额 + .20资源份额 + .25声量 + .15制度 + .10军事 + .05凝聚力`
    """
    base_spec = spec if spec is not None else FACTION_POP_BASIS.get(name, {})
    spec = dict(base_spec or {})
    spec["_name"] = name                      # 让 faction_slice 知道自己在算哪个集团
    sl = faction_slice(state, spec, name)
    nat = national_totals(state)
    pop_share = (sl["population"] / nat["population"]) if nat["population"] > 0 else 0.0
    res_share = (sl["resources"] / nat["resources"]) if nat["resources"] > 0 else 0.0
    try:
        from core.faction_voice import voice_norm
        voice = _clamp(voice_norm(state, name), 0.0, 1.0)
    except Exception as e:  # noqa: BLE001
        log.debug("faction_power 取声量失败：%s", e)
        voice = 0.0
    inst = _institutional_access(state, spec, nat, name)
    mil = _military_leverage(state, spec, nat, name)
    fac = (getattr(state, "factions", None) or {}).get(name)
    coh = 0.0
    if isinstance(fac, dict):
        coh = _clamp(_num(fac.get("cohesion"), 0.0) / 100.0, 0.0, 1.0)
    raw = (POWER_W_POP * pop_share + POWER_W_RES * res_share + POWER_W_VOICE * voice
           + POWER_W_INST * inst + POWER_W_MIL * mil + POWER_W_COH * coh)
    influence = round(_clamp(raw * 100.0, 0.0, 100.0), 2)
    # 无基本盘读数（旧档/未迁移）→ 回退旧 influence（迁移期兜底）
    fallback = False
    if sl["population"] <= 0:
        old = _num((fac or {}).get("influence"), 0.0) if isinstance(fac, dict) else 0.0
        influence, fallback = round(_clamp(old, 0.0, 100.0), 2), True
    return {
        "name": name, "population": sl["population"], "resources": sl["resources"],
        "population_share": round(pop_share, 6), "resource_share": round(res_share, 6),
        "voice": round(voice, 6),
        "institutional_access": round(inst, 6), "military_leverage": round(mil, 6),
        "cohesion": round(coh, 6), "influence": influence, "fallback": fallback,
    }


def all_faction_power(state) -> Dict[str, Dict[str, Any]]:
    """全部集团的派生指标（含改革催生的额外集团）。"""
    out: Dict[str, Dict[str, Any]] = {}
    facs = getattr(state, "factions", None) or {}
    for name in list(FACTION_POP_BASIS) + [n for n in facs if n not in FACTION_POP_BASIS]:
        spec = FACTION_POP_BASIS.get(name)
        if spec is None:
            continue
        out[name] = faction_power(state, name, spec)
    return out
