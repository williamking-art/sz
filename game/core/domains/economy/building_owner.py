# -*- coding: utf-8 -*-
"""建筑**归属（P2 第一片）**：`building_meta` 幂等登记（保形态、零数值变化） —— M91。

依据：M90《P2 建筑实例字段落地设计》+ Jev 放行。
🔴 **保形态**：`buildings = {建筑名: 等级}` **一字不动**；并列新增
`prefectures[路].seats[治所].building_meta = {建筑名: {"owner": <id>, "owner_basis": <依据>}}`。
**它不是账本**（不含存量/金额）⇒ 不违反「不新增与 POP 平行的账本」。

归属规则（**逐条给依据**；未登记者**留 `undefined`**，不按人口/等级摊派）
------------------------------------------------------------------------
* `水利`／`常平仓` ⇒ `local:<路>`（**官府兴办**：水利为官办工程、常平仓为官仓平粜）；
* 其余建筑类型**未登记** ⇒ `undefined` + reason ⇒ 待逐类型给依据后再补表。

纪律：幂等（只填缺失）· 判不出归属**跳过并计数** · `load_game` 失败**不拒档** ·
**首期零数值变化**（本字段不被任何结算读取）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

#: 治所真账里承载**建筑归属**的键名（与 `"buildings"` 并列；**不是**账本）
META_KEY = "building_meta"

#: 建筑类型 → `(owner_kind, 依据)`；**未登记 ⇒ 不写**（留 undefined）
OWNER_BY_TYPE: Dict[str, tuple] = {
    "水利": ("local", "官府兴办工程（非民业）"),
    "常平仓": ("local", "官仓：平粜/常平为官府职能（M40a 已州府化）"),
}

__all__ = ["META_KEY", "OWNER_BY_TYPE", "owner_for", "assign_building_owners",
           "survey_building_owners"]


def _seats(state, route: str) -> Optional[dict]:
    prefs = getattr(state, "prefectures", None)
    pdata = (prefs or {}).get(route) if isinstance(prefs, dict) else None
    seats = (pdata or {}).get("seats") if isinstance(pdata, dict) else None
    return seats if isinstance(seats, dict) else None


def owner_for(route: str, building: str) -> Dict[str, Any]:
    """解析该路该建筑的货主（只读）：`{defined, owner, reason}`。未登记类型 ⇒ `defined=False`。"""
    rule = OWNER_BY_TYPE.get(str(building))
    if rule is None:
        return {"defined": False, "owner": None,
                "reason": f"建筑类型 {building!r} **未登记归属规则** ⇒ 不臆造（须先给依据并补表）"}
    kind, basis = rule
    owner = f"local:{route}" if kind == "local" else None
    if owner is None:
        return {"defined": False, "owner": None, "reason": f"规则形态未支持：{kind!r}"}
    return {"defined": True, "owner": owner, "basis": basis, "owner_kind": kind}


def assign_building_owners(state) -> Dict[str, Any]:
    """**幂等迁移**：给缺失归属的建筑补 `building_meta[建筑]["owner"]`。

    只填缺失（**不覆盖**已有值）；未登记类型**跳过并计数**（不臆造）；**零数值变化**。
    """
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return {"assigned": 0, "kept": 0, "undefined": 0, "reason": "无 prefectures"}
    assigned = kept = undefined = 0
    samples = []
    for route, pdata in prefs.items():
        seats = (pdata or {}).get("seats") if isinstance(pdata, dict) else None
        if not isinstance(seats, dict):
            continue
        for seat, srow in seats.items():
            if not isinstance(srow, dict):
                continue
            buildings = srow.get("buildings")
            if not isinstance(buildings, dict):
                continue
            meta = srow.setdefault(META_KEY, {})
            if not isinstance(meta, dict):                  # 脏数据 ⇒ 不覆盖，跳过
                undefined += len(buildings)
                continue
            for b in buildings:
                entry = meta.get(b)
                if isinstance(entry, dict) and entry.get("owner"):
                    kept += 1
                    continue
                rep = owner_for(route, b)
                if not rep["defined"]:
                    undefined += 1
                    if len(samples) < 5:
                        samples.append({"route": route, "seat": seat, "building": b,
                                        "reason": rep["reason"]})
                    continue
                meta.setdefault(b, {})
                meta[b]["owner"] = rep["owner"]
                meta[b]["owner_kind"] = rep.get("owner_kind")
                meta[b]["owner_basis"] = rep.get("basis")
                assigned += 1
    return {"assigned": assigned, "kept": kept, "undefined": undefined,
            "undefined_samples": samples,
            "note": ("只填缺失、不覆盖；未登记类型跳过（不臆造）；"
                     f"**不是账本**（`{META_KEY}` 只放归属元数据，不含存量/金额）")}


def survey_building_owners(state) -> Dict[str, Any]:
    """只读对账：建筑总数、已登记/缺失/未登记规则计数（**不写 state**）。"""
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return {"total": 0, "reason": "无 prefectures"}
    total = with_owner = missing = undef_rule = 0
    for route, pdata in prefs.items():
        seats = (pdata or {}).get("seats") if isinstance(pdata, dict) else None
        if not isinstance(seats, dict):
            continue
        for srow in seats.values():
            if not isinstance(srow, dict):
                continue
            buildings = srow.get("buildings")
            if not isinstance(buildings, dict):
                continue
            meta = srow.get(META_KEY) if isinstance(srow.get(META_KEY), dict) else {}
            for b in buildings:
                total += 1
                entry = meta.get(b) if isinstance(meta, dict) else None
                if isinstance(entry, dict) and entry.get("owner"):
                    with_owner += 1
                elif owner_for(route, b)["defined"]:
                    missing += 1
                else:
                    undef_rule += 1
    return {"total": total, "with_owner": with_owner, "missing": missing,
            "undefined_rule": undef_rule}
