# -*- coding: utf-8 -*-
"""舆图运行期 overlay 读数（M3，2026-10-19）。

原则（设计稿 §15.3）：**底图静态、归属运行期**。
本模块只读 `state.regions` 派生 overlay；**不重建 geojson/topojson**、不写 state。

输出给前端：
```text
[{region_id, level, name, owner, parent, occupied, transition, owner_changed}, ...]
```
- `occupied`：owner != 本朝（当前恒以「宋」为本朝）；
- `transition`：`transition_until` 未到期（税/产打折期）；
- `owner_changed`：与 `REGIME_GEO` 静态 owner 不同（占领/更替）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = ["map_overlay", "overlay_summary"]


def _current_month(state) -> Optional[int]:
    try:
        from core.civil_building import abs_month_index
        return abs_month_index(state)
    except Exception:  # noqa: BLE001
        return None


def map_overlay(state, *, player_regime: str = "宋") -> List[Dict[str, Any]]:
    """按 `state.regions` 生成 overlay 行（只读）。"""
    from content.geo_admin import REGIME_GEO

    book = getattr(state, "regions", None)
    if not isinstance(book, dict):
        return []
    now = _current_month(state)
    rows: List[Dict[str, Any]] = []
    for rid, r in book.items():
        if not isinstance(r, dict):
            continue
        owner = r.get("owner")
        # 静态归属：优先用 region 上的 `owner_at_init`（建表时快照）；旧数据退回 REGIME_GEO
        static_owner = r.get("owner_at_init") or ((REGIME_GEO.get(owner) or {}).get("owner"))
        until = r.get("transition_until")
        in_transition = bool(now is not None and isinstance(until, int) and until > now)
        rows.append({
            "region_id": rid,
            "level": r.get("level"),
            "name": r.get("name"),
            "owner": owner,
            "parent": r.get("parent"),
            "occupied": bool(owner and owner != player_regime),
            "transition": in_transition,
            "transition_until": until,
            "owner_changed": bool(static_owner and owner and static_owner != owner),
        })
    return rows


def overlay_summary(state, *, player_regime: str = "宋") -> Dict[str, Any]:
    rows = map_overlay(state, player_regime=player_regime)
    by_level: Dict[str, int] = {}
    owners: Dict[str, int] = {}
    for r in rows:
        by_level[r["level"]] = by_level.get(r["level"], 0) + 1
        owners[r["owner"]] = owners.get(r["owner"], 0) + 1
    return {"total": len(rows), "by_level": by_level, "by_owner": owners,
            "transition": sum(1 for r in rows if r["transition"]),
            "owner_changed": sum(1 for r in rows if r["owner_changed"]),
            "occupied": sum(1 for r in rows if r["occupied"])}