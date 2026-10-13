# -*- coding: utf-8 -*-
"""治所级市场切片**影子**（主线 F 第一切片） —— M53。

规格（`reviews/未落地设计裁定与实施路线.md` §主线F）：
> **先做一个真实地点、货主、商品、路线、买方的最小州府市场切片**，再扩展全商品、工坊投料、
> 外贸和远方市场。必须完成**产地—运输—成交—到货—加工**链条的守恒和缺失诊断。

本模块给出**只读**影子读数（Jev choose A 0.948）：**不改正式成交**
（正式成交仍是路级 `market.trade_goods`）。

口径（单点复用，不自造）
------------------------
* **地点**＝治所（`prefectures[路]["seats"][治所]`）；
* **货主**＝持有该商品的 **POP 类**（治所真账 `pops[类]["goods"]`）——M51 缺的是「作坊 owner」，
  与「商品的持有人」不是一回事；
* **需求**＝既有单点 `demand.basic_need(cls, dim, size)`（未配置 ⇒ `None`）+ 余量释放
  `demand.demand_release(cls, 人均 wealth)`；
* **在途**＝`core.transport.in_transit`（批次含 `to`/`dim`/`qty`）；
* **缺口原因**＝复用 `market_gap` 的原因码与五分组（**不另立命名**）；
* 🔴 **价**：本模块**不臆造**——价格单点（`effective_buy_price` 的调用口径）未接 ⇒ `price=None` + reason；
* **缺失 ≠ 0**：任一项不可读 ⇒ `None` + `reason`，绝不回落 0。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

#: 五段链条（规格要求"守恒和缺失诊断"逐段可见）
CHAIN_STAGES = ("origin", "transport", "trade", "arrival", "processing")

__all__ = [
    "SCHEMA_VERSION", "CHAIN_STAGES", "seat_holders", "seat_supply",
    "seat_purchasing_power", "seat_demand", "in_transit_to", "seat_reachability",
    "seat_price_or_none", "shadow_match", "chain_diagnosis", "survey_seat_market_shadow",
]


def _num(v) -> Optional[float]:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def _flatten_sum(v) -> Optional[float]:
    """数值直取；dict（治所桶）⇒ 递归求和；其它 ⇒ `None`（缺失≠0）。"""
    n = _num(v)
    if n is not None:
        return n
    if isinstance(v, dict):
        tot, seen = 0.0, False
        for x in v.values():
            y = _flatten_sum(x)
            if y is not None:
                tot += y
                seen = True
        return tot if seen else None
    return None


def _seat_row(state, route: str, seat: str) -> Optional[Dict[str, Any]]:
    prefs = getattr(state, "prefectures", None)
    pdata = (prefs or {}).get(route) if isinstance(prefs, dict) else None
    seats = (pdata or {}).get("seats") if isinstance(pdata, dict) else None
    srow = (seats or {}).get(seat) if isinstance(seats, dict) else None
    return srow if isinstance(srow, dict) else None


def seat_holders(state, route: str, seat: str, dim: str) -> Optional[Dict[str, int]]:
    """该治所**持有人**＝持有 `dim` 的 POP 类及数量；治所/货物不可读 ⇒ `None`。"""
    srow = _seat_row(state, route, seat)
    if srow is None:
        return None
    pops = srow.get("pops")
    if not isinstance(pops, dict):
        return None
    out: Dict[str, int] = {}
    try:
        from core.foundation.ledger.material_holding import goods_amount as _gamt
    except Exception:                                       # noqa: BLE001
        _gamt = None
    for cls, row in pops.items():
        g = row.get("goods") if isinstance(row, dict) else None
        if not isinstance(g, dict):
            continue
        # 🔴 走**既有单点** `goods_amount`（它同时处理扁平与治所桶；自造摊平会漏桶 → 已踩）
        v = _gamt(g, dim) if _gamt is not None else _flatten_sum(g.get(dim))
        if v is not None and v > 0:
            out[str(cls)] = int(v)
    return out


def seat_supply(state, route: str, seat: str, dim: str) -> Optional[int]:
    """该治所**可售供给**＝Σ持有人持仓；不可读 ⇒ `None`。"""
    holders = seat_holders(state, route, seat, dim)
    if holders is None:
        return None
    return int(sum(holders.values()))


def seat_purchasing_power(state, route: str, seat: str) -> Dict[str, Optional[int]]:
    """该治所各 POP 类**购买力**（wealth）；治所不可读 ⇒ `{}`。"""
    srow = _seat_row(state, route, seat)
    pops = (srow or {}).get("pops") if isinstance(srow, dict) else None
    if not isinstance(pops, dict):
        return {}
    out: Dict[str, Optional[int]] = {}
    for cls, row in pops.items():
        v = _num(row.get("wealth")) if isinstance(row, dict) else None
        out[str(cls)] = None if v is None else int(v)
    return out


def seat_demand(state, route: str, seat: str, dim: str) -> Dict[str, Any]:
    """该治所对 `dim` 的**需求**（既有单点 `demand.basic_need` × size，按余量释放加权）。

    任一环不可读（无 `basic_need` 配置 / 无 size）⇒ 该类的量 `None`（**不臆造**）。
    """
    srow = _seat_row(state, route, seat)
    pops = (srow or {}).get("pops") if isinstance(srow, dict) else None
    if not isinstance(pops, dict):
        return {"total": None, "by_class": {}, "reasons": ["治所/pops 不可读（缺失≠0）"]}
    try:
        from core.domains.economy import demand as _dm
    except Exception:                                       # noqa: BLE001
        return {"total": None, "by_class": {}, "reasons": ["demand 单点不可用"]}
    by_class: Dict[str, Any] = {}
    reasons: List[str] = []
    total = 0.0
    readable_all = True
    for cls, row in pops.items():
        if not isinstance(row, dict):
            continue
        size = _num(row.get("size"))
        wealth = _num(row.get("wealth"))
        if size is None or size <= 0:
            continue
        need = _dm.basic_need(str(cls), dim, int(size))
        if need is None:
            readable_all = False
            by_class[str(cls)] = {"need": None, "release": None, "effective": None}
            reasons.append(f"{cls}: `basic_need` 未配置该维 ⇒ 需求不可定义（不臆造）")
            continue
        per_capita = None if wealth is None else wealth / size
        rel = _dm.demand_release(str(cls), per_capita)
        # 🔴 `basic_need` 是**人均·月**需求 ⇒ 需求总量 = 人均 × size × 余量释放（漏乘 size 已踩）
        eff = None if rel is None else float(need) * float(size) * float(rel)
        by_class[str(cls)] = {"need_per_capita": float(need), "size": int(size),
                              "release": None if rel is None else float(rel),
                              "effective": eff}
        if eff is None:
            readable_all = False
            reasons.append(f"{cls}: 余量释放不可读（人均 wealth 缺失）⇒ 有效需求不可定义")
        else:
            total += eff
    return {"total": float(total) if readable_all else None, "by_class": by_class,
            "reasons": reasons}


def in_transit_to(state, route: str, seat: str, dim: str) -> Optional[int]:
    """**在途到该治所**的量（`transport.in_transit` 批次按 `to`/`dim` 过滤）；不可用 ⇒ `None`。

    ⚠️ **真·只读**：`transport.in_transit` 读时会**惰性创建** `state.material_transit`（实测），
    故先看容器是否已存在——不存在 ⇒ 直接返回 0（**没有在途**），不去触发那次写。
    """
    book = getattr(state, "material_transit", None)
    if book is None:
        return 0                                            # 无容器 ⇒ 无在途，且**不创建**它
    try:
        from core.transport import in_transit
        batches = in_transit(state)
    except Exception:                                       # noqa: BLE001
        log.warning("seat_market_shadow: 在途读数不可用", exc_info=True)
        return None
    if batches is None:
        return None
    tot = 0
    hit = False
    for b in batches or ():
        if not isinstance(b, dict):
            continue
        to = str(b.get("to") or "")
        if not to:
            continue
        if seat and seat not in to:
            continue
        qty = b.get("qty")
        if isinstance(qty, dict):
            v = _num(qty.get(dim))
        elif b.get("dim") == dim:
            v = _num(b.get("qty"))
        else:
            v = None
        if v is not None:
            tot += int(v)
            hit = True
    return tot if hit else 0                                  # 有读数、只是没有在途 ⇒ 0


def seat_reachability(state, route: str, seat: str, dim: str) -> Dict[str, Any]:
    """**可达性/同路货源**：本路其他治所是否持有该货（不臆造"可达"结论，只报事实）。"""
    prefs = getattr(state, "prefectures", None)
    pdata = (prefs or {}).get(route) if isinstance(prefs, dict) else None
    seats = (pdata or {}).get("seats") if isinstance(pdata, dict) else None
    if not isinstance(seats, dict) or not seats:
        return {"same_route_seats_with_stock": None, "reason": "无 seats（缺失≠0）"}
    n = 0
    others = {}
    for sid in seats:
        if str(sid) == str(seat):
            continue
        s = seat_supply(state, route, str(sid), dim)
        if s:
            n += 1
            others[str(sid)] = s
    return {"same_route_seats_with_stock": n, "detail": dict(list(others.items())[:5]),
            "reason": None}


def demand_coverage(state, dims=None, classes=None) -> Dict[str, Any]:
    """`demand.basic_need` 的**配置覆盖率**：哪些 `(阶层, 商品维)` 有配置、哪些没有。

    这是 M53 影子撮合恒为 `None` 的**数据级根因**：`basic_need` 未配置的维 ⇒ 需求不可定义。
    只读；`dims` 缺省取『本局有货的维 ∪ 各作坊 recipe 维』。
    """
    try:
        from core.domains.economy import demand as _dm
    except Exception:                                       # noqa: BLE001
        return {"reason": "demand 单点不可用", "configured": [], "missing": []}
    if dims is None:
        found = set()
        try:
            from core.domains.economy.seat_goods_readout import seat_goods
            for _r, seats in (seat_goods(state) or {}).items():
                if not isinstance(seats, dict):
                    continue
                for cl in seats.values():
                    for g in (cl or {}).values():
                        found |= set((g or {}).keys())
        except Exception:                                   # noqa: BLE001
            pass
        for ws in (getattr(state, "workshops", None) or {}).values():
            if isinstance(ws, dict):
                found |= {d for d in (ws.get("recipe") or {})
                          if d not in ("grain_feed", "ration_weight")}
        dims = sorted(found)
    cls_list = list(classes or ("士绅", "官僚", "商人", "工匠", "农", "兵"))
    configured, missing = [], []
    for cls in cls_list:
        for dim in dims:
            need = _dm.basic_need(str(cls), str(dim), 1)     # size=1 ⇒ 得人均月需求
            rec = {"cls": cls, "dim": dim, "need_per_capita": None if need is None else float(need)}
            (configured if need is not None else missing).append(rec)
    return {"checked": len(configured) + len(missing), "configured": configured,
            "missing": missing, "dims": list(dims), "classes": cls_list,
            "source": "core.domains.economy.demand.basic_need",
            "note": "缺失项 ⇒ 该 (阶层,维) 的需求不可定义（**不是 0**）；要跑影子撮合须先补配置"}


def seat_price_or_none(state, route: str, dim: str) -> Dict[str, Any]:
    """**价**：走**公开单点** `market_price.effective_buy_price`（官定价 → 本路动态价 → 基准价）。

    ⚠️ **口径（重要）**：该单点给的是**路级**价（键 = `pref`，即路名），**不是治所级**。
    `market_price` 里**治所级原语已存在**（`seat_good_key` / `record_seat_trade_price` /
    `discover_seat_price`），但其**公开查口缺失**——内部 `_lookup_seat_price` 是**私有名**
    ⇒ 按项目纪律（不跨模块 import 私有名）本模块**不碰它**，只报路级价并标 `level="route"`；
    治所级查口缺失记为**欠账**（`tasks/M62-m53-price-and-demand.json`）。
    读不到（`kind=="none"` 或单点不可用）⇒ `price=None` + reason（缺失≠0）。
    """
    src = "core.market_price.effective_buy_price(dim=…, state=…, pref=route)"
    try:
        from core.market_price import effective_buy_price
        r = effective_buy_price(dim=str(dim), state=state, pref=route)
    except Exception as e:                                  # noqa: BLE001
        log.warning("seat_market_shadow: 价单点不可用", exc_info=True)
        return {"price": None, "level": None, "kind": None, "source": src,
                "reason": f"价单点不可用：{type(e).__name__}: {e}"}
    price = _num(r.get("price")) if isinstance(r, dict) else None
    if price is None:
        return {"price": None, "level": None, "kind": (r or {}).get("kind"), "source": src,
                "reason": ((r or {}).get("reason") or "价不可读（缺失≠0）")}
    return {"price": price, "level": "route", "kind": r.get("kind"), "source": src,
            "reason": r.get("reason"),
            "note": "**路级**价（非治所级）；治所级公开查口缺失 ⇒ 已登记欠账"}


def shadow_match(state, route: str, seat: str, dim: str) -> Dict[str, Any]:
    """**影子撮合**（只读）：成交量上界＝min(供给, 有效需求)；未满足部分给**原因码**。

    原因码复用 `market_gap`（**不另立命名**）。
    """
    supply = seat_supply(state, route, seat, dim)
    dem = seat_demand(state, route, seat, dim)
    need = dem.get("total")
    arrivals = in_transit_to(state, route, seat, dim)
    trade = None
    unmet = None
    if supply is not None and need is not None:
        trade = int(min(float(supply), float(need)))
        unmet = int(max(0.0, float(need) - float(supply)))
    gaps: List[Dict[str, Any]] = []
    try:
        from core.domains.economy import market_gap as _mg
        if supply == 0:
            gaps.append(_mg.gap("no_stock_local", need=need, have=supply,
                                source_id=f"{route}:{seat}",
                                note="治所无可售供给（真账为 0）"))
        if unmet:
            gaps.append(_mg.gap("insufficient_stock", need=need, have=supply,
                                source_id=f"{route}:{seat}",
                                note="供给不足以满足有效需求"))
    except Exception:                                       # noqa: BLE001
        # 🔴 不得静默（项目禁区）：缺口原因构造失败必须留痕，否则"没有缺口"与"构造失败"无法区分
        log.warning("seat_market_shadow: 缺口原因构造失败（market_gap 调用口径？）", exc_info=True)
        gaps = []
    return {"route": route, "seat": seat, "dim": dim,
            "supply": supply, "demand": need, "demand_detail": dem,
            "arrivals": arrivals, "shadow_trade_qty": trade, "unmet": unmet,
            "gap_reasons": [g for g in gaps if g],
            "price": seat_price_or_none(state, route, dim)}


def chain_diagnosis(state, route: str, seat: str, dim: str) -> Dict[str, Any]:
    """**五段链条**诊断：产地/运输/成交/到货/加工 各自值或 `None` + reason。"""
    m = shadow_match(state, route, seat, dim)
    reach = seat_reachability(state, route, seat, dim)
    return {
        "origin": {"value": m["supply"], "reason": None if m["supply"] is not None
                   else "治所供给不可读"},
        "transport": {"value": m["arrivals"], "reason": None if m["arrivals"] is not None
                      else "在途读数不可用"},
        "trade": {"value": m["shadow_trade_qty"], "reason": None if m["shadow_trade_qty"] is not None
                  else "供给或需求不可读 ⇒ 影子成交量不可定义"},
        "arrival": {"value": None,
                    "reason": "到货段需与『产地—运输—成交』配平（正式成交仍在路级）⇒ 本批未接"},
        "processing": {"value": None,
                       "reason": "加工段属 P2/主线C 生产层（产出已按路落治所真账，见 M47）⇒ 本批未接"},
        "reachability": reach,
        "gap_reasons": m["gap_reasons"],
    }


def survey_seat_market_shadow(state, top: int = 8) -> Dict[str, Any]:
    """汇总：挑**有货**的 (治所, 商品) 对做影子读数（避免 20 路 × 全维爆炸）。"""
    try:
        from core.domains.economy.seat_goods_readout import seat_goods
        sg = seat_goods(state)
    except Exception:                                       # noqa: BLE001
        sg = None
    if not isinstance(sg, dict):
        return {"schema_version": SCHEMA_VERSION, "reason": "seat_goods 不可用（缺失≠0）"}
    pairs: List[Any] = []
    for route, seats in sg.items():
        if not isinstance(seats, dict):
            continue
        for seat, classes in seats.items():
            if not isinstance(classes, dict):
                continue
            tot: Dict[str, int] = {}
            for g in classes.values():
                for d, q in (g or {}).items():
                    tot[d] = tot.get(d, 0) + int(q)
            for dim, q in tot.items():
                if q > 0:
                    pairs.append((q, route, seat, dim))
    pairs.sort(reverse=True)
    rows = []
    for _q, route, seat, dim in pairs[:top]:
        rows.append({"route": route, "seat": seat, "dim": dim,
                     "chain": chain_diagnosis(state, route, seat, dim)})
    return {"schema_version": SCHEMA_VERSION, "pairs_with_stock": len(pairs),
            "sampled": len(rows), "rows": rows,
            "note": "只读影子：不改正式成交（正式仍路级 `market.trade_goods`）"}
