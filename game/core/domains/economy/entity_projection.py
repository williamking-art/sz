# -*- coding: utf-8 -*-
"""P2 建筑实例**只读投影**（M86）—— 规格要求的字段逐项报出，缺的**如实 `undefined`**。

依据：`specs/economy/unified-civilian-market/tasks.md` §4 P2——
「每个试点建筑/经营记录须能确定：蓝图版本、稳定地点、等级和完工/可运营月份、所有者、
经营者/管理 Agent、维护责任、经营方式（家庭兼业/民营雇工/官营/官有承包）、可选生产方法、
岗位容量/**实到**、配方、投入/产出库存、收入去向。**缺字段标未定义，不能用默认全员就业或默认满产补齐**。」

口径（**零数值变化、只读**）
--------------------------
* **能算的算**：`level`（`seats[治所]["buildings"]`）· `jobs_capacity`（`JOBS_PER_LEVEL`×等级）·
  `jobs_filled`（`allocate_employment_detail` 纯函数，M78）；
* 🔴 **不能算的如实 `undefined` + reason**：`blueprint`（无蓝图版本字段）· `completed_month`
  （仅 `civil_building` 有建成月，本模块**不臆造**）· `owner`（**建筑**无货主；M66 只登记了**作坊**）·
  `operator`/`maintenance`/`operation_mode`/`methods` · `recipe`（建筑无配方）·
  `io_stock`（库存**不按主体分栏**）· `income_to`（利润归主未接，见 M71）；
* 每个字段都给 `source` 与 `reason`（**可下钻**）；并汇总 `undefined_fields`。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

#: P2 规格要求的字段（**枚举单点**：改动请同步规格与用例）
FIELDS = ("blueprint", "seat", "level", "completed_month", "owner", "operator",
          "maintenance", "operation_mode", "methods", "jobs_capacity", "jobs_filled",
          "recipe", "io_stock", "income_to")

__all__ = ["SCHEMA_VERSION", "FIELDS", "project_building", "project_seat", "survey_entity_projection"]


def _seat_row(state, route: str, seat: str) -> Optional[dict]:
    prefs = getattr(state, "prefectures", None)
    pdata = (prefs or {}).get(route) if isinstance(prefs, dict) else None
    seats = (pdata or {}).get("seats") if isinstance(pdata, dict) else None
    row = (seats or {}).get(seat) if isinstance(seats, dict) else None
    return row if isinstance(row, dict) else None


def _jobs_context(state, route: str, seat: str) -> Dict[str, Any]:
    """该治所的岗位上下文：`{建筑: {"capacity", "filled", "source"}}`（不可用 ⇒ 空表）。"""
    try:
        from core.domains.economy import jobs_readout as jr
        rep = jr.seat_jobs(state, route, seat)
        out: Dict[str, Any] = {}
        for row in rep.get("rows") or []:
            b = str(row.get("building"))
            out[b] = {"capacity": row.get("capacity"),
                      "filled": (row.get("filled") or {}) if row.get("filled") else None,
                      "source": rep.get("filled_source")}
        return out
    except Exception:                                       # noqa: BLE001
        log.warning("entity_projection: 岗位上下文不可用 route=%s seat=%s", route, seat, exc_info=True)
        return {}


def project_building(state, route: str, seat: str, building: str, level: Any = None,
                     jobs_ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """单座建筑的 P2 字段投影（只读）：每个字段 `{value, defined, source, reason}`。"""
    ctx = jobs_ctx if jobs_ctx is not None else _jobs_context(state, route, seat)
    j = ctx.get(str(building)) or {}
    # 🔴 M91：建筑**归属**读 `seats[治所].building_meta`（保形态、**非账本**；未迁移/未登记 ⇒ undefined）
    _meta = (((_seat_row(state, route, seat) or {}).get("building_meta") or {}).get(str(building))) or {}

    def _undef(reason: str, source: str = "（无）") -> Dict[str, Any]:
        return {"value": None, "defined": False, "source": source, "reason": reason}

    fields: Dict[str, Any] = {
        "blueprint": _undef("无「蓝图版本」字段（建筑只有名称+等级）"),
        "seat": {"value": f"{route}|{seat}", "defined": True,
                 "source": "prefectures[路].seats[治所]（M38 已州府化）", "reason": None},
        "level": {"value": level, "defined": level is not None,
                  "source": "seats[治所][\"buildings\"]", "reason": None},
        "completed_month": _undef("建成月仅 `civil_building` 有；本模块**不臆造**"),
        "owner": {"value": _meta.get("owner"), "defined": bool(_meta.get("owner")),
                  "source": "prefectures[路].seats[治所].building_meta（M91 P2 第一片；保形态、**非账本**）",
                  "reason": None if _meta.get("owner") else "该建筑类型未登记归属规则，或旧档未迁移（缺失≠0）"},
        "operator": (lambda _o: (
            {"value": _o, "defined": bool(_o), "source": "building_owner.derive_operator（M92：**首期与 owner 同值**，无独立经营者模型）",
             "reason": None if _o else "无 owner ⇒ 经营者亦不可定义（缺失≠0）"}))(_meta.get("owner")),
        "maintenance": _undef("无维护责任字段"),
        "operation_mode": (lambda _o: (lambda _m: (
            {"value": _m, "defined": bool(_m), "source": "building_owner.derive_operation_mode（M92 口径单点：local:→官营 · pop:…:商人→民营雇工 · 其它 pop:→家庭兼业）",
             "reason": None if _m else "无 owner 前缀可派生 ⇒ 经营方式不可定义（缺失≠0）"}))(
            __import__("core.domains.economy.building_owner", fromlist=["x"]).derive_operation_mode(_o)))(
            _meta.get("owner")),
        "methods": _undef("无可选生产方法字段"),
        "jobs_capacity": {"value": j.get("capacity"), "defined": j.get("capacity") is not None,
                          "source": "core.domains.economy.jobs_readout:capacity_of（= lv × 每级）",
                          "reason": None if j.get("capacity") is not None else "该建筑非岗位建筑（`JOBS_PER_LEVEL` 未登记）"},
        "jobs_filled": {"value": j.get("filled"), "defined": j.get("filled") is not None,
                        "source": j.get("source") or "core.building_jobs:allocate_employment_detail",
                        "reason": None if j.get("filled") is not None else "实到不可算（该建筑非岗位建筑或无池）"},
        "recipe": _undef("建筑无配方（配方在**作坊**上）"),
        "io_stock": _undef("库存**不按主体分栏**（产出入 `resources`/工匠 `goods` 池）"),
        "income_to": _undef("利润归主未接（营运资金来源待口径，见 M71）"),
    }
    undefined = [k for k in FIELDS if not (fields.get(k) or {}).get("defined")]
    return {"route": route, "seat": seat, "building": str(building), "level": level,
            "fields": fields, "undefined_fields": undefined,
            "defined_count": len(FIELDS) - len(undefined), "field_count": len(FIELDS),
            "note": ("P2 只读投影：**能算的算（等级/岗位容量/实到）**，其余**如实 undefined**；"
                     "规格明令**不得用默认全员就业或默认满产补齐**")}


def project_seat(state, route: str, seat: str) -> Dict[str, Any]:
    """整治所的 P2 投影（只读）：逐建筑一行 + 汇总。"""
    row = _seat_row(state, route, seat)
    if row is None:
        return {"route": route, "seat": seat, "rows": [], "reason": "治所不可读（缺失≠0）"}
    buildings = row.get("buildings") or {}
    if not isinstance(buildings, dict):
        return {"route": route, "seat": seat, "rows": [], "reason": "该治所 buildings 不可读"}
    ctx = _jobs_context(state, route, seat)
    rows = [project_building(state, route, seat, b, lv, ctx) for b, lv in buildings.items()]
    return {"route": route, "seat": seat, "rows": rows, "buildings": len(rows),
            "schema_version": SCHEMA_VERSION,
            "note": "逐建筑 P2 字段投影（只读）；`undefined_fields` 列出未定义字段"}


def survey_entity_projection(state, top: int = 8) -> Dict[str, Any]:
    """全图汇总（只读）：建筑总数、**逐字段的已定义率**（规格 14 项里哪些已有真实来源）。"""
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return {"reason": "无 prefectures", "rows": []}
    total = 0
    defined_by_field: Dict[str, int] = {k: 0 for k in FIELDS}
    rows: List[Dict[str, Any]] = []
    for route, pdata in prefs.items():
        seats = (pdata or {}).get("seats") if isinstance(pdata, dict) else None
        if not isinstance(seats, dict):
            continue
        for seat in seats:
            rep = project_seat(state, route, seat)
            for r in rep.get("rows") or []:
                total += 1
                for k in FIELDS:
                    if (r["fields"].get(k) or {}).get("defined"):
                        defined_by_field[k] += 1
            if rep.get("rows"):
                rows.append({"route": route, "seat": seat, "buildings": rep["buildings"]})
    return {"rows": rows[:top], "route_seat_count": len(rows), "buildings": total,
            "defined_by_field": defined_by_field,
            "defined_ratio": {k: (None if not total else round(v / total, 4))
                              for k, v in defined_by_field.items()},
            "note": ("P2 字段可定义率：**能算的（等级/岗位容量/实到）有值**；"
                     "owner/operator/完工月/经营方式/配方/库存栏/收入去向**尚未落地**（如实 undefined）")}
