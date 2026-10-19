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

__all__ = ["_t1_of_province", "distribute_regime_pops", "verify_pop_conservation", "init_regions", "migrate_regions", "aggregate_regime", "aggregate_song", "verify_aggregation", "REGIME_POP_UNIT", "init_regions", "verify_region_invariants", "region_of", "regions_by_owner",
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
        from content.data_external_admin import (PROVINCE_WITHOUT_MAP, REGIME_PROVINCE_MAP,
                                                REGIME_SEATS, REGIME_TIER1)
    except Exception:  # noqa: BLE001
        REGIME_SEATS, REGIME_TIER1 = {}, ()
        REGIME_PROVINCE_MAP, PROVINCE_WITHOUT_MAP = {}, {}
    for name in REGIME_TIER1:
        info = regimes.get(name)
        if not isinstance(info, dict):
            continue
        provinces = info.get("provinces") or []
        seats_map = REGIME_SEATS.get(name) or {}
        prov_map = REGIME_PROVINCE_MAP.get(name) or {}
        # ① T2：以**运行态 provinces**（账）为准
        t2_id = {}
        for idx, prov in enumerate(provinces):
            pname = str((prov or {}).get("name") or ("省%d" % (idx + 1)))
            pid = "%s_p%d" % (name, idx)
            t2_id[pname] = pid
            book[pid] = {"level": "T2", "name": pname, "kind": "省", "owner": name,
                         "parent": name, "pop": None, "land": None,
                         "map_provinces": [],
                         "note": None if pname not in (PROVINCE_WITHOUT_MAP.get(name) or {})
                                 else (PROVINCE_WITHOUT_MAP[name][pname])}
            foreign_provinces += 1
        # ② T1：以**地图切分**（面）为准，父节点 = 运行态省（经映射）
        for map_prov, seats in seats_map.items():
            parent_name = prov_map.get(map_prov, map_prov)
            pid = t2_id.get(parent_name)
            if pid is None:
                # 运行态无该省 ⇒ 挂到同名新 T2（不丢块，标记待补）
                pid = "%s_map_%s" % (name, map_prov)
                book[pid] = {"level": "T2", "name": map_prov, "kind": "省", "owner": name,
                             "parent": name, "pop": None, "land": None,
                             "map_provinces": [map_prov], "note": "运行态缺该省（按地图补登）"}
                t2_id[parent_name] = pid
                foreign_provinces += 1
            else:
                book[pid]["map_provinces"].append(map_prov)
            for seat in seats:
                sid = "%s_%s" % (pid, seat.get("name"))
                book[sid] = {"level": "T1", "name": seat.get("name"),
                             "kind": seat.get("kind") or "州", "owner": name,
                             "parent": pid, "pop": None, "land": None,
                             "weight": seat.get("weight"),
                             "center_lonlat": seat.get("lonlat"),
                             "map_province": map_prov,
                             "note": seat.get("note"),
                             "transition_until": None}
                foreign_seats += 1

    state.regions = book
    try:
        distribute_regime_pops(state)   # P4：省→州府人口分解（守恒）
    except Exception as exc:  # noqa: BLE001
        import logging as _lg
        _lg.getLogger(__name__).warning("人口分解失败：%r", exc, exc_info=True)
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


#: 国级 `population` 单位 = **万人**；省级 `population` 单位 = **人**
REGIME_POP_UNIT = 10000


def _seat_pop_total(prefs) -> dict:
    """宋：Σ 治所 6 类 POP（真账在 seats）。缺失 ⇒ 空 dict（不臆造）。"""
    total: Dict[str, int] = {}
    for pdata in (prefs or {}).values():
        for srow in ((pdata or {}).get("seats") or {}).values():
            for cls, pop in (((srow or {}).get("pops") or {})).items():
                if isinstance(pop, dict) and isinstance(pop.get("size"), (int, float)):
                    total[str(cls)] = total.get(str(cls), 0) + int(pop["size"])
    return total


def aggregate_regime(state, owner: str) -> Dict[str, Any]:
    """政权级聚合 + **与现有国级字段对账**（P2）。

    口径：
    - 国级 `external_regimes[国].population` 单位 = **万人**；
    - 运行态 `provinces[*].population` 单位 = **人**；
    - 对账：Σ省人口(人) == 国人口 × REGIME_POP_UNIT（逐国）；
    - T1 人口尚未分解 ⇒ `pop_total=None` + reason（**缺失≠0**）。
    """
    rows = regions_by_owner(state, owner)
    t1 = [r for r in rows if r.get("level") == "T1"]
    t2 = [r for r in rows if r.get("level") == "T2"]
    info = (getattr(state, "external_regimes", None) or {}).get(owner) or {}
    provs = info.get("provinces") or []
    prov_pop = sum(int((p or {}).get("population") or 0) for p in provs)
    country = info.get("population")
    country_people = int(country) * REGIME_POP_UNIT if isinstance(country, (int, float)) else None
    pops = [r.get("pop") for r in t1 if isinstance(r.get("pop"), dict)]
    pop_total = None
    if pops:
        pop_total = {}
        for p in pops:
            for cls, v in (p or {}).items():
                if isinstance(v, dict) and isinstance(v.get("size"), (int, float)):
                    pop_total[cls] = pop_total.get(cls, 0) + int(v["size"])
    ok = country_people is None or prov_pop == country_people
    return {"owner": owner, "t1_count": len(t1), "t2_count": len(t2),
            "province_pop_sum": prov_pop, "country_population": country,
            "country_population_people": country_people,
            "pop_total": pop_total,
            "pop_reason": None if pop_total is not None else "T1 人口尚未分解（缺失≠0）",
            "reconcile_ok": ok,
            "reconcile_reason": None if ok else
            ("国级人口缺失" if country_people is None else
             "Σ省人口 %d != 国人口×%d = %d" % (prov_pop, REGIME_POP_UNIT, country_people))}


def aggregate_song(state) -> Dict[str, Any]:
    """宋：从 `prefectures` 真账聚合（T1 只存指针，人口不在 regions 里）。"""
    prefs = getattr(state, "prefectures", None) or {}
    rows = regions_by_owner(state, "宋")
    return {"owner": "宋",
            "t1_count": sum(1 for r in rows if r.get("level") == "T1"),
            "t2_count": sum(1 for r in rows if r.get("level") == "T2"),
            "pop_total": _seat_pop_total(prefs) or None,
            "source": "prefectures[路][seats][治所][pops]（真账）"}


def verify_aggregation(state) -> List[str]:
    """P2 对账：逐国 Σ省人口 == 国人口×10000；缺失只报 None 不造假。"""
    bad: List[str] = []
    for owner in (getattr(state, "external_regimes", None) or {}):
        if not regions_by_owner(state, owner):
            continue
        agg = aggregate_regime(state, owner)
        if not agg["reconcile_ok"]:
            bad.append("%s: %s" % (owner, agg["reconcile_reason"]))
    song = aggregate_song(state)
    prefs = getattr(state, "prefectures", None) or {}
    expect = sum(len(((p or {}).get("seats") or {})) for p in prefs.values())
    if song["t1_count"] != expect:
        bad.append("宋: T1 %d != 治所数 %d" % (song["t1_count"], expect))
    return bad


def migrate_regions(state) -> Dict[str, Any]:
    """P3 迁移入口（幂等）：旧档无 regions ⇒ 建；已有 ⇒ created=0。"""
    existing = getattr(state, "regions", None)
    if isinstance(existing, dict) and existing:
        return {"migrated": False, "created": 0, "total": len(existing)}
    out = init_regions(state)
    return {"migrated": True, **out}

def _apportion(total: int, weights: list) -> list:
    """整数分摊（**最大余数法**，总和精确等于 total）。"""
    nums = [max(0.0, float(w)) for w in weights]
    s = sum(nums)
    if s <= 0 or total <= 0:
        return [0 for _ in nums]
    raw = [total * w / s for w in nums]
    base = [int(x) for x in raw]
    left = int(total) - sum(base)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - base[i], reverse=True)
    for i in order[:max(0, left)]:
        base[i] += 1
    return base


