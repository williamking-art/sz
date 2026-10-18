# -*- coding: utf-8 -*-
"""外贸与运输**读数层**（P2，2026-10-18）。

只读：不写 state、不改结算。数据来源严格限定：

| 读数 | 来源 | 缺失语义 |
|---|---|---|
| 贸易额/货值/税费 | `state.trade_journal`（逐笔货腿） | 无流水 ⇒ **0（真零）**；字段缺 ⇒ `None` |
| 通道拆分 | `FOREIGN_TRADE_PORTS` 的 partner→channel | partner 不在口岸表 ⇒ `None`（不猜） |
| 进口额/白银流 | 逐笔字段（当前只有 export） | `None` + `reason`（缺失≠0） |
| 口岸级货值 | 需 leg.seat（当前为 None） | `None` + `reason`（不臆造路→口岸归属） |
| 运力/在途 | `transport_capacity` / `transport_used` / `in_transit` | 无载具 ⇒ 0 且标 bottleneck |

纪律：**不复制算法**（税率/运费一律来自流水），**不臆造**（缺字段就 None）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = ["survey_foreign_trade", "survey_transport", "survey_all"]


def _partner_channel(partner: str) -> Optional[str]:
    """partner → 通道（sea/land）；多通道（如交趾）取**先登记**者，读不出 ⇒ None。"""
    from content.data_constants import FOREIGN_TRADE_PORTS

    for p in FOREIGN_TRADE_PORTS or ():
        if str(p.get("partner")) == str(partner):
            return str(p.get("channel"))
    return None


def _legs(state) -> Optional[List[dict]]:
    """逐笔货腿；字段缺失 ⇒ None（不把"没有该字段"当成空流水）。"""
    journal = getattr(state, "trade_journal", None)
    if journal is None:
        return None
    return [x for x in journal if isinstance(x, dict)]


def survey_foreign_trade(state) -> Dict[str, Any]:
    """外贸读数：通道级贸易额/货值/税费、货种 TopN、阻塞归因、区间化口岸。

    缺失一律 `None` 并附 `reasons`，**不回落 0**（只有"确有流水但为零"才报 0）。
    """
    legs = _legs(state)
    if legs is None:
        return {"implemented": False, "reason": "state.trade_journal 缺失（缺失≠0）"}

    reasons: Dict[str, str] = {}
    channels: Dict[str, Dict[str, Any]] = {}
    dims: Dict[str, int] = {}
    blocked: List[Dict[str, Any]] = []
    total = 0
    unknown_partner: List[str] = []

    for leg in legs:
        partner = str(leg.get("partner") or "")
        value = leg.get("goods_value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            reasons.setdefault("goods_value", "部分流水 goods_value 缺失（缺失≠0）")
            continue
        value = int(value)
        total += value
        ch = _partner_channel(partner)
        if ch is None:
            unknown_partner.append(partner)
            ch = "unknown"
        row = channels.setdefault(ch, {"trade_value": 0, "export_value": 0,
                                       "import_value": None, "tax": 0, "batches": 0})
        row["trade_value"] += value
        direction = str(leg.get("direction") or "")
        if direction == "export":
            row["export_value"] += value
        elif direction == "import":
            row["import_value"] = (row["import_value"] or 0) + value
        else:
            reasons.setdefault("direction", "部分流水 direction 缺失")
        for tk in ("tax_over", "tax_stay"):
            tv = leg.get(tk)
            if isinstance(tv, (int, float)) and not isinstance(tv, bool):
                row["tax"] += int(tv)
        row["batches"] += 1
        dim = str(leg.get("dim") or "")
        if dim:
            dims[dim] = dims.get(dim, 0) + value
        if leg.get("reason"):
            blocked.append({"partner": partner, "dim": dim, "reason": str(leg.get("reason"))})

    if unknown_partner:
        reasons.setdefault("partner_channel", f"对家未登记通道：{sorted(set(unknown_partner))}")
    if all(r["import_value"] is None for r in channels.values()):
        reasons.setdefault("import_value", "当前流水只记出口腿（进口未接线）")
    reasons.setdefault("silver_flow", "逐笔流水无白银结算字段（P5 接货腿后补）")
    reasons.setdefault("ports", "逐笔流水 seat 为空 ⇒ 无法归到口岸（缺失≠0，不臆造）")

    top = sorted(dims.items(), key=lambda kv: -kv[1])[:5]
    return {
        "implemented": True,
        "trade_value": total,
        "channels": channels,
        "top_dims": [{"dim": d, "value": v} for d, v in top],
        "blocked": blocked,
        "import_value": None,
        "silver_flow": None,
        "ports": None,
        "batches": len(legs),
        "reasons": reasons,
    }


def survey_transport(state) -> Dict[str, Any]:
    """运输读数：各方式 运力/已用/剩余/瓶颈 + 在途批次**剩余回合**。"""
    from core.transport import (KM_PER_MONTH, _now, in_transit, transport_capacity,
                                transport_remaining)

    out: Dict[str, Any] = {"modes": {}}
    for mode in ("waterway", "maritime", "overland", "post"):
        cap = transport_capacity(state, mode)
        out["modes"][mode] = {
            "capacity": cap.get("capacity"),
            "remaining": round(transport_remaining(state, mode), 1),
            "bottleneck": cap.get("bottleneck"),
            "availability": cap.get("availability"),
        }
    now = _now(state)
    rows = []
    for b in in_transit(state):
        arrive = b.get("arrive_month")
        remain = (int(arrive) - int(now)) if (now is not None and isinstance(arrive, int)) else None
        rows.append({"from": b.get("from"), "to": b.get("to"), "dim": b.get("dim"),
                     "qty": b.get("qty"), "mode": b.get("mode"),
                     "arrive_month": arrive, "remaining_months": remain})
    out["in_transit"] = rows
    out["in_transit_count"] = len(rows)
    return out


def survey_all(state) -> Dict[str, Any]:
    return {"foreign_trade": survey_foreign_trade(state),
            "transport": survey_transport(state)}