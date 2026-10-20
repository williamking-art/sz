# -*- coding: utf-8 -*-
"""州府间**交通边与在途批次**（P0 · 2026-10-02）—— 物流的第一层。

## 为什么现在做它

口径 **C-c** 定的是「**工地只从本地取料，取不到即缺料**」，
理由是「**这样物流才有意义**」。但在 `trade_material()` 里建材是**瞬移**的——
成交即到货，"运没运到"根本不可观测。**没有在途，C-c 只是句口号**。

`market.py` 与 `market_readout.py` 早已为此留好接口并**显式标注"在途未实现"**
（`market_readout.in_transit.implemented = False`）——本模块就是来填这个洞的。

## 口径（严格区分"能算的"与"不能臆造的"）

| | |
|---|---|
| ✅ **能算** | 距离（经纬度）→ **运输耗时**；批次到达月份；同州府内 = 0 耗时 |
| ⚠️ **不臆造** | **路况**（道路等级/损耗/劫掠）——**无史料支撑**。故 `ROAD_QUALITY` **默认为空**，耗时按**平地常数**计，并显式声明"未含路况修正"。若日后有史料，在此表补，不改算法。 |

🚫 **不做**（§14.4 明确排除）：市场圈派生、断路/改道、季节性封冻。
这些都要真实地理与路况数据支撑，**没有就不做**，不做就是不做。

## 不变量

1. **缺失 ≠ 0**：未登记的路线 **不建边**（`route_days` 返回 `None`），
   **不得**回落 0（那等于"瞬移"）；
2. **在途不凭空产生**：`dispatch` 必须**同时**从卖方扣货 + 建批次，
   钱货两清或两不做；
3. **到达才入账**：`arrive_due` 未到的批次**不进** `material_holding_for_circuit`；
4. **批次可查**：`in_transit()` 报 `{implemented: True, items: [...]}`，
   与 `market_readout` 既有结构对齐（原先是 `implemented: False`）。
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

__all__ = [
    "EARTH_RADIUS_KM", "KM_PER_MONTH", "ADJACENT_KM", "ROAD_QUALITY",
    "haversine_km", "is_adjacent", "route_days", "transport_links",
    "dispatch", "arrive_due", "in_transit", "transit_report",
    "transit_by_seat",
]

#: 地球半径（km）
EARTH_RADIUS_KM = 6371.0

#: 🔴 **平地月行里程**（km/月）。
#: ⚠️ 这是**设定值**，不是史料——宋代驿路的具体速度无可靠逐程记载。
#: 取宋制"千里之程约一月"量级，故 1000 km/月。**凡由此推出的耗时都带此不确定性**，
#: 故本模块所有读数都随附该说明，**不得**当成史料。
KM_PER_MONTH = 2400.0   # 2026-10-18 重标定（设定值）：境内任意两地**月度内可达**——
                        # 实测境内陆路最长 2,356km；2400km/月 ≈ 80km/日（驿传/商旅换乘
                        # 混合量级）。原 1000km/月 会让 4,515/8,912 对超过 1 月，
                        # 与回合制（1 回合 = 1 月）及宋境驿路密度不符。

#: ⚠️ **路况修正表默认为空**——宋代各路道路等级无可靠史料，**不臆造**。
#: 结构预留：`{州府主键: 速度倍率}`；空 ⇒ 耗时按平地常数计。
ROAD_QUALITY: Dict[str, float] = {}

#: 🔴 **相邻可达阈值（km）**——决定「哪些两地之间**有路**」。
#: ⚠️ **这是设定值，不是史料**：宋代驿路里程无可靠逐程记载，
#: 此处取 **200km**（按实测：136 席两两距离中位 850km，200km 处平均度 5.5、最接近
#: 「相邻」的图结构；300km 即平均度 11.5，过密）。
#: ⇒ 超出此距的两地**没有直达道路**，**不是**"远"而是**"不通"** ⇒ `route_days` 返回 `None`。
ADJACENT_KM = 200.0


def is_adjacent(frm: str, to: str, threshold_km: float = ADJACENT_KM) -> Optional[bool]:
    """两地是否**有直达道路**。`None` = 读数未定义（坐标缺失/未知州府）。

    ⚠️ 阈值 `ADJACENT_KM` 是**设定值非史料**；此函数**只判有无道路**，
    **不判路况好坏**（路况表 `ROAD_QUALITY` 目前为空，不臆造）。
    """
    if frm == to:
        return True
    idx = _seat_index()
    a, b = idx.get(frm), idx.get(to)
    if not a or not b:
        return None
    km = haversine_km(float(a["lon"]), float(a["lat"]),
                      float(b["lon"]), float(b["lat"]))
    return km <= float(threshold_km)


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """两经纬度间大圆距离（km）。纯计算，无外部依赖。"""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


_SEAT_INDEX_CACHE: Dict[str, Dict[str, Any]] = {}


def _seat_index() -> Dict[str, Dict[str, Any]]:
    """州府限定名 → 治所实体。**按对象身份（`id()`）构建一次并缓存**。

    🔴 **性能（实测）**：`is_adjacent` / `route_days` / `dispatch` 都调本函数，
    一次 12 月长局的补货循环会调它**上万次**。而 `all_seats()` **每次调用都重新
    构造 136 席**（0.53ms/次），不缓存会把 12 月结算从 3.5 秒拖到分钟级。
    实测（cProfile）：3 个月结算 1.39s，其中 **1.02s 花在 `procure_materials` →**
    **`_bridge_seats` → `is_adjacent` → `_seat_index` → `all_seats`（1851 次）**。

    ⚠️ 缓存以 **`prefecture_entity` 模块里的席位表对象身份**为键；模块重载
    （测试里 `importlib.reload`）会换对象 ⇒ 自动重建，**不会读到过期数据**。
    """
    import core.foundation.ledger.prefecture_entity as pe
    key = str(id(pe))
    hit = _SEAT_INDEX_CACHE.get(key)
    if hit is not None:
        return hit
    idx = {s["seat_id"]: s for s in pe.all_seats()}
    _SEAT_INDEX_CACHE.clear()          # 只保留当前模块身份的一份，防 id 复用
    _SEAT_INDEX_CACHE[key] = idx
    return idx


def route_days(frm: str, to: str) -> Optional[int]:
    """从 `frm` 到 `to` 的运输耗时（月）。

    · 同州府 = **0**（市内调拨，不涉道路）；
    · 🔴 **无直达道路 ⇒ `None`**（`ADJACENT_KM` 阈值外）——这是「**不通**」，
      不是「远」。规格 `unified-civilian-market/tasks.md:88` 明确
      「**不做全图任意互通**」，故远处两地**不得**凭空互通；
    · 无坐标 ⇒ `None`。

    ⚠️ 两种 `None` 语义不同（不通 vs 读不出），但都**不得回落 0**——
    回落 0 等于"瞬移"，会让"运没运到"不可观测。
    """
    if frm == to:
        return 0
    adj = is_adjacent(frm, to)
    if adj is None or adj is False:
        return None
    idx = _seat_index()
    a, b = idx[frm], idx[to]
    km = haversine_km(float(a["lon"]), float(a["lat"]),
                      float(b["lon"]), float(b["lat"]))
    mult = float(ROAD_QUALITY.get(frm, 1.0)) * float(ROAD_QUALITY.get(to, 1.0))
    if mult <= 0:
        return None
    months = km / (KM_PER_MONTH * mult)
    return max(1, int(math.ceil(months)))       # 至少 1 月，不做"同月到达"


# ---------------------------------------------------------------------------
# 多跳路由（G-3/P5a，2026-10-18）：邻接图最短路
# ---------------------------------------------------------------------------
_ROUTE_CACHE: Dict[str, Dict[Any, Any]] = {}


def _graph_cache_key() -> str:
    import core.foundation.ledger.prefecture_entity as pe

    return str(id(pe))


def transport_graph():
    """构建**邻接图**：返回 (nodes, adj)。adj[a][b] = km（无向，仅 ≤ ADJACENT_KM 的边）。

    与 `is_adjacent` **同源同阈值**（200km 设定值，非史料）；不另造一套连通规则。
    节点 = 治所 id；孤立节点保留在 nodes 里（连通性分析需要看到它们）。
    """
    key = _graph_cache_key()
    cached = _ROUTE_CACHE.get("__graph__")
    if isinstance(cached, dict) and cached.get("key") == key:
        return cached["nodes"], cached["adj"]
    idx = _seat_index()
    nodes = list(idx)
    coords = {sid: (float(idx[sid]["lon"]), float(idx[sid]["lat"])) for sid in nodes}
    adj: Dict[str, Dict[str, float]] = {sid: {} for sid in nodes}
    for i, a in enumerate(nodes):
        alon, alat = coords[a]
        for b in nodes[i + 1:]:
            blon, blat = coords[b]
            km = haversine_km(alon, alat, blon, blat)
            if km <= float(ADJACENT_KM):
                adj[a][b] = km
                adj[b][a] = km
    # 显式例外边（史实依据的补边；不降低全局阈值，见 content/data_constants.TRANSPORT_EXTRA_LINKS）
    try:
        from content.data_constants import TRANSPORT_EXTRA_LINKS

        for link in TRANSPORT_EXTRA_LINKS:
            a, b = str(link.get("a") or ""), str(link.get("b") or "")
            if a not in coords or b not in coords or a == b:
                continue
            alon, alat = coords[a]
            blon, blat = coords[b]
            km = haversine_km(alon, alat, blon, blat)
            if a in adj and b in adj and b not in adj[a]:
                adj[a][b] = km
                adj[b][a] = km
    except Exception:  # noqa: BLE001 — 补边失败不得影响主图
        pass
    _ROUTE_CACHE["__graph__"] = {"key": key, "nodes": nodes, "adj": adj}
    return nodes, adj


def route_path(frm: str, to: str) -> Optional[Dict[str, Any]]:
    """**多跳最短路**（Dijkstra，边权 km）。

    返回：`{reachable, path, km, days, hops}`；`path` 含起终点。

    · 未知治所 ⇒ **None**（读不出，不是『不通』）；
    · 同点 ⇒ `reachable=True, path=[点], km=0, days=0, hops=0`；
    · 连通但无路径 / 全图不连通 ⇒ `reachable=False`（**显式**，不回落 0、不臆造直线）。

    ⚠️ 与 `route_days` 分工：`route_days` 仍只判**相邻**（既有 6 处调用方依赖该语义），
    本函数才是『怎么走、几天到』的入口。
    """
    import heapq

    if not frm or not to or frm not in _seat_index() or to not in _seat_index():
        return None
    if frm == to:
        return {"reachable": True, "path": [frm], "km": 0.0, "days": 0, "hops": 0}
    key = (frm, to)
    cache = _ROUTE_CACHE.get("__routes__")
    if not isinstance(cache, dict) or cache.get("key") != _graph_cache_key():
        cache = {"key": _graph_cache_key(), "items": {}}
        _ROUTE_CACHE["__routes__"] = cache
    hit = cache["items"].get(key)
    if hit is not None:
        return dict(hit)

    _nodes, adj = transport_graph()
    dist: Dict[str, float] = {frm: 0.0}
    prev: Dict[str, str] = {}
    heap = [(0.0, frm)]
    seen = set()
    while heap:
        d, u = heapq.heappop(heap)
        if u in seen:
            continue
        seen.add(u)
        if u == to:
            break
        for v, w in adj.get(u, {}).items():
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))
    if to not in dist:
        res = {"reachable": False, "path": [], "km": None, "days": None, "hops": 0}
    else:
        path = [to]
        cur = to
        while cur != frm:
            cur = prev[cur]
            path.append(cur)
        path.reverse()
        km = float(dist[to])
        mult = 1.0
        for sid in path:
            mult *= float(ROAD_QUALITY.get(sid, 1.0))
        if mult <= 0:
            res = {"reachable": False, "path": path, "km": km, "days": None,
                   "hops": len(path) - 1}
        else:
            months = km / (KM_PER_MONTH * mult)
            res = {"reachable": True, "path": path, "km": round(km, 1),
                   "days": max(1, int(math.ceil(months))), "hops": len(path) - 1}
    cache["items"][key] = dict(res)
    return dict(res)




def _carriage_of(state, owner: str) -> dict:
    """某所有权的载具数；缺失 ⇒ 空表（不臆造 0）。"""
    car = getattr(state, "carriage", None) or {}
    got = car.get(owner)
    return got if isinstance(got, dict) else {}


def _labor_of(state, owner: str) -> dict:
    """某所有权的夫役数；缺失 ⇒ 空表。"""
    lab = getattr(state, "transport_labor", None) or {}
    got = lab.get(owner)
    return got if isinstance(got, dict) else {}


def _carrier_keys(mode: str) -> tuple:
    """路网 → 载具键（与 CARRIAGE_INITIAL 的命名对应）。"""
    return {
        "waterway": ("boat",),
        "maritime": ("sea_boat",),
        "overland": ("cart", "mule", "porter"),
        "post": ("horse",),
    }.get(mode, ())


def _labor_keys(mode: str) -> tuple:
    return {
        "waterway": ("boatman",),
        "maritime": ("sailor",),
        "overland": ("hired_porter",),
        "post": ("post_soldier",),
    }.get(mode, ())


def transport_availability(state, mode: str) -> float:
    """可用率（1 − 漕淤惩罚，clamp 到 [1−cap, 1]）；非水运不受漕淤影响。"""
    from content.data_constants import TRANSPORT_AVAILABILITY as AV

    base = float((AV or {}).get("base", 1.0))
    if mode not in ("waterway", "maritime"):
        return base
    block = float(getattr(state, "canal_block", 0) or 0)
    pen = min(float((AV or {}).get("canal_block_cap", 0.4)),
              block * float((AV or {}).get("canal_block_penalty", 0.006)))
    return max(0.0, base - pen)


def transport_capacity(state, mode: str) -> dict:
    """**派生运力**（P3）：`min(载具上限, 人力上限) × 可用率`，并标出瓶颈。

    · 载具上限 = Σ(官私载具数 × **该载具真实载重**) × 月趟数（`CARRIAGE_CARRIER_MAP`）；
    · 人力上限 = Σ夫役数 ÷ 既有矩阵人石比；
    · 官私**相加**（不是覆盖）；缺失 ⇒ 该项 0 且 bottleneck 说明。
    """
    from content.data_constants import (CARRIAGE_CARRIER_MAP, CARRIAGE_MONTHLY_TRIPS,
                                        TRANSIT_LABOR_PER_STONE)

    by_name = {c.get("name"): c for c in carriers_for(mode)}
    key_map = CARRIAGE_CARRIER_MAP.get(mode) or {}
    trips = float((CARRIAGE_MONTHLY_TRIPS or {}).get(mode, 1.0))
    base_labor_rate = float(TRANSIT_LABOR_PER_STONE.get(mode, 0.5) or 0.5)
    avail = transport_availability(state, mode)

    counts: Dict[str, int] = {}
    vehicle_cap = 0.0
    for owner in ("official", "private"):
        own = _carriage_of(state, owner)
        for key, carrier_name in key_map.items():
            n = int(own.get(key) or 0)
            if n <= 0:
                continue
            counts[key] = counts.get(key, 0) + n
            c = by_name.get(carrier_name) or {}
            vehicle_cap += n * float(c.get("load") or 0)
    vehicle_cap *= trips
    lab_total = sum(int(_labor_of(state, owner).get(k) or 0)
                    for owner in ("official", "private")
                    for k in _labor_keys(mode))
    labor_cap = (lab_total / base_labor_rate) if base_labor_rate > 0 else 0.0
    eff = min(vehicle_cap, labor_cap) * avail
    if vehicle_cap <= 0 and labor_cap <= 0:
        bottleneck = "none"
    elif vehicle_cap <= labor_cap:
        bottleneck = "vehicles"
    else:
        bottleneck = "labor"
    return {"mode": mode, "vehicles": counts, "vehicle_cap": round(vehicle_cap, 1),
            "labor_total": lab_total, "labor_cap": round(labor_cap, 1),
            "trips_per_month": trips, "availability": round(avail, 4),
            "capacity": round(eff, 1), "bottleneck": bottleneck}

def _used_book(state) -> dict:
    """运力占用账（**货/客分列**，共用同一池）：{"goods": {mode: 石}, "passenger": {mode: 石}}。

    兼容旧格式（扁平的 `{mode: number}` 视为货运用量，自动迁移一次）。
    """
    u = getattr(state, "transport_used", None)
    if not isinstance(u, dict):
        u = {}
    if any(isinstance(v, (int, float)) and not isinstance(v, bool) for v in u.values()):
        legacy = {k: float(v) for k, v in u.items()
                  if isinstance(v, (int, float)) and not isinstance(v, bool)}
        u = {"goods": legacy, "passenger": {}}
    u.setdefault("goods", {})
    u.setdefault("passenger", {})
    state.transport_used = u
    return u


def transport_used(state, mode: str, kind: str = "goods") -> float:
    """本月已用运力（默认货运；kind=passenger 为客运）。"""
    book = _used_book(state).get(kind) or {}
    try:
        return float(book.get(mode, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def transport_remaining(state, mode: str, kind: str = "goods") -> float:
    """本月剩余运力（石）——**客货共用同一池**：货占则客少、客占则货少。"""
    book = _used_book(state)
    used = float((book.get("goods") or {}).get(mode, 0) or 0) \
        + float((book.get("passenger") or {}).get(mode, 0) or 0)
    return max(0.0, float(transport_capacity(state, mode)["capacity"]) - used)


def transport_consume(state, mode: str, qty: float, kind: str = "goods") -> dict:
    """占用本月运力（不足按剩余截断，不拒办）；kind 只影响**分列记账**。"""
    want = max(0.0, float(qty or 0))
    rem = transport_remaining(state, mode)
    take = min(want, rem)
    book = _used_book(state)
    slot = book.setdefault(kind, {})
    slot[mode] = float(slot.get(mode, 0) or 0) + take
    state.transport_used = book
    return {"ok": take > 0, "taken": round(take, 1), "short": round(want - take, 1),
            "remaining": round(rem - take, 1), "kind": kind}


def transport_queue(state) -> list:
    """待运队列（超额部分，下回合继续；瞬态，不落档）。"""
    q = getattr(state, "transport_queue", None)
    if not isinstance(q, list):
        q = []
        state.transport_queue = q
    return q


def transport_ship_or_queue(state, mode: str, qty: float, kind: str = "goods",
                            payload: Optional[dict] = None) -> dict:
    """**发运或排队**：能运多少运多少，余量入队（回合制下的正确语义：不拒办）。

    2026-10-20 全审 R-N-3 收口：
    · 队列上限常量缺失/非正 ⇒ 按「不限制」处理并 WARNING，**不再静默全丢**；
    · 丢弃量累计进 `state.statistics["transport_queue_dropped"]`（随档序列化）并留痕；
    · 返回增加 `status`（shipped/partial/queued/dropped/none），`ok` 语义保持兼容。
    """
    want = max(0.0, float(qty or 0))
    took = transport_consume(state, mode, want, kind=kind)
    shipped = float(took["taken"])
    queued = float(took["short"])
    dropped = 0.0
    if queued > 0:
        from content.data_constants import TRANSPORT_QUEUE_MAX_STONE
        _q = transport_queue(state)
        _cur = 0.0
        _clean = []
        for _it in _q:
            try:
                _qty = max(0.0, float((_it or {}).get("qty") or 0))
            except (TypeError, ValueError):
                # 坏队列条目（qty 非数值）不得按 0 低估占用、也不得留到续发时崩溃
                import logging
                logging.getLogger(__name__).warning(
                    "运输队列条目 qty 非数值，已丢弃：%r", _it)
                continue
            _clean.append(_it)
            _cur += _qty
        _q[:] = _clean
        _qmax = float(TRANSPORT_QUEUE_MAX_STONE or 0)
        if _qmax <= 0:
            import logging
            logging.getLogger(__name__).warning(
                "TRANSPORT_QUEUE_MAX_STONE=%r 非正，队列上限按不限制处理", TRANSPORT_QUEUE_MAX_STONE)
            _room = float("inf")
        else:
            _room = max(0.0, _qmax - _cur)
        _keep = min(queued, _room)
        dropped = queued - _keep
        if _keep > 0:
            _q.append({"mode": mode, "qty": round(_keep, 3), "kind": kind,
                       "payload": dict(payload or {})})
        if dropped > 0:
            _stats = getattr(state, "statistics", None)
            if isinstance(_stats, dict):
                _tot = float(_stats.get("transport_queue_dropped", 0) or 0) + dropped
                _stats["transport_queue_dropped"] = _tot
            else:
                _tot = float(getattr(state, "transport_queue_dropped", 0) or 0) + dropped
            state.transport_queue_dropped = _tot
            import logging
            logging.getLogger(__name__).warning(
                "运输队列超限：丢弃未入队记录 %.3f 石（累计 %.3f；货已按货腿处理，此处只丢运输记录）",
                dropped, _tot)
    if dropped > 0:
        status = "dropped"
    elif shipped > 0 and (queued - dropped) > 0:
        status = "partial"
    elif shipped > 0:
        status = "shipped"
    elif (queued - dropped) > 0:
        status = "queued"
    else:
        status = "none"
    return {"ok": shipped > 0, "shipped": round(shipped, 1),
            "queued": round(queued - dropped, 1), "dropped": round(dropped, 1),
            "remaining": took["remaining"], "status": status}


def transport_flush_queue(state, dispatcher=None) -> dict:
    """回合初**续发**队列：FIFO，能运多少运多少；`dispatcher(payload)` 返回真表示已建批次。

    · 无 `dispatcher` 时只做账（用于纯运力回归）；
    · 容量不足的条目**原样留在队里**（不丢弃、不臆造）。
    """
    q = transport_queue(state)
    shipped, kept = 0.0, []
    import logging as _lg
    for item in q:
        if not isinstance(item, dict):
            _lg.getLogger(__name__).warning("运输队列条目非 dict，已丢弃：%r", item)
            continue
        mode = str(item.get("mode") or "")
        try:
            remain_qty = float(item.get("qty") or 0)
        except (TypeError, ValueError):
            _lg.getLogger(__name__).warning("运输队列条目 qty 非数值，已丢弃：%r", item)
            continue
        if remain_qty <= 0 or not mode:
            continue
        took = transport_consume(state, mode, remain_qty, kind=str(item.get("kind") or "goods"))
        take = float(took["taken"])
        if take > 0 and callable(dispatcher):
            try:
                item["payload"] = dict(item.get("payload") or {})
            except (TypeError, ValueError):
                item["payload"] = {}
            item["payload"]["qty"] = take
            try:
                ok = bool(dispatcher(item["payload"]))
            except Exception as exc:  # noqa: BLE001
                _lg.getLogger(__name__).warning("队列续发回调失败：%r", exc, exc_info=True)
                ok = False
            if not ok:
                # 回调失败 ⇒ 退回额度，条目留在队列
                book = _used_book(state)
                kind = str(item.get("kind") or "goods")
                slot = book.setdefault(kind, {})
                slot[mode] = max(0.0, float(slot.get(mode, 0) or 0) - take)
                kept.append(item)
                continue
        shipped += take
        left = remain_qty - take
        if left > 1e-9:
            item["qty"] = round(left, 3)
            kept.append(item)
    state.transport_queue = kept
    return {"shipped": round(shipped, 1), "pending": len(kept),
            "pending_qty": round(sum(float(x.get("qty") or 0) for x in kept), 1)}


def hire_private(state, mode: str, qty: float, fee_per_stone: float) -> dict:
    """**和雇**民运力：付钱补运力（费用 = 石 × 单价），国库不足即失败。"""
    from core.transport import transport_consume as _tc

    want = max(0.0, float(qty or 0))
    fee = int(round(want * max(0.0, float(fee_per_stone or 0))))
    treasury = int(getattr(state, "treasury", 0) or 0)
    if fee > treasury:
        return {"ok": False, "reason": "insufficient_treasury", "fee": fee,
                "available": treasury}
    took = _tc(state, mode, want, kind="goods")
    if took["taken"] <= 0:
        return {"ok": False, "reason": "no_capacity", "fee": 0}
    state.treasury = treasury - fee
    return {"ok": True, "hired": took["taken"], "fee": fee,
            "remaining": took["remaining"]}


def impress_private(state, mode: str, qty: float, penalty_per_1000: float = 0.05,
                    penalty_cap: float = 0.3) -> dict:
    """**差雇**民运力：免运费，但降民心（按征用量，封顶 `penalty_cap`）。"""
    from core.transport import transport_consume as _tc

    want = max(0.0, float(qty or 0))
    took = _tc(state, mode, want, kind="goods")
    if took["taken"] <= 0:
        return {"ok": False, "reason": "no_capacity"}
    raw = float(took["taken"]) / 1000.0 * float(penalty_per_1000 or 0)
    penalty = min(float(penalty_cap or 0.3), max(0.0, raw))
    sat = float(getattr(state, "population_satisfaction", 0) or 0)
    state.population_satisfaction = max(0.0, sat - penalty)
    return {"ok": True, "impressed": took["taken"], "penalty": round(penalty, 4),
            "satisfaction": round(state.population_satisfaction, 4)}

def transport_reset_month(state) -> None:
    """回合初清空本月运力占用（货/客两本账；**队列保留**待续发）。"""
    state.transport_used = {"goods": {}, "passenger": {}}

def route_season(mode: str, month: Optional[int] = None) -> dict:
    """季节通航窗口（P3）：返回 `{open, capacity_mult, speed_mult, risk_mult, deferred_to}`。

    · `month` 缺失 ⇒ `open=None`（未知，不臆断为通航或不通风）；
    · 停航月 ⇒ `open=False` 且 `deferred_to` = 下一个开放月（1–12 循环）；
    · 倍率缺省 1.0（不在表里即无影响）。
    """
    from content.data_constants import SEASON_RULES

    rule = (SEASON_RULES or {}).get(str(mode or "")) or {}
    if month is None:
        return {"open": None, "capacity_mult": 1.0, "speed_mult": 1.0,
                "risk_mult": 1.0, "deferred_to": None, "reason": "month_missing"}
    try:
        m = int(month) % 12 or 12
    except (TypeError, ValueError):
        return {"open": None, "capacity_mult": 1.0, "speed_mult": 1.0,
                "risk_mult": 1.0, "deferred_to": None, "reason": "month_invalid"}
    closed = tuple(int(x) for x in (rule.get("closed_months") or ()))
    out = {"open": m not in closed,
           "capacity_mult": float((rule.get("capacity_mult") or {}).get(m, 1.0)),
           "speed_mult": float((rule.get("speed_mult") or {}).get(m, 1.0)),
           "risk_mult": float((rule.get("risk_mult") or {}).get(m, 1.0)),
           "deferred_to": None, "reason": None}
    if not out["open"]:
        nxt = m
        for _ in range(12):
            nxt = nxt % 12 + 1
            if nxt not in closed:
                out["deferred_to"] = nxt
                break
        out["reason"] = "closed"
    return out

def transit_km(frm: str, to: str, mode: str) -> Optional[float]:
    """两治所间该方式的**实际里程**（km）；取不到 ⇒ None（不臆造）。

    · maritime ⇒ `sea_route` 海路图（非海港 ⇒ 回落大圆距离）；
    · 其它 ⇒ `route_path` 陆路图（不可达 ⇒ 回落大圆距离）。
    """
    if mode == "maritime":
        r = sea_route(frm, to)
        if r and r.get("km"):
            return float(r["km"])
    else:
        r = route_path(frm, to)
        if r and r.get("reachable") and r.get("km"):
            return float(r["km"])
    idx = _seat_index()
    if frm not in idx or to not in idx:
        return None
    a, b = idx[frm], idx[to]
    return haversine_km(float(a["lon"]), float(a["lat"]), float(b["lon"]), float(b["lat"]))




def carriers_for(mode: str) -> list:
    """该路网可用载具（载重/速度/人石比/口粮率）；未登记 ⇒ 空表（不臆造）。"""
    from content.data_constants import TRANSPORT_CARRIERS

    return list(TRANSPORT_CARRIERS.get(str(mode or "")) or ())


def baseline_carrier(mode: str) -> Optional[dict]:
    """基准载具（既有矩阵系数的来源）；无 ⇒ None。"""
    for c in carriers_for(mode):
        if c.get("baseline"):
            return dict(c)
    return None


def carrier_labor(qty_stone: float, carrier: dict) -> int:
    """该载具运 qty 石所需**夫役人数**：ceil(qty × 人石比)，至少 1。"""
    import math as _m

    rate = float(carrier.get("labor_per_stone") or 0)
    n = int(_m.ceil(max(0.0, float(qty_stone)) * rate))
    return max(1, n) if qty_stone > 0 else 0


def carrier_ration(qty_stone: float, carrier: dict, days: int) -> float:
    """在途口粮（石）= 夫役数 × 日耗 × 天数（沈括模型，与既有实现同构）。"""
    n = carrier_labor(qty_stone, carrier)
    rate = float(carrier.get("ration_per_labor_day") or 0)
    return float(n) * rate * max(0, int(days))




def _tech_value(tech: dict, src: str) -> Optional[float]:
    """读科技值（level/hydraulics/铁 …）；缺失 ⇒ None（不按 0 处理）。"""
    if not isinstance(tech, dict):
        return None
    v = tech.get(src)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)




# ---------------------------------------------------------------------------
# 运输效果**接口层**（2026-10-18：国策/科技模型未定，先留可插拔接口）
# ---------------------------------------------------------------------------
#: 效果提供者注册表：name -> callable(state) -> list[{source_type, source_id, key, value}]
#: 约定：提供者只返回「原始效果值」，**不负责封顶**；封顶统一在 transport_effects 做。
#: 将来国策模型/科技模型定稿后，只需 `register_transport_effect_provider(...)` 接入，
#: 运输层与载具参数**不用改**。
_EFFECT_PROVIDERS: Dict[str, Any] = {}
#: 运行期新增效果键（模型未定时的扩展口）：key -> cap
_EFFECT_KEY_OVERLAY: Dict[str, float] = {}


def register_transport_effect_provider(name: str, fn) -> Dict[str, Any]:
    """注册效果提供者（幂等覆盖同名）。`fn(state)` 返回 row 列表或 `{key: value}`。"""
    key = str(name or "").strip()
    if not key or not callable(fn):
        return {"ok": False, "reason": "bad_provider"}
    _EFFECT_PROVIDERS[key] = fn
    return {"ok": True, "name": key}


def unregister_transport_effect_provider(name: str) -> bool:
    return _EFFECT_PROVIDERS.pop(str(name or ""), None) is not None


def list_transport_effect_providers() -> list:
    return sorted(_EFFECT_PROVIDERS)


def register_transport_effect_key(key: str, cap: float, note: str = "") -> Dict[str, Any]:
    """运行期新增/覆盖一个效果键及封顶（供未定型的科技/国策模型先接）。"""
    k = str(key or "").strip()
    if not k:
        return {"ok": False, "reason": "bad_key"}
    try:
        c = abs(float(cap))
    except (TypeError, ValueError):
        return {"ok": False, "reason": "bad_cap"}
    _EFFECT_KEY_OVERLAY[k] = c
    return {"ok": True, "key": k, "cap": c, "note": note}


def transport_effect_caps() -> Dict[str, float]:
    """当前生效的效果键封顶表（数据表 + 运行期覆盖）。"""
    from content.data_constants import TRANSPORT_EFFECT_CAPS

    merged: Dict[str, float] = {k: abs(float(v)) for k, v in (TRANSPORT_EFFECT_CAPS or {}).items()}
    for k, v in _EFFECT_KEY_OVERLAY.items():
        merged[k] = abs(float(v))
    return merged


def _default_effect_providers() -> list:
    """默认三源实现（**可被替换/停用**，不是硬口径）。"""
    return [_provider_official_tech, _provider_player_tech, _provider_decrees]


def _provider_official_tech(state) -> list:
    rows = []
    tech = getattr(state, "tech", None) or {}
    unlocked = set(tech.get("unlocked") or [])
    try:
        from content.data import TECH_NODES

        for nd in TECH_NODES or ():
            try:
                nid, eff = nd[0], nd[9]
            except (IndexError, TypeError):
                continue
            if nid in unlocked:
                rows.extend(_rows_from_effect("tech", nid, eff))
    except Exception:  # noqa: BLE001
        pass
    return rows


def _provider_player_tech(state) -> list:
    rows = []
    for nid, node in (getattr(state, "tech_registry", None) or {}).items():
        if isinstance(node, dict) and node.get("active"):
            rows.extend(_rows_from_effect("tech_player", nid, node.get("effect")))
    return rows


def _provider_decrees(state) -> list:
    rows = []
    for i, dec in enumerate(getattr(state, "active_decrees", None) or []):
        if isinstance(dec, dict):
            rows.extend(_rows_from_effect("decree",
                                        str(dec.get("title") or f"decree#{i}"),
                                        dec.get("effects")))
    return rows


def _rows_from_effect(source_type: str, source_id: str, eff) -> list:
    """把 {key: value} 归一成 row 列表（只保留数值、跳过布尔）。"""
    rows = []
    if not isinstance(eff, dict):
        return rows
    for k, v in eff.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        rows.append({"source_type": str(source_type), "source_id": str(source_id),
                     "key": str(k), "value": float(v)})
    return rows

def transport_effect_sources(state) -> list:
    """**多来源**运输类效果明细（逐条，可溯源）。

    🔴 模型未定，本函数只是**接口**：默认挂三个提供者（官方科技 / 玩家科技 / 国策-诏令），
    将来科技或国策模型定稿后，用 `register_transport_effect_provider()` 替换或追加即可，
    **调用方（carrier_params / 面板）无需改动**。

    返回 `[{source_type, source_id, key, value}]`；只保留 `transport_effect_caps()` 登记的键。
    """
    caps = transport_effect_caps()
    if not _EFFECT_PROVIDERS:
        for fn in _default_effect_providers():
            register_transport_effect_provider(getattr(fn, "__name__", str(fn)), fn)
    rows = []
    for name, fn in sorted(_EFFECT_PROVIDERS.items()):
        try:
            got = fn(state)
        except Exception as exc:  # noqa: BLE001 — 单个提供者失败不得拖垮运输
            log.warning("transport 效果提供者 %s 失败：%r", name, exc, exc_info=True)
            continue
        if isinstance(got, dict):
            got = _rows_from_effect(name, name, got)
        for row in got or ():
            if not isinstance(row, dict):
                continue
            k = row.get("key")
            if k not in caps:
                continue
            rows.append(row)
    return rows

def transport_effects(state) -> dict:
    """聚合运输类科技/国策效果（**多项 + 边际递减**，再按 cap 封顶）。

    · 来源：`transport_effect_sources`（官方科技 / 玩家科技 / 国策，均可多项）；
    · **边际递减**：同键各来源按 |值| 降序，第 i 项权重 = `TRANSPORT_EFFECT_DIMINISH^i`
      （首项 1.0、次项 0.85、再 0.72…）——多份同向加成会重叠，不线性叠加；
    · 求和后按 `transport_effect_caps()` 封顶（可为负）；无来源 ⇒ `{}`（缺失≠0）。
    """
    from content.data_constants import TRANSPORT_EFFECT_DIMINISH

    caps = transport_effect_caps()
    decay = float(TRANSPORT_EFFECT_DIMINISH)
    acc: Dict[str, float] = {}
    by_key: Dict[str, list] = {}
    for row in transport_effect_sources(state):
        by_key.setdefault(row["key"], []).append(float(row["value"]))
    for key, values in by_key.items():
        # 边际递减：按绝对值从大到小，逐项乘衰减权重
        ordered = sorted(values, key=abs, reverse=True)
        total = 0.0
        for i, v in enumerate(ordered):
            total += v * (decay ** i)
        cap = abs(float(caps.get(key, 0.0)))
        acc[key] = max(-cap, min(cap, total))
    return acc

def carrier_params(state, mode: str, carrier: dict) -> dict:
    """载具参数 + **科技修正**（效果词条驱动，不绑节点）。

    · 来源：`transport_effects(state)`（官方节点 + 玩家自创节点，见该函数）；
    · 映射：水/海/陆各有 speed/load 词条；`transport_labor_save` 降人石比；
    · 只受 `TRANSPORT_EFFECT_CAPS` 封顶；无任何词条 ⇒ 参数原样返回（缺失≠0）。
    """
    from content.data_constants import TRANSPORT_EFFECT_CAPS

    caps = TRANSPORT_EFFECT_CAPS or {}
    eff = transport_effects(state)
    speed_key = {"waterway": "transport_water_speed", "maritime": "transport_sea_speed",
                 "overland": "transport_land_speed", "post": "transport_land_speed"}.get(mode)
    load_key = {"waterway": "transport_water_load", "maritime": "transport_sea_load",
                "overland": "transport_land_load"}.get(mode)
    out = {k: carrier.get(k) for k in ("load", "km_per_day", "labor_per_stone")}
    bonus = {}
    if load_key and load_key in eff and isinstance(out.get("load"), (int, float)):
        b = float(eff[load_key])
        out["load"] = float(out["load"]) * (1.0 + b)
        bonus["load"] = b
    if speed_key and speed_key in eff and isinstance(out.get("km_per_day"), (int, float)):
        b = float(eff[speed_key])
        out["km_per_day"] = float(out["km_per_day"]) * (1.0 + b)
        bonus["km_per_day"] = b
    save = float(eff.get("transport_labor_save") or 0)
    if save and isinstance(out.get("labor_per_stone"), (int, float)):
        save = max(0.0, min(float(caps.get("transport_labor_save", 0.2)), save))
        out["labor_per_stone"] = float(out["labor_per_stone"]) * (1.0 - save)
        bonus["labor_per_stone"] = -save
    out["tech_bonus"] = bonus
    return out



def carrier_days(mode: str, frm: str, to: str, carrier: Optional[dict] = None) -> Optional[int]:
    """载具级时效：max(近程基准, ceil(km / 载具 km/日))；无里程 ⇒ None。"""
    import math as _m

    from content.data_constants import TRANSIT_NEAR_DAYS

    km = transit_km(frm, to, mode)
    if km is None:
        return None
    c = carrier or baseline_carrier(mode) or {}
    speed = float(c.get("km_per_day") or 25)
    near = int(TRANSIT_NEAR_DAYS.get(mode, 30))
    return max(near, int(_m.ceil(km / speed)))

def transit_days(mode: str, frm: str, to: str) -> Optional[int]:
    """**分档时效**（2026-10-18 Jev A 0.881）：近程用近程基准，超阈值按距离放大。

    ```text
    days = 近程基准                      （km ≤ TRANSIT_NEAR_KM）
         = max(方式基准, ceil(km/speed))  （km >  阈值）
    ```
    缺失里程 ⇒ None（调用方回落既有常量，不臆造）。
    """
    import math as _m

    from content.data_constants import (TRANSIT_MODE_BASE_DAYS, TRANSIT_NEAR_DAYS,
                                        TRANSIT_NEAR_KM, TRANSIT_SPEED_KM_PER_DAY)

    km = transit_km(frm, to, mode)
    if km is None:
        return None
    near = int(TRANSIT_NEAR_DAYS.get(mode, TRANSIT_MODE_BASE_DAYS.get(mode, 30)))
    speed = float(TRANSIT_SPEED_KM_PER_DAY.get(mode, 25))
    # 平滑：近程用近程基准作**下限**，超阈值后按距离线性放大（阈值处不跳变）
    return max(near, int(_m.ceil(km / speed)))

def transport_fee(mode: str, value: float, km: float) -> Optional[int]:
    """运费（设定模型）：`货值 × fee_rate × (km/1000)`，向上取整；未知方式 ⇒ None。

    2026-10-18 标定：原实现按「批数 × 每 km 固定价」，50 万贯陆运会算出 90 万贯运费（超本金），
    不合理；改为**按货值比例**计费（陆 2%/千km、水 0.5%、海 0.3%、驿 5%）。
    """
    from content.data_constants import TRANSPORT_MODES

    spec = TRANSPORT_MODES.get(str(mode or ""))
    if not spec:
        return None
    rate = float(spec.get("fee_rate", 0) or 0)
    v = max(0.0, float(value or 0))
    d = max(0.0, float(km or 0))
    return int(math.ceil(v * rate * (d / 1000.0)))


def sea_lanes_graph():
    """海路图（**沿海岸线**）：返回 (nodes, adj)；边权为**沿岸航线里程**。

    ⚠️ 里程是**设定值非史料**（见 content/data_constants.SEA_LANES 的 note）。
    旧口径「大圆距离 × 1.2」已废弃：它不绕半岛（登州—密州直线 235km，实际须绕成山头）。
    """
    from content.data_constants import SEA_LANES

    adj: Dict[str, Dict[str, float]] = {}
    for link in SEA_LANES:
        a, b = str(link.get("a") or ""), str(link.get("b") or "")
        km = float(link.get("km") or 0)
        if not a or not b or km <= 0:
            continue
        adj.setdefault(a, {})[b] = km
        adj.setdefault(b, {})[a] = km
    return list(adj), adj


def sea_route(frm: str, to: str, month: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """海运航线（**沿海路图最短路**）：{km, days, path, hops}；非海港 ⇒ None。

    · 端点必须是海路图节点（沿海治所）——不在图里 ⇒ **None**（不臆造直线）；
    · km = Dijkstra 累计段里程 + 两端河口加价；days = ceil(km / (1000 × 海速))；
    · 季风修正默认关闭（SEA_MONSOON_ENABLED）。
    """
    import heapq

    from content.data_constants import (SEA_INLET_EXTRA_KM,
                                        SEA_MONSOON_ENABLED, SEA_MONSOON_NORTHBOUND,
                                        SEA_MONSOON_SOUTHBOUND, TRANSPORT_MODES)
    _KM = KM_PER_MONTH

    _nodes, adj = sea_lanes_graph()
    if frm == to:
        return {"km": 0.0, "days": 0, "path": [frm], "hops": 0}
    if frm not in adj or to not in adj:
        return None
    dist: Dict[str, float] = {frm: 0.0}
    prev: Dict[str, str] = {}
    heap = [(0.0, frm)]
    seen = set()
    while heap:
        d, u = heapq.heappop(heap)
        if u in seen:
            continue
        seen.add(u)
        if u == to:
            break
        for v, w in adj.get(u, {}).items():
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))
    if to not in dist:
        return None
    path = [to]
    cur = to
    while cur != frm:
        cur = prev[cur]
        path.append(cur)
    path.reverse()
    km = (float(dist[to])
          + float(SEA_INLET_EXTRA_KM.get(frm, 0))
          + float(SEA_INLET_EXTRA_KM.get(to, 0)))
    speed = float((TRANSPORT_MODES.get("sea") or {}).get("speed") or 1.0)
    if SEA_MONSOON_ENABLED and month is not None:
        idx = _seat_index()
        lat_a = float((idx.get(frm) or {}).get("lat") or 0)
        lat_b = float((idx.get(to) or {}).get("lat") or 0)
        winter = int(month) % 12 in (11, 12, 1, 2)
        season = 1.0
        if lat_b < lat_a and winter:
            season = float(SEA_MONSOON_SOUTHBOUND)
        elif lat_b > lat_a and not winter:
            season = float(SEA_MONSOON_NORTHBOUND)
        speed *= season
    days = 0 if km == 0 else max(1, int(math.ceil(km / (_KM * speed))))
    return {"km": round(km, 1), "days": days, "path": path, "hops": len(path) - 1}



def overseas_route(from_seat: str, partner: str) -> Optional[Dict[str, Any]]:
    """**外海航线**（日本/高丽/南洋）：返回 {km, days, port, partner, note}；无航线 ⇒ None。

    · 外邦港是虚拟节点（无 POP、不落库存），只用于算运费/耗时；
    · 里程/开航季是设定值非史料（见 content/data_constants.SEA_OVERSEAS_LANES 的 note）；
    · `days = ceil(km / (1000 × 海速))`；季风修正仅在 SEA_MONSOON_ENABLED 时生效。
    """
    from content.data_constants import SEA_OVERSEAS_LANES, TRANSPORT_MODES

    best = None
    transship_via = None
    for lane in SEA_OVERSEAS_LANES:
        if str(lane.get("partner")) != str(partner):
            continue
        km = float(lane.get("km") or 0)
        if km <= 0:
            continue
        origin = str(lane.get("from"))
        total = km
        via = None
        if origin != str(from_seat):
            # 转口：境内先沿海路到该港，再出外海（如 明州→广州→三佛齐）
            domestic = sea_route(from_seat, origin)
            if domestic is None:
                continue
            total = float(domestic["km"]) + km
            via = origin
        if best is None or total < float(best.get("km") or 0):
            best = {"km": total, "port": lane.get("port"),
                    "partner": lane.get("partner"), "note": lane.get("note")}
            transship_via = via
    if best is None:
        return None
    speed = float((TRANSPORT_MODES.get("sea") or {}).get("speed") or 1.0)
    km = float(best["km"])
    days = max(1, int(math.ceil(km / (KM_PER_MONTH * speed))))
    return {"km": round(km, 1), "days": days, "port": best.get("port"),
            "partner": best.get("partner"), "transship_via": transship_via,
            "note": best.get("note")}


def overseas_partners() -> list:
    """全部外海对家（含境内航线覆盖情况）。"""
    from content.data_constants import OVERSEAS_PARTNERS

    return list(OVERSEAS_PARTNERS)



def transport_capability(state, frm: str, to: str, mode: str = "land",
                         cargo: Optional[str] = None) -> Dict[str, Any]:
    """**能力判定（只读）**：该方式此刻能否承运该对治所、运力上限、耗时与费率。

    语义：
    · 未知方式 / 未知治所 / 不连通 / 方式不可用 ⇒ `ok=False` + 明确 `reason`（**不回落、不臆造**）；
    · `water`：需全路径各段所属路都在 `WATER_ROUTE_CIRCUITS`（设定表）内 + 漕淤 ≤ 阈值 + 有漕船；
    · `sea`：需政策开海（`state.transport_policy.open_sea`）+ 沿海路；
    · `post`：只允许 `POST_CARGO_KINDS` 里的轻货（运钱粮大宗 ⇒ 拒绝）；
    · 耗时 = ceil(路径天数 / 速度倍率)，至少 1 月；运力 = 方式基数（水/海按漕船数放大）。
    """
    from content.data_constants import (BARGES_POOL_DEFAULT, CANAL_BLOCK_WATER_LIMIT,
                                        POST_CARGO_KINDS, SEA_ROUTE_CIRCUITS,
                                        TRANSPORT_MODES, WATER_ROUTE_CIRCUITS)

    m = str(mode or "land")
    spec = TRANSPORT_MODES.get(m)
    if not spec:
        return {"ok": False, "mode": m, "reason": "unknown_mode"}
    _sea_days_final = False
    if m == "sea":
        sr = sea_route(frm, to)
        if sr is None:
            return {"ok": False, "mode": m, "reason": "unknown_seat"}
        rp = {"reachable": True, "path": list(sr.get("path") or [frm, to]),
              "km": sr["km"], "days": sr["days"],
              "hops": int(sr.get("hops") or len(sr.get("path") or [frm, to]) - 1)}
        _sea_days_final = True
    else:
        rp = route_path(frm, to)
        if rp is None:
            return {"ok": False, "mode": m, "reason": "unknown_seat"}
        if not rp.get("reachable"):
            return {"ok": False, "mode": m, "reason": "unreachable"}

    idx = _seat_index()
    circuits = {str((idx.get(s) or {}).get("circuit") or "") for s in rp["path"]}
    circuits.discard("")
    stats = getattr(state, "statistics", None)
    barges = int(stats.get("barges_pool", BARGES_POOL_DEFAULT) or 0) if isinstance(stats, dict) else BARGES_POOL_DEFAULT
    canal = int(getattr(state, "canal_block", 0) or 0)
    capacity = int(spec["capacity"])

    if m == "water":
        if not WATER_ROUTE_CIRCUITS or not circuits.issubset(WATER_ROUTE_CIRCUITS):
            return {"ok": False, "mode": m, "reason": "not_waterway", "circuits": sorted(circuits)}
        if canal > int(CANAL_BLOCK_WATER_LIMIT):
            return {"ok": False, "mode": m, "reason": "canal_blocked", "canal_block": canal}
        if barges < 1:
            return {"ok": False, "mode": m, "reason": "no_barges"}
        capacity *= max(1, barges)
    elif m == "sea":
        # 2026-10-18 用户质疑「怎么会没开海呢」：此前默认**关闭**且无任何代码能开
        # （与 `MARITIME_INFO[open]` 同型的实现缺陷）。史实：宋代海运/海贸本开，
        # 故**缺失 = 开放**；只有显式 open_sea=False（禁海令）才关闭。
        policy = getattr(state, "transport_policy", None)
        policy = policy if isinstance(policy, dict) else {}
        if policy.get("open_sea") is False:
            return {"ok": False, "mode": m, "reason": "sea_closed_by_policy"}
        # 海运不沿陆路走：只要求**两端**都是沿海路（路径经内陆不影响海运资格）
        ends = {str((idx.get(frm) or {}).get("circuit") or ""),
                str((idx.get(to) or {}).get("circuit") or "")}
        ends.discard("")
        if not SEA_ROUTE_CIRCUITS or not ends or not ends.issubset(SEA_ROUTE_CIRCUITS):
            return {"ok": False, "mode": m, "reason": "not_coastal", "circuits": sorted(ends)}
        capacity *= max(1, barges)
    elif m == "post":
        if cargo is not None and str(cargo) not in POST_CARGO_KINDS:
            return {"ok": False, "mode": m, "reason": "cargo_not_allowed", "cargo": str(cargo)}

    speed = float(spec.get("speed") or 1.0)
    if _sea_days_final:
        days = int(rp.get("days") or 0)
    else:
        # 2026-10-18：改为**按里程算**，不再拿已取整的天数去除速度
        # （base_days=1 时 ÷0.9 会变成 2，把"同一个月内可达"放大成两个月）
        km_val = float(rp.get("km") or 0)
        days = 0 if km_val <= 0 else max(1, int(math.ceil(km_val / (KM_PER_MONTH * speed))))
    return {"ok": True, "mode": m, "name": spec.get("name", m),
            "days": days, "hops": int(rp.get("hops") or 0),
            "km": rp.get("km"), "capacity": capacity,
            "fee_rate": float(spec.get("fee_rate") or 0.0)}


def available_modes(state, frm: str, to: str, cargo: Optional[str] = None) -> Dict[str, Any]:
    """列出各方式此刻的可用性（只读，供 AI 快照/面板用）。"""
    from content.data_constants import TRANSPORT_MODES

    return {m: transport_capability(state, frm, to, mode=m, cargo=cargo)
            for m in TRANSPORT_MODES}


def connectivity_report() -> Dict[str, Any]:
    """全图连通性分析：`{components: [[seat...]], isolated: [...], connected: bool}`。

    治所间无驿路（>200km 且无中转）时如实报**分裂**，**不硬连**。
    """
    nodes, adj = transport_graph()
    seen = set()
    comps = []
    for n in nodes:
        if n in seen:
            continue
        stack = [n]
        comp = []
        seen.add(n)
        while stack:
            u = stack.pop()
            comp.append(u)
            for v in adj.get(u, {}):
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        comps.append(sorted(comp))
    comps.sort(key=len, reverse=True)
    return {"components": comps, "isolated": [c[0] for c in comps if len(c) == 1],
            "connected": len(comps) <= 1, "node_count": len(nodes)}


def transport_links(circuit: Optional[str] = None) -> List[Dict[str, Any]]:
    """列出**同一州府内**的治所对（同路调拨 ⇒ 0 耗时），供读数与测试用。

    ⚠️ 跨路的边**不在此列出**——跨路耗时依赖 `route_days`，且是否发货
    由市场决定，此处只暴露"地理上可算"的事实。
    """
    from content.geo_admin import CIRCUIT_INFO
    from core.foundation.ledger.prefecture_entity import seat_id_of
    out: List[Dict[str, Any]] = []
    for ck, info in CIRCUIT_INFO.items():
        if circuit and ck != circuit:
            continue
        members = [m[0] for m in (info.get("members") or [])]
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                try:
                    out.append({"from": seat_id_of(ck, a), "to": seat_id_of(ck, b),
                                "days": 0})
                except Exception:              # noqa: BLE001 — 脏成员跳过，不猜
                    continue
    return out


def _now(state) -> Optional[int]:
    """当前**绝对月序**（`year × 12 + month`，跨年连续）。

    🔴 **不用 `state.month_index`**——那个字段**不存在**，`getattr(..., 0)`
    会**恒返回 0** ⇒ 在途批次的 `arrive_month` 永远等于发货当月 ⇒
    **物流彻底失效**（所有货瞬间到达，正是 C-c 要防的事）。

    `year`/`month` 读不到 ⇒ 返回 `None`（**未定义**），调用方**拒绝建批次**，
    **不回落 0**——宁可"发不了货"，也不制造"瞬时到达"的假象。
    """
    from core.civil_building import abs_month_index
    return abs_month_index(state)


def dispatch(state, *, frm: str, to: str, dim: str, qty: int,
             trade_id: Optional[str] = None, mode: str = "overland") -> Dict[str, Any]:
    """发货：**立刻从卖方扣货**，建一条**在途批次**，`arrive_month` 月才入账。

    🔴 **钱货两清或两不做**：扣不到货就**不建批次**，不产生"凭空在途"。
    """
    from core.foundation.ledger.material_holding import consume_for_circuit
    idx = _seat_index()
    a = idx.get(frm)
    if not a:
        return {"ok": False, "reason": "unknown_origin", "from": frm}
    days = route_days(frm, to)
    if days is None:
        return {"ok": False, "reason": "route_undefined", "from": frm, "to": to}

    want = max(0, int(qty))
    if want == 0:
        return {"ok": True, "reason": "no_demand", "shipped": 0}
    now = _now(state)
    if now is None:
        # 🔴 时点未定义 ⇒ **拒绝建批次**（不猜、不回落 0）
        return {"ok": False, "reason": "time_undefined", "from": frm, "to": to}
    # P3 季节通航：停航 ⇒ 拒建批次并给下一窗口（不瞬移）；减载/降速按倍率（缺省 1.0）
    _month = (int(now) % 12) or 12
    _season = route_season(mode, _month)
    if _season.get("open") is False:
        return {"ok": False, "reason": "season_closed", "mode": mode,
                "month": _month, "deferred_to": _season.get("deferred_to")}
    _cap_mult = float(_season.get("capacity_mult") or 1.0)
    if 0 < _cap_mult < 1:
        want = max(1, int(want * _cap_mult)) if want > 0 else 0
    _speed_mult = float(_season.get("speed_mult") or 1.0)
    if 0 < _speed_mult < 1:
        days = max(1, int(round(days / _speed_mult)))
    circuit = a["circuit"]
    shipped = consume_for_circuit(state, circuit, dim, want)
    if shipped <= 0:
        return {"ok": False, "reason": "no_stock_local", "shipped": 0}

    dst0 = idx.get(to) or {}
    batch = {
        "trade_id": trade_id,
        "from": frm, "to": to, "dim": dim, "qty": int(shipped),
        # 2026-10-03（方案 C）：批次自带路级归属，「运到哪条路」不必反查州府索引
        "from_circuit": a["circuit"], "to_circuit": dst0.get("circuit"),
        "arrive_month": now + int(days),
        "days": int(days),
        "mode": mode,
        "season_risk_mult": float(_season.get("risk_mult") or 1.0),
        "season_capacity_mult": float(_season.get("capacity_mult") or 1.0),
    }
    book = _book(state)
    book.append(batch)
    return {"ok": True, "reason": "ok", "shipped": int(shipped),
            "arrive_month": batch["arrive_month"], "days": int(days),
            "batch": batch}


def arrive_due(state) -> List[Dict[str, Any]]:
    """把**本月至期**的在途批次入账到目的地商人货栈，返回已到批次列表。

    ⚠️ 只处理 `arrive_month <= 当前月`；**未到期的绝不入账**
    （这是"运没运到"可观测的关键）。
    """
    from core.foundation.ledger.material_holding import merchant_goods
    idx = _seat_index()
    now = _now(state)
    if now is None:
        # 🔴 时点未定义 ⇒ **本批一律不入账**（不猜、不回落 0）
        return []
    book = _book(state)
    arrived: List[Dict[str, Any]] = []
    keep: List[Dict[str, Any]] = []
    for b in book:
        if int(b.get("arrive_month", 0)) > now:
            keep.append(b)
            continue
        dst = idx.get(b["to"])
        goods = merchant_goods(state, dst["circuit"]) if dst else None
        if goods is None:
            # 目的地**无商人货栈** ⇒ 无法入账，保留批次并如实记账，
            # 绝不静默丢弃（缺失≠0）。
            keep.append(b)
            continue
        # 2026-10-18 修：此前还要求 `b["dim"] in goods`，导致「货栈存在但缺该维」
        # 的批次**永远到不了账**（实测：京西路商人 goods={} 时，跨路到货永久挂起）。
        # 缺该维 = 该维库存为 0，不是「货栈不存在」⇒ 建键入账。
        goods[b["dim"]] = int(goods.get(b["dim"], 0) or 0) + int(b["qty"])
        # 2026-10-03（方案 C）：到货**落在哪个治所**必须可观测。
        # 料仍入「本路商人货栈」（路级持有口径未动），但把目的地治所显式带出，
        # 供 `transit_by_seat` / 面板回答「这批料运到了哪个州府」——
        # 这正是 C-c「先运到才能用」此前缺的那一半可观测性。
        arrived.append({**b,
                        "arrived_month": now,
                        "arrived_seat": dst.get("seat"),
                        "arrived_seat_id": dst.get("seat_id"),
                        "arrived_circuit": dst.get("circuit")})
    _set_book(state, keep)
    return arrived


def in_transit(state) -> List[Dict[str, Any]]:
    """当前仍在途的批次（只读）。"""
    return [dict(b) for b in _book(state)]


def transit_by_seat(state) -> Dict[str, Any]:
    """🔴 **州府级在途读数**（2026-10-03 · 口径方案 `建材州府级下沉` §三补二 方案 C）。

    按**目的地治所**汇总在途量：`{seat_id: {seat, circuit, batches, qty:{dim:n}}}`。

    ⚠️ **本函数只做「可观测」，不改变建材记在哪**：料仍入「本路商人货栈」（路级）。
    州府级**存量**读数需先裁定「路级 POP 持有的料如何归属州府」（同方案 A/B）——
    在那之前**不臆造**州府归属。

    缺失即缺：`in_transit` 为空 ⇒ 返回 `{}`（不是 0 州府在途）。
    """
    idx = _seat_index()
    rows: Dict[str, Any] = {}
    for b in in_transit(state):
        seat_id = str(b.get("to") or "")
        dim = str(b.get("dim") or "")
        if not seat_id or not dim:
            continue
        row = rows.get(seat_id)
        if row is None:
            ent = idx.get(seat_id) or {}
            row = {"seat": ent.get("seat"), "circuit": b.get("to_circuit") or ent.get("circuit"),
                   "batches": 0, "qty": {}}
            rows[seat_id] = row
        row["batches"] = int(row["batches"]) + 1
        try:
            q = int(b.get("qty", 0) or 0)
        except (TypeError, ValueError):
            continue
        row["qty"][dim] = int(row["qty"].get(dim, 0) or 0) + q
    return rows


def transit_report(state) -> Dict[str, Any]:
    """与 `market_readout.in_transit` 对齐的结构（原先 `implemented: False`）。"""
    items = in_transit(state)
    return {"implemented": True, "items": items, "count": len(items),
            "by_seat": transit_by_seat(state),
            "note": ("运输耗时按平地常数 KM_PER_MONTH 推算（**设定值，非史料**）；"
                     "路况修正表 ROAD_QUALITY 目前为空——无可靠史料，不臆造。"
                     "`by_seat` 为州府级**在途**量；料仍按路记在商人货栈，"
                     "州府级**存量**口径待裁定（见 docs/建材州府级下沉_口径方案_2026-10-03.md）")}


def _book(state) -> List[Dict[str, Any]]:
    book = getattr(state, "material_transit", None)
    if not isinstance(book, list):
        book = []
        setattr(state, "material_transit", book)
    return book


def _set_book(state, book: List[Dict[str, Any]]) -> None:
    setattr(state, "material_transit", list(book))

#: 交通政策白名单（P5d）：这些键才允许由政令/AI 调整，且取值受限
TRANSPORT_POLICY_KEYS: Dict[str, tuple] = {
    "open_sea": (True, False),
    "mode_pref": ("水运优先", "陆运优先", "驿传优先"),
    "escort": ("无", "镖", "军"),
    "batch": ("整批", "分批", "随到随运"),
    "priority": ("军需", "赈济", "上供", "商货"),
    "use_jiaozi": ("是", "否"),
}

#: 政策默认值（缺失 = 取默认；open_sea 缺省 True = 史实开海）
TRANSPORT_POLICY_DEFAULTS: Dict[str, Any] = {
    "open_sea": True,
    "mode_pref": "水运优先",
    "escort": "无",
    "batch": "随到随运",
    "priority": "商货",
    "use_jiaozi": "否",
}


def transport_policy(state) -> Dict[str, Any]:
    """读取交通政策（补默认值；非法存量值回落默认，**不抛错**）。"""
    cur = getattr(state, "transport_policy", None)
    cur = cur if isinstance(cur, dict) else {}
    out = dict(TRANSPORT_POLICY_DEFAULTS)
    for k, v in cur.items():
        if k in TRANSPORT_POLICY_KEYS and v in TRANSPORT_POLICY_KEYS[k]:
            out[k] = v
    return out


def set_transport_policy(state, **kw) -> Dict[str, Any]:
    """设置交通政策（白名单 + 取值校验）：返回 {ok, applied, rejected}。

    · 未知键 ⇒ 进 rejected（**拒绝式**，不静默忽略）；
    · 非法取值 ⇒ 进 rejected，不写；
    · 一次调用只写通过校验的键，其余存量保持不变。
    """
    applied, rejected = {}, {}
    for k, v in kw.items():
        allowed = TRANSPORT_POLICY_KEYS.get(k)
        if allowed is None:
            rejected[k] = "unknown_key"
        elif v not in allowed:
            rejected[k] = "bad_value（允许：%s）" % (list(allowed),)
        else:
            applied[k] = v
    cur = getattr(state, "transport_policy", None)
    if not isinstance(cur, dict):
        cur = {}
    cur.update(applied)
    state.transport_policy = cur
    return {"ok": not rejected, "applied": applied, "rejected": rejected}


def _tier_of(value: float, cuts) -> str:
    for label, limit in cuts:
        if value <= limit:
            return label
    return cuts[-1][0]


def transport_snapshot(state, route: Optional[str] = None) -> Dict[str, Any]:
    """**区间化快照**（喂 AI prompt）：不吐精密数值，只吐档位区间（审查 P0-2）。"""
    from content.data_constants import BARGES_POOL_DEFAULT

    stats = getattr(state, "statistics", None)
    barges = int(stats.get("barges_pool", BARGES_POOL_DEFAULT) or 0) if isinstance(stats, dict) else BARGES_POOL_DEFAULT
    canal = int(getattr(state, "canal_block", 0) or 0)
    batches = len(in_transit(state))
    nodes, _adj = transport_graph()
    reach = None if route is None else sum(1 for n in nodes if n.startswith(str(route) + "|"))
    return {
        "barges": _tier_of(barges, [("无", 0), ("少", 10), ("中", 30), ("多", 10 ** 9)]),
        "canal": _tier_of(canal, [("通", 10), ("缓", 35), ("淤", 60), ("断", 10 ** 9)]),
        "in_transit": "有" if batches > 0 else "无",
        "in_transit_batches": _tier_of(batches, [("无", 0), ("少", 5), ("多", 10 ** 9)]),
        "reachable": reach,
        "policy": transport_policy(state),
        "note": "区间化快照：精确数值不进 prompt",
    }
