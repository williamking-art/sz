# -*- coding: utf-8 -*-
"""岗位**只读读数**（P2 缺口 1 的第一切片） —— M77。

裁定：Jev **丙 0.5014**（甲按本治所 POP 摊 0.310 / 乙 走既有岗位队列 0.102 / 丁 按等级占比 0.087）
⇒ **先只读**：**容量与所需阶层照实报，`实到` 一律 `undefined`**——因为今天**没有就业实例**，
规格亦明令「缺字段标未定义，**不能用默认全员就业或默认满产补齐**」。

口径（**全部复用既有单点，不新增账本**）
--------------------------------------
* **容量**：`building_jobs.song_job_cfg()["JOBS_PER_LEVEL"][建筑类型]`（原值照报）；
  ⚠️ **等级缩放未定义**：配置值是**标量**（如 `自耕农庄: 160`）⇒ 本模块**不臆造**按等级乘除，
  仅在配置本身是「按等级的表」（list/dict）时才做等级取值；否则 `level_scaling="undefined"`。
* **所需阶层**：`BUILDING_WORKER[建筑类型]`（农田/庄园→农、工坊→工匠、商铺→商人）。
* **建筑实例**：`prefectures[路]["seats"][治所]["buildings"]`（M38 已州府化；路级为派生镜像）。
* **实到岗位**：**无就业实例 ⇒ `None` + reason**（**不默认全员就业/满产**）。
* **缺失 ≠ 0**：建筑类型未登记 ⇒ `undefined`（**不是 0 岗位**）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

#: 本批**不提供**实到岗位（见模块 docstring）：写死为 None，避免调用方误以为可算
UNDEFINED_REASON = ("**无就业实例**：岗位侧只有『容量』（`JOBS_PER_LEVEL`×等级）与『所需阶层』"
                    "（`BUILDING_WORKER`），且 `JOB_SHARE`/`JOB_QUEUE` 是**政权/阶层级流量**、"
                    "**没有按路/治所的实到记录** ⇒ 按 Jev 丙 0.5014 报 `undefined`"
                    "（规格明令**不得默认全员就业或满产补齐**）")

__all__ = ["UNDEFINED_REASON", "capacity_of", "class_of", "seat_jobs", "survey_jobs"]


def _num(v) -> Optional[float]:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def _cfg() -> Dict[str, Any]:
    try:
        from core.building_jobs import song_job_cfg
        return song_job_cfg() or {}
    except Exception:                                       # noqa: BLE001
        log.warning("jobs_readout: song_job_cfg 不可用", exc_info=True)
        return {}


def capacity_of(building: str, level: Any = None) -> Dict[str, Any]:
    """某建筑类型的**岗位容量**（只读）：`{jobs_per_level, level, capacity, level_scaling, reason}`。

    * 配置值是**标量** ⇒ `capacity` 取该标量，`level_scaling="undefined"`（**不臆造等级缩放**）；
    * 配置值是**按等级的表**（list/dict）⇒ 有 `level` 时取值，否则 `capacity=None`（不可读）；
    * 建筑类型未登记 ⇒ `capacity=None` + reason（**缺失≠0**）。
    """
    cfg = _cfg()
    table = cfg.get("JOBS_PER_LEVEL") or {}
    if building not in table:
        return {"jobs_per_level": None, "level": level, "capacity": None,
                "level_scaling": "n/a",
                "reason": f"`JOBS_PER_LEVEL` 未登记 {building!r} ⇒ 容量不可定义（缺失≠0）"}
    raw = table.get(building)
    if isinstance(raw, (list, tuple)):
        if level is None:
            return {"jobs_per_level": raw, "level": None, "capacity": None,
                    "level_scaling": "per_level_table",
                    "reason": "配置是按等级的表，但未给等级 ⇒ 容量不可定义"}
        idx = max(0, min(len(raw) - 1, int(level) - 1))
        return {"jobs_per_level": raw, "level": int(level), "capacity": _num(raw[idx]),
                "level_scaling": "per_level_table", "reason": None}
    if isinstance(raw, dict):
        key = str(level) if level is not None else None
        v = _num(raw.get(key)) if key else None
        return {"jobs_per_level": raw, "level": level, "capacity": v,
                "level_scaling": "per_level_map",
                "reason": None if v is not None else "按等级的表里取不到该等级 ⇒ 容量不可定义"}
    v = _num(raw)
    return {"jobs_per_level": raw, "level": level, "capacity": v,
            "level_scaling": "undefined",
            "reason": ("配置是**标量** ⇒ **不臆造等级缩放**（容量按原值报）"
                       if v is not None else "容量值不可解析")}


def class_of(building: str) -> Dict[str, Any]:
    """某建筑类型**所需阶层**（`BUILDING_WORKER`）；未登记 ⇒ `None` + reason。"""
    cfg = _cfg()
    m = cfg.get("BUILDING_WORKER") or {}
    cls = m.get(building)
    return {"class": cls, "source": "BUILDING_WORKER",
            "reason": None if cls else f"`BUILDING_WORKER` 未登记 {building!r} ⇒ 所需阶层不可定义"}


def seat_jobs(state, route: str, seat: str) -> Dict[str, Any]:
    """某治所的**岗位读数**（只读）：逐建筑报容量/所需阶层/`实到=None`。"""
    prefs = getattr(state, "prefectures", None)
    pdata = (prefs or {}).get(route) if isinstance(prefs, dict) else None
    seats = (pdata or {}).get("seats") if isinstance(pdata, dict) else None
    srow = (seats or {}).get(seat) if isinstance(seats, dict) else None
    if not isinstance(srow, dict):
        return {"route": route, "seat": seat, "rows": [], "capacity_total": None,
                "reason": "治所不可读（缺失≠0）"}
    buildings = srow.get("buildings") or {}
    if not isinstance(buildings, dict):
        return {"route": route, "seat": seat, "rows": [], "capacity_total": None,
                "reason": "该治所 buildings 不可读"}
    rows: List[Dict[str, Any]] = []
    total = 0
    readable = False
    for b, lv in buildings.items():
        cap = capacity_of(str(b), lv)
        rows.append({"building": str(b), "level": lv,
                     "capacity": cap["capacity"], "level_scaling": cap["level_scaling"],
                     "class": class_of(str(b))["class"],
                     "filled": None, "filled_reason": UNDEFINED_REASON,
                     "reason": cap["reason"]})
        if cap["capacity"] is not None:
            total += int(cap["capacity"])
            readable = True
    return {"route": route, "seat": seat, "rows": rows,
            "capacity_total": total if readable else None,
            "filled_total": None, "filled_reason": UNDEFINED_REASON,
            "note": "容量＝`JOBS_PER_LEVEL` 原值（**不臆造等级缩放**）；**实到一律 undefined**"}


def survey_jobs(state, top: int = 12) -> Dict[str, Any]:
    """全图岗位读数汇总（只读）：有岗位建筑的路数、容量合计、实到（恒 undefined）。"""
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return {"reason": "无 prefectures", "routes": [], "capacity_total": None}
    routes: List[Dict[str, Any]] = []
    total = 0
    readable_routes = 0
    for route, pdata in prefs.items():
        seats = (pdata or {}).get("seats") if isinstance(pdata, dict) else None
        if not isinstance(seats, dict):
            continue
        r_cap = 0
        any_cap = False
        for seat in seats:
            rep = seat_jobs(state, route, seat)
            if rep.get("capacity_total") is not None:
                r_cap += int(rep["capacity_total"])
                any_cap = True
        if any_cap:
            readable_routes += 1
            total += r_cap
            routes.append({"route": route, "capacity_total": r_cap, "filled_total": None})
    routes.sort(key=lambda r: -r["capacity_total"])
    return {"routes": routes[:top], "route_count": len(routes),
            "readable_routes": readable_routes,
            "capacity_total": total if readable_routes else None,
            "filled_total": None, "filled_reason": UNDEFINED_REASON,
            "note": ("岗位**容量**可算；**实到恒 `undefined`**（无就业实例）"
                     "⇒ P1/P2/P4 的『实到』须先走既有岗位队列细化到路/治所（另批）")}
