# -*- coding: utf-8 -*-
"""产业上游原料物理确权与水陆物流运力调拨调度器（单一权威源）。

## 规格与背景（M314 / 产业上游与物流体系深度耦合）

针对产业上游（矿山开采、生丝采摘、原麻收割）与下游工坊、朝廷太仓脱节，
物料曾存在“空中虚拟池”或“瞬移到货”的弊端，本模块实现两大闭环：

1. **产业上游物料真账确权入仓（`ingest_upstream_production`）**：
   - 上游开采产出的煤炭、铁矿、生铜、原麻、生丝、木石，直接依据物权属性，
     物理写入该路首府治所的物理四仓：
     - 官营矿山/朝廷税收部分 → `public_depot`（官方料场）或 `public_granary`（常平仓/州仓）；
     - 民间商贾开采/采户自留部分 → `civilian_depots`（民间货栈塌房）。
   - 彻底消灭“产物挂在空中无处可查”的伪现实。

2. **跨州府产业物流调度与运力制约（`dispatch_industry_logistics`）**：
   - 下游工坊、京师铸钱监、官工营造缺料时，自动发起空间调拨；
   - 遵循《宋祚》水陆立体交通网络：
     - **水路漕运（优先）**：途经黄河、汴河、长江、运河水系，速度快（15天），途耗低（0.5%/日）；
       但受该路**漕运淤塞（canal_block）**与**新造漕船（barges）运力池**制约；
       无船或河道淤塞时，调拨被迫受阻或转向陆运；
     - **陆路驿道（次选）**：大车驮马与民夫挑担，速度慢（30天），沈括途耗高（2.0%/日）；
   - 扣减始发地物理仓库，生成在途批次（`in_transit_batches`），按日结算民夫途耗，
     运抵后确权注入目标治所仓位。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from core.foundation.ledger.spatial_warehouse_bridge import (
    dispatch_spatial_transfer,
    warehouse_stock_add,
    warehouse_stock_get,
)

log = logging.getLogger(__name__)

__all__ = [
    "ingest_upstream_production",
    "dispatch_industry_logistics",
    "survey_logistics_coupling",
]


def ingest_upstream_production(
    state: Any,
    circuit: str,
    raw_materials: Dict[str, float],
    clerk_grip: float = 0.45,
) -> Dict[str, Any]:
    """将某路上游采掘/收获的原料，物理确权写入该路治所四仓。

    官营入 `public_depot`，民办入 `civilian_depots`。
    """
    if state is None or not raw_materials:
        return {"ingested_total": 0.0}

    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict) or circuit not in prefs:
        return {"ingested_total": 0.0}

    p = prefs[circuit]
    seats = p.get("seats")
    if not isinstance(seats, dict) or not seats:
        return {"ingested_total": 0.0}

    # 定位该路首府/主治所
    from core.foundation.ledger.building_bridge import capital_seat_id
    cap_sid = capital_seat_id(p, circuit)
    if not cap_sid or cap_sid not in seats:
        cap_sid = next(iter(seats.keys()))

    total_ingested = 0.0
    ingested_details: Dict[str, Dict[str, float]] = {}

    for dim, qty in raw_materials.items():
        if qty <= 0 or dim == "mine_tax_coin":
            continue

        # 官营上解比重（铜、盐大部归官；煤铁木石官民并进）
        if dim in ("铜", "盐", "copper_ore", "salt_raw"):
            gov_ratio = 0.70 - clerk_grip * 0.15
        elif dim in ("grain", "原粮"):
            gov_ratio = 0.35  # 两税纳粮入仓
        else:
            gov_ratio = 0.40 - clerk_grip * 0.15

        gov_ratio = max(0.20, min(0.90, gov_ratio))
        gov_qty = round(qty * gov_ratio, 1)
        civ_qty = round(qty - gov_qty, 1)

        # 1. 官营部分入官仓/料场
        wh_gov = "public_granary" if dim in ("grain", "原粮") else "public_depot"
        warehouse_stock_add(state, cap_sid, wh_gov, dim, gov_qty, reason="upstream_harvest_gov")

        # 2. 民营部分入市井货栈
        warehouse_stock_add(state, cap_sid, "civilian_depots", dim, civ_qty, reason="upstream_harvest_civ")

        total_ingested += qty
        ingested_details[dim] = {"gov_share": gov_qty, "civ_share": civ_qty}

    return {
        "circuit": circuit,
        "capital_seat": cap_sid,
        "total_ingested": round(total_ingested, 1),
        "details": ingested_details,
    }


def dispatch_industry_logistics(
    state: Any,
    origin_circuit: str,
    target_circuit: str,
    goods_dim: str,
    amount: float,
    owner: str = "state:treasury",
    log: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """跨州府调度产业原料物流（受运力与水陆交通网络物理约束）。

    - 自动判断水路（漕运）与陆路；
    - 水路检查该路漕运通畅度（canal_block）与漕船可用量；
    - 扣减始发地仓储，建立在途批次，清算沈括途耗。
    """
    if state is None or amount <= 0:
        return {"ok": False, "reason": "invalid_parameters"}

    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return {"ok": False, "reason": "no_prefectures"}

    p_orig = prefs.get(origin_circuit)
    p_targ = prefs.get(target_circuit)
    if not p_orig or not p_targ:
        return {"ok": False, "reason": "circuit_not_found"}

    from core.foundation.ledger.building_bridge import capital_seat_id
    orig_sid = capital_seat_id(p_orig, origin_circuit) or next(iter(p_orig.get("seats", {}).keys()), origin_circuit)
    targ_sid = capital_seat_id(p_targ, target_circuit) or next(iter(p_targ.get("seats", {}).keys()), target_circuit)

    # 1. 判定交通模式：检查始发与终点路的水路航道档位（'强', '有', '弱'）
    from core.domains.economy.waterway_seats import waterway_tier_route
    orig_w_tier = waterway_tier_route(origin_circuit)
    targ_w_tier = waterway_tier_route(target_circuit)

    # 两端皆有水路（档位为 '强' 或 '有'）时走水运漕运；否则走陆运
    can_waterway = (orig_w_tier in ("强", "有") and targ_w_tier in ("强", "有"))

    stats = getattr(state, "statistics", {}) or {}
    barges_avail = int(stats.get("barges_pool", 50) or 50)
    canal_block = int(getattr(state, "canal_block", 0) or 0)

    # 若漕运严重淤塞 (>35) 或无漕船，水路运力受限降级为陆运
    if can_waterway and canal_block <= 35 and barges_avail >= 2:
        transit_mode = "waterway"
        # 占用漕船运力（调拨结束后释放，此处模拟运力池占用）
        stats["barges_pool"] = max(0, barges_avail - 2)
    else:
        transit_mode = "overland"

    # 2. 调用物理仓储底座建立在途物流批次
    res = dispatch_spatial_transfer(
        state=state,
        origin_seat=orig_sid,
        target_seat=targ_sid,
        goods_dim=goods_dim,
        amount=amount,
        owner=owner,
        transit_mode=transit_mode,
    )

    if res.get("ok"):
        days = res.get("days", 30)
        porters = res.get("porters", 10)
        mode_desc = "汴淮漕运水路" if transit_mode == "waterway" else "驿道陆运大车"
        if isinstance(log, list):
            log.append(f"[产业物流] 从{origin_circuit}调拨{amount:,.0f}单位【{goods_dim}】发往{target_circuit}："
                       f"经{mode_desc}，预计耗时{days}日，征调夫役{porters}人（沈括途耗清算中）。")

    return {
        "ok": res.get("ok", False),
        "origin_seat": orig_sid,
        "target_seat": targ_sid,
        "transit_mode": transit_mode,
        "batch_id": res.get("batch_id"),
        "reason": res.get("reason"),
    }


def survey_logistics_coupling(state: Any) -> Dict[str, Any]:
    """汇总当前全域产业物流在途与调拨运转总览（只读派生）。"""
    batches = getattr(state, "in_transit_batches", []) or []
    by_dim: Dict[str, float] = {}
    by_mode: Dict[str, int] = {"waterway": 0, "overland": 0, "maritime": 0}

    for b in batches:
        dim = str(b.get("goods_dim", "unknown"))
        amt = float(b.get("gross_amount", 0.0) or 0.0)
        mode = str(b.get("transit_mode", "overland"))
        by_dim[dim] = by_dim.get(dim, 0.0) + amt
        by_mode[mode] = by_mode.get(mode, 0) + 1

    stats = getattr(state, "statistics", {}) or {}
    barges_pool = int(stats.get("barges_pool", 50) or 50)

    return {
        "active_batches_count": len(batches),
        "in_transit_by_dim": by_dim,
        "batches_by_mode": by_mode,
        "barges_pool_available": barges_pool,
        "canal_block_status": int(getattr(state, "canal_block", 0) or 0),
    }
