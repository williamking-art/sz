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
KM_PER_MONTH = 1000.0

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
             trade_id: Optional[str] = None) -> Dict[str, Any]:
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
        if goods is None or b["dim"] not in goods:
            # 目的地无商人货栈 ⇒ 无法入账，**保留批次**并如实记账，
            # 绝不静默丢弃（缺失≠0）。
            keep.append(b)
            continue
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