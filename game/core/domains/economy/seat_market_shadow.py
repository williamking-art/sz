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
    readable_n = 0
    unreadable: List[str] = []
    for cls, row in pops.items():
        if not isinstance(row, dict):
            continue
        size = _num(row.get("size"))
        wealth = _num(row.get("wealth"))
        if size is None or size <= 0:
            continue
        need = _dm.basic_need(str(cls), dim, int(size))
        per_capita = None if wealth is None else wealth / size
        rel = _dm.demand_release(str(cls), per_capita)
        # 🔴 M74b 修**双重计数**（Jev 甲 0.998）：`demand.basic_need(cls, dim, pop_size)`
        #   **内部已经乘过 `pop_size`**（返回该阶层的**需求总量**，不是人均）⇒ 这里**不得再乘 size**
        #   （M53 原写 `need * size * rel` 并附了一句"漏乘 size 已踩"的**错误**注释，实测把影子需求
        #    放大约 size 倍，使 `shadow_match` 的成交量几乎总是"供给被全额吃掉"）。
        eff = None if (need is None or rel is None) else float(need) * float(rel)

        # 🟢 M74：**耐用品通道**（存量缺口）。口径 = **max(基本需求, 耐用品缺口)**，
        #   **不是相加**（Jev 乙 0.49998 vs 甲 0.363 —— 差 0.14 且乙压在阈值下，属**实质平手**，
        #   按 AGENTS.md「平手须自论证」：**max 是零行为变化选择**——`durable_gap` 未配置该维 ⇒ `None`
        #   ⇒ 退化为原行为；已配置时也不会把"流量+存量缺口"重复计成双份）。
        gap = None
        goods = row.get("goods")
        if isinstance(goods, dict):
            raw = goods.get(dim)
            if raw is not None and not isinstance(raw, dict):
                held = _num(raw)                     # 扁平写法：**键在即读**（持有 0 也算可读）
            else:
                try:
                    # 桶形态（`{治所: {dim: qty}}`）走既有单点；不可读 ⇒ 本通道不可读
                    from core.foundation.ledger.material_holding import goods_amount
                    held = _num(goods_amount(goods, dim))
                except Exception:                           # noqa: BLE001
                    log.warning("seat_market_shadow: 持有量不可读 cls=%s dim=%s",
                                cls, dim, exc_info=True)
                    held = None
            if held is not None:
                # ⚠️ 签名是 `durable_gap(dim, pop_size, held)` —— **第一个参数是维、不是阶层**
                #   （本轮曾把 `cls` 传成 `dim` ⇒ 永远查不到目标库存 ⇒ 通道恒 None）
                gap = _num(_dm.durable_gap(str(dim), int(size), held))
        # ⚠️ `demand.durable_gap` 对 `held=None` 会**按 0 算**（缺口=全目标，违反缺失≠0）；
        #   本模块**不改他人单点**，改为「持有不可读 ⇒ 本通道不可读」（gap 保持 None）。

        eff_final = eff if gap is None else (float(gap) if eff is None else max(float(eff), float(gap)))
        by_class[str(cls)] = {"need_total": None if need is None else float(need),
                              "size": int(size),
                              "release": None if rel is None else float(rel),
                              "effective": eff_final,
                              "basic_effective": eff,
                              "durable_gap": gap,
                              "channel": ("basic+durable" if (eff is not None and gap is not None)
                                          else "basic" if eff is not None
                                          else "durable" if gap is not None else None)}
        if eff_final is None:
            unreadable.append(str(cls))
            if need is None and gap is None:
                reasons.append(f"{cls}: 两条需求通道皆不可读 ⇒ 该类需求不可定义（不臆造）")
            else:
                reasons.append(f"{cls}: 余量释放不可读（人均 wealth 缺失）⇒ 该类有效需求不可定义")
        else:
            total += eff_final
            readable_n += 1
    # 🔴 M74：**可读部分合计 + `partial` 标记**（照 M52 家计先例）。
    #   否则"某阶层无该通道"会污染整个治所的需求（混合 POP 的治所永远看不到量）。
    return {"total": float(total) if readable_n else None,
            "readable_classes": readable_n,
            "unreadable_classes": unreadable,
            "partial": bool(unreadable) and readable_n > 0,
            "by_class": by_class, "reasons": reasons,
            "composition": "max(基本需求×余量释放, 耐用品缺口)；耐用品未配置/持有不可读 ⇒ 退化为基本需求",
            "note": ("`total` ＝ **可读阶层**合计（缺失≠0）；`partial=True` 表示有阶层不可读，"
                     "**不得当作全所需求**")}


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


