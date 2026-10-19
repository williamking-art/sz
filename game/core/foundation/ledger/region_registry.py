# -*- coding: utf-8 -*-
"""行政区划注册表（P1 只读骨架，2026-10-19）。

统一归属与层级索引：

```text
state.regions = {
  song_<路>:        {level: T2, name: <路>, owner: 宋, parent: 宋, prefecture_ref: {route}}
  song_<路>_<治所>: {level: T1, name: <治所>, owner: 宋, parent: song_<路>,
                     prefecture_ref: {route, seat}}
  <国>_p<i>:        {level: T2, name: <省名>, owner: <国>, parent: <国>}
  <国>_p<i>_<名>:   {level: T1, name: <州府>, owner: <国>, parent: <国>_p<i>}
}
```

🔴 P1 阶段纪律：
- **只读骨架**：不写人口、不改结算、不动 `prefectures` 详账；
- 宋只存 `prefecture_ref` 指针（详账仍在 `prefectures`）；
- 外邦六国用静态表 `content/data_external_admin.REGIME_SEATS` 铺州府名；
- `init_regions` **幂等**：已有 `regions` 则跳过（返回 created=0）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = ["init_regions", "verify_region_invariants", "region_of", "regions_by_owner",
           "aggregate_by_owner", "REGION_DEPTH_MAX"]

#: 层级深度上限：政权 → 省（T2）→ 州府（T1）
REGION_DEPTH_MAX = 3


def _song_region_id(route: str, seat: Optional[str] = None) -> str:
    base = "song_" + str(route)
    if seat:
        return base + "_" + str(seat).split("|")[-1]
    return base


def init_regions(state) -> Dict[str, Any]:
    """登记宋与外邦六国的行政区划（**幂等、只读**）。

    返回 `{created, song_seats, song_routes, foreign_seats, foreign_provinces}`。
    """
    book = getattr(state, "regions", None)
    if isinstance(book, dict) and book:
        return {"created": 0, "reason": "already", "total": len(book)}
    book: Dict[str, Any] = {}

    song_routes = song_seats = 0
    prefs = getattr(state, "prefectures", None) or {}
    for route, pdata in prefs.items():
        rid = _song_region_id(route)
        book[rid] = {"level": "T2", "name": str(route), "kind": "路", "owner": "宋",
                     "parent": "宋", "prefecture_ref": {"route": route}}
        song_routes += 1
        for seat in ((pdata or {}).get("seats") or {}):
            sid = _song_region_id(route, seat)
            book[sid] = {"level": "T1", "name": str(seat).split("|")[-1], "kind": "州府",
                         "owner": "宋", "parent": rid,
                         "prefecture_ref": {"route": route, "seat": seat},
                         "transition_until": None}
            song_seats += 1

    foreign_seats = foreign_provinces = 0
    regimes = getattr(state, "external_regimes", None) or {}
    try:
        from content.data_external_admin import REGIME_SEATS, REGIME_TIER1
    except Exception:  # noqa: BLE001
        REGIME_SEATS, REGIME_TIER1 = {}, ()
    for name in REGIME_TIER1:
        info = regimes.get(name)
        if not isinstance(info, dict):
            continue
        provinces = info.get("provinces") or []
        seats_map = REGIME_SEATS.get(name) or {}
        for idx, prov in enumerate(provinces):
            pname = str((prov or {}).get("name") or ("省%d" % (idx + 1)))
            pid = "%s_p%d" % (name, idx)
            book[pid] = {"level": "T2", "name": pname, "kind": "省", "owner": name,
                         "parent": name, "pop": None, "land": None,
                         "note": "外邦省（静态/既有 provinces 镜像）"}
            foreign_provinces += 1
            for seat in (seats_map.get(pname) or ()):
                sid = "%s_%s" % (pid, seat.get("name"))
                book[sid] = {"level": "T1", "name": seat.get("name"),
                             "kind": seat.get("kind") or "州", "owner": name,
                             "parent": pid, "pop": None, "land": None,
                             "weight": seat.get("weight"),
                             "center_lonlat": seat.get("lonlat"),
                             "note": seat.get("note"),
                             "transition_until": None}
                foreign_seats += 1

    state.regions = book
    try:
        state.region_admin_version = 1
    except Exception:  # noqa: BLE001
        pass
    return {"created": len(book), "song_routes": song_routes, "song_seats": song_seats,
            "foreign_provinces": foreign_provinces, "foreign_seats": foreign_seats}


def region_of(state, region_id: str) -> Optional[Dict[str, Any]]:
    book = getattr(state, "regions", None) or {}
    got = book.get(region_id)
    return got if isinstance(got, dict) else None


def regions_by_owner(state, owner: str) -> List[Dict[str, Any]]:
    book = getattr(state, "regions", None) or {}
    return [dict(v, region_id=k) for k, v in book.items()
            if isinstance(v, dict) and v.get("owner") == owner]


def _chain_depth(book: Dict[str, Any], rid: str) -> int:
    depth, cur = 0, rid
    while cur in book:
        depth += 1
        parent = (book.get(cur) or {}).get("parent")
        if not parent or parent not in book:
            break
        cur = parent
        if depth > 10:
            break
    return depth


def verify_region_invariants(state) -> List[str]:
    """不变量校验（返回违规清单；空 = 自洽）。**只读**。"""
    book = getattr(state, "regions", None)
    if not isinstance(book, dict) or not book:
        return ["regions 未初始化"]
    bad: List[str] = []
    ids = set(book)
    for rid, r in book.items():
        if not isinstance(r, dict):
            bad.append("%s 条目非 dict" % rid)
            continue
        parent = r.get("parent")
        if r.get("level") == "T1":
            if not parent or parent not in ids:
                bad.append("%s 是 T1 但 parent 缺失/不存在：%r" % (rid, parent))
        if parent and parent in ids:
            p = book[parent]
            if isinstance(p, dict) and p.get("owner") != r.get("owner"):
                bad.append("%s owner=%r 与父 %s owner=%r 不一致" % (
                    rid, r.get("owner"), parent, p.get("owner")))
        if _chain_depth(book, rid) > REGION_DEPTH_MAX:
            bad.append("%s 层级深度超过 %d" % (rid, REGION_DEPTH_MAX))
    # 宋覆盖：117 治所全登记（若宋有治所）
    prefs = getattr(state, "prefectures", None) or {}
    expect = sum(len(((p or {}).get("seats") or {})) for p in prefs.values())
    got_song = sum(1 for r in book.values()
                   if isinstance(r, dict) and r.get("owner") == "宋" and r.get("level") == "T1")
    if expect and got_song != expect:
        bad.append("宋 T1 登记数 %d != 治所数 %d" % (got_song, expect))
    return bad


def aggregate_by_owner(state, owner: str) -> Dict[str, Any]:
    """按政权汇总（P1 只做计数与人口占位；人口缺失 ⇒ None，不回落 0）。"""
    rows = regions_by_owner(state, owner)
    t1 = [r for r in rows if r.get("level") == "T1"]
    t2 = [r for r in rows if r.get("level") == "T2"]
    pops = [r.get("pop") for r in t1 if isinstance(r.get("pop"), dict)]
    total = None
    if pops:
        total = {}
        for p in pops:
            for cls, v in (p or {}).items():
                if isinstance(v, dict) and isinstance(v.get("size"), (int, float)):
                    total[cls] = total.get(cls, 0) + int(v["size"])
    return {"owner": owner, "t1_count": len(t1), "t2_count": len(t2),
            "pop_total": total, "pop_reason": None if total is not None else "T1 人口尚未分解（缺失≠0）"}