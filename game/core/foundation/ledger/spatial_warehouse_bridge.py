# -*- coding: utf-8 -*-
"""空间确权仓储底座桥接层（spatial_warehouse_bridge）。

定位：
- 落实商品物理空间定位与物权归属两大铁律；
- 真账挂载于 seats[治所]["warehouses"]，四大物理仓位：
  1. public_granary: 官方粮廪 (州仓/常平仓实粮)
  2. public_depot: 官工料场 (建材木石铁料、官文纸张)
  3. civilian_depots: 民间市井货栈塌房 (商贾待售商品现货)
  4. private_storage: 私家地窖村落囤廪 (士绅地窖窖藏、农户木囤)
- 四大物权主体 (state / imperial / local / pop) 的合法流转原子操作 transfer_goods_ownership；
- 跨治所物理调拨原子操作 dispatch_spatial_transfer。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

log = logging.getLogger(__name__)

__all__ = [
    "WAREHOUSE_TYPES", "OWNER_PREFIXES", "ensure_seat_warehouses",
    "warehouse_stock_get", "warehouse_stock_add", "transfer_goods_ownership",
    "dispatch_spatial_transfer", "sink_spatial_warehouses_to_seats",
    "survey_spatial_warehouses", "advance_in_transit_batches",
    "dispatch_passenger_trip", "advance_passenger_trips",
    "consume_project_materials_spatial", "changping_grain_spatial_op"
]

WAREHOUSE_TYPES = ("public_granary", "public_depot", "civilian_depots", "private_storage")
OWNER_PREFIXES = ("state:", "imperial:", "local:", "pop:")


def ensure_seat_warehouses(seat_data: Dict[str, Any]) -> Dict[str, Any]:
    """为治所节点幂等确保 warehouses 物理仓储字典结构。"""
    if "warehouses" not in seat_data or not isinstance(seat_data["warehouses"], dict):
        seat_data["warehouses"] = {}
    
    wh = seat_data["warehouses"]
    if "public_granary" not in wh:
        wh["public_granary"] = {"capacity_shi": 2000000, "damp_proof_level": 1, "stocks": {}}
    if "public_depot" not in wh:
        wh["public_depot"] = {"stocks": {}}
    if "civilian_depots" not in wh:
        wh["civilian_depots"] = {"capacity_rented": 50000, "stocks": {}}
    if "private_storage" not in wh:
        wh["private_storage"] = {"stocks": {}}
    return wh


def _locate_seat(state: Any, seat_id: str) -> Optional[Dict[str, Any]]:
    """在全域 prefectures[路]["seats"] 中寻径治所对象。"""
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return None

    # 1. 若传的是路名，优先定位该路首府治所
    if seat_id in prefs:
        pdata = prefs[seat_id]
        if isinstance(pdata, dict):
            seats = pdata.get("seats")
            if isinstance(seats, dict):
                try:
                    from core.foundation.ledger.building_bridge import capital_seat_id
                    cap = capital_seat_id(pdata, seat_id)
                    if cap and cap in seats:
                        return seats[cap]
                except Exception:
                    pass

    # 2. 尝试精准或已知别名查找到对应治所
    for pname, pdata in prefs.items():
        if not isinstance(pdata, dict):
            continue
        seats = pdata.get("seats")
        if not isinstance(seats, dict):
            continue
        if seat_id in seats:
            return seats[seat_id]
        for skey, sdata in seats.items():
            if skey.endswith(f"|{seat_id}") or skey == seat_id:
                return sdata
            if seat_id == "kaifeng" and "开封" in skey:
                return sdata
            if seat_id == "jiangning" and "江宁" in skey:
                return sdata

    # 3. 兜底模糊匹配（非路名时）
    for pname, pdata in prefs.items():
        if not isinstance(pdata, dict):
            continue
        seats = pdata.get("seats")
        if not isinstance(seats, dict):
            continue
        for skey, sdata in seats.items():
            if seat_id in skey:
                return sdata
    return None


def warehouse_stock_get(
    state: Any, 
    seat_id: str, 
    wh_type: str, 
    dim: str
) -> Optional[float]:
    """读取治所特定物理仓位的商品实存量。缺失返回 None (缺失≠0)。"""
    seat = _locate_seat(state, seat_id)
    if not seat or "warehouses" not in seat:
        return None
    wh = seat.get("warehouses", {}).get(wh_type)
    if not isinstance(wh, dict):
        return None
    stocks = wh.get("stocks")
    # P1-3（2026-10-17）：仓位存在但该维未登记 ⇒ **None**（缺失≠0）；
    # 只有 stocks 里显式写了数值 0 才返回 0.0（“空仓”这一声明）。
    if not isinstance(stocks, dict) or dim not in stocks:
        return None
    val = stocks.get(dim)
    return float(val) if val is not None else None


def warehouse_stock_add(
    state: Any,
    seat_id: str,
    wh_type: str,
    dim: str,
    delta: float,
    reason: str = "spatial_ops"
) -> Optional[float]:
    """变更治所物理仓位库存（带零下限钳位）。返回变更后存量，不可写返回 None。"""
    seat = _locate_seat(state, seat_id)
    if not seat:
        return None
    wh = ensure_seat_warehouses(seat)
    target_wh = wh.get(wh_type)
    if not isinstance(target_wh, dict):
        return None
    stocks = target_wh.setdefault("stocks", {})
    curr = float(stocks.get(dim, 0.0) or 0.0)
    new_val = max(0.0, round(curr + float(delta), 4))
    stocks[dim] = new_val
    return new_val


def transfer_goods_ownership(
    state: Any,
    dim: str,
    amount: float,
    from_owner: str,
    to_owner: str,
    reason: str,
    money_consideration: Optional[float] = None,
    seat_id: Optional[str] = None
) -> Dict[str, Any]:
    """物权流转原子操作。
    
    支持: 和买交割 (pop -> local)、榷货专卖 (local -> pop)、官产调拨等。
    严格保证 ΔStock == 0，若有对价则同步划款保证 ΔMoney == 0。
    """
    amt = max(0.0, float(amount))
    if amt <= 0 and (money_consideration is None or money_consideration <= 0):
        return {"ok": True, "transferred": 0.0, "money_paid": 0.0}

    # 1. 货币对价结算
    money_paid = 0.0
    if money_consideration is not None and money_consideration > 0:
        if hasattr(state, "transfer_money"):
            money_paid = float(state.transfer_money(to_owner, from_owner, int(money_consideration)))
        else:
            money_paid = float(money_consideration)

    # 2. 真实扣减源头存量 (保证 ΔStock == 0)
    stock_deducted = 0.0
    if amt > 0:
        if from_owner.startswith("pop:"):
            parts = from_owner.split(":")
            circuit = parts[1] if len(parts) > 1 else ""
            cls_name = parts[2] if len(parts) > 2 else "商人"
            pdata = (getattr(state, "prefectures", {}) or {}).get(circuit, {})

            # 优先使用治所真账桥扣减 (pop_goods_sub)
            taken = None
            try:
                from core.foundation.ledger.pop_bridge import pop_goods_sub
                taken = pop_goods_sub(pdata, cls_name, dim, int(amt), seat_id=seat_id)
            except Exception:
                taken = None

            # 若指定治所未扣到，尝试在全路真账扣减
            if taken is None and seat_id:
                try:
                    taken = pop_goods_sub(pdata, cls_name, dim, int(amt), seat_id=None)
                except Exception:
                    taken = None

            # 若仍未扣到（未下沉路），回落到路级扁平 goods 直扣
            if taken is None:
                pop_obj = (pdata.get("pops", {}) or {}).get(cls_name, {})
                goods = pop_obj.get("goods") if isinstance(pop_obj, dict) else None
                if isinstance(goods, dict):
                    cur_flat = int(goods.get(dim, 0) or 0)
                    take = max(0, min(cur_flat, int(amt)))
                    goods[dim] = cur_flat - take
                    taken = take
                else:
                    taken = 0
            stock_deducted = float(taken or 0)
        elif from_owner.startswith("local:") or from_owner.startswith("state:"):
            src_seat = seat_id or from_owner.split(":")[-1]
            wh_type = "public_granary" if dim == "grain" else "public_depot"
            cur_wh = warehouse_stock_get(state, src_seat, wh_type, dim)
            # 缺失维 = 无该货可转，不是数值 0；只有显式库存才参与 min。
            take_wh = min(cur_wh, amt) if cur_wh is not None else 0.0
            if take_wh > 0:
                warehouse_stock_add(state, src_seat, wh_type, dim, -take_wh, reason=f"transfer_out:{reason}")
                stock_deducted = float(take_wh)

    # 3. 登记物权流向台账 (只读测量与审计)
    return {
        "ok": True,
        "dim": dim,
        "amount": amt,
        "stock_deducted": stock_deducted,
        "from_owner": from_owner,
        "to_owner": to_owner,
        "reason": reason,
        "money_paid": money_paid
    }


def dispatch_spatial_transfer(
    state: Any,
    origin_seat: str,
    target_seat: str,
    goods_dim: str,
    amount: float,
    owner: str,
    transit_mode: str = "waterway"
) -> Dict[str, Any]:
    """发起跨治所物理运输批次。彻底消除隔空取料。"""
    amt = max(0.0, float(amount))
    if amt <= 0:
        return {"ok": False, "reason": "invalid_amount"}
    
    # 1. 检查始发地是否有货 (粮食从 public_granary，物料从 public_depot，民间从 civilian_depots)
    if goods_dim == "grain":
        wh_source = "public_granary" if owner.startswith("local:") or owner.startswith("state:") else "civilian_depots"
    else:
        wh_source = "public_depot" if owner.startswith("local:") or owner.startswith("state:") else "civilian_depots"
    
    avail = warehouse_stock_get(state, origin_seat, wh_source, goods_dim)
    if avail is None or avail < amt:
        return {"ok": False, "reason": "insufficient_source_stock",
                "available": avail, "required": amt}
    
    # 2. 扣减始发地物理仓库
    warehouse_stock_add(state, origin_seat, wh_source, goods_dim, -amt, reason="dispatch_out")
    
    # 3. 构造移动载具批次（沈括民夫与三维交通模式配置）
    batches = getattr(state, "in_transit_batches", None)
    if batches is None:
        batches = []
        setattr(state, "in_transit_batches", batches)
    
    if transit_mode == "waterway":
        base_days = 15
        porters = max(2, int(amt * 0.05))
        daily_ration = 0.005
    elif transit_mode == "maritime":
        base_days = 45
        porters = max(5, int(amt * 0.02))
        daily_ration = 0.008
    else:  # overland
        base_days = 30
        porters = max(2, int(amt * 0.5))
        daily_ration = 0.020

    batch_id = f"batch_{origin_seat}_{target_seat}_{goods_dim}_{len(batches)+1}"
    batch = {
        "batch_id": batch_id,
        "origin_seat": origin_seat,
        "target_seat": target_seat,
        "goods_dim": goods_dim,
        "gross_amount": amt,
        "initial_amount": amt,
        "owner": owner,
        "transit_mode": transit_mode,
        "remaining_days": base_days,
        "porters_count": porters,
        "daily_ration": daily_ration,
        "rations_consumed": 0.0,
        "status": "in_transit"
    }
    batches.append(batch)
    return {"ok": True, "batch_id": batch_id, "days": base_days, "porters": porters}


def advance_in_transit_batches(state: Any, days: int = 30) -> List[Dict[str, Any]]:
    """月度在途批次推进与运抵入库结算（沈括民夫口粮途耗）。"""
    batches = getattr(state, "in_transit_batches", None)
    if not batches or not isinstance(batches, list):
        return []
    
    arrived = []
    active = []
    for b in batches:
        elapsed = min(days, b["remaining_days"])
        # 沈括口粮途耗计算（仅粮食扣减实物途耗）
        if b.get("goods_dim") == "grain":
            consumed = b.get("porters_count", 1) * b.get("daily_ration", 0.02) * elapsed
            actual_loss = min(float(b["gross_amount"]), consumed)
            b["gross_amount"] = max(0.0, round(float(b["gross_amount"]) - actual_loss, 4))
            b["rations_consumed"] = round(float(b.get("rations_consumed", 0.0)) + actual_loss, 4)

        b["remaining_days"] -= days
        if b["remaining_days"] <= 0:
            # 运抵目的地物理入库
            t_seat = b["target_seat"]
            dim = b["goods_dim"]
            amt = b["gross_amount"]
            owner = b["owner"]
            if dim == "grain":
                wh_target = "public_granary" if owner.startswith("local:") or owner.startswith("state:") else "civilian_depots"
            else:
                wh_target = "public_depot" if owner.startswith("local:") or owner.startswith("state:") else "civilian_depots"
            
            warehouse_stock_add(state, t_seat, wh_target, dim, amt, reason="dispatch_in")
            b["status"] = "delivered"
            b["net_delivered"] = amt
            arrived.append(b)
        else:
            active.append(b)
    
    setattr(state, "in_transit_batches", active)
    return arrived


def dispatch_passenger_trip(
    state: Any,
    origin_seat: str,
    target_seat: str,
    passenger_type: str,
    count: int,
    transit_mode: str = "waterway"
) -> Dict[str, Any]:
    """发起客运时空流动旅程 (官员赴任/学子赴考/商贾贩运/流民迁徙)。"""
    trips = getattr(state, "passenger_trips", None)
    if trips is None:
        trips = []
        setattr(state, "passenger_trips", trips)
    
    base_days = 15 if transit_mode == "waterway" else (45 if transit_mode == "maritime" else 30)
    trip_id = f"trip_{origin_seat}_{target_seat}_{passenger_type}_{len(trips)+1}"
    trip = {
        "trip_id": trip_id,
        "origin_seat": origin_seat,
        "target_seat": target_seat,
        "passenger_type": passenger_type,
        "count": max(1, int(count)),
        "transit_mode": transit_mode,
        "remaining_days": base_days,
        "status": "in_transit"
    }
    trips.append(trip)
    return {"ok": True, "trip_id": trip_id, "days": base_days}


def advance_passenger_trips(state: Any, days: int = 30) -> List[Dict[str, Any]]:
    """月度客运时空流动推进与到埠结算。"""
    trips = getattr(state, "passenger_trips", None)
    if not trips or not isinstance(trips, list):
        return []
    
    arrived = []
    active = []
    for t in trips:
        t["remaining_days"] -= days
        if t["remaining_days"] <= 0:
            t["status"] = "arrived"
            arrived.append(t)
        else:
            active.append(t)
    setattr(state, "passenger_trips", active)
    return arrived


def sink_spatial_warehouses_to_seats(state: Any) -> Dict[str, Any]:
    """全域治所物理仓储幂等初始化与下沉。"""
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return {"ok": False, "count": 0}
    
    count = 0
    for pname, pdata in prefs.items():
        if not isinstance(pdata, dict):
            continue
        seats = pdata.get("seats")
        if isinstance(seats, dict):
            for sname, sdata in seats.items():
                if isinstance(sdata, dict):
                    ensure_seat_warehouses(sdata)
                    count += 1
    return {"ok": True, "count": count}


def survey_spatial_warehouses(state: Any) -> Dict[str, Any]:
    """对全域治所物理仓储进行只读体检。"""
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return {"defined": False}
    
    total_seats = 0
    with_wh = 0
    for pname, pdata in prefs.items():
        if not isinstance(pdata, dict):
            continue
        seats = pdata.get("seats")
        if isinstance(seats, dict):
            for sname, sdata in seats.items():
                if isinstance(sdata, dict):
                    total_seats += 1
                    if "warehouses" in sdata:
                        with_wh += 1
    return {
        "defined": True,
        "total_seats": total_seats,
        "with_warehouses": with_wh,
        "ratio": round(with_wh / max(1, total_seats), 4)
    }


def consume_project_materials_spatial(
    state: Any,
    route_or_seat: str,
    dim: str,
    qty: float
) -> Tuple[float, str]:
    """工程施工原子领料接口。
    
    规则：
    1. 优先从所在治所/首府官方料场 (public_depot) 领料；
    2. 官方料场有存料无偿领料（采购时已完成交割，属官府实物）；
    3. 官方料场不足时，缺口转由本路商人货栈 (civilian_depots / material_holding) 采购补充；
    4. 两个渠道均不足时按实领量返回，绝不凭空造料。
    
    返回: (actual_consumed, source_summary)
    """
    if qty <= 0:
        return 0.0, "zero_need"
    
    # 查找首府治所或匹配治所
    seat = _locate_seat(state, route_or_seat)
    total_got = 0.0
    sources = []
    
    # 1. 优先查 public_depot
    if seat and "warehouses" in seat:
        depot = seat["warehouses"].get("public_depot", {})
        stocks = depot.get("stocks", {}) if isinstance(depot, dict) else {}
        curr_stock = float(stocks.get(dim, 0.0) or 0.0)
        if curr_stock > 0:
            take_from_depot = min(curr_stock, qty)
            stocks[dim] = max(0.0, round(curr_stock - take_from_depot, 4))
            total_got += take_from_depot
            sources.append(f"官方料场:{take_from_depot:.1f}")
    
    # 2. 若仍有缺口，从本路商人货栈补充
    rem_need = qty - total_got
    if rem_need > 0:
        try:
            from core.foundation.ledger.material_holding import consume_for_circuit, to_material_dim
            mdim = to_material_dim(dim) or dim
            circuit = route_or_seat
            if seat and "circuit" in seat:
                circuit = seat["circuit"]
            elif "|" in route_or_seat:
                circuit = route_or_seat.split("|")[0]
            
            got_market = consume_for_circuit(state, circuit, mdim, int(round(rem_need)))
            if got_market > 0:
                total_got += float(got_market)
                sources.append(f"商人行栈:{got_market}")
        except Exception as _e:
            log.warning("从商人货栈领料补充失败: %r", _e)
            
    summary = "+".join(sources) if sources else "无库存"
    return total_got, summary


def changping_grain_spatial_op(
    state: Any,
    circuit_name: str,
    op: str,
    amount: float
) -> float:
    """常平仓平籴平粜与治所 public_granary 实物存粮同源同步接口。
    
    - op == 'buy': 平籴买粮，实物入库治所 public_granary['grain']；
    - op == 'sell': 平粜出粮，实物从治所 public_granary['grain'] 扣减（受实存量严格约束）；
    返回实际入库或实际出库的粮石数。
    """
    amt = max(0.0, float(amount))
    if amt <= 0:
        return 0.0
    
    seat = _locate_seat(state, circuit_name)
    if not seat:
        return 0.0
    
    wh = ensure_seat_warehouses(seat)
    granary = wh.get("public_granary", {})
    stocks = granary.setdefault("stocks", {})
    curr = float(stocks.get("grain", 0.0) or 0.0)
    
    if op == "buy":
        new_val = round(curr + amt, 4)
        stocks["grain"] = new_val
        return amt
    elif op == "sell":
        actual_sell = min(curr, amt)
        stocks["grain"] = round(curr - actual_sell, 4)
        return actual_sell
    return 0.0
