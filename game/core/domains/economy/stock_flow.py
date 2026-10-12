# -*- coding: utf-8 -*-
"""逐维商品流量账（登记式测量仪器） —— 统一民间市场 P1 / M42。

为什么需要它
------------
P1 第一句要求「**逐月复原货币与商品库存恒等式**」。M41c 全流水取证证明：货确实在动，
但 `state.statistics` 只有**聚合**流量键、`granary_stats` 只有粮腿 ⇒ 拿不到
`flows = {dim: 产−耗}` ⇒ `stock_identity.residual_report` 只能把各维判 `unclosed`。

本模块提供**逐维、逐 custody** 的流量登记，使残差可逐条链闭合。

保管方（custody）维度
--------------------
不同链的"进/出"含义不同（全国仓的进＝生产/和买；POP 侧另有产出与消费）⇒ 账目**按 custody 分列**：

* `CUSTODY_NATIONAL`（默认）＝ `state.resources` 全国仓；
* `CUSTODY_POP` ＝ 民间 POP `goods` 池；
* 其它 custody 允许登记（字符串），`stock_snapshot` 里同为 `by_custody` 的键即可对齐。

性质与纪律
----------
* 🔴 **测量仪器，不是 custody 真账**：不持货、不参与结算判定 ⇒ **部分接线安全**
  （覆盖不到的写点只表现为残差偏大，不会造成账本漂移）。
* **不新增平行账本**：只是**登记**既有写点已发生的量（按既有写点的**返回值/前后差**）。
* **按月分桶**：`state.stock_flow = {月序: {custody: {dim: {in, out, by_reason}}}}`
  ⇒ **无需清零点** ⇒ 不改 `run_monthly_settlement`（它有 AST 内省测试）。
  ⚠️ **键规范化为字符串**：JSON 存档会把 int 键回转成 str，用 int 键会让读档后读成空。
* **账实一致**：只登记**实际发生量**；**缺失 ≠ 0**：未登记维**缺席**（调用方判 `unclosed`）。
* **登记不抛**：测量仪器不得中断结算。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

#: 🔴 承载容器：state 上的**独立**属性（`state.stock_flow`）。
#: 为什么**不**放进 `state.statistics`：`statistics` 被**财政隔离契约**整表比对
#: （`test_m36_4/5`：同种子两局 `dict(a.statistics) == dict(b.statistics)`）⇒
#: 把逐月流量账塞进去会让"测量仪器"污染该契约（实测 2026-10-13 两例转红）。
#: 为什么可以新增该属性：它是**登记式测量仪器**——不持 custody 真账、不参与任何结算判定、
#: 不 gate 任何玩法；「禁新增状态属性」守卫（`test_b2r6_export.test_no_parallel_ledger_is_created`）
#: 已按**有理由的例外**登记（见该用例的 allowlist 注释）。
STATE_KEY = "stock_flow"

CUSTODY_NATIONAL = "national_resources"
CUSTODY_POP = "pop_goods"
CUSTODY_IN_TRANSIT = "in_transit"

__all__ = [
    "STATE_KEY", "CUSTODY_NATIONAL", "CUSTODY_POP", "CUSTODY_IN_TRANSIT",
    "current_month", "flows_container", "record_in", "record_out", "flows_for",
    "flows_delta", "cumulative_flows", "coverage", "residual_for_custody",
]


def flows_container(state, *, create: bool = False) -> Optional[Dict[str, Any]]:
    """取（或按需建）流量账容器；不可用 ⇒ `None`（不抛）。"""
    flow = getattr(state, STATE_KEY, None)
    if isinstance(flow, dict):
        return flow
    if not create:
        return None
    flow = {}
    try:
        setattr(state, STATE_KEY, flow)
    except Exception:                                       # noqa: BLE001
        log.warning("stock_flow: 无法创建容器", exc_info=True)
        return None
    return flow


def current_month(state) -> Optional[int]:
    """当前**绝对月序**（既有单点：`civil_building.abs_month_index`）；取不到 ⇒ `None`。"""
    try:
        from core.civil_building import abs_month_index
        m = abs_month_index(state)
        return int(m) if isinstance(m, (int, float)) else None
    except Exception:                                       # noqa: BLE001
        return None


def _bucket(state, month: Optional[int] = None, custody: str = CUSTODY_NATIONAL, *,
            create: bool = False) -> Optional[Dict[str, Any]]:
    flow = flows_container(state, create=create)
    if not isinstance(flow, dict):
        return None
    m = month if month is not None else current_month(state)
    # 🔴 **键规范化为字符串**（月序与 custody 都是）：JSON 会把 int 键回转成 str，
    #    用 int 键会让读档后 `flows_for(month=7)` **读成空**（2026-10-13 实测踩到并修）。
    mkey = "unknown" if m is None else str(int(m))
    if create:
        month_b = flow.setdefault(mkey, {})
        if not isinstance(month_b, dict):
            return None
        return month_b.setdefault(str(custody), {})
    month_b = flow.get(mkey)
    if not isinstance(month_b, dict):
        return None
    b = month_b.get(str(custody))
    return b if isinstance(b, dict) else None


def _add(state, dim: str, qty, direction: str, reason: str, custody: str) -> int:
    try:
        q = int(qty or 0)
    except (TypeError, ValueError):
        return 0
    if q <= 0:
        return 0
    try:
        bucket = _bucket(state, None, custody, create=True)
        if bucket is None:
            return 0
        row = bucket.setdefault(str(dim), {"in": 0, "out": 0, "by_reason": {}})
        row[direction] = int(row.get(direction, 0) or 0) + q
        reasons = row.setdefault("by_reason", {})
        rk = f"{direction}:{reason or 'unspecified'}"
        reasons[rk] = int(reasons.get(rk, 0) or 0) + q
        return q
    except Exception:                                       # noqa: BLE001 — 仪器不得中断结算
        log.warning("stock_flow: 登记失败 dim=%s dir=%s custody=%s", dim, direction, custody,
                    exc_info=True)
        return 0


def record_in(state, dim: str, qty, reason: str = "",
              custody: str = CUSTODY_NATIONAL) -> int:
    """登记**进入**该 custody 的量（全国仓：生产/和买；POP：产出/买入）。"""
    return _add(state, dim, qty, "in", reason, custody)


def record_out(state, dim: str, qty, reason: str = "",
               custody: str = CUSTODY_NATIONAL) -> int:
    """登记**离开**该 custody 的量（全国仓：领料/售出；POP：被买走/消费/折旧）。"""
    return _add(state, dim, qty, "out", reason, custody)


def flows_for(state, month: Optional[int] = None,
              custody: str = CUSTODY_NATIONAL) -> Dict[str, Dict[str, Any]]:
    """某月某 custody 的逐维流量 `{dim: {in, out, net, by_reason}}`；无登记 ⇒ `{}`。"""
    bucket = _bucket(state, month, custody, create=False)
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


def flows_delta(state, month: Optional[int] = None,
                custody: str = CUSTODY_NATIONAL) -> Dict[str, int]:
    """某月某 custody 的逐维**净流量**（供 `residual_report(flows=…)` 直接使用）。"""
    return {d: v["net"] for d, v in flows_for(state, month, custody).items()}


def cumulative_flows(state, custody: str = CUSTODY_NATIONAL) -> Dict[str, int]:
    """**跨全月桶累计**净流量 `{dim: Σ(in−out)}`（逐月对账用）。"""
    net: Dict[str, int] = {}
    flow = flows_container(state) or {}
    if not isinstance(flow, dict):
        return net
    for _m, month_b in flow.items():
        if not isinstance(month_b, dict):
            continue
        bucket = month_b.get(str(custody))
        if not isinstance(bucket, dict):
            continue
        for dim, row in bucket.items():
            if not isinstance(row, dict):
                continue
            net[str(dim)] = (net.get(str(dim), 0) + int(row.get("in", 0) or 0)
                             - int(row.get("out", 0) or 0))
    return net


def coverage(state, month: Optional[int] = None,
             custody: str = CUSTODY_NATIONAL, *, all_months: bool = False) -> Dict[str, Any]:
    """某 custody 的**覆盖率读数**：登记了哪些维/哪些原因。

    ⚠️ `all_months=False`（默认）只报**当前月**——结算跑完后当前月通常已无登记 ⇒ 会显示 0 维
    （2026-10-13 实测误导）。看"整体覆盖了多少"应传 `all_months=True`（跨全月桶汇总）。
    """
    if all_months:
        dims = sorted(cumulative_flows(state, custody=custody))
        reasons: Dict[str, int] = {}
        flow = flows_container(state) or {}
        if isinstance(flow, dict):
            for _m, month_b in flow.items():
                b = month_b.get(str(custody)) if isinstance(month_b, dict) else None
                if not isinstance(b, dict):
                    continue
                for _d, row in b.items():
                    if isinstance(row, dict):
                        for k, q in (row.get("by_reason") or {}).items():
                            reasons[k] = reasons.get(k, 0) + int(q)
        return {"custody": custody, "month": None, "all_months": True,
                "dims": dims, "dim_count": len(dims),
                "reasons": reasons, "registered": bool(dims)}
    f = flows_for(state, month, custody)
    reasons = {}
    for v in f.values():
        for k, q in (v.get("by_reason") or {}).items():
            reasons[k] = reasons.get(k, 0) + int(q)
    return {"custody": custody, "all_months": False,
            "month": current_month(state) if month is None else int(month),
            "dims": sorted(f), "dim_count": len(f),
            "reasons": reasons, "registered": bool(f)}


def residual_for_custody(prev: Dict[str, Any], curr: Dict[str, Any], custody: str,
                         flows: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """**单 custody 残差**：`Δ(custody) − flows`（配合 `stock_identity.stock_delta` 用）。

    判定（2026-10-13 修正）：`Δ` 不可读 ⇒ `unclosed`；**`Δ==0` 且无账目 ⇒ 视为闭合**
    （零变动维本就无需账目）；**`Δ≠0` 且无账目 ⇒ `unclosed`**（有变动却没账，必须报出来）。
    """
    from core.domains.economy import stock_identity as si
    delta = si.stock_delta(prev, curr)
    row = (delta.get("by_custody") or {}).get(custody) or {}
    residual: Dict[str, Optional[float]] = {}
    unclosed = []
    for dim, dv in row.items():
        fv = None if not isinstance(flows, dict) else flows.get(dim)
        if dv is None:
            residual[dim] = None
            unclosed.append(dim)
            continue
        if not isinstance(fv, (int, float)):
            if abs(float(dv)) < 1e-9:
                residual[dim] = 0.0
                continue
            residual[dim] = None
            unclosed.append(dim)
            continue
        residual[dim] = float(dv) - float(fv)
    nonzero = sorted(d for d, r in residual.items()
                     if isinstance(r, (int, float)) and abs(r) > 1e-6)
    return {"custody": custody, "residual": residual, "unclosed": sorted(unclosed),
            "nonzero": nonzero, "ok": bool(not nonzero and not unclosed)}
