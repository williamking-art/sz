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
    "national_resources_by_dim", "in_transit_by_dim", "pending_stock_by_dim",
    "stock_snapshot", "money_identity", "identity_report",
]

SCHEMA_VERSION = 1

#: 保管方（**顺序即报表顺序**；不合并——合并会把"待定"与"在途"混进合计）
CUSTODY_KEYS = ("pop_goods", "national_resources", "in_transit", "pending_stock")


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
def pop_goods_by_dim(state) -> Optional[Dict[str, float]]:
    """Σ 民间 POP 手持货（逐维）。无 `prefectures` ⇒ `None`（**不是 0**）。"""
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
                for dim, q in goods.items():
                    _add(out, dim, q)
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


def in_transit_by_dim(state) -> Optional[Dict[str, float]]:
    """在途批次合计（逐维）。**运输模块不可用 ⇒ `None`**（不回落 0＝不冒充"没有在途"）。"""
    try:
        from core.transport import in_transit
        batches = in_transit(state)
    except Exception:                                       # noqa: BLE001
        log.warning("stock_identity: 在途读数不可用", exc_info=True)
        return None
    if batches is None:
        return None
    out: Dict[str, float] = {}
    for b in batches or ():
        if not isinstance(b, dict):
            continue
        qty = b.get("qty")
        if isinstance(qty, dict):
            for dim, q in qty.items():
                _add(out, dim, q)
        else:
            dim = b.get("dim")
            if dim is not None:
                _add(out, dim, b.get("qty"))
    return out


def pending_stock_by_dim(state) -> Optional[Dict[str, float]]:
    """**归属待定**槽（逐维）。缺失 ⇒ `None`（用户裁定 6.33：**不并入** `state.resources`）。"""
    pend = getattr(state, "pending_stock", None)
    if pend is None:
        return None
    if not isinstance(pend, dict):
        return None
    out: Dict[str, float] = {}
    for dim, q in pend.items():
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
            "note": ("totals 只含 民间POP + 全国仓 + 在途；**不含**归属待定"
                     "（裁定 6.33：不并入 resources）")}


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
