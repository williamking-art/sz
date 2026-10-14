# -*- coding: utf-8 -*-
"""外贸逐笔**派生记账**（主线 F · 载体甲 · 维度分配甲）—— **纯函数、不写 state**。

依据：`decisions/M175-trade-dimension-allocation-scope.json`（Jev 甲 0.550：按产能/人口权重分配）·
`decisions/JEV-台账-Round149-三口径-2026-10-14.json`（载体甲 0.875）· 设计档 §8/§9。

纪律
----
* **纯函数**：`allocate_legs(state, total_value)` **只算不写** ⇒ 本模块可独立测试、零接线风险；
  接线（把结果 append 进 `state.trade_journal`）由结算批在 `settlement_econ.py:551-570` 一次完成。
* 🔴 **不新增账本**：产出的是**事件元素**（无余额字段），存量仍落 POP/国库/内帑/地方府库。
* 🔴 **守恒**：`Σ(各笔 goods_value) == total_value`（**精确**，用最大余数法分配，最后一步补差）。
* 🔴 **不臆造**：外邦**人口**数据当前不可得 ⇒ 政权侧权重用其**进口品种数**（可升级）；
  缺数据的路/政权**跳过并计数**，不填 0 假装有。
* **口径单点**：税率/费率一律取自 `trade_shadow`（本模块**不复制**数字）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

#: 🔴 **禁止出现在任何流水元素里的键**（出现即视为"在造平行账本"，违反 §3-1）
BANNED_KEYS = frozenset({"balance", "stock", "inventory", "on_hand", "holdings"})

#: 流水元素字段（M175/设计档 §8.1）
LEG_FIELDS = ("month", "route", "seat", "partner", "dim", "qty", "unit_price", "goods_value",
              "freight", "tax_over", "tax_stay", "tax_to", "freight_to", "direction", "reason")

__all__ = ["BANNED_KEYS", "LEG_FIELDS", "route_weights", "allocate_legs", "assert_guards"]


def _num(v) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def route_weights(state) -> List[Tuple[str, float]]:
    """路级权重（**产能口径**）：`yields['盐'] + yields['丝']`（缺数据 ⇒ 该路权重 0 并跳过）。

    返回按权重降序的 `[(路, 权重)]`，仅含**游戏真实路**（`state.prefectures` 的键）。
    """
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return []
    out: List[Tuple[str, float]] = []
    for route, p in prefs.items():
        y = (p or {}).get("yields") or {}
        w = 0.0
        for dim in ("盐", "丝"):
            v = _num(y.get(dim))
            if v:
                w += float(v)
        if w > 0:
            out.append((str(route), w))
    out.sort(key=lambda kv: -kv[1])
    return out


def allocate_legs(state, total_value: int, *, month: Optional[int] = None,
                  partners: Optional[List[str]] = None) -> Dict[str, Any]:
    """把外贸**总量**拆成「路 × 政权 × 商品」的**事件元素**（纯函数；**不写 state**）。

    * 路侧权重：`route_weights`（产能）· **政权侧**：按其 `REGIME_IMPORTS` 的**进口品种数**权重
      （人口不可得 ⇒ 不臆造）；商品取该政权的进口品种（轮转取）。
    * **守恒**：Σ `goods_value` ≡ `total_value`（最大余数法 + 末笔补差）。
    * 无可用路/政权/总量 ≤ 0 ⇒ 返回 `legs=[]` 且 `reason` 非空（**缺失≠0**）。
    """
    from core.domains.economy import trade_shadow as ts          # 口径单点

    route_w = route_weights(state)
    imports: Dict[str, Tuple[str, ...]] = dict(getattr(ts, "REGIME_IMPORTS", {}) or {})
    if partners is not None:
        imports = {k: v for k, v in imports.items() if k in set(partners)}
    tv = _num(total_value)
    if not route_w or not imports or not tv or tv <= 0:
        return {"legs": [], "total": 0, "reason":
                "无可用路（产能为 0）或无可分配政权或总量不可读 ⇒ 不分配（缺失≠0）"}

    # 权重 = 路产能份额 × 政权进口品种数份额；用**整数化**的权重做最大余数分配（确定性、可复现）
    pairs: List[Tuple[Tuple[str, str], float]] = []
    for route, rw in route_w:
        for partner, dims in imports.items():
            k = max(1, len(dims or ()))
            pairs.append(((route, partner), float(rw) * float(k)))
    wsum = sum(w for _k, w in pairs) or 1.0
    targets = [((k, w), float(tv) * w / wsum) for k, w in pairs]
    base = [(k, int(t)) for k, t in targets]
    rem = int(tv) - sum(v for _k, v in base)
    # 最大余数法补差（确定性：按小数部分降序，再按 key 排序打破并列）
    order = sorted(range(len(targets)),
                   key=lambda i: (-(targets[i][1] - int(targets[i][1])), targets[i][0]))
    vals = [v for _k, v in base]
    for i in order[:max(0, rem)]:
        vals[i] += 1

    legs: List[Dict[str, Any]] = []
    dim_cursor: Dict[str, int] = {}
    for (key, _w), value in zip([k for k, _v in base], vals):
        route, partner = key
        dims = imports.get(partner) or ()
        if value <= 0 or not dims:
            continue
        idx = dim_cursor.get(partner, 0) % len(dims)
        dim_cursor[partner] = idx + 1
        legs.append({
            "month": month, "route": route, "seat": None, "partner": partner,
            "dim": dims[idx], "qty": None, "unit_price": None, "goods_value": int(value),
            "freight": None, "tax_over": None, "tax_stay": None,
            "tax_to": f"local_treasury:{route}（过税→沿途地方府库 · 住税→交易地）",
            "freight_to": None, "direction": "export",
            "reason": None if month is not None else "month 未给 ⇒ 绝对月序不可读（缺失≠0）",
        })
    return {"legs": legs, "total": sum(x["goods_value"] for x in legs),
            "routes": len({x["route"] for x in legs}),
            "partners": len({x["partner"] for x in legs}),
            "weight_basis": "路侧＝产能(yields 盐+丝)；政权侧＝其进口品种数（**外邦人口不可得 ⇒ 不臆造**）",
            "reason": None}


def assert_guards(legs: List[Dict[str, Any]], state, total_value: int) -> List[str]:
    """返回**违规清单**（空 = 全过）；供结算批与用例共用（**口径单点**）。

    ① 非平行账本（无 BANNED 键）② 路名 ∈ `state.prefectures` ③ Σ 货值 ≡ 总量 ④ 字段不越界。
    """
    bad: List[str] = []
    prefs = set((getattr(state, "prefectures", {}) or {}).keys())
    for i, leg in enumerate(legs):
        hit = BANNED_KEYS & set(leg)
        if hit:
            bad.append(f"[{i}] 含禁止键（平行账本嫌疑）：{sorted(hit)}")
        if leg.get("route") not in prefs:
            bad.append(f"[{i}] 路名不在 state.prefectures：{leg.get('route')!r}（防幽灵路）")
        extra = set(leg) - set(LEG_FIELDS)
        if extra:
            bad.append(f"[{i}] 越界字段：{sorted(extra)}")
    got = sum(int(x.get("goods_value") or 0) for x in legs)
    if got != int(total_value):
        bad.append(f"守恒破坏：Σ货值 {got} ≠ 总量 {int(total_value)}")
    return bad