def demand_coverage(state, dims=None) -> Dict[str, Any]:
    """**需求通道矩阵**（只读；M62 建、**M73 更正口径**）。

    🔴 **M73 更正**：`demand.basic_need(cls, dim, size)` 里 **`cls` 根本不参与**
    （人均需求量按**维**配置在 `BASIC_NEED_BASKET`）⇒ M62 报的「6/42（6 阶层 × 布）」
    **表述有误**：真实是「**7 个有货维里只配了 1 维（布）**」。
    本函数改为**逐维**报**三条既有需求通道**：
      * `basket`：`BASIC_NEED_BASKET[dim]`（人均·月，**维级**）；
      * `durable`：`DURABLE_TARGET_STOCK[dim]`（耐用品目标库存）；
      * `grain`：`GRAIN_CONSUME_PER_CAPITA[类]`（**按阶层**的人均口粮，只对粮维有意义）；
    无任何通道 ⇒ `channels=[]`（**无来源不启用**：机制文档明写「先加少量能由当前资源/作坊生产的
    日用品；无来源不启用」）。
    ⚠️ **M73 取证结论**：其余维**不得拍数**——`specs/economy/market-civilian-economy/tasks.md`
    §「参数待裁（阻塞）」明写：这些参数**由 B2-R 先补足因果环与局部市场定价，再用 60/240 月实测校准**，
    「不把『裁定参数』作为提前调数的许可」⇒ 属**校准门控**，不是缺史料。
    """
    def _cfg(name: str) -> dict:
        try:
            from content import data as _d
            v = getattr(_d, name, None)
            return v if isinstance(v, dict) else {}
        except Exception:                                   # noqa: BLE001
            log.warning("seat_market_shadow: %s 不可读", name, exc_info=True)
            return {}

    basket = _cfg("BASIC_NEED_BASKET")
    durable = _cfg("DURABLE_TARGET_STOCK")
    grain_pc = _cfg("GRAIN_CONSUME_PER_CAPITA")
    if dims is None:
        found = set(basket) | set(durable)
        # 并入 content 的**维表**（RAW/FINISHED/GOODS/RESOURCE_DIMS：条令维集，避免只靠"有货维"漏维）
        try:
            from content import data as _d
            for nm in ("RAW_DIMS", "FINISHED_DIMS", "GOODS_DIMS", "RESOURCE_DIMS",
                       "GRAIN_DIMS", "FINISHED_TAX_DIMS"):
                v = getattr(_d, nm, None)
                if isinstance(v, (list, tuple, set, frozenset)):
                    found |= {str(x) for x in v}
        except Exception:                                   # noqa: BLE001
            log.warning("seat_market_shadow: content 维表不可读", exc_info=True)
        # 并入「本局有货的维」与「作坊 recipe 维」（只读枚举；任一不可用不影响其余）
        try:
            from core.domains.economy.seat_goods_readout import seat_goods
            for _r, seats in (seat_goods(state) or {}).items():
                if isinstance(seats, dict):
                    for cl in seats.values():
                        for g in (cl or {}).values():
                            found |= set((g or {}).keys())
        except Exception:                                   # noqa: BLE001
            log.warning("seat_market_shadow: 有货维枚举不可用", exc_info=True)
        for ws in (getattr(state, "workshops", None) or {}).values():
            if isinstance(ws, dict):
                found |= {d for d in (ws.get("recipe") or {})
                          if d not in ("grain_feed", "ration_weight")}
        dims = sorted(found)
    rows, no_channel = [], []
    for dim in dims:
        ch = []
        if _num(basket.get(dim)) is not None:
            ch.append("basket")
        if _num(durable.get(dim)) is not None:
            ch.append("durable")
        if dim in ("粮", "grain", "米", "麦") and grain_pc:
            ch.append("grain")
        rows.append({"dim": dim, "channels": ch,
                     "basket_per_capita": _num(basket.get(dim)),
                     "durable_target": _num(durable.get(dim))})
        if not ch:
            no_channel.append(dim)
    return {"dims": rows, "checked": len(rows),
            "with_channel": len(rows) - len(no_channel),
            "no_channel": no_channel,
            "source": "content.data: BASIC_NEED_BASKET / DURABLE_TARGET_STOCK / GRAIN_CONSUME_PER_CAPITA",
            "note": ("**维级**口径（`basic_need` 不吃 `cls`）；无通道维按机制文档「**无来源不启用**」；"
                     "其余参数属**校准门控**（B2-R：先因果环+局部定价，再 60/240 月实测校准）——"
                     "**不得拍数**")}


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
