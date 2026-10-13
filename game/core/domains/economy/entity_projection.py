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
    # 🔴 M99：`completed_month` **可如实读取**——非岗位类建筑写结构化条目
    #   `{"lv": n, "built_month": m}`（`civil_building`；`built_month`＝**绝对月序** = year×12+month）；
    #   岗位类建筑写**标量**（无建成月）⇒ 后者如实 `undefined`（缺失≠0）。
    _raw = ((_seat_row(state, route, seat) or {}).get("buildings") or {}).get(str(building))
    _built = _raw.get("built_month") if isinstance(_raw, dict) else None
    _built_ok = isinstance(_built, (int, float)) and not isinstance(_built, bool)
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
        "completed_month": {"value": int(_built) if _built_ok else None, "defined": _built_ok,
                            "source": ("seats[治所].buildings[建筑].built_month（**绝对月序**＝year×12+month；"
                                       "`civil_building` 结构写法）"),
                            "reason": None if _built_ok else
                            ("该建筑以**标量**登记（岗位类写法）或为开局建筑（无 built_month）"
                             "⇒ 无建成月（缺失≠0，**不臆造**）")},
        "owner": {"value": _meta.get("owner"), "defined": bool(_meta.get("owner")),
                  "source": "prefectures[路].seats[治所].building_meta（M91 P2 第一片；保形态、**非账本**）",
                  "reason": None if _meta.get("owner") else "该建筑类型未登记归属规则，或旧档未迁移（缺失≠0）"},
        "operator": (lambda _o: (
            {"value": _o, "defined": bool(_o), "source": "building_owner.derive_operator（M92：**首期与 owner 同值**，无独立经营者模型）",
             "reason": None if _o else "无 owner ⇒ 经营者亦不可定义（缺失≠0）"}))(_meta.get("owner")),
        "maintenance": (lambda _o: {"value": _o, "defined": bool(_o),
                                    "source": ("M104（Jev 甲 0.907）：**首期维护责任＝与 owner 同责**；"
                                               "维护**费**参数在 `content` constants（如 常平仓 maintain=0.005）"),
                                    "reason": None if _o else "无 owner ⇒ 维护责任不可定义（缺失≠0）"})(_meta.get("owner")),
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
        "io_stock": _undef("库存**不在建筑上**：货由 POP 持有（治所级）或入 `resources`/工匠 `goods` 池 ⇒ "
                           "本字段不按建筑分栏；**查持有方**用 `seat_goods_readout`（治所×阶层）／"
                           "`material_holding`（全国池）（**不臆造建筑库存**）"),
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


def project_workshop(state, wid: str) -> Dict[str, Any]:
    """**作坊（经营记录）**的 P2 字段投影（只读）——规格原文是「建筑/经营记录」，
    而**作坊才是经营记录**（M96 补）。

    能算的：地点（键名/`route_of_workshop`）· `owner`（M66）· `recipe` · 产出维（`output_dim`）
    · 经营方式（M92 由 owner 派生）· 经营者（首期＝owner）；**不能算的如实 `undefined`**
    （蓝图/完工月/维护责任/生产方法/岗位容量与实到/投入产出库存/收入去向）——不臆造。
    """
    ws = getattr(state, "workshops", None)
    row = (ws or {}).get(wid) if isinstance(ws, dict) else None
    if not isinstance(row, dict):
        return {"wid": wid, "fields": {}, "reason": "作坊不存在（缺失≠0）"}
    try:
        from core.domains.economy.building_owner import derive_operation_mode, derive_operator
    except Exception:                                       # noqa: BLE001
        derive_operation_mode = derive_operator = lambda _o: None    # type: ignore
    owner = row.get("owner") or row.get("owner_ref")
    route = None
    try:
        from core.domains.economy.seat_goods_readout import route_of_workshop
        route = route_of_workshop(state, wid)
    except Exception:                                       # noqa: BLE001
        log.warning("entity_projection: 作坊路名不可用 wid=%s", wid, exc_info=True)

    def _def(value, source, reason=None):
        return {"value": value, "defined": value is not None, "source": source, "reason": reason}

    def _undef(reason, source="（无）"):
        return {"value": None, "defined": False, "source": source, "reason": reason}

    fields = {
        "blueprint": _undef("无「蓝图版本」字段（作坊只有名称/配方/产出）"),
        "seat": _def(route, "seat_goods_readout.route_of_workshop（键名含路名）",
                     None if route else "判不出所属路（不臆造地点）"),
        "level": _undef("作坊无等级字段（等级在建筑上）"),
        "completed_month": _undef("无完工月字段"),
        "owner": _def(owner, "M66 `workshops[wid].owner`（既有词表）",
                      None if owner else "未登记货主（M66 迁移未覆盖）"),
        "operator": _def(derive_operator(owner), "building_owner.derive_operator（M92：首期＝owner）",
                         None if owner else "无 owner ⇒ 经营者不可定义"),
        "maintenance": _def(derive_operator(owner),
                            "M104（Jev 甲 0.907）：**首期维护责任＝与 owner 同责**；维护费参数在 `content` constants",
                            None if owner else "无 owner ⇒ 维护责任不可定义（缺失≠0）"),
        "operation_mode": _def(derive_operation_mode(owner),
                               "building_owner.derive_operation_mode（M92 口径单点）",
                               None if owner else "无 owner 前缀可派生"),
        "methods": _undef("无可选生产方法字段"),
        "jobs_capacity": _undef("作坊**不在 `JOBS_PER_LEVEL`**（M67：作坊岗位数无权威来源）"),
        "jobs_filled": _undef("同上（M67）——**不按人口均分、不默认满员**"),
        "recipe": _def(row.get("recipe"), "`workshops[wid].recipe`（原料消耗）"),
        "io_stock": _undef("作坊的投入/产出**不单独分栏**：原料/成品由 POP 持有（治所级 `goods`）或入 "
                           "`resources`/工匠 `goods` 池 ⇒ **查持有方**用 `seat_goods_readout.route_of_workshop` "
                           "定路后看该路治所真账（**不臆造作坊库存**）"),
        "income_to": _undef("利润归主未接（营运资金来源待口径，见 M71）"),
    }
    undefined = [k for k in FIELDS if not (fields.get(k) or {}).get("defined")]
    return {"wid": wid, "route": route, "fields": fields, "undefined_fields": undefined,
            "defined_count": len(FIELDS) - len(undefined), "field_count": len(FIELDS),
            "note": "作坊＝**经营记录**（规格原文「建筑/经营记录」）；能算的算，其余如实 undefined"}


def survey_workshop_projection(state, top: int = 8) -> Dict[str, Any]:
    """全图作坊投影汇总（只读）：作坊数 + **逐字段可定义率**（与建筑投影分列）。"""
    ws = getattr(state, "workshops", None)
    if not isinstance(ws, dict):
        return {"reason": "无 workshops", "workshops": 0}
    defined = {k: 0 for k in FIELDS}
    total = 0
    rows = []
    for wid in ws:
        rep = project_workshop(state, wid)
        if not rep.get("fields"):
            continue
        total += 1
        for k in FIELDS:
            if (rep["fields"].get(k) or {}).get("defined"):
                defined[k] += 1
        if len(rows) < top:
            rows.append({"wid": wid, "route": rep.get("route"),
                         "defined_count": rep.get("defined_count")})
    return {"workshops": total, "rows": rows, "defined_by_field": defined,
            "defined_ratio": {k: (None if not total else round(v / total, 4))
                              for k, v in defined.items()},
            "note": "作坊（经营记录）字段就绪度；与建筑投影**分列**（两类实体）"}


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
