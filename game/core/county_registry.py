# -*- coding: utf-8 -*-
"""县制记忆库登记（2026-10-19）。

游戏没有独立县席位表；县治/县官统一写进 MemoryGraph：
- 县实体 `etype="county"`，attrs 带 `posts/quotas/parent_seat_id/route/tier`；
- 县官实体 `etype="minister"`，用 `governs` 关系挂到县；
- 县 → 父州府用 `belongs_to` 关系；
- 不新增顶层 `state.*`，随 MemoryGraph 存档往返。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = [
    "COUNTY_POSTS", "county_eid", "ensure_county_establishment",
    "assign_county_official", "county_officials", "county_of_official",
]

#: 简化县制编制（宋制县有赤/畿/望/紧/上/中/下；这里先做统一模板，tier 记档）
COUNTY_POSTS = (
    {"title": "知县", "quota": 1, "rank": "从八品"},
    {"title": "县丞", "quota": 1, "rank": "从八品"},
    {"title": "主簿", "quota": 1, "rank": "从九品"},
    {"title": "县尉", "quota": 1, "rank": "从九品"},
)


def county_eid(county_name: str) -> str:
    return "county:" + str(county_name or "").strip()


def _has_relation(mem, src: str, dst: str, rtype: str) -> bool:
    for r in getattr(mem, "relations", []) or []:
        if r.get("src") == src and r.get("dst") == dst and r.get("rtype") == rtype:
            return True
    return False


def _resolve_agent(mem, actor: str) -> str:
    """人名 → 记忆库实体 eid（兼容 eid=人名 / minister_人名）。"""
    name = str(actor or "").strip()
    ents = getattr(mem, "entities", {}) or {}
    if name in ents:
        return name
    for eid, ent in ents.items():
        if isinstance(ent, dict) and str(ent.get("name") or "") == name:
            return str(eid)
    return name


def ensure_county_establishment(
    mem,
    county_name: str,
    *,
    route: Optional[str] = None,
    parent_seat_id: Optional[str] = None,
    turn: int = 0,
    tier: str = "中县",
) -> Optional[str]:
    """幂等写入县实体（含编制/父州府）；返回县 eid。"""
    name = str(county_name or "").strip()
    if not name:
        return None
    eid = county_eid(name)
    attrs = {
        "posts": [p["title"] for p in COUNTY_POSTS],
        "quotas": {p["title"]: int(p["quota"]) for p in COUNTY_POSTS},
        "establishment": [dict(p) for p in COUNTY_POSTS],
        "route": route,
        "parent_seat_id": parent_seat_id,
        "tier": tier,
        "source": "county_registry",
    }
    existing = getattr(mem, "entities", {}).get(eid)
    if isinstance(existing, dict) and existing.get("type") == "county":
        cur = existing.setdefault("attrs", {})
        for k, v in attrs.items():
            if v is not None:
                cur[k] = v
    else:
        mem.add_entity(eid, "county", name, attrs=attrs, turn=turn)
    if parent_seat_id and not _has_relation(mem, eid, str(parent_seat_id), "belongs_to"):
        mem.add_relation(eid, str(parent_seat_id), "belongs_to",
                         turn=turn, note="县隶州府")
    return eid


def assign_county_official(
    mem,
    official_name: str,
    county_name: str,
    *,
    post: str = "知县",
    route: Optional[str] = None,
    parent_seat_id: Optional[str] = None,
    turn: int = 0,
) -> Optional[str]:
    """把县官挂到县（governs），幂等；返回县 eid。"""
    name = str(official_name or "").strip()
    if not name:
        return None
    src = _resolve_agent(mem, name)
    eid = ensure_county_establishment(
        mem, county_name, route=route, parent_seat_id=parent_seat_id, turn=turn)
    if eid and not _has_relation(mem, src, eid, "governs"):
        mem.add_relation(src, eid, "governs", turn=turn, note=f"任{post}")
    return eid


def county_officials(mem, county_name: str) -> List[Dict[str, Any]]:
    """从记忆库取某县在任县官（governs 关系）。"""
    eid = county_eid(county_name)
    out: List[Dict[str, Any]] = []
    for r in getattr(mem, "relations", []) or []:
        if r.get("archived") or r.get("rtype") != "governs":
            continue
        if r.get("dst") != eid:
            continue
        ent = (getattr(mem, "entities", {}) or {}).get(r.get("src"))
        if isinstance(ent, dict) and ent.get("type") == "minister":
            out.append(ent)
    return out


def county_of_official(mem, official_name: str) -> Optional[str]:
    """反查某官员所治县名（governs 关系）。"""
    name = str(official_name or "").strip()
    src = _resolve_agent(mem, name)
    for r in getattr(mem, "relations", []) or []:
        if r.get("archived") or r.get("rtype") != "governs" or r.get("src") != src:
            continue
        dst = str(r.get("dst") or "")
        if dst.startswith("county:"):
            return dst[len("county:"):]
    return None

