# -*- coding: utf-8 -*-
"""政权归属变更（P5，2026-10-19）。

设计稿 §7：**只改 owner 与 territory**；人口/土地/建筑/详账**一律不动**；
政权字段（treasury/armies/tech/attitude）**不随地域走**。

```text
transfer_regions(state, from_regime, to_regime, region_ids)
  T2 传入 ⇒ 级联其 T1 子块（默认 cascade=True）
  T1 传入 ⇒ 挂到 to 的同名 T2（无则新建 `to` 的 T2，parent 单点）
  历史 ⇒ state.region_changes 追加（可逆向重放）
```

用于：金登场接管辽地、金南下占宋地、和议归还（反向调用）。
"""
from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional

__all__ = ["transfer_regions", "regime_territory", "revert_change", "transfer_summary"]


def _now_month(state) -> Optional[int]:
    try:
        from core.civil_building import abs_month_index
        return int(abs_month_index(state))
    except Exception:  # noqa: BLE001
        return None


def regime_territory(state, regime: str) -> List[str]:
    """政权当前 territory（region_id 列表，惰性由 regions 反推并回写）。"""
    info = (getattr(state, "external_regimes", None) or {}).get(regime)
    book = getattr(state, "regions", None) or {}
    if isinstance(info, dict) and isinstance(info.get("territory"), list):
        return list(info["territory"])
    ids = [rid for rid, r in book.items() if isinstance(r, dict) and r.get("owner") == regime]
    if isinstance(info, dict):
        info["territory"] = ids
    return ids


def _ensure_regime(state, regime: str) -> Dict[str, Any]:
    """确保政权存在（**新建时政权字段从零起，不继承任何 treasury**）。"""
    regimes = getattr(state, "external_regimes", None)
    if not isinstance(regimes, dict):
        regimes = {}
        state.external_regimes = regimes
    info = regimes.get(regime)
    if not isinstance(info, dict):
        info = {"name": regime, "type": "政权", "power": "中", "attitude": 50,
                "population": 0, "pop": {}, "provinces": [], "armies": [],
                "treasury": 0, "tech": {}, "land": 0, "grain": 0, "storage": 0,
                "territory": [], "note": "P5 由 transfer_regions 新建（政权字段从零起）"}
        regimes[regime] = info
    if not isinstance(info.get("territory"), list):
        info["territory"] = [rid for rid, r in (getattr(state, "regions", None) or {}).items()
                             if isinstance(r, dict) and r.get("owner") == regime]
    return info


def _pick_t2_for(state, owner: str, t1: Dict[str, Any]) -> str:
    """给 T1 找 `owner` 名下合适的 T2：同名 map_province 优先，否则任意 T2，再否则新建。"""
    book = state.regions
    mp = t1.get("map_province")
    for rid, r in book.items():
        if (isinstance(r, dict) and r.get("level") == "T2"
                and r.get("owner") == owner and mp and r.get("name") == mp):
            return rid
    for rid, r in book.items():
        if isinstance(r, dict) and r.get("level") == "T2" and r.get("owner") == owner:
            return rid
    pid = "%s_t2_%s" % (owner, mp or "新省")
    book[pid] = {"level": "T2", "name": mp or ("%s治下" % owner), "kind": "省",
                 "owner": owner, "parent": owner, "pop": None, "land": None,
                 "map_provinces": [mp] if mp else [], "note": "P5 因 T1 改属而新建"}
    return pid


def transfer_regions(state, from_regime: str, to_regime: str,
                     region_ids: Iterable[str], *, cascade: bool = True,
                     create_to: bool = True, reason: str = "") -> Dict[str, Any]:
    """把地域从 `from_regime` 转给 `to_regime`（**只改 owner**）。

    返回 `{ok, moved, cascaded, created_t2, change_id, reason}`。
    """
    book = getattr(state, "regions", None)
    if not isinstance(book, dict) or not book:
        return {"ok": False, "reason": "regions 未初始化"}
    ids = [str(x) for x in region_ids]
    bad = [rid for rid in ids if not isinstance(book.get(rid), dict)]
    if bad:
        return {"ok": False, "reason": "region 不存在：%s" % bad[:5]}
    wrong = [rid for rid in ids if book[rid].get("owner") != from_regime]
    if wrong:
        return {"ok": False, "reason": "owner 不是 %s：%s" % (from_regime, wrong[:5])}
    if create_to:
        _ensure_regime(state, to_regime)
    elif to_regime not in (getattr(state, "external_regimes", None) or {}):
        return {"ok": False, "reason": "目标政权不存在：%s" % to_regime}

    moved: List[str] = []
    created_t2: List[str] = []
    for rid in ids:
        r = book[rid]
        r["owner"] = to_regime
        moved.append(rid)
        if cascade and r.get("level") == "T2":
            for cid, child in book.items():
                if (isinstance(child, dict) and child.get("parent") == rid
                        and child.get("owner") == from_regime):
                    child["owner"] = to_regime
                    moved.append(cid)
        if r.get("level") == "T1":
            parent = book.get(str(r.get("parent") or ""))
            if not isinstance(parent, dict) or parent.get("owner") != to_regime:
                pid = _pick_t2_for(state, to_regime, r)
                if pid not in created_t2 and pid not in book:
                    created_t2.append(pid)
                r["parent"] = pid

    from_info = _ensure_regime(state, from_regime)
    to_info = _ensure_regime(state, to_regime)
    from_info["territory"] = [x for x in from_info.get("territory", []) if x not in moved]
    to_ter = list(to_info.get("territory", []))
    to_info["territory"] = sorted(set(to_ter) | set(moved))

    month = _now_month(state)
    change = {"change_id": "rc_%d_%s" % (int(time.time() * 1000), to_regime),
              "op": "transfer", "from": from_regime, "to": to_regime,
              "region_ids": moved, "month": month, "reason": reason,
              "reversible": True}
    if not isinstance(getattr(state, "region_changes", None), list):
        state.region_changes = []
    state.region_changes.append(change)
    return {"ok": True, "moved": moved, "cascaded": len(moved) - len(ids),
            "created_t2": created_t2,
            "change_id": change["change_id"], "reason": reason}


def revert_change(state, change_id: str) -> Dict[str, Any]:
    """撤销一条 transfer（和议归还 / 回档）。"""
    changes = getattr(state, "region_changes", None) or []
    hit = next((c for c in changes if isinstance(c, dict) and c.get("change_id") == change_id), None)
    if not hit:
        return {"ok": False, "reason": "change 不存在：%s" % change_id}
    if hit.get("op") != "transfer":
        return {"ok": False, "reason": "只支持撤销 transfer"}
    out = transfer_regions(state, hit.get("to"), hit.get("from"), hit.get("region_ids") or [],
                           reason="revert:%s" % change_id)
    if out.get("ok"):
        hit["reverted"] = True
    return out


def transfer_summary(state) -> Dict[str, Any]:
    changes = [c for c in (getattr(state, "region_changes", None) or [])
               if isinstance(c, dict) and c.get("op") == "transfer"]
    return {"transfers": len(changes),
            "reverted": sum(1 for c in changes if c.get("reverted")),
            "regimes_touched": sorted({c.get("to") for c in changes if c.get("to")})}