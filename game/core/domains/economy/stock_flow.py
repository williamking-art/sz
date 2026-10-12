# -*- coding: utf-8 -*-
"""逐维商品流量账（登记式测量仪器） —— 统一民间市场 P1 / M42a。

为什么需要它
------------
P1 第一句要求「**逐月复原货币与商品库存恒等式**」。M41c 全流水取证证明：货确实在动
（6 轮 10 维变动），但 `state.statistics` 只有**聚合**流量键、`granary_stats` 只有粮腿
⇒ 拿不到 `flows = {dim: 产−耗}` ⇒ `stock_identity.residual_report` 对全部维度判 `unclosed`。

本模块提供**逐维流量登记**，使残差可闭合。

性质与纪律
----------
* 🔴 **测量仪器，不是 custody 真账**：它**不持有货、不参与结算判定**。因此**部分接线是安全的**
  —— 覆盖不到的写点只表现为"残差偏大/该维未闭合"，**不会**像 M37 那样造成账本漂移。
* **不新增平行账本**：只是**登记**既有写点已经发生的量（"入/出"由调用方按既有写点的返回值登记），
  真账仍是 `state.resources` / `pops[].goods` / `state.pending_stock`。
* **按月分桶，无需清零点**：`state.stock_flow = {月序: {dim: {in, out, by_reason}}}`。
  ⚠️ 不改 `run_monthly_settlement`（它有 AST 内省测试）；月桶天然隔离，且保留历史便于逐月对账。
* **账实一致**：只登记**实际发生量**（既有写点的返回值），不按意图量登记——否则会造出
  「记了流量但货没动」的假账。
* **缺失 ≠ 0**：取不到月序 ⇒ `month=None` 桶（如实标注），**不假装落在某月**；某维无登记 ⇒
  该维在 `flows_for` 里**缺席**（调用方据此判 `unclosed`，而不是当 0）。
* **纯登记、可失败**：登记函数**不抛**（结算不得因测量仪器失败而中断），异常只留痕。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

#: state 上的容器键（**登记式**；随档整表序列化）
STATE_KEY = "stock_flow"

__all__ = [
    "STATE_KEY", "current_month", "record_in", "record_out", "flows_for",
    "flows_delta", "coverage", "residual_for_custody",
]


def current_month(state) -> Optional[int]:
    """当前**绝对月序**（既有单点：`civil_building.abs_month_index`）。

    取不到 ⇒ `None`（**不假装落在某月**）。"""
    try:
        from core.civil_building import abs_month_index
        m = abs_month_index(state)
        return int(m) if isinstance(m, (int, float)) else None
    except Exception:                                       # noqa: BLE001
        return None


def _bucket(state, month: Optional[int] = None, *, create: bool = False) -> Optional[Dict[str, Any]]:
    flow = getattr(state, STATE_KEY, None)
    if not isinstance(flow, dict):
        if not create:
            return None
        flow = {}
        try:
            setattr(state, STATE_KEY, flow)
        except Exception:                                   # noqa: BLE001
            log.warning("stock_flow: 无法在 state 上创建容器", exc_info=True)
            return None
    m = month if month is not None else current_month(state)
    # 🔴 **键规范化为字符串**：JSON（存档整表序列化）会把 int 键回转成 str ⇒
    #    若这里用 int 键，读档后 `flows_for(month=7)` 会**读成空**（实测踩到）。
    #    统一 str(m)，并在查找侧同样规范化 ⇒ int/str 两种写法都能命中。
    key = "unknown" if m is None else str(int(m))
    if create:
        return flow.setdefault(key, {})
    return flow.get(key)


def _add(state, dim: str, qty, direction: str, reason: str) -> int:
    """**内部**：登记一笔（不抛）。返回登记量（不可读/非正 ⇒ 0）。"""
    try:
        q = int(qty or 0)
    except (TypeError, ValueError):
        return 0
    if q <= 0:
        return 0
    try:
        bucket = _bucket(state, None, create=True)
        if bucket is None:
            return 0
        row = bucket.setdefault(str(dim), {"in": 0, "out": 0, "by_reason": {}})
        row[direction] = int(row.get(direction, 0) or 0) + q
        reasons = row.setdefault("by_reason", {})
        rk = f"{direction}:{reason or 'unspecified'}"
        reasons[rk] = int(reasons.get(rk, 0) or 0) + q
        return q
    except Exception:                                       # noqa: BLE001 — 测量仪器不得中断结算
        log.warning("stock_flow: 登记失败 dim=%s dir=%s", dim, direction, exc_info=True)
        return 0


def record_in(state, dim: str, qty, reason: str = "") -> int:
    """登记**进入**该 custody 的量（如生产入仓、和买入仓）。"""
    return _add(state, dim, qty, "in", reason)


def record_out(state, dim: str, qty, reason: str = "") -> int:
    """登记**离开**该 custody 的量（如领料出仓、熔铜、售出）。"""
    return _add(state, dim, qty, "out", reason)


def flows_for(state, month: Optional[int] = None) -> Dict[str, Dict[str, int]]:
    """某月逐维流量 `{dim: {in, out, net, by_reason}}`；无登记 ⇒ `{}`（**不是 0**）。"""
    bucket = _bucket(state, month, create=False)
    if not isinstance(bucket, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for dim, row in bucket.items():
        if not isinstance(row, dict):
            continue
        i = int(row.get("in", 0) or 0)
        o = int(row.get("out", 0) or 0)
        out[str(dim)] = {"in": i, "out": o, "net": i - o,
                         "by_reason": dict(row.get("by_reason") or {})}
    return out


def flows_delta(state, month: Optional[int] = None) -> Dict[str, int]:
    """某月逐维**净流量** `{dim: in − out}`（供 `residual_report(flows=…)` 直接使用）。"""
    return {d: v["net"] for d, v in flows_for(state, month).items()}


def coverage(state, month: Optional[int] = None) -> Dict[str, Any]:
    """**覆盖率读数**：本月登记了哪些维/哪些原因（用于判断"还能闭合多少"）。"""
    f = flows_for(state, month)
    reasons: Dict[str, int] = {}
    for v in f.values():
        for k, q in (v.get("by_reason") or {}).items():
            reasons[k] = reasons.get(k, 0) + int(q)
    return {"month": current_month(state) if month is None else int(month),
            "dims": sorted(f), "dim_count": len(f),
            "reasons": reasons, "registered": bool(f)}


def residual_for_custody(prev: Dict[str, Any], curr: Dict[str, Any], custody: str,
                         flows: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """**单 custody 残差**：`Δ(custody) − flows`（配合 `stock_identity.stock_delta` 用）。

    适用于「只跟踪一条 custody 链」的批次（M42a：全国仓）；`flows` 没给的维 ⇒ `unclosed`。
    """
    from core.domains.economy import stock_identity as si
    delta = si.stock_delta(prev, curr)
    row = (delta.get("by_custody") or {}).get(custody) or {}
    residual: Dict[str, Optional[float]] = {}
    unclosed = []
    for dim, dv in row.items():
        fv = None if not isinstance(flows, dict) else flows.get(dim)
        if dv is None or not isinstance(fv, (int, float)):
            residual[dim] = None
            unclosed.append(dim)
        else:
            residual[dim] = float(dv) - float(fv)
    nonzero = sorted(d for d, r in residual.items()
                     if isinstance(r, (int, float)) and abs(r) > 1e-6)
    return {"custody": custody, "residual": residual, "unclosed": sorted(unclosed),
            "nonzero": nonzero, "ok": bool(not nonzero and not unclosed)}
