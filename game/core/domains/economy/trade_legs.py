# -*- coding: utf-8 -*-
"""外贸货腿（P5，2026-10-18；Jev：默认关 0.970）。

三段：**计划 → 执行 → 计税**，全部纯函数式，不自己造账本（存取走 `resource_stock_bridge`，
运力走 `core.transport`）。

🔴 纪律：
- 出口**不足即缩量**（不凭空造货、不让库存变负）；
- 关税按**实际成交额**（缩量后计税，禁止按目标额收税）；
- 运力不足**排队不拒办**；
- 总开关 `FOREIGN_TRADE_LEGS` 默认 0（关），开=1。

⚠️ P5 局限（如实登记）：出口先扣**官仓/资源仓**（`resource_stock_bridge`），
「商人池优先」待 P8 商人资产落地后接入；进口受仓容 `cap` 限制。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

__all__ = ["trade_legs_enabled", "plan_legs", "execute_leg", "apply_tariff",
           "settle_foreign_trade"]


def trade_legs_enabled() -> bool:
    """总开关（默认关）。"""
    from content.data_constants import FOREIGN_TRADE_LEGS

    return bool(int(FOREIGN_TRADE_LEGS or 0))


def _price(dim: str) -> Optional[int]:
    from content.data_constants import MATERIAL_PRICE_BASE

    v = (MATERIAL_PRICE_BASE or {}).get(dim)
    return int(v) if isinstance(v, (int, float)) else None


def route_key(leg: Dict[str, Any]) -> str:
    """路线键：对家|货种|方向。"""
    return "%s|%s|%s" % (leg.get("partner"), leg.get("dim"), leg.get("direction"))


def _route_book(state) -> dict:
    book = getattr(state, "trade_routes", None)
    if not isinstance(book, dict):
        book = {}
        state.trade_routes = book
    return book


def quote_route(state, leg: Dict[str, Any]) -> Dict[str, Any]:
    """按 V3 口径报价：买价 / 卖价 / 关税 / 运费 ⇒ 毛利与毛利比。

    · 出口（export）：宋卖外邦 —— 收入 = 基准价 × PARTNER_PRICE_FACTORS；
    · 进口（import）：宋买外邦 —— 成本 = 基准价 × PARTNER_IMPORT_FACTORS；
    · 本路卖价 = 基准价 × `state.price_level`（缺失按 1.0，缺失≠0 的近似口径已注明）；
    · 关税按通道 `FOREIGN_TARIFF_RATE`；运费用 `FOREIGN_FREIGHT_RATE` 代理（外邦无里程）。
    """
    from content.data_constants import (FOREIGN_FREIGHT_RATE, FOREIGN_TARIFF_RATE,
                                        PARTNER_IMPORT_FACTORS, PARTNER_PRICE_FACTORS)

    dim = str(leg.get("dim") or "")
    partner = str(leg.get("partner") or "")
    direction = str(leg.get("direction") or "")
    channel = str(leg.get("channel") or "sea")
    price = leg.get("unit_price")
    if not isinstance(price, (int, float)) or price <= 0:
        return {"ok": False, "reason": "price_missing", "dim": dim}
    base = float(price)
    level = float(getattr(state, "price_level", 1.0) or 1.0)
    domestic = base * level
    abroad = base * float(PARTNER_PRICE_FACTORS.get(partner, 1.0))
    if direction == "export":
        revenue, cost = abroad, domestic
    else:
        revenue, cost = domestic, base * float(PARTNER_IMPORT_FACTORS.get(partner, 1.0))
    tariff = revenue * float(FOREIGN_TARIFF_RATE.get(channel, 0.0))
    freight = revenue * float(FOREIGN_FREIGHT_RATE.get(channel, 0.0))
    margin = revenue - cost - tariff - freight
    margin_ratio = (margin / cost) if cost > 0 else 0.0
    return {"ok": True, "dim": dim, "partner": partner, "direction": direction,
            "buy_price": round(cost, 2), "sell_price": round(revenue, 2),
            "tariff": round(tariff, 2), "freight": round(freight, 2),
            "margin": round(margin, 2), "margin_ratio": round(margin_ratio, 4)}


def target_volume(quote: Dict[str, Any], base_units: int) -> float:
    """V3：目标量 = 基准量 × clamp(margin_ratio / TARGET, 0, MAX_MULT)；亏损 ⇒ 0。"""
    from content.data_constants import TRADE_MAX_MULT, TRADE_TARGET_MARGIN

    if not quote.get("ok"):
        return 0.0
    ratio = float(quote.get("margin_ratio") or 0.0)
    if ratio <= 0:
        return 0.0
    target = float(base_units) * min(float(TRADE_MAX_MULT or 6.0),
                                     ratio / float(TRADE_TARGET_MARGIN or 0.2))
    return max(0.0, target)


def step_volume(state, leg: Dict[str, Any], quote: Dict[str, Any],
                base_units: int) -> Dict[str, Any]:
    """推进一条路线本月的量（**渐变**：盈利慢慢加、亏损慢慢减，V3 口径）。"""
    from content.data_constants import (TRADE_INIT_RATIO, TRADE_VOLUME_FLOOR,
                                        TRADE_VOLUME_GROWTH, TRADE_VOLUME_SHRINK)

    book = _route_book(state)
    key = route_key(leg)
    prev = book.get(key)
    cur = float(prev.get("volume") or 0) if isinstance(prev, dict) else None
    tgt = target_volume(quote, base_units)
    if cur is None:
        cur = max(float(TRADE_VOLUME_FLOOR or 1), tgt * float(TRADE_INIT_RATIO or 0.25)) if tgt > 0 else 0.0
    elif tgt > cur:
        cur = min(tgt, cur + max(float(TRADE_VOLUME_FLOOR or 1),
                                 cur * float(TRADE_VOLUME_GROWTH or 0.25)))
    elif tgt < cur:
        cur = max(tgt, cur * (1.0 - float(TRADE_VOLUME_SHRINK or 0.30)))
        if cur < float(TRADE_VOLUME_FLOOR or 1) and tgt <= 0:
            cur = 0.0
    book[key] = {"volume": round(cur, 3), "margin_ratio": quote.get("margin_ratio"),
                 "target": round(tgt, 3), "direction": leg.get("direction"),
                 "dim": leg.get("dim"), "partner": leg.get("partner")}
    return book[key]

def plan_legs(state, month: Optional[int] = None, advance: bool = False) -> List[Dict[str, Any]]:
    """计划货腿（**纯函数**）：每条口岸×对家×方向×货种一条腿。

    量取 `FOREIGN_LEG_BASE_UNITS`，价取 `MATERIAL_PRICE_BASE`；缺价 ⇒ 该腿 `unit_price=None`
    且 `estimated_value=None`（缺失≠0，不臆造）。
    """
    from content.data_constants import (EXPORT_BASKET, FOREIGN_LEG_BASE_UNITS,
                                        FOREIGN_TRADE_PORTS, IMPORT_BASKET)

    qty = int(FOREIGN_LEG_BASE_UNITS or 0)
    legs: List[Dict[str, Any]] = []
    for port in FOREIGN_TRADE_PORTS or ():
        partner = str(port.get("partner") or "")
        channel = str(port.get("channel") or "")
        for direction, basket in (("export", EXPORT_BASKET), ("import", IMPORT_BASKET)):
            for dim in basket.get(partner, ()):
                price = _price(dim)
                _leg = {
                    "month": month, "channel": channel, "seat": port.get("seat"),
                    "route": str(port.get("seat") or "").split("|")[0] or None,
                    "port": port.get("name"), "partner": partner,
                    "direction": direction, "dim": dim, "unit_price": price,
                }
                _q = quote_route(state, _leg)
                if advance:
                    _vol = step_volume(state, _leg, _q, qty)
                else:
                    _book = getattr(state, "trade_routes", None) or {}
                    _vol = _book.get(route_key(_leg))
                    if not isinstance(_vol, dict):
                        _tgt = target_volume(_q, qty)
                        from content.data_constants import TRADE_INIT_RATIO, TRADE_VOLUME_FLOOR
                        _vol = {"volume": (max(float(TRADE_VOLUME_FLOOR or 1),
                                           _tgt * float(TRADE_INIT_RATIO or 0.25))
                                 if _tgt > 0 else 0.0)}
                if not isinstance(_vol, dict):
                    _vol = {"volume": 0.0}
                _legs_qty = float(_vol.get("volume") or 0)
                _is_contraband = False
                if direction == "export":
                    try:
                        from content.data_constants import CONTRABAND_DIMS
                        _is_contraband = dim in set(CONTRABAND_DIMS or ())
                    except Exception:  # noqa: BLE001
                        _is_contraband = False
                if _is_contraband:
                    # 禁榷腿**始终进计划**（否则禁榷闸会空转，走私也无从谈起）
                    _legs_qty = float(qty)
                if _legs_qty <= 0:
                    continue   # 无利润/未铺开 ⇒ 本月不走这条线（V3：路线会关停）
                legs.append({
                    "month": month,
                    "channel": channel,
                    "seat": port.get("seat"),
                    "route": str(port.get("seat") or "").split("|")[0] or None,
                    "port": port.get("name"),
                    "partner": partner,
                    "direction": direction,
                    "dim": dim,
                    "planned_qty": round(_legs_qty, 3),
                    "unit_price": price,
                    "estimated_value": (round(_legs_qty * price) if price is not None else None),
                    "margin_ratio": _q.get("margin_ratio"),
                    "buy_price": _q.get("buy_price"), "sell_price": _q.get("sell_price"),
                    "tariff_unit": _q.get("tariff"), "freight_unit": _q.get("freight"),
                })
    return legs


def _seat_merchant_pops(state, route: str) -> list:
    """该路**治所级**商人 POP 列表（真账；路级是派生镜像，不可写）。"""
    out = []
    prefs = getattr(state, "prefectures", None) or {}
    pdata = prefs.get(route) or {}
    for seat_id, srow in (pdata.get("seats") or {}).items():
        pop = ((srow or {}).get("pops") or {}).get("商人")
        if isinstance(pop, dict):
            out.append(pop)
    return out

def _pay_import(state, route: str, dim: str, qty: float, price) -> float:
    """进口**付款**：从该路商人 wealth 扣货款；不足按钱缩量（返回可付数量）。

    · 钱付给外邦（外部流出），登记 external 货币流水，避免对账残差；
    · wealth / 商人 POP 缺失 ⇒ 返回 0（不凭空付款、不赊账）。
    """
    from content.data_constants import FOREIGN_IMPORT_PAY_RATIO
    from core.foundation.ledger.material_holding import merchant_of

    if not isinstance(price, (int, float)) or price <= 0 or qty <= 0:
        return 0.0
    pops = _seat_merchant_pops(state, route)
    wealth = sum(float((p.get("wealth") or 0)) for p in pops)
    if not pops or wealth <= 0:
        return 0.0
    ratio = float(FOREIGN_IMPORT_PAY_RATIO or 1.0)
    unit_cost = float(price) * ratio
    if unit_cost <= 0:
        return float(qty)
    afford = float(wealth) / unit_cost
    pay_qty = min(float(qty), afford)
    if pay_qty <= 0:
        return 0.0
    cost = int(round(pay_qty * unit_cost))
    # 🔴 2026-10-20 全审 P0-1（A-2）：治所级 pop 不是路级行，`pop_obj_add` 恒定位
    # 失败（`locate_pops` 只比对 `pdata["pops"]`）⇒ 原实现回落直写治所、路级镜像
    # 不刷新；同一回合稍后的熔铜步「读镜像→重铺治所」会把已付货款整额复活。
    # 改走 `pop_seat_add`（写单治所 + 即时刷镜像）；未下沉/定位失败才回落直写。
    from core.foundation.ledger.pop_bridge import pop_seat_add
    pdata = (getattr(state, "prefectures", None) or {}).get(route) or {}
    left = int(cost)
    for p in pops:
        if left <= 0:
            break
        pw = float(p.get("wealth") or 0)
        take = int(min(pw, left))
        if take <= 0:
            continue
        if pop_seat_add(pdata, "商人", p, "wealth", -take) is None:
            p["wealth"] = pw - take
        left -= take
    try:
        from core.settlement_common import register_money_flow
        register_money_flow(state, "burn", cost, "外贸进口货款（外流）")
    except Exception as exc:  # noqa: BLE001
        import logging as _lg
        _lg.getLogger(__name__).warning("进口货款流水登记失败：%r", exc, exc_info=True)
    return pay_qty

def _stock_of(state, dim: str, route) -> Optional[float]:
    """读存量：优先州府桥（已下沉）；未下沉 ⇒ 回落 `state.resources` 旧池。

    桥约定：返回 None = **未接管**，调用方保留原写法（不得据此判断为「零库存」）。
    """
    from core.foundation.ledger.resource_stock_bridge import stock_get

    got = stock_get(state, dim, route=route)
    if got is not None:
        return float(got)
    meta = (getattr(state, "resources", {}) or {}).get(dim)
    if isinstance(meta, dict):
        v = meta.get("stock")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    return None


def _add_stock(state, dim: str, delta: float, route) -> bool:
    """写存量：优先州府桥；未接管 ⇒ 写旧池（**截断避免负库存**、按 cap 封顶）。"""
    from core.foundation.ledger.resource_stock_bridge import stock_add

    if stock_add(state, dim, delta, route=route) is not None:
        return True
    from core.foundation.ledger.material_holding import stock_adjust

    got = stock_adjust(state, dim, delta)
    if got is None:
        return False
    # 库存恒等式：任何入/出仓都必须登记流量（否则残差=未登记写点）
    try:
        from core.domains.economy import stock_flow as _sf
        if delta >= 0:
            _sf.record_in(state, dim, delta, "外贸进口")
        else:
            _sf.record_out(state, dim, -delta, "外贸出口")
    except Exception as exc:  # noqa: BLE001
        import logging as _lg
        _lg.getLogger(__name__).warning("外贸库存流水登记失败：%r", exc, exc_info=True)
    return True

def execute_leg(state, leg: Dict[str, Any]) -> Dict[str, Any]:
    """执行单条货腿：出口扣货（不足缩量）/ 进口加货（受仓容限制）。

    返回 `{ok, shipped_qty, received_qty, short_qty, value, reason}`；
    **不改运力账**（由调用方统一占用/排队）。
    """

    dim = str(leg.get("dim") or "")
    want = float(leg.get("planned_qty") or 0)
    price = leg.get("unit_price")
    direction = str(leg.get("direction") or "")
    route = str(leg.get("route") or "") or None
    if route is None:
        # 物资存量在**州府级**（stock_get 需 route）；无 route 不臆读、不写。
        return {"ok": False, "reason": "route_missing", "dim": dim}
    seat = leg.get("seat")
    if not dim or want <= 0:
        return {"ok": False, "reason": "bad_leg"}
    if direction == "export":
        # 🔴 外销只走**商人货**（consume_for_circuit 内部商人优先→官仓，且登记库存流水）；
        # 官仓是漕粮/上供，**不得被外销抽空**——否则 supply_goods_to_seats 无货可配（门会红）。
        from core.foundation.ledger.material_holding import consume_for_circuit
        take = 0.0
        if route:
            take = float(int(consume_for_circuit(state, str(route), dim, int(want))))
        if take <= 0:
            have = _stock_of(state, dim, route)
            return {"ok": False, "reason": "no_merchant_stock", "dim": dim,
                    "available": have}
        value = int(take * price) if isinstance(price, (int, float)) else None
        return {"ok": True, "shipped_qty": round(take, 3),
                "received_qty": 0.0, "short_qty": round(want - take, 3),
                "value": value, "reason": None if take >= want else "short_supply"}
    if direction == "import":
        before = _stock_of(state, dim, route) or 0
        cap = None
        try:
            meta = (getattr(state, "resources", {}) or {}).get(dim) or {}
            cap = meta.get("cap")
        except Exception:  # noqa: BLE001
            cap = None
        room = want
        if isinstance(cap, (int, float)):
            room = max(0.0, float(cap) - float(before))
        recv = min(want, room)
        _pay = _pay_import(state, route, dim, recv, price)
        if _pay < recv:
            recv = _pay        # 无钱即缩量（不赊账、不凭空）
        recv = float(int(recv))
        if recv <= 0:
            return {"ok": False, "reason": "no_storage", "dim": dim, "cap": cap}
        _add_stock(state, dim, recv, route)   # 进口入官仓（登记 national 流水）
        value = int(recv * price) if isinstance(price, (int, float)) else None
        return {"ok": True, "shipped_qty": 0.0, "received_qty": round(recv, 3),
                "short_qty": round(want - recv, 3), "value": value,
                "reason": None if recv >= want else "storage_limited"}
    return {"ok": False, "reason": "bad_direction", "direction": direction}


def apply_tariff(leg: Dict[str, Any], actual_value: Optional[int]) -> Dict[str, Any]:
    """按**实际成交额**计税（value=None ⇒ 税额 None，缺失≠0）。"""
    from content.data_constants import FOREIGN_TARIFF_RATE

    if actual_value is None:
        return {"ok": False, "reason": "value_missing", "tax": None}
    channel = str(leg.get("channel") or "")
    rate = float((FOREIGN_TARIFF_RATE or {}).get(channel, 0.0))
    tax = int(round(int(actual_value) * rate))
    return {"ok": True, "tax": tax, "rate": rate}


def contraband_check(leg: Dict[str, Any]) -> Dict[str, Any]:
    """禁榷查验：**出口**禁榷品 ⇒ 不放行（`blocked`），并给出明确 reason。

    · 清单：`CONTRABAND_DIMS`（官铸铜钱/铁/熟铁/铁锭/兵刃器械）；
    · 只查**出口**（进口不禁）；进口铜钱/铁不属此闸；
    · ⚠️ 走私实现现状：私贩需**商人持有货**才有货可走（P8 商人资产落地后接），
      现在只拦截 + 归因，**不凭空生成私货**（`smuggling: pending_p8` 写进 reason）。
    """
    from content.data_constants import CONTRABAND_DIMS

    dim = str(leg.get("dim") or "")
    if str(leg.get("direction") or "") != "export":
        return {"forbidden": False, "reason": None}
    if dim in set(CONTRABAND_DIMS or ()):
        return {"forbidden": True, "dim": dim,
                "reason": f"contraband:{dim}", "smuggling": "pending_p8"}
    return {"forbidden": False, "reason": None}

def attempt_smuggle(state, leg: Dict[str, Any]) -> Dict[str, Any]:
    """禁榷品**走私**（P7）：只走**商人私货**，按固定查获率拆分没收/流出。

    · 私货来源：该路商人 POP 的 `goods`（无 ⇒ `no_merchant_stock`，不外流）；
    · 查获 = 尝试量 × `CONTRABAND_SEIZURE_RATE`，**没收入官仓**（`stock_adjust` 加回）；
    · 走私成功部分**无税**（不走 `apply_tariff`），记 `direction=smuggle`；
    · 守恒：商人池减少 = 走私流出 + 查获没收；官仓增加 = 查获没收。
    """
    from content.data_constants import CONTRABAND_SEIZURE_RATE
    from core.foundation.ledger.material_holding import (consume_for_circuit, goods_amount,
                                                        merchant_goods)

    dim = str(leg.get("dim") or "")
    route = str(leg.get("route") or "")
    want = float(leg.get("planned_qty") or 0)
    if not dim or not route or want <= 0:
        return {"ok": False, "reason": "bad_leg"}
    goods = merchant_goods(state, route)
    have = int(goods_amount(goods, dim) or 0) if isinstance(goods, dict) else 0
    if have <= 0:
        return {"ok": False, "reason": "no_merchant_stock", "dim": dim}
    try_qty = min(int(want), have)
    taken = int(consume_for_circuit(state, route, dim, try_qty))
    if taken <= 0:
        return {"ok": False, "reason": "consume_failed", "dim": dim}
    rate = float(CONTRABAND_SEIZURE_RATE or 0)
    seized = max(0, min(taken, int(round(taken * rate))))
    smuggled = taken - seized
    if seized > 0:
        _add_stock(state, dim, float(seized), route)      # 没收入官仓（走流水登记）
    return {"ok": smuggled > 0 or seized > 0, "smuggled_qty": smuggled,
            "seized_qty": seized, "consumed_qty": taken,
            "reason": None if smuggled > 0 else "all_seized"}

def land_market_open(state, partner: str) -> Dict[str, Any]:
    """榷场（陆路互市）开关：**战时闭场**；态度低于阈值亦闭场（玩法设定）。

    · 战时判据：`state._at_war[partner]` 为真；
    · 态度判据：`state.external_regimes[partner].attitude < LAND_MARKET_MIN_ATTITUDE`；
    · 无该外邦（如大理/交趾未登记）⇒ 按**开放**处理但 reason 记 `partner_unmodeled`（不臆断为敌）。
    """
    from content.data_constants import LAND_MARKET_MIN_ATTITUDE

    war = getattr(state, "_at_war", None) or {}
    if isinstance(war, dict) and war.get(partner):
        return {"open": False, "reason": "at_war"}
    regimes = getattr(state, "external_regimes", None) or {}
    info = regimes.get(partner) if isinstance(regimes, dict) else None
    if not isinstance(info, dict):
        return {"open": True, "reason": "partner_unmodeled"}
    att = info.get("attitude")
    if isinstance(att, (int, float)) and not isinstance(att, bool):
        if float(att) < float(LAND_MARKET_MIN_ATTITUDE or 0):
            return {"open": False, "reason": f"low_attitude:{int(att)}", "attitude": att}
        return {"open": True, "reason": None, "attitude": att}
    return {"open": True, "reason": "attitude_missing"}


def settle_land_tariff(state, leg: Dict[str, Any], tax: Optional[int]) -> Dict[str, Any]:
    """陆路榷税入账：**过税 40% → 沿途路府库；住税 60% → 交易地府库**（设定值）。

    🔴 2026-10-20 全审 P0-2（A-3）：原实现只 `local_treasury += tax`、**无付款方**，
    等于凭空造币（实测 3.9–11.7 万贯/月）。现由该路**商人 POP wealth** 经桥扣缴，
    不足者按实扣（`credited` < `tax`，reason=`payer_short`），杜绝单边入账。
    缺 `local_treasury`/商人 POP ⇒ 不入账并返回 reason（不臆造通道）。
    """
    from content.data_constants import LAND_TAX_OVER_SHARE

    if tax is None:
        return {"ok": False, "reason": "tax_missing"}
    if tax <= 0:
        return {"ok": True, "over_tax": 0, "stay_tax": 0, "credited": 0, "short": 0}
    over_share = float(LAND_TAX_OVER_SHARE or 0.4)
    over_tax = int(round(int(tax) * over_share))
    stay_tax = int(tax) - over_tax
    route = str(leg.get("route") or "")
    prefs = getattr(state, "prefectures", None) or {}
    pdata = prefs.get(route) if isinstance(prefs, dict) else None
    if not isinstance(pdata, dict) or "local_treasury" not in pdata:
        return {"ok": False, "reason": "no_local_treasury", "route": route,
                "over_tax": over_tax, "stay_tax": stay_tax}
    _pops = pdata.get("pops") if isinstance(pdata.get("pops"), dict) else {}
    seller = _pops.get("商人") if isinstance(_pops, dict) else None
    if not isinstance(seller, dict):
        return {"ok": False, "reason": "no_merchant_payer", "route": route,
                "over_tax": over_tax, "stay_tax": stay_tax, "credited": 0}
    wealth = int(float(seller.get("wealth", 0) or 0))
    actual = int(min(int(tax), max(0, wealth)))
    if actual <= 0:
        return {"ok": False, "reason": "payer_insufficient", "route": route,
                "over_tax": over_tax, "stay_tax": stay_tax, "credited": 0,
                "short": int(tax)}
    from core.foundation.ledger.pop_bridge import pop_obj_add
    if pop_obj_add(state, seller, "wealth", -actual) is None:
        seller["wealth"] = wealth - actual
    # 2026-10-20 全审：地方府库写点走桥（治所真账 + 路级镜像同步）。
    from core.foundation.ledger import local_treasury_bridge as _ltb
    if _ltb.local_treasury_add(state, route, actual) is None:
        pdata["local_treasury"] = int(pdata.get("local_treasury", 0) or 0) + actual
    return {"ok": True, "over_tax": over_tax, "stay_tax": stay_tax, "credited": actual,
            "short": int(tax) - actual,
            "reason": None if actual >= int(tax) else "payer_short", "route": route}

def settle_foreign_trade(state, month: Optional[int] = None,
                         dry_run: Optional[bool] = None) -> Dict[str, Any]:
    """跑一个月的外贸货腿（**总开关默认关**）。

    流程：plan → execute（缩量）→ 关税（按实际额）→ 占运力（不足排队）→ 记账入 `trade_journal`。
    `dry_run=True` 时只算不改（影子对账用）。
    """
    from content.data_constants import FOREIGN_LEG_STONE_PER_UNIT

    if not trade_legs_enabled():
        return {"enabled": False, "reason": "FOREIGN_TRADE_LEGS=0（默认关）"}
    if dry_run is None:
        dry_run = False
    from core.transport import transport_ship_or_queue

    legs = plan_legs(state, month=month, advance=True)
    journal = getattr(state, "trade_journal", None)
    rows: List[Dict[str, Any]] = []
    totals = {"export_value": 0, "import_value": 0, "tax": 0,
              "queued_stone": 0.0, "blocked": 0}
    for leg in legs:
        # P6：陆路榷场受**和战/态度**约束（战时闭场）
        if leg.get("channel") == "land":
            _gate = land_market_open(state, str(leg.get("partner") or ""))
            if not _gate.get("open"):
                totals["blocked"] += 1
                rows.append({**leg, "j": {"ok": False,
                                           "reason": "market_closed:" + str(_gate.get("reason"))}})
                continue
        # P7：禁榷查验（出口禁榷品 ⇒ 拦截；走私待 P8 商人持有货后接）
        _cb = contraband_check(leg)
        if _cb.get("forbidden"):
            if not dry_run:
                _sm = attempt_smuggle(state, leg)
            else:
                _sm = {"ok": False, "reason": "dry_run"}
            if _sm.get("ok"):
                # 走私：无税、记 smuggle；查获部分已没收入官仓
                totals["smuggled_qty"] = totals.get("smuggled_qty", 0) + int(_sm.get("smuggled_qty") or 0)
                totals["seized_qty"] = totals.get("seized_qty", 0) + int(_sm.get("seized_qty") or 0)
                _row = {**leg, "shipped_qty": float(_sm.get("smuggled_qty") or 0),
                        "received_qty": 0.0, "short_qty": 0.0, "goods_value": None,
                        "tax": 0, "reason": _sm.get("reason"), "smuggled": True,
                        "seized_qty": int(_sm.get("seized_qty") or 0)}
                rows.append(_row)
                # 走私腿无货币流水 ⇒ 不写 trade_journal（报告与 state 明细保留）
                continue
            totals["blocked"] += 1
            totals["contraband_blocked"] = totals.get("contraband_blocked", 0) + 1
            rows.append({**leg, "j": {"ok": False, "reason": _cb.get("reason"),
                                       "smuggling": _sm.get("reason") or "no_merchant_stock"}})
            continue
        out = execute_leg(state, leg) if not dry_run else {"ok": True,
                                                          "shipped_qty": leg.get("planned_qty"),
                                                          "received_qty": 0.0, "short_qty": 0.0,
                                                          "value": leg.get("estimated_value")}
        if not out.get("ok"):
            totals["blocked"] += 1
            rows.append({**leg, "j": out})
            continue
        value = out.get("value")
        tax = apply_tariff(leg, value)
        _split = None
        _tax_credited = int(tax.get("tax") or 0)
        if leg.get("channel") == "land" and not dry_run:
            _split = settle_land_tariff(state, leg, tax.get("tax"))
            # P0-2：陆路税以**实扣成功额**入账/统计（付款方不足时不得按请求额虚报）
            _tax_credited = int((_split or {}).get("credited") or 0)
        qty = float(out.get("shipped_qty") or 0) + float(out.get("received_qty") or 0)
        stone = qty * float(FOREIGN_LEG_STONE_PER_UNIT or 1.0)
        if not dry_run and stone > 0:
            mode = "maritime" if leg.get("channel") == "sea" else "overland"
            ship = transport_ship_or_queue(
                state, mode, stone, kind="goods",
                payload={"dim": leg.get("dim"), "partner": leg.get("partner"),
                         "direction": leg.get("direction"), "month": month})
            totals["queued_stone"] += float(ship.get("queued") or 0)
        if leg.get("direction") == "export":
            totals["export_value"] += int(value or 0)
        else:
            totals["import_value"] += int(value or 0)
        totals["tax"] += _tax_credited
        # O3（修复复审）：流水/行数据用**实扣额**，与 totals 同口径；应征额另存
        # tax_requested，供对账（陆路付款方不足时两者会不等）。
        row = {**leg, "shipped_qty": out.get("shipped_qty"),
               "received_qty": out.get("received_qty"), "short_qty": out.get("short_qty"),
               "goods_value": value, "tax": _tax_credited,
               "tax_requested": tax.get("tax"), "reason": out.get("reason")}
        rows.append(row)
        if not dry_run and isinstance(journal, list):
            journal.append({"month": month, "route": leg.get("route"), "seat": leg.get("seat"),
                            "partner": leg.get("partner"), "dim": leg.get("dim"),
                            "qty": qty, "unit_price": leg.get("unit_price"),
                            "goods_value": value,
                            "tax": _tax_credited, "tax_requested": tax.get("tax"),
                            "tax_over": (_split or {}).get("over_tax", tax.get("tax")),
                            "tax_stay": (_split or {}).get("stay_tax"),
                            "direction": leg.get("direction"), "freight": None,
                            "reason": out.get("reason")})
    return {"enabled": True, "dry_run": bool(dry_run), "legs": len(legs),
            "executed": sum(1 for r in rows if "j" not in r), **totals, "rows": rows}