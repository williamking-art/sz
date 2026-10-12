# -*- coding: utf-8 -*-
"""市场缺失原因与来源 ID 的**结构化契约** —— 统一民间市场 P1（M41a）。

为什么需要它（P1 验收第二句）
------------------------------
P1 验收要求「**缺钱／缺货／缺岗位／缺料／缺运力 分别可见**」。现状是各返回值里散着
`reason` 字符串（如 `no_stock_local` / `insufficient_purchasing_power`），**没有统一枚举、
没有"缺口多少"与"本该由谁供"的来源 ID**，读数只能靠调用方各自 `if` 猜。

本模块只做三件事（**不新增账本、不改任何既有字段语义**）：
1. **收敛原因码**：沿用 `market.trade_goods` 既有 `reason` 词汇（**不重命名**，零行为变化）；
2. **五分组映射**：把原因码归到 P1 的五类短缺（钱／货／岗位／料／运力）；
3. **结构化缺口**：`gap(code, need, have, source_id, note)` → 可序列化 dict ＋ `summarize()` 汇总。

纪律
----
* **纯函数、零副作用**：本模块不读写 state、不参与成交；
* **缺失 ≠ 0**：`need`/`have` 不可读时**留 `None`**，不回落 0；
* **可选层**：调用方（如 `market.trade_goods`）挂 `gap` 字段失败**不得影响成交本身**。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    "REASON_CODES", "SHORTAGE_GROUPS", "group_of", "gap",
    "from_trade_outcome", "summarize",
]

# --------------------------------------------------------------------------
# 1. 原因码（**与 market.trade_goods 既有 reason 词汇一致，不重命名**）
# --------------------------------------------------------------------------
REASON_OK = "ok"
REASON_NO_DEMAND = "no_demand"                              # 期望量为 0（不是未满足）
REASON_NO_STOCK = "no_stock_local"                          # 可售为 0 ⇒ 缺货
REASON_NO_MONEY = "insufficient_purchasing_power"           # 买得起量不足 ⇒ 缺钱
REASON_DUPLICATE = "duplicate_trade"                        # 同回合同 trade_id 幂等
REASON_INVALID = "invalid"                                  # 入参非法（拒绝式）
# 以下为**其他域**已用/待用的原因码（登记于此以便统一归组；不改变其产生方）
REASON_NOT_ARRIVED = "not_arrived"                          # 在途未到 ⇒ 运力/时滞
REASON_NO_MATERIAL = "material_short"                       # 缺料
REASON_STOCK_UNKNOWN = "material_stock_unknown"             # 料存量读不出（缺失≠0）
REASON_NO_POST = "no_post"                                  # 无在岗（缺岗位）
REASON_NO_SELLER = "no_seller"                              # 无卖方持有人
REASON_BLOCKED = "unreachable"                              # 两点不通（`route_days` 返回 None）

REASON_CODES = (
    REASON_OK, REASON_NO_DEMAND, REASON_NO_STOCK, REASON_NO_MONEY,
    REASON_DUPLICATE, REASON_INVALID, REASON_NOT_ARRIVED,
    REASON_NO_MATERIAL, REASON_STOCK_UNKNOWN, REASON_NO_POST,
    REASON_NO_SELLER, REASON_BLOCKED,
)

#: P1「五类短缺分别可见」的归组（钱／货／岗位／料／运力）
SHORTAGE_GROUPS: Dict[str, tuple] = {
    "钱": (REASON_NO_MONEY,),
    "货": (REASON_NO_STOCK, REASON_NO_SELLER),
    "岗位": (REASON_NO_POST,),
    "料": (REASON_NO_MATERIAL, REASON_STOCK_UNKNOWN),
    "运力": (REASON_NOT_ARRIVED, REASON_BLOCKED),
}


def group_of(code: str) -> Optional[str]:
    """原因码 → P1 五类短缺之一；非短缺（`ok`/`no_demand`/`invalid`/`duplicate`）⇒ `None`。"""
    for g, codes in SHORTAGE_GROUPS.items():
        if code in codes:
            return g
    return None


# --------------------------------------------------------------------------
# 2. 结构化缺口
# --------------------------------------------------------------------------
def gap(code: str, *, need: Any = None, have: Any = None,
        source_id: Optional[str] = None, note: str = "") -> Dict[str, Any]:
    """一条结构化缺口。

    * `code`：原因码（见 `REASON_CODES`；未知码**如实保留**，不猜）；
    * `need`/`have`：期望量／实有量；**不可读留 `None`（缺失≠0）**；
    * `source_id`：**本该由谁供**的稳定标识（如 `pop:路:阶层` / `local:路:<治所>` /
      `seat:路|治所` / `market:路|商品`）；无依据 ⇒ `None`（**不臆造**）；
    * `group`：由 `code` 派生的 P1 五分组（非短缺 ⇒ `None`）。
    """
    return {"code": str(code), "group": group_of(str(code)),
            "need": need, "have": have, "source_id": source_id, "note": str(note)}


def from_trade_outcome(out: Dict[str, Any], *, need: Any = None,
                       have: Any = None, source_id: Optional[str] = None
                       ) -> Optional[Dict[str, Any]]:
    """从 `market.trade_goods` 的返回**派生**一条缺口；成交/零需求 ⇒ `None`。

    **只读**：不修改 `out`；`unmet_qty > 0` 时以 `out["reason"]` 为码。
    """
    if not isinstance(out, dict):
        return None
    code = str(out.get("reason") or "")
    unmet = out.get("unmet_qty")
    if not isinstance(unmet, (int, float)) or unmet <= 0:
        return None
    if code in (REASON_OK, REASON_NO_DEMAND):
        return None
    return gap(code if code in REASON_CODES else code,
               need=need if need is not None else unmet,
               have=have, source_id=source_id,
               note=str(out.get("detail") or ""))


def summarize(gaps: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """汇总：按码／按五分组计数与缺口量。**空输入 ⇒ 全零 + by_* 为空 dict**（不是"无短缺"。）"""
    by_code: Dict[str, int] = {}
    by_group: Dict[str, int] = {}
    total_unmet: List[float] = []
    n = 0
    for g in gaps or ():
        if not isinstance(g, dict):
            continue
        n += 1
        code = str(g.get("code") or "?")
        by_code[code] = by_code.get(code, 0) + 1
        grp = g.get("group") or group_of(code)
        if grp:
            by_group[grp] = by_group.get(grp, 0) + 1
        v = g.get("need")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            total_unmet.append(float(v))
    return {"count": n, "by_code": by_code, "by_group": by_group,
            "by_group_ordered": {g: by_group.get(g, 0) for g in SHORTAGE_GROUPS},
            "total_need": sum(total_unmet) if total_unmet else 0.0}