def _map_prov_of(owner: str) -> Dict[str, str]:
    """地图省 → 运行态省（读 `REGIME_PROVINCE_MAP`；未登记 ⇒ 同名）。"""
    try:
        from content.data_external_admin import REGIME_PROVINCE_MAP
    except Exception:  # noqa: BLE001
        return {}
    return dict((REGIME_PROVINCE_MAP or {}).get(owner) or {})


def _t1_of_province(book, owner: str, pname: str) -> list:
    """该运行态省下的 T1（经地图省映射匹配）。"""
    rev = _map_prov_of(owner)
    out = []
    for r in (book or {}).values():
        if not isinstance(r, dict) or r.get("owner") != owner or r.get("level") != "T1":
            continue
        mp = str(r.get("map_province") or "")
        if rev.get(mp, mp) == pname:
            out.append(r)
    return out


def distribute_regime_pops(state, *, force: bool = False) -> Dict[str, Any]:
    """P4：省 → 州府人口分解（**逐类守恒**，尾差归首府）。

    · 数据源：运行态 `provinces[*].pops`（6 类 size/wealth/grain）；缺失 ⇒ 整省跳过（`None`）；
    · 权重：州府 `weight`（首都 1.5 / 要冲 1.2 / 普通 1.0）× 省内归一；
    · 守恒：Σ州府 == 省（逐类 × size/wealth/grain，整数精确）；
    · 幂等：已分解（T1 有 `pop`）⇒ 跳过，除非 `force=True`。
    """
    regimes = getattr(state, "external_regimes", None) or {}
    book = getattr(state, "regions", None) or {}
    out = {"distributed": [], "skipped": [], "missing": []}
    for owner, info in regimes.items():
        if not any(isinstance(r, dict) and r.get("owner") == owner for r in book.values()):
            continue
        for prov in (info.get("provinces") or []):
            pname = str((prov or {}).get("name") or "")
            pops = (prov or {}).get("pops")
            if not isinstance(pops, dict) or not pname:
                if pname:
                    out["missing"].append("%s/%s" % (owner, pname))
                continue
            t1 = _t1_of_province(book, owner, pname)
            if not t1:
                continue
            if not force and all(isinstance(r.get("pop"), dict) for r in t1):
                out["skipped"].append("%s/%s" % (owner, pname))
                continue
            weights = [float(r.get("weight") or 1.0) for r in t1]
            classes = [c for c, v in pops.items() if isinstance(v, dict)]
            for cls in classes:
                base = pops.get(cls) or {}
                sizes = _apportion(int(base.get("size") or 0), weights)
                wealth = _apportion(int(base.get("wealth") or 0), weights)
                grain = _apportion(int(base.get("grain") or 0), weights)
                for i, r in enumerate(t1):
                    if not isinstance(r.get("pop"), dict):
                        r["pop"] = {}
                    cell = r["pop"]
                    cell.setdefault(cls, {})
                    cell[cls]["size"] = int(cell[cls].get("size") or 0) + sizes[i]
                    cell[cls]["wealth"] = int(cell[cls].get("wealth") or 0) + wealth[i]
                    cell[cls]["grain"] = int(cell[cls].get("grain") or 0) + grain[i]
            out["distributed"].append("%s/%s(%d块)" % (owner, pname, len(t1)))
    return out


def verify_pop_conservation(state) -> List[str]:
    """P4 门：逐省逐类 Σ州府 == 省（size/wealth/grain），整数精确。"""
    regimes = getattr(state, "external_regimes", None) or {}
    book = getattr(state, "regions", None) or {}
    bad: List[str] = []
    for owner, info in regimes.items():
        for prov in (info.get("provinces") or []):
            pname = str((prov or {}).get("name") or "")
            pops = (prov or {}).get("pops")
            if not isinstance(pops, dict) or not pname:
                continue
            t1 = _t1_of_province(book, owner, pname)
            if not t1:
                continue
            for cls, base in pops.items():
                if not isinstance(base, dict):
                    continue
                got = {"size": 0, "wealth": 0, "grain": 0}
                for r in t1:
                    cell = (r.get("pop") or {}).get(cls) or {}
                    for f in got:
                        got[f] += int(cell.get(f) or 0)
                for f in got:
                    want = int(base.get(f) or 0)
                    if got[f] != want:
                        bad.append("%s/%s/%s: Σ州府 %d != 省 %d" % (
                            owner, pname, cls + "." + f, got[f], want))
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