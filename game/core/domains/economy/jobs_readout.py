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
UNDEFINED_REASON = ("⚠️ **M78 更正**：M77 曾据此报『实到一律 undefined』，但实测 **`building_jobs.allocate_employment_detail` "
                    "是纯函数、按传入 `pops`/`buildings` 工作** ⇒ 传本治所数据即可**只读算出实到**。"
                    "本常量仅用于**就业分配单点异常/数据不可读**时的 reason，不再作为默认值。")

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

    🔴 **M78 更正 M77**：等级缩放**本就存在**——`building_jobs.jobs_by_position` 明写
    「岗位数 = **lv × 每级岗位**」⇒ `JOBS_PER_LEVEL` 是**每级**岗位数
    ⇒ **容量 = lv × 每级**（M77 报『不臆造等级缩放』**过于保守、等于报错**）。
    * 等级缺省 ⇒ 用 `building_level` 的默认（1）；
    * 建筑类型未登记 ⇒ `capacity=None` + reason（**缺失≠0**）。
    """
    cfg = _cfg()
    table = cfg.get("JOBS_PER_LEVEL") or {}
    if building not in table:
        return {"jobs_per_level": None, "level": level, "capacity": None,
                "level_scaling": "n/a",
                "reason": f"`JOBS_PER_LEVEL` 未登记 {building!r} ⇒ 容量不可定义（缺失≠0）"}
    per = _num(table.get(building))
    if per is None:
        return {"jobs_per_level": table.get(building), "level": level, "capacity": None,
                "level_scaling": "unknown", "reason": "每级岗位数不可解析（缺失≠0）"}
    lv = 1
    if level is not None:
        try:
            lv = max(0, int(level))
        except (TypeError, ValueError):
            lv = 1
    return {"jobs_per_level": per, "level": lv, "capacity": per * lv,
            "level_scaling": "per_level（见 jobs_by_position：岗位数 = lv × 每级）",
            "source": "core.building_jobs.jobs_by_position（同一口径）", "reason": None}


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
    # 🔴 **M78：实到可算**（M77 报『一律 undefined』**不对**）——`building_jobs.allocate_employment_detail`
    #   是**纯函数**且**按传入的 `pops`/`buildings` 工作** ⇒ 传本治所的 pops/buildings 即可在
    #   **只读、不改仿真** 下算出「在岗数」。口径：农池 = `农 size × JOB_SHARE`（OVERRIDE 优先）、
    #   工匠/商人/士绅池 = 各自 `size` 全额；类内按 `JOB_QUEUE_<类>` 建筑序、建筑内按职位槽 `min(槽位, 池余)`。
    filled: Dict[str, Any] = {}
    filled_reason = None
    try:
        from core.building_jobs import allocate_employment_detail, song_job_cfg
        alloc = allocate_employment_detail(srow.get("pops") or {}, buildings, song_job_cfg())
        for b, positions in (alloc or {}).items():
            filled[str(b)] = {str(p): int(v) for p, v in (positions or {}).items()}
    except Exception:                                       # noqa: BLE001
        log.warning("jobs_readout: 实到岗位不可算（allocate_employment_detail）", exc_info=True)
        filled, filled_reason = {}, "实到岗位不可算（就业分配单点异常）"
    for b, lv in buildings.items():
        cap = capacity_of(str(b), lv)
        rows.append({"building": str(b), "level": lv,
                     "capacity": cap["capacity"], "level_scaling": cap["level_scaling"],
                     "class": class_of(str(b))["class"],
                     "filled": filled.get(str(b)), "filled_reason": filled_reason or None,
                     "reason": cap["reason"]})
        if cap["capacity"] is not None:
            total += int(cap["capacity"])
            readable = True
    return {"route": route, "seat": seat, "rows": rows,
            "capacity_total": total if readable else None,
            "filled_total": (None if filled_reason else sum(sum(d.values()) for d in filled.values())),
            "filled_reason": filled_reason,
            "filled_source": "core.building_jobs.allocate_employment_detail（**纯函数**，按传入 pops/buildings）",
            "note": ("容量＝`JOBS_PER_LEVEL` 每级 × 等级（口径同 `jobs_by_position`）；"
                     "**实到**＝既有纯函数 `allocate_employment_detail` 的就地计算（只读）")}


def survey_jobs(state, top: int = 12) -> Dict[str, Any]:
    """全图岗位读数汇总（只读）：有岗位建筑的路数、容量合计、实到（恒 undefined）。"""
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return {"reason": "无 prefectures", "routes": [], "capacity_total": None}
    routes: List[Dict[str, Any]] = []
    total = 0
    filled_total = 0
    readable_routes = 0
    filled_routes = 0
    for route, pdata in prefs.items():
        seats = (pdata or {}).get("seats") if isinstance(pdata, dict) else None
        if not isinstance(seats, dict):
            continue
        r_cap = 0
        r_filled = 0
        any_cap = False
        any_filled = False
        for seat in seats:
            rep = seat_jobs(state, route, seat)
            if rep.get("capacity_total") is not None:
                r_cap += int(rep["capacity_total"])
                any_cap = True
            if rep.get("filled_total") is not None:
                r_filled += int(rep["filled_total"])
                any_filled = True
        if any_cap:
            readable_routes += 1
            total += r_cap
        if any_filled:
            filled_routes += 1
            filled_total += r_filled
        if any_cap or any_filled:
            routes.append({"route": route, "capacity_total": r_cap if any_cap else None,
                           "filled_total": r_filled if any_filled else None})
    routes.sort(key=lambda r: -(r["capacity_total"] or 0))
    return {"routes": routes[:top], "route_count": len(routes),
            "readable_routes": readable_routes,
            "capacity_total": total if readable_routes else None,
            "filled_total": filled_total if filled_routes else None,
            "filled_routes": filled_routes,
            "filled_source": "core.building_jobs.allocate_employment_detail（**纯函数**，按治所 pops/buildings）",
            "note": ("容量与**实到**均**只读可算**（口径见 `seat_jobs`）；⚠️ 开局各路的 buildings 只有"
                     "水利/常平仓（**非岗位建筑**）⇒ 实到为 **0**（真值：无岗可上），"
                     "但**非岗位建筑上的人不得被默认补进来**")}
