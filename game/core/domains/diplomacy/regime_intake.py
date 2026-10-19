# -*- coding: utf-8 -*-
"""攻占州府的接收通道（P5.5，2026-10-19）。

Jev 裁定：**只计人口/土地，税/产冻结**（0.614 / B 0.262 / C 0.124）——
占领方先"拿到人口与土地"，税收与产出**不立即归其所有**（避免与宋侧冻结规则冲突、也不双记账）。

数据来源（缺失一律 None，不回落 0）：
- 外邦 T1：region["pop"]（6 类 size/wealth/grain）、region["land"]
- 宋 T1：prefecture_ref → prefectures[路][seats][治所]["pops"]（人口）；**土地无座级字段 ⇒ None + reason**

不动：treasury / armies / tech / attitude（政权字段不随地域走）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = ["regime_intake", "status_of_occupied"]


def _son_regions(state, regime: str) -> List[Dict[str, Any]]:
    book = getattr(state, "regions", None) or {}
    return [dict(r, region_id=rid) for rid, r in book.items()
            if isinstance(r, dict) and r.get("owner") == regime]


def _seat_pops(state, route: str, seat: str) -> Optional[Dict[str, Any]]:
    prefs = getattr(state, "prefectures", None) or {}
    p = prefs.get(route) or {}
    row = (p.get("seats") or {}).get(seat)
    if not isinstance(row, dict):
        return None
    pops = row.get("pops")
    return pops if isinstance(pops, dict) else None


def regime_intake(state, regime: str) -> Dict[str, Any]:
    """接收方口径：人口（人/万人）、土地；税产冻结。"""
    rows = _son_regions(state, regime)
    t1 = [r for r in rows if r.get("level") == "T1"]
    pop_people = 0
    pop_known = False
    land_total = 0
    land_missing: List[str] = []
    frozen: List[str] = []
    for r in t1:
        ref = r.get("prefecture_ref") or {}
        if ref.get("route"):     # 宋州府：人口读 seats 真账；土地无座级字段
            pops = _seat_pops(state, str(ref["route"]), str(ref.get("seat")))
            if pops:
                pop_known = True
                for cls, v in pops.items():
                    if isinstance(v, dict) and isinstance(v.get("size"), (int, float)):
                        pop_people += int(v["size"])
            land_missing.append(r.get("region_id"))
            frozen.append(r.get("region_id"))
            continue
        pop = r.get("pop")       # 外邦州府：人口在 region 内
        if isinstance(pop, dict):
            pop_known = True
            for cls, v in pop.items():
                if isinstance(v, dict) and isinstance(v.get("size"), (int, float)):
                    pop_people += int(v["size"])
        if isinstance(r.get("land"), (int, float)):
            land_total += int(r["land"])
        else:
            land_missing.append(r.get("region_id"))
        frozen.append(r.get("region_id"))
    return {
        "regime": regime,
        "t1_count": len(t1),
        "population_people": pop_people if pop_known else None,
        "population_wan": round(pop_people / 10000.0, 2) if pop_known else None,
        "population_reason": None if pop_known else "州府人口缺失（缺失≠0）",
        "land": land_total if not land_missing else None,
        "land_missing_regions": land_missing,
        "tax_output_frozen": True,
        "frozen_regions": frozen,
        "note": "Jev A：只计人口/土地；税产冻结（占领方尚未进项）",
    }


def status_of_occupied(state, regime: str) -> Dict[str, Any]:
    """占领方当前进项状态（供面板/调试；默认政权无占领地 ⇒ 空）。"""
    intake = regime_intake(state, regime)
    return {"regime": regime, "occupied_t1": intake["t1_count"],
            "population_wan": intake["population_wan"],
            "tax_output_frozen": intake["tax_output_frozen"]}
