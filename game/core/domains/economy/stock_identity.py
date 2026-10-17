# -*- coding: utf-8 -*-
"""库存与货币恒等式**只读投影** —— 统一民间市场 P1 第一句（M41b）。

P1 验收第一句：「**逐月复原货币与商品库存恒等式**」。
本模块只做**读**：把"货现在在谁手里"与"钱现在记在哪本账上"按**保管方**分列，
并给出可逐月对比的快照；**不写任何 state、不改任何数值**（零行为变化）。

口径
----
* **货（按保管方分列，不合并）**：
  · `pop_goods`：Σ 各路 `pops[阶层].goods[dim]`（路级 pops 是治所真账的**派生镜像**）；
  · `national_resources`：`state.resources[dim]["stock"]`（**全国仓**口径，不是本地市场）；
  · `in_transit`：`core.transport` 在途批次（**已离源、尚未到**——既不在来源可售、也不在目的可售）；
  · `pending_stock`：**归属待定**槽（用户裁定 6.33 **不并入** `state.resources`）⇒ **单列**，
    绝不并入任何合计，否则等于给待定货硬派归属。
* **钱**：直接复用 `money.snapshot`（M0–M3 与 `ACCOUNTS` 的既有单点），本模块**不重算公式**，
  只把 `M_ALL` 与各账户之和的**残差**如实报出（用于发现账本漂移）。
* **缺失 ≠ 0**：任一保管方不可读 ⇒ 该项 `None` ＋ `warnings`，**不回落 0**；
  合计只在**全部可读**时给出，否则 `None`。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

__all__ = [
    "SCHEMA_VERSION", "CUSTODY_KEYS", "pop_goods_by_dim",
    "national_resources_by_dim", "seat_warehouses_by_dim",
    "in_transit_by_dim", "pending_stock_by_dim",
    "stock_snapshot", "money_identity", "identity_report",
    "stock_delta", "residual_report",
    "GRAIN_CUSTODY_KEYS", "central_granary", "prefectural_storage",
    "prefectural_changping", "pop_grain", "in_transit_grain",
    "grain_snapshot", "grain_delta", "master_economic_balance_sheet",
    "format_master_balance_sheet",
]

SCHEMA_VERSION = 1

#: 商品保管方（**顺序即报表顺序**；不合并——合并会把"待定"与"在途"混进合计）
CUSTODY_KEYS = ("pop_goods", "national_resources", "seat_warehouses",
                "in_transit", "pending_stock")

#: 粮食保管方（Jev 裁定 P=0.993：官民分立、中央与地方分列、在途独立）
GRAIN_CUSTODY_KEYS = (
    "central_granary",      # 中央太仓 state.granary
    "prefectural_storage",  # 地方州仓 storage
    "changping_stock",      # 地方常平仓 changping_stock
    "pop_grain",            # 民间各阶层手持私粮 pops[*].grain
    "in_transit_grain",     # 漕运与商队在途批次粮
)


def _num(v) -> Optional[float]:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def _add(acc: Dict[str, float], dim: str, qty) -> None:
    q = _num(qty)
    if q is None:
        return
    acc[str(dim)] = acc.get(str(dim), 0.0) + q


# --------------------------------------------------------------------------
# 各保管方（逐商品维）
# --------------------------------------------------------------------------
def _sum_leaves(node, depth: int = 0) -> Dict[str, float]:
    """把**数值**或**嵌套桶**（如 `{治所: {dim: n}}`，POP `goods` 的州府桶形态）摊平成 `{dim: n}`。

    🔴 **为什么必须兼容两种形态**：POP 下沉后 `pops[阶层]["goods"]` 可能是
    `{dim: n}`，也可能是 `{治所: {dim: n}}`（州府桶）。只看数值会把后者**全部跳过** ⇒
    读数恒为 0、恒等式假"闭合"（2026-10-13 实测踩到）。`depth` 上限防脏档无限递归。
    """
    out: Dict[str, float] = {}
    if not isinstance(node, dict) or depth > 4:
        return out
    for k, v in node.items():
        q = _num(v)
        if q is not None:
            out[str(k)] = out.get(str(k), 0.0) + q
        elif isinstance(v, dict):
            for d, x in _sum_leaves(v, depth + 1).items():
                out[d] = out.get(d, 0.0) + x
    return out


def pop_goods_by_dim(state) -> Optional[Dict[str, float]]:
    """Σ 民间 POP 手持货（逐维）。无 `prefectures` ⇒ `None`（**不是 0**）。

    兼容 `goods` 的两种形态：`{dim: n}` 与 `{治所: {dim: n}}`（州府桶）——见 `_sum_leaves`。
    """
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return None
    out: Dict[str, float] = {}
    for pdata in prefs.values():
        pops = (pdata or {}).get("pops") if isinstance(pdata, dict) else None
        if not isinstance(pops, dict):
            continue
        for slot in pops.values():
            goods = (slot or {}).get("goods") if isinstance(slot, dict) else None
            if isinstance(goods, dict):
                for dim, q in _sum_leaves(goods).items():
                    out[dim] = out.get(dim, 0.0) + q
    return out


def national_resources_by_dim(state) -> Optional[Dict[str, float]]:
    """全国仓存量（逐维）。无 `resources` ⇒ `None`；`resources` 存在但某维读不出 ⇒ 跳过该维。"""
    res = getattr(state, "resources", None)
    if not isinstance(res, dict):
        return None
    out: Dict[str, float] = {}
    for dim, cell in res.items():
        stock = cell.get("stock") if isinstance(cell, dict) else cell
        _add(out, dim, stock)
    return out


def seat_warehouses_by_dim(state) -> Optional[Dict[str, float]]:
    """Σ 治所物理四仓（`seats[治所].warehouses[*].stocks`）逐维合计。

    无任何 `warehouses` 桶 ⇒ `None`（缺失≠0）；桶存在但为空 ⇒ `{}`。
    """
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return None
    out: Dict[str, float] = {}
    for pdata in prefs.values():
        seats = (pdata or {}).get("seats") if isinstance(pdata, dict) else None
        if not isinstance(seats, dict):
            continue
        for seat in seats.values():
            if not isinstance(seat, dict):
                continue
            warehouses = seat.get("warehouses")
            if not isinstance(warehouses, dict):
                continue
            for cell in warehouses.values():
                stocks = cell.get("stocks") if isinstance(cell, dict) else None
                if not isinstance(stocks, dict):
                    continue
                for dim, q in stocks.items():
                    _add(out, dim, q)
    # prefectures 存在但尚无 warehouses ⇒ 空持仓（可读零），不是 None；
    # 只有 prefectures 容器本身缺失才返回 None（缺失≠0）。
    return out


def in_transit_by_dim(state) -> Optional[Dict[str, float]]:
    """在途批次合计（逐维）：兼容 `material_transit` 与 `in_transit_batches` 两账。

    真·只读：不创建没出现的容器；两者都不存在 ⇒ `{}`（没有在途是可读事实）；
    `material_transit` 存在时沿用 `transport.in_transit`（既有 monkeypatch 契约），
    再额外并入 `in_transit_batches`（空间桥接账）。
    """
    _mt = getattr(state, "material_transit", None)
    _it = getattr(state, "in_transit_batches", None)
    if _mt is None and _it is None:
        return {}
    if (_mt is not None and not isinstance(_mt, list)) or \
            (_it is not None and not isinstance(_it, list)):
        return None
    out: Dict[str, float] = {}

    def _consume(batches, spatial=False):
        for b in batches or ():
            if not isinstance(b, dict):
                continue
            qty = b.get("qty")
            if isinstance(qty, dict):
                for dim, q in qty.items():
                    _add(out, dim, q)
                continue
            dim = b.get("dim") or (b.get("goods_dim") if spatial else None)
            if dim is None:
                continue
            q = b.get("qty")
            if q is None:
                q = b.get("gross_amount", b.get("net_delivered", b.get("volume")))
            _add(out, dim, q)

    if _mt is not None:
        try:
            from core.transport import in_transit
            batches = in_transit(state)
        except Exception:  # noqa: BLE001
            log.warning("stock_identity: 在途读数不可用", exc_info=True)
            return None
        if batches is None:
            return None
        _consume(batches, spatial=False)
    if _it is not None:
        _consume(_it, spatial=True)
    return out


def pending_stock_by_dim(state) -> Optional[Dict[str, float]]:
    """**归属待定**槽（逐维）。缺失 ⇒ `None`（用户裁定 6.33：**不并入** `state.resources`）。

    真实结构是 `{路: {dim: {qty, owner_status, ...}}}`；旧实现按 `{dim: qty}` 展平
    ⇒ 读到 dict 就跳过，待定货永远从恒等式消失。
    """
    pend = getattr(state, "pending_stock", None)
    if pend is None:
        return None
    if not isinstance(pend, dict):
        return None
    out: Dict[str, float] = {}
    for key, value in pend.items():
        if isinstance(value, dict) and "qty" in value:
            # 兼容旧的扁平形态 `{dim: {qty, ...}}`
            if value.get("owner_status") != "已确权":
                _add(out, key, value.get("qty"))
            continue
        if not isinstance(value, dict):
            # 兼容旧的扁平形态 `{dim: qty}`
            _add(out, key, value)
            continue
        # 真实结构 `{路: {dim: {qty, owner_status, ...}}}`
        for dim, entry in value.items():
            if isinstance(entry, dict):
                if entry.get("owner_status") == "已确权":
                    continue
                q = entry.get("qty")
            else:
                q = entry
            _add(out, dim, q)
    return out


def stock_snapshot(state) -> Dict[str, Any]:
    """按保管方分列的库存快照（**含合计，但只有在全部可读时才给**）。

    返回 `{schema_version, by_custody: {...}, dims: [...], totals: {dim: 合计|None},
            all_readable: bool, warnings: [...]}`。
    `totals` **不含** `pending_stock`（归属待定，单列）。
    """
    parts = {
        "pop_goods": pop_goods_by_dim(state),
        "national_resources": national_resources_by_dim(state),
        "seat_warehouses": seat_warehouses_by_dim(state),
        "in_transit": in_transit_by_dim(state),
        "pending_stock": pending_stock_by_dim(state),
    }
    warnings: List[str] = []
    for k, v in parts.items():
        if v is None:
            warnings.append(f"{k} 不可读（缺失≠0，不回落 0）")

    dims = sorted({d for v in parts.values() if isinstance(v, dict) for d in v})
    addable = [k for k in CUSTODY_KEYS if k != "pending_stock"]
    all_readable = all(isinstance(parts[k], dict) for k in addable)
    totals: Dict[str, Optional[float]] = {}
    for d in dims:
        if not all_readable:
            totals[d] = None
        else:
            totals[d] = sum(float(parts[k].get(d, 0.0)) for k in addable)
    return {"schema_version": SCHEMA_VERSION, "by_custody": parts, "dims": dims,
            "totals": totals, "all_readable": all_readable, "warnings": warnings,
            "note": ("totals 只含 民间POP + 全国仓 + 治所四仓 + 在途；"
                     "**不含**归属待定（裁定 6.33：不并入 resources）")}


# --------------------------------------------------------------------------
# 货币恒等式（复用既有单点，不重算公式）
# --------------------------------------------------------------------------
def money_identity(state) -> Dict[str, Any]:
    """复用 `money.snapshot` 给出 M0–M3 与 `ACCOUNTS` 之和的**残差**（只读）。

    `residual == 0` 表示 `M_ALL` 与账户投影一致；读不到 ⇒ 各项 `None` ＋ `warning`。
    """
    try:
        from core.foundation.ledger import money
        snap = money.snapshot(state)
    except Exception as e:                                  # noqa: BLE001
        log.warning("stock_identity: 货币快照不可用", exc_info=True)
        return {"available": False, "reason": f"{type(e).__name__}: {e}",
                "m_all": None, "accounts_sum": None, "residual": None}
    keys = tuple(getattr(money, "ACCOUNTS", ()) or ())
    vals = [snap.get(k) for k in keys]
    readable = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals)
    acc_sum = float(sum(vals)) if readable else None
    m_all = snap.get("M_ALL")
    residual = (float(m_all) - acc_sum) if (acc_sum is not None
                                           and isinstance(m_all, (int, float))) else None
    return {"available": True, "keys": list(keys), "m_all": m_all,
            "accounts_sum": acc_sum, "residual": residual,
            "m0": snap.get("m0"), "m1": snap.get("m1"),
            "m2": snap.get("m2"), "m3": snap.get("m3")}


def identity_report(state) -> Dict[str, Any]:
    """P1 第一句的**只读**报表：库存按保管方分列 ＋ 货币残差。"""
    stock = stock_snapshot(state)
    mon = money_identity(state)
    warnings = list(stock.get("warnings") or [])
    if isinstance(mon.get("residual"), (int, float)) and abs(mon["residual"]) > 1e-6:
        warnings.append(f"货币残差非零：M_ALL − ΣACCOUNTS = {mon['residual']}")
    if not mon.get("available"):
        warnings.append("货币快照不可读")
    return {"schema_version": SCHEMA_VERSION, "stock": stock, "money": mon,
            "warnings": warnings}


# --------------------------------------------------------------------------
# 逐月 Δ 与残差（P1 第一句「**逐月**复原恒等式」）
# --------------------------------------------------------------------------
def stock_delta(prev: Dict[str, Any], curr: Dict[str, Any]) -> Dict[str, Any]:
    """两次 `stock_snapshot` 的**逐保管方／逐维**差额（纯函数、只读）。

    * `by_custody[k][dim] = curr − prev`（任一侧该保管方不可读 ⇒ 该维 `None`——缺失≠0）；
    * `net[dim]` ＝ **可加四方**（民间 POP ＋ 全国仓 ＋ 治所四仓 ＋ 在途）的 Δ合计；
      任一项不可读 ⇒ `None`；**不含** `pending_stock`（归属待定，单列在
      `by_custody` 里，便于发现"待定池变动"）；
    * `all_readable` 为两侧可加 custody 均可读。
    """
    def _parts(snap):
        if not isinstance(snap, dict):
            return None
        return snap.get("by_custody")

    p, c = _parts(prev), _parts(curr)
    out: Dict[str, Any] = {"by_custody": {}, "net": {}, "all_readable": False}
    if not isinstance(p, dict) or not isinstance(c, dict):
        return out
    dims = sorted({d for k in CUSTODY_KEYS for d in
                   list((p.get(k) or {})) + list((c.get(k) or {}))})
    addable = [k for k in CUSTODY_KEYS if k != "pending_stock"]
    for k in CUSTODY_KEYS:
        pv, cv = p.get(k), c.get(k)
        # 旧快照（资产字段引入前）没有 seat_warehouses：按空持仓兼容，
        # 否则所有历史快照的 net 都会因缺键变 None。
        if k == "seat_warehouses" and pv is None and cv is None:
            pv = cv = {}
        row: Dict[str, Optional[float]] = {}
        for d in dims:
            if not isinstance(pv, dict) or not isinstance(cv, dict):
                row[d] = None
            else:
                row[d] = float(cv.get(d, 0.0)) - float(pv.get(d, 0.0))
        out["by_custody"][k] = row
    def _readable(snap, k):
        return isinstance(snap.get(k), dict) or (k == "seat_warehouses" and snap.get(k) is None)

    for d in dims:
        if all(_readable(p, k) and _readable(c, k) for k in addable):
            out["net"][d] = sum(out["by_custody"][k][d] for k in addable)
        else:
            out["net"][d] = None
    out["all_readable"] = all(_readable(p, k) and _readable(c, k) for k in addable)
    return out


def residual_report(prev: Dict[str, Any], curr: Dict[str, Any],
                    flows: Optional[Dict[str, float]] = None,
                    tol: float = 1e-6) -> Dict[str, Any]:
    """**残差报告**：`Δ库存` 对 `已记录流量`（`flows = {dim: 产−耗}`）。

    🔴 **`flows` 由调用方提供**：本模块**不猜**流量账。若某个维的产量/消费量在现库里
    没有权威记录键，就**给不出残差**——此时 `residual[dim] = None` 并在 `unclosed` 里列出，
    绝不把"没有账"当成"残差 0"（那是把未知当已验）。
    """
    delta = stock_delta(prev, curr)
    residual: Dict[str, Optional[float]] = {}
    unclosed: List[str] = []
    for d, dv in (delta.get("net") or {}).items():
        fv = None if not isinstance(flows, dict) else flows.get(d)
        if dv is None:
            residual[d] = None
            unclosed.append(d)
            continue
        if not isinstance(fv, (int, float)):
            # Δ==0 且无账目 ⇒ 视为闭合（"零变动维"不该被误判为无账）
            if abs(float(dv)) < 1e-9:
                residual[d] = 0.0
                continue
            residual[d] = None
            unclosed.append(d)
            continue
        residual[d] = float(dv) - float(fv)
    bad = sorted(d for d, r in residual.items() if isinstance(r, (int, float)) and abs(r) > tol)
    return {"delta": delta, "flows_provided": isinstance(flows, dict),
            "residual": residual, "unclosed": sorted(unclosed), "nonzero": bad,
            "ok": bool(not bad and not unclosed)}


# --------------------------------------------------------------------------
# 粮食全息保管方（Jev 裁定 P=0.993：官民分立、中央与地方分列、在途独立）
# --------------------------------------------------------------------------
def central_granary(state) -> Optional[float]:
    """中央太仓存粮（石）。无 `granary` 属性 ⇒ None（缺失≠0）。"""
    if not hasattr(state, "granary"):
        return None
    return _num(getattr(state, "granary", None))


def prefectural_storage(state) -> Optional[float]:
    """全域州仓/上供仓粮食合计（石）。

    无 `prefectures` 属性 ⇒ None（缺失≠0）。
    兼容治所下沉：若路下有 `seats`，优先累加治所真账中的 `storage`，
    否则累加路级 `storage`（保双向兼容与零破坏）。
    """
    prefs = getattr(state, "prefectures", None)
    if prefs is None or not isinstance(prefs, dict):
        return None
    total = 0.0
    for pdata in prefs.values():
        if not isinstance(pdata, dict):
            continue
        seats = pdata.get("seats")
        if isinstance(seats, dict) and seats:
            for s in seats.values():
                if isinstance(s, dict):
                    q = _num(s.get("storage"))
                    if q is not None:
                        total += q
        else:
            q = _num(pdata.get("storage"))
            if q is not None:
                total += q
    return total


def prefectural_changping(state) -> Optional[float]:
    """全域常平仓粮食合计（石）。

    无 `prefectures` 属性 ⇒ None（缺失≠0）。
    兼容治所下沉：若路下有 `seats`，优先累加治所真账中的 `changping_stock`，
    否则累加路级 `changping_stock`。
    """
    prefs = getattr(state, "prefectures", None)
    if prefs is None or not isinstance(prefs, dict):
        return None
    total = 0.0
    for pdata in prefs.values():
        if not isinstance(pdata, dict):
            continue
        seats = pdata.get("seats")
        if isinstance(seats, dict) and seats:
            for s in seats.values():
                if isinstance(s, dict):
                    q = _num(s.get("changping_stock"))
                    if q is not None:
                        total += q
        else:
            q = _num(pdata.get("changping_stock"))
            if q is not None:
                total += q
    return total


def pop_grain(state) -> Optional[float]:
    """全域民间 POP 手持粮食合计（石，包含自耕农口粮、士绅窖藏等）。

    无 `prefectures` 属性 ⇒ None（缺失≠0）。
    兼容治所桶形态：`pop["grain"]` 可能是数值，也可能是 `{治所: n}` 字典。
    """
    prefs = getattr(state, "prefectures", None)
    if prefs is None or not isinstance(prefs, dict):
        return None
    total = 0.0
    for pdata in prefs.values():
        pops = (pdata or {}).get("pops") if isinstance(pdata, dict) else None
        if not isinstance(pops, dict):
            continue
        for slot in pops.values():
            if not isinstance(slot, dict):
                continue
            g = slot.get("grain")
            q = _num(g)
            if q is not None:
                total += q
            elif isinstance(g, dict):
                for val in g.values():
                    vq = _num(val)
                    if vq is not None:
                        total += vq
    return total


def in_transit_grain(state) -> Optional[float]:
    """在途批次中的粮食合计（石）。

    真·只读：无 `material_transit` 属性 ⇒ 返回 0.0 且不创建该容器。
    容器在但读数不可用 ⇒ None（不冒充无在途）。
    """
    if getattr(state, "material_transit", None) is None:
        return 0.0
    try:
        from core.transport import in_transit
        batches = in_transit(state)
    except Exception:
        log.warning("stock_identity: 粮食在途读数不可用", exc_info=True)
        return None
    if batches is None:
        return None
    total = 0.0
    for b in batches or ():
        if not isinstance(b, dict):
            continue
        qty = b.get("qty")
        if isinstance(qty, dict):
            for k, v in qty.items():
                if str(k) in ("grain", "粮", "粮食"):
                    q = _num(v)
                    if q is not None:
                        total += q
        else:
            dim = b.get("dim")
            if str(dim) in ("grain", "粮", "粮食"):
                q = _num(b.get("qty"))
                if q is not None:
                    total += q
    return total


def grain_snapshot(state) -> Dict[str, Any]:
    """全域粮食保管方快照（只读）。

    返回：`{schema_version, by_custody: {...}, total: 合计|None, all_readable: bool, warnings: [...]}`。
    """
    parts = {
        "central_granary": central_granary(state),
        "prefectural_storage": prefectural_storage(state),
        "changping_stock": prefectural_changping(state),
        "pop_grain": pop_grain(state),
        "in_transit_grain": in_transit_grain(state),
    }
    warnings: List[str] = []
    for k, v in parts.items():
        if v is None:
            warnings.append(f"粮食保管方 {k} 不可读（缺失≠0）")
    all_readable = all(v is not None for v in parts.values())
    total = sum(float(v) for v in parts.values()) if all_readable else None
    return {
        "schema_version": SCHEMA_VERSION,
        "by_custody": parts,
        "total": total,
        "all_readable": all_readable,
        "warnings": warnings,
    }


def grain_delta(prev: Dict[str, Any], curr: Dict[str, Any]) -> Dict[str, Any]:
    """两次 `grain_snapshot` 的保管方差额（纯函数）。"""
    def _parts(snap):
        if not isinstance(snap, dict):
            return None
        return snap.get("by_custody")

    p, c = _parts(prev), _parts(curr)
    out: Dict[str, Any] = {"by_custody": {}, "total": None, "all_readable": False}
    if not isinstance(p, dict) or not isinstance(c, dict):
        return out
    for k in GRAIN_CUSTODY_KEYS:
        pv, cv = p.get(k), c.get(k)
        if pv is None or cv is None:
            out["by_custody"][k] = None
        else:
            out["by_custody"][k] = float(cv) - float(pv)
    all_readable = all(out["by_custody"].get(k) is not None for k in GRAIN_CUSTODY_KEYS)
    out["all_readable"] = all_readable
    if all_readable:
        out["total"] = sum(float(out["by_custody"][k]) for k in GRAIN_CUSTODY_KEYS)
    return out


# --------------------------------------------------------------------------
# 系统级全息经济变动总表（Master Economic Balance Sheet）
# --------------------------------------------------------------------------
def master_economic_balance_sheet(
    prev_state,
    curr_state,
    monthly_flows: Optional[Dict[str, Any]] = None,
    tol: float = 1e-6,
) -> Dict[str, Any]:
    """系统级全息经济变动总表（开发与测试生命体征监护仪）。

    支持传入 state 对象，或预先取样的 snapshot。
    涵盖：
    - 粮食（太仓 + 州仓 + 常平仓 + POP私粮 + 在途）
    - 20 维商品（POP手持 + 全国仓 + 在途）
    - 货币（M_ALL 与各账户核验）

    :param prev_state: 期初 state 或其 snapshot 字典
    :param curr_state: 期末 state 或其 snapshot 字典
    :param monthly_flows: 可选的月度产耗流量表，形如：
           `{"grain": {"harvest": 100, "consume": -80, ...}, "timber": 20, ...}`
           若对应维为 dict，净流量 = sum(flows.values())；若为数值，净流量即该值。
    :param tol: 残差容差（默认 1e-6）
    :return: 包含 balance_sheet、all_closed、unclosed、nonzero 的完整全息审计报告
    """
    # 1. 粮食快照与 Δ
    p_grain = prev_state.get("grain") if isinstance(prev_state, dict) and "grain" in prev_state else grain_snapshot(prev_state)
    c_grain = curr_state.get("grain") if isinstance(curr_state, dict) and "grain" in curr_state else grain_snapshot(curr_state)
    g_delta = grain_delta(p_grain, c_grain)

    # 2. 商品快照与 Δ
    p_stock = prev_state.get("stock") if isinstance(prev_state, dict) and "stock" in prev_state else stock_snapshot(prev_state)
    c_stock = curr_state.get("stock") if isinstance(curr_state, dict) and "stock" in curr_state else stock_snapshot(curr_state)
    s_delta = stock_delta(p_stock, c_stock)

    # 3. 货币快照
    c_money = curr_state.get("money") if isinstance(curr_state, dict) and "money" in curr_state else money_identity(curr_state)

    # 4. 构建全维度总表
    balance_sheet: Dict[str, Any] = {}
    unclosed: List[str] = []
    nonzero: List[str] = []

    # (a) 粮食项
    g_init = p_grain.get("total") if p_grain.get("all_readable") else None
    g_final = c_grain.get("total") if c_grain.get("all_readable") else None
    g_diff = g_delta.get("total") if g_delta.get("all_readable") else None

    g_flows_entry = (monthly_flows or {}).get("grain")
    g_net_flow: Optional[float] = None
    if isinstance(g_flows_entry, dict):
        g_net_flow = sum(float(_num(v) or 0.0) for v in g_flows_entry.values())
    elif isinstance(g_flows_entry, (int, float)):
        g_net_flow = float(g_flows_entry)

    g_res: Optional[float] = None
    g_closed = False
    if g_diff is not None:
        if g_net_flow is not None:
            g_res = float(g_diff) - float(g_net_flow)
            g_closed = abs(g_res) <= tol
            if not g_closed:
                nonzero.append("grain")
        elif abs(float(g_diff)) < 1e-9:
            g_res = 0.0
            g_closed = True
        else:
            unclosed.append("grain")
    else:
        unclosed.append("grain")

    balance_sheet["grain"] = {
        "unit": "石",
        "initial": g_init,
        "final": g_final,
        "delta": g_diff,
        "flows": g_flows_entry,
        "net_flow": g_net_flow,
        "residual": g_res,
        "is_closed": g_closed,
        "by_custody": {
            "initial": p_grain.get("by_custody"),
            "final": c_grain.get("by_custody"),
            "delta": g_delta.get("by_custody"),
        },
    }

    # (b) 20 维商品项
    all_dims = sorted(list(p_stock.get("dims") or []) + list(c_stock.get("dims") or []))
    for dim in all_dims:
        d_init = (p_stock.get("totals") or {}).get(dim)
        d_final = (c_stock.get("totals") or {}).get(dim)
        d_diff = (s_delta.get("net") or {}).get(dim)

        d_flows_entry = (monthly_flows or {}).get(dim)
        d_net_flow = None
        if isinstance(d_flows_entry, dict):
            d_net_flow = sum(float(_num(v) or 0.0) for v in d_flows_entry.values())
        elif isinstance(d_flows_entry, (int, float)):
            d_net_flow = float(d_flows_entry)

        d_res = None
        d_closed = False
        if d_diff is not None:
            if d_net_flow is not None:
                d_res = float(d_diff) - float(d_net_flow)
                d_closed = abs(d_res) <= tol
                if not d_closed:
                    nonzero.append(dim)
            elif abs(float(d_diff)) < 1e-9:
                d_res = 0.0
                d_closed = True
            else:
                unclosed.append(dim)
        else:
            unclosed.append(dim)

        balance_sheet[dim] = {
            "unit": "单位",
            "initial": d_init,
            "final": d_final,
            "delta": d_diff,
            "flows": d_flows_entry,
            "net_flow": d_net_flow,
            "residual": d_res,
            "is_closed": d_closed,
        }

    # (c) 货币核验
    mon_res = c_money.get("residual")
    mon_ok = (mon_res is not None and abs(float(mon_res)) <= tol) if c_money.get("available") else False

    warnings: List[str] = []
    warnings.extend(p_grain.get("warnings") or [])
    warnings.extend(c_grain.get("warnings") or [])
    warnings.extend(p_stock.get("warnings") or [])
    warnings.extend(c_stock.get("warnings") or [])
    if not mon_ok and c_money.get("available"):
        warnings.append(f"货币账户核验残差非零：{mon_res}")

    all_closed = (not unclosed) and (not nonzero) and (mon_ok or not c_money.get("available"))

    return {
        "schema_version": SCHEMA_VERSION,
        "balance_sheet": balance_sheet,
        "money": c_money,
        "grain": {"initial": p_grain, "final": c_grain, "delta": g_delta},
        "all_closed": all_closed,
        "unclosed": sorted(unclosed),
        "nonzero": sorted(nonzero),
        "warnings": warnings,
    }


def format_master_balance_sheet(report: Dict[str, Any]) -> str:
    """将全息变动总表渲染为整齐易读的 ASCII 控制台报表。"""
    bs = report.get("balance_sheet") or {}
    lines = [
        "========================= 宋祚 · 系统级全息经济变动总表 =========================",
        f"{'物资维度':<10} | {'期初全域存量':>14} | {'净流量 (产-耗)':>14} | {'实际期末存量':>14} | {'残差 (差额)':>12} | {'闭合状态'}",
        "-" * 81,
    ]
    for dim, row in bs.items():
        init_s = f"{row['initial']:,.1f}" if row['initial'] is not None else "None"
        final_s = f"{row['final']:,.1f}" if row['final'] is not None else "None"
        flow_s = f"{row['net_flow']:+,.1f}" if row['net_flow'] is not None else "-"
        res_s = f"{row['residual']:+,.2f}" if row['residual'] is not None else "未闭合"
        status_s = "[OK]" if row['is_closed'] else "[UNCLOSED]"
        lines.append(f"{dim:<10} | {init_s:>14} | {flow_s:>14} | {final_s:>14} | {res_s:>12} | {status_s}")
    lines.append("=" * 81)
    mon = report.get("money") or {}
    if mon.get("available"):
        m_all = f"{mon.get('m_all'):,.1f}" if mon.get('m_all') is not None else "None"
        m_res = f"{mon.get('residual'):,.2f}" if mon.get('residual') is not None else "None"
        lines.append(f"货币 M_ALL: {m_all} 贯 | 账户与总量残差: {m_res} 贯")
        lines.append("=" * 81)
    return "\n".join(lines)

