# -*- coding: utf-8 -*-
"""行政区划调整（P7，2026-10-19）。

设计稿 §6：改隶 / 分省 / 合省 / 改治改级改名。
owner（归属政权）与 parent（行政上级）分离——本模块只动 parent/level/name，
**不动 owner**（跨政权只能走 regime_transfer）。

成本：府库银 + 民众满意度 + 吏治阻力（记读数）+ 过渡期（税产打折，只作用一次）。
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

__all__ = ["can_redivide", "redivide_regions", "undo_redivision",
           "redivision_history", "REDIVIDE_COST_PER_SEAT",
           "REDIVIDE_TRANSITION_MONTHS", "PROVINCE_MIN_SEATS", "PROVINCE_MAX_SEATS"]

REDIVIDE_COST_PER_SEAT = 2000
REDIVIDE_TRANSITION_MONTHS = {"transfer_seat": 3, "split_province": 6,
                              "merge_provinces": 6, "retype": 3}
PROVINCE_MIN_SEATS = 2
PROVINCE_MAX_SEATS = 12


def _now_month(state) -> Optional[int]:
    try:
        from core.civil_building import abs_month_index
        return int(abs_month_index(state))
    except Exception:  # noqa: BLE001
        return None


def _children(state, pid: str) -> List[str]:
    book = getattr(state, "regions", None) or {}
    return [rid for rid, r in book.items()
            if isinstance(r, dict) and r.get("level") == "T1" and r.get("parent") == pid]


def _owner_of(state, rid: str) -> Optional[str]:
    r = (getattr(state, "regions", None) or {}).get(rid)
    return r.get("owner") if isinstance(r, dict) else None


def _cost(state, op: str, n_seats: int) -> int:
    base = REDIVIDE_COST_PER_SEAT * max(1, int(n_seats))
    if op in ("split_province", "merge_provinces"):
        base = int(base * 1.5)
    return base


def can_redivide(state, op: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """预检（**不动任何状态**）。"""
    book = getattr(state, "regions", None)
    if not isinstance(book, dict) or not book:
        return {"ok": False, "reason": "regions 未初始化"}
    op = str(op)
    if op not in REDIVIDE_TRANSITION_MONTHS:
        return {"ok": False, "reason": "未知操作：%s" % op}
    if op == "transfer_seat":
        seat, to_pid = str(params.get("seat") or ""), str(params.get("to_province") or "")
        r, tgt = book.get(seat), book.get(to_pid)
        if not isinstance(r, dict) or r.get("level") != "T1":
            return {"ok": False, "reason": "不是 T1：%s" % seat}
        if not isinstance(tgt, dict) or tgt.get("level") != "T2":
            return {"ok": False, "reason": "目标省不存在：%s" % to_pid}
        if r.get("owner") != tgt.get("owner"):
            return {"ok": False, "reason": "不得跨政权改隶（请走 regime_transfer）"}
        src = str(r.get("parent") or "")
        if src == to_pid:
            return {"ok": False, "reason": "已在该省"}
        if len(_children(state, src)) <= PROVINCE_MIN_SEATS:
            return {"ok": False, "reason": "源省州府将少于 %d 个" % PROVINCE_MIN_SEATS}
        if len(_children(state, to_pid)) >= PROVINCE_MAX_SEATS:
            return {"ok": False, "reason": "目标省已满 %d 个州府" % PROVINCE_MAX_SEATS}
        n = 1
    elif op == "split_province":
        src = str(params.get("province") or "")
        seats = list(params.get("seats") or [])
        if not isinstance(book.get(src), dict) or book[src].get("level") != "T2":
            return {"ok": False, "reason": "省不存在：%s" % src}
        kids = _children(state, src)
        bad = [s for s in seats if s not in kids]
        if bad:
            return {"ok": False, "reason": "州府不属该省：%s" % bad[:3]}
        if len(seats) < PROVINCE_MIN_SEATS:
            return {"ok": False, "reason": "新省至少 %d 个州府" % PROVINCE_MIN_SEATS}
        if len(kids) - len(seats) < PROVINCE_MIN_SEATS:
            return {"ok": False, "reason": "原省须保留至少 %d 个州府" % PROVINCE_MIN_SEATS}
        n = len(seats)
    elif op == "merge_provinces":
        a = str(params.get("from_province") or "")
        b = str(params.get("into_province") or "")
        ra, rb = book.get(a), book.get(b)
        if not isinstance(ra, dict) or not isinstance(rb, dict):
            return {"ok": False, "reason": "省不存在"}
        if ra.get("owner") != rb.get("owner"):
            return {"ok": False, "reason": "不得跨政权合省"}
        total = len(_children(state, a)) + len(_children(state, b))
        if total > PROVINCE_MAX_SEATS:
            return {"ok": False, "reason": "合并后超上限 %d" % PROVINCE_MAX_SEATS}
        n = total
    else:
        rid = str(params.get("region") or "")
        if not isinstance(book.get(rid), dict):
            return {"ok": False, "reason": "region 不存在：%s" % rid}
        n = 1
    cost = _cost(state, op, n)
    hint = "巨" if n >= 6 else ("大" if n >= 4 else ("中" if n >= 2 else "小"))
    return {"ok": True, "cost": cost, "resistance_hint": hint}


def _deduct_cost(state, owner: str, amount: int) -> Optional[int]:
    if amount <= 0:
        return 0
    prefs = getattr(state, "prefectures", None) or {}
    if owner == "宋" and prefs:
        # 复审补丁（2026-10-20）：余额判断与扣款都必须以**治所真账**为准。
        # 路级 `local_treasury` 是派生镜像，旧档/直写可能滞后；镜像高于真账时
        # 原写法会返回"已付"但实际只扣到治所能扣的部分（差额＝凭空造币）。
        from core.foundation.ledger import local_treasury_bridge as _ltb

        def _seat_or_mirror(p, mirror):
            _seat = _ltb.seat_local_treasury_total(p)
            return int(_seat) if _seat is not None else int(mirror)

        pool = sum(_seat_or_mirror(p or {}, (p or {}).get("local_treasury", 0))
                   for p in prefs.values())
        if pool < amount:
            return None
        left = amount
        for _rname, p in prefs.items():
            mirror = int((p or {}).get("local_treasury", 0) or 0)
            have = _seat_or_mirror(p or {}, mirror)   # 以治所真账为准；镜像只作未下沉回退
            take = min(have, left)
            if take:
                # 地方府库写点走桥（直写镜像会让治所滞后，后续走桥写入校正镜像时
                # 表现为凭空销毁）。未下沉 ⇒ 回落原写法。
                if _ltb.local_treasury_add(state, _rname, -take) is None:
                    p["local_treasury"] = mirror - take
                left -= take
            if left <= 0:
                break
        return amount if left <= 0 else (amount - left)
    info = (getattr(state, "external_regimes", None) or {}).get(owner) or {}
    have = int(info.get("treasury") or 0)
    if have < amount:
        return None
    info["treasury"] = have - amount
    return amount


def redivide_regions(state, op: str, params: Dict[str, Any], *, reason: str = "") -> Dict[str, Any]:
    pre = can_redivide(state, op, params)
    if not pre.get("ok"):
        return {"ok": False, "reason": pre.get("reason")}
    book = state.regions
    op = str(op)
    if op == "transfer_seat":
        owner = _owner_of(state, str(params.get("seat")))
    elif op == "split_province":
        owner = _owner_of(state, str(params.get("province")))
    elif op == "merge_provinces":
        owner = _owner_of(state, str(params.get("from_province")))
    else:
        owner = _owner_of(state, str(params.get("region")))
    paid = _deduct_cost(state, owner or "", int(pre["cost"]))
    if paid is None:
        return {"ok": False, "reason": "行政成本不足（需 %d）" % int(pre["cost"])}
    now = _now_month(state)
    months = REDIVIDE_TRANSITION_MONTHS[op]
    until = (now + months) if now is not None else None
    moved: List[str] = []
    if op == "transfer_seat":
        seat = str(params.get("seat"))
        to_pid = str(params.get("to_province"))
        book[seat]["parent"] = to_pid
        book[seat]["transition_until"] = until
        moved = [seat]
    elif op == "split_province":
        src = str(params.get("province"))
        seats = list(params.get("seats") or [])
        name = str(params.get("name") or (str(book[src].get("name")) + "分省"))
        pid = "%s_split_%d" % (src, int(time.time() * 1000) % 100000)
        book[pid] = {"level": "T2", "name": name, "kind": "省", "owner": owner,
                     "parent": owner, "pop": None, "land": None,
                     "map_provinces": [], "note": "P7 分省新建",
                     "transition_until": until}
        for s in seats:
            book[s]["parent"] = pid
            book[s]["transition_until"] = until
        moved = list(seats)
        book[src]["transition_until"] = until
    elif op == "merge_provinces":
        a = str(params.get("from_province"))
        b = str(params.get("into_province"))
        moved = list(_children(state, a))
        for s in moved:
            book[s]["parent"] = b
            book[s]["transition_until"] = until
        book[a]["merged_into"] = b
        book[a]["note"] = "P7 已并入 %s" % b
        book[b]["transition_until"] = until
    else:
        rid = str(params.get("region"))
        if params.get("name"):
            book[rid]["name"] = str(params["name"])
        if params.get("level"):
            book[rid]["level"] = str(params["level"])
        book[rid]["transition_until"] = until
        moved = [rid]

    drop = min(3, max(1, len(moved) // 2))
    try:
        state.population_satisfaction = int(getattr(state, "population_satisfaction", 55)) - drop
    except Exception:  # noqa: BLE001
        pass
    if not isinstance(getattr(state, "region_changes", None), list):
        state.region_changes = []
    change = {"change_id": "ra_%d_%s" % (int(time.time() * 1000), op), "op": op,
              "params": dict(params), "owner": owner, "moved": moved,
              "cost": int(pre["cost"]), "satisfaction_delta": -drop,
              "clerks_grip_delta": round(0.01 * len(moved), 4),
              "transition_until": until, "month": now, "reason": reason,
              "reversible": True, "prev": {}}
    for rid in moved:
        change["prev"][rid] = {"parent": book[rid].get("parent"),
                               "level": book[rid].get("level"),
                               "name": book[rid].get("name")}
    state.region_changes.append(change)
    return {"ok": True, "op": op, "moved": moved, "cost": int(pre["cost"]),
            "transition_until": until, "change_id": change["change_id"]}


def undo_redivision(state, change_id: str) -> Dict[str, Any]:
    changes = getattr(state, "region_changes", None) or []
    hit = next((c for c in changes if isinstance(c, dict) and c.get("change_id") == change_id), None)
    if not hit or hit.get("op") not in REDIVIDE_TRANSITION_MONTHS:
        return {"ok": False, "reason": "无法回滚：%s" % change_id}
    book = state.regions
    for rid, prev in (hit.get("prev") or {}).items():
        if rid in book:
            for k, v in prev.items():
                if v is not None:
                    book[rid][k] = v
            book[rid].pop("merged_into", None)
    if hit.get("op") == "split_province":
        pid = next((rid for rid, r in book.items()
                    if isinstance(r, dict) and r.get("note") == "P7 分省新建"
                    and rid not in (hit.get("prev") or {})), None)
        if pid and not _children(state, pid):
            book.pop(pid, None)
    hit["reverted"] = True
    return {"ok": True, "change_id": change_id}


def redivision_history(state) -> List[Dict[str, Any]]:
    return [c for c in (getattr(state, "region_changes", None) or [])
            if isinstance(c, dict) and c.get("op") in REDIVIDE_TRANSITION_MONTHS]
