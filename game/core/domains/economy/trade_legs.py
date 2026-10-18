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


def plan_legs(state, month: Optional[int] = None) -> List[Dict[str, Any]]:
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
                legs.append({
                    "month": month,
                    "channel": channel,
                    "seat": port.get("seat"),
                    "route": str(port.get("seat") or "").split("|")[0] or None,
                    "port": port.get("name"),
                    "partner": partner,
                    "direction": direction,
                    "dim": dim,
                    "planned_qty": qty,
                    "unit_price": price,
                    "estimated_value": (qty * price) if price is not None else None,
                })
    return legs


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

    return stock_adjust(state, dim, delta) is not None

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
        have = _stock_of(state, dim, route)
        if have is None:
            return {"ok": False, "reason": "stock_unreadable", "dim": dim}
        take = min(want, float(have))
        if take <= 0:
            return {"ok": False, "reason": "insufficient_stock", "dim": dim,
                    "available": have}
        _add_stock(state, dim, -take, route)
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
        if recv <= 0:
            return {"ok": False, "reason": "no_storage", "dim": dim, "cap": cap}
        _add_stock(state, dim, recv, route)
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

    缺 `local_treasury` 字段 ⇒ 不入账并返回 reason（不臆造入账通道）。
    """
    from content.data_constants import LAND_TAX_OVER_SHARE

    if tax is None:
        return {"ok": False, "reason": "tax_missing"}
    if tax <= 0:
        return {"ok": True, "over_tax": 0, "stay_tax": 0, "credited": 0}
    over_share = float(LAND_TAX_OVER_SHARE or 0.4)
    over_tax = int(round(int(tax) * over_share))
    stay_tax = int(tax) - over_tax
    route = str(leg.get("route") or "")
    prefs = getattr(state, "prefectures", None) or {}
    pdata = prefs.get(route) if isinstance(prefs, dict) else None
    if not isinstance(pdata, dict) or "local_treasury" not in pdata:
        return {"ok": False, "reason": "no_local_treasury", "route": route,
                "over_tax": over_tax, "stay_tax": stay_tax}
    pdata["local_treasury"] = int(pdata.get("local_treasury", 0) or 0) + int(tax)
    return {"ok": True, "over_tax": over_tax, "stay_tax": stay_tax, "credited": int(tax),
            "route": route}

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

    legs = plan_legs(state, month=month)
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
            totals["blocked"] += 1
            totals["contraband_blocked"] = totals.get("contraband_blocked", 0) + 1
            rows.append({**leg, "j": {"ok": False, "reason": _cb.get("reason"),
                                       "smuggling": _cb.get("smuggling")}})
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
        if leg.get("channel") == "land" and not dry_run:
            _split = settle_land_tariff(state, leg, tax.get("tax"))
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
        totals["tax"] += int(tax.get("tax") or 0)
        row = {**leg, "shipped_qty": out.get("shipped_qty"),
               "received_qty": out.get("received_qty"), "short_qty": out.get("short_qty"),
               "goods_value": value, "tax": tax.get("tax"), "reason": out.get("reason")}
        rows.append(row)
        if not dry_run and isinstance(journal, list):
            journal.append({"month": month, "route": leg.get("route"), "seat": leg.get("seat"),
                            "partner": leg.get("partner"), "dim": leg.get("dim"),
                            "qty": qty, "unit_price": leg.get("unit_price"),
                            "goods_value": value,
                            "tax_over": (_split or {}).get("over_tax", tax.get("tax")),
                            "tax_stay": (_split or {}).get("stay_tax"),
                            "direction": leg.get("direction"), "freight": None,
                            "reason": out.get("reason")})
    return {"enabled": True, "dry_run": bool(dry_run), "legs": len(legs),
            "executed": sum(1 for r in rows if "j" not in r), **totals, "rows": rows}