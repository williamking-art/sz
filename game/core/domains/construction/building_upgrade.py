# -*- coding: utf-8 -*-
"""V3 风格**建筑分级升级**（2026-10-19）。

V3 里建筑有等级、每级一份产能，升级要建材 + 工钱 + 工期（建造部门限流）。
《宋祚》现状：`buildings` 条目**已有等级形态**（标量 / `{"lv": n}`，见 `building_bridge`），
缺的是**升级机制**与**产出倍率**——本模块补这两块。

纪律：
- 写等级只走 `building_bridge.building_add`（真账在治所，路级是 Σ 镜像）；
- 建材从官仓扣、银从**地方府库**扣，并登记库存流水（否则恒等式残差）；
- 工期以月计，`advance_building_construction` 每月推进（队列空 ⇒ 无操作，零行为变更）；
- 等级上限、同路在建上限、建材不足 ⇒ 明确 `reason`（不静默）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = ["level_multiplier", "upgrade_requirement", "start_upgrade",
           "advance_building_construction", "construction_readout"]


def level_multiplier(level: Optional[int]) -> float:
    """等级 → 产出倍率：`1 + (level-1) × BONUS`（≤1 视为 1.0；缺失 ⇒ 1.0 并标注）。"""
    from content.data_constants import BUILDING_LEVEL_OUTPUT_BONUS

    if not isinstance(level, int) or level <= 1:
        return 1.0
    return 1.0 + float(BUILDING_LEVEL_OUTPUT_BONUS) * (level - 1)


def _queue(state) -> list:
    q = getattr(state, "building_construction", None)
    if not isinstance(q, list):
        q = []
        state.building_construction = q
    return q


def _req_for(target_level: int) -> Dict[str, Any]:
    from content.data_constants import BUILDING_UPGRADE_REQ

    req = (BUILDING_UPGRADE_REQ or {})
    if not req:
        return {}
    lv = max(int(target_level), min(int(k) for k in req))
    lv = min(lv, max(int(k) for k in req))
    return dict(req.get(lv) or {})


def upgrade_requirement(state, route: str, name: str) -> Dict[str, Any]:
    """查升级条件：当前等级 / 目标等级 / 费用 / 能否升级 + reason。"""
    from content.data_constants import BUILDING_CONSTRUCTION_MAX_PER_ROUTE, BUILDING_LEVEL_MAX
    from core.foundation.ledger.building_bridge import building_level, is_sunk

    pdata = (getattr(state, "prefectures", None) or {}).get(route) or {}
    cur = building_level(state, route, name)
    if cur is None:
        # 未下沉：退回路级镜像口径（只读）
        from core.foundation.ledger.building_bridge import norm_level
        cur = norm_level((pdata.get("buildings") or {}).get(name))
    if cur is None or cur <= 0:
        return {"ok": False, "reason": "building_missing", "route": route, "name": name}
    target = int(cur) + 1
    if target > int(BUILDING_LEVEL_MAX):
        return {"ok": False, "reason": "level_max", "level": cur, "route": route, "name": name}
    pending = [x for x in _queue(state) if x.get("route") == route]
    if len(pending) >= int(BUILDING_CONSTRUCTION_MAX_PER_ROUTE or 1):
        return {"ok": False, "reason": "route_busy", "level": cur, "pending": len(pending)}
    if any(x.get("route") == route and x.get("name") == name for x in _queue(state)):
        return {"ok": False, "reason": "already_queued", "level": cur}
    req = _req_for(target)
    treasury = int(pdata.get("local_treasury", 0) or 0)
    silver = int(req.get("银") or 0)
    if treasury < silver:
        return {"ok": False, "reason": "insufficient_silver", "needed": silver,
                "available": treasury, "level": cur}
    mats = {k: v for k, v in req.items() if k not in ("银", "months")}
    for dim, need in mats.items():
        have = int(((getattr(state, "resources", {}) or {}).get(dim) or {}).get("stock") or 0)
        if have < int(need):
            return {"ok": False, "reason": f"insufficient_{dim}", "needed": int(need),
                    "available": have, "level": cur}
    return {"ok": True, "reason": None, "level": int(cur), "target_level": target,
            "materials": mats, "silver": silver, "months": int(req.get("months") or 3)}


def start_upgrade(state, route: str, name: str) -> Dict[str, Any]:
    """扣建材 + 银，登记在建（**写点全走桥/流水**）；失败给 reason。"""
    from core.domains.economy import stock_flow as _sf
    from core.foundation.ledger.material_holding import stock_adjust

    req = upgrade_requirement(state, route, name)
    if not req.get("ok"):
        return req
    pdata = (getattr(state, "prefectures", None) or {}).get(route) or {}
    for dim, need in (req.get("materials") or {}).items():
        if stock_adjust(state, dim, -float(need)) is None:
            return {"ok": False, "reason": f"stock_write_failed_{dim}"}
        try:
            _sf.record_out(state, dim, int(need), "建筑升级")
        except Exception as exc:  # noqa: BLE001
            import logging as _lg
            _lg.getLogger(__name__).warning("建筑升级库存流水登记失败：%r", exc, exc_info=True)
    pdata["local_treasury"] = int(pdata.get("local_treasury", 0) or 0) - int(req.get("silver") or 0)
    item = {"route": route, "name": name, "seat": None,
            "months_left": int(req.get("months") or 3),
            "target_level": int(req.get("target_level") or 0)}
    _queue(state).append(item)
    return {"ok": True, **item}


def advance_building_construction(state) -> List[Dict[str, Any]]:
    """每月推进：到期 ⇒ 等级 +1（走 `building_bridge.building_add`），返回完工项。"""
    from core.foundation.ledger.building_bridge import building_add

    done: List[Dict[str, Any]] = []
    keep: List[Dict[str, Any]] = []
    for item in _queue(state):
        item["months_left"] = int(item.get("months_left") or 0) - 1
        if item["months_left"] > 0:
            keep.append(item)
            continue
        route, name = item.get("route"), item.get("name")
        new_lv = building_add(state, route, name, 1)
        if new_lv is None:
            # 未下沉（当前建筑真账仍在路级）⇒ 回落原写法：保形态 +1，不引入新字段
            from core.foundation.ledger.building_bridge import norm_level
            pdata = (getattr(state, "prefectures", None) or {}).get(route) or {}
            bmap = pdata.get("buildings")
            if not isinstance(bmap, dict):
                bmap = {}
                pdata["buildings"] = bmap
            entry = bmap.get(name)
            cur = norm_level(entry) or 0
            if isinstance(entry, dict):
                entry["lv"] = int(cur) + 1
                new_lv = int(cur) + 1
            else:
                bmap[name] = int(cur) + 1
                new_lv = int(cur) + 1
        done.append({"route": route, "name": name, "level": new_lv,
                     "target_level": item.get("target_level")})
    state.building_construction = keep
    log = getattr(state, "building_upgrades_done", None)
    if not isinstance(log, list):
        log = []
        state.building_upgrades_done = log
    log.extend(done)
    return done


def construction_readout(state) -> Dict[str, Any]:
    """读数：在建队列 + 已完成历史 + 等级→倍率说明（只读）。"""
    return {"queue": list(getattr(state, "building_construction", None) or []),
            "done": list(getattr(state, "building_upgrades_done", None) or []),
            "queue_len": len(getattr(state, "building_construction", None) or []),
            "note": "等级倍率 = 1 + (level-1) × BUILDING_LEVEL_OUTPUT_BONUS"}