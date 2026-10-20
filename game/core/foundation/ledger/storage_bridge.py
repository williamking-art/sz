# -*- coding: utf-8 -*-
"""仓储（`changping_stock` 常平仓 / `storage` 州仓）**治所级**真账桥接 —— 主线 B 批次 4 仓储片。

口径（Jev 裁定 2026-10-13）
--------------------------
* **真账**：`prefectures[路]["seats"][治所][<键>]`（石；`<键>` = `changping_stock` 或 `storage`）。
* **派生镜像**：路级同名键 = **Σ 各治所**（choose A **0.874**——可加实物，与 POP/粮/府库同口径）。
* **下沉初始分配**：**首府承载**（choose A，见 Q3 **0.730**）——无逐治所来源 ⇒ **不编造**差异；
  其余治所留空（`None`，不写 0——0 石是「空仓」这一**声明**，不是缺失）。
* **写点必须走桥**：`changping_add/set`（未下沉 ⇒ `None`，调用方回落原写法）。
* **缺失 ≠ 0**：无 `seats` / 未下沉 ⇒ 聚合 `None`；无值治所不参与 Σ。

本批（M40a）只做 **`changping_stock`**（Jev Q1 choose A **0.958**：写点是**单点**
`settlement_common._changping_trade`、读点均为普通读数 ⇒ 风险最低）。
`storage`（州仓）留下一批 **M40b**——它的读点含 `situations.py` 的条件路径
`prefectures.*.storage`（:1103）与拨帑赈济 inflow 判据（:1253），属**规则路径**，须单独核对。

⚠️ 不动中央太仓 `state.granary`（中央库存，非州府仓）。
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

log = logging.getLogger(__name__)

from core.foundation.ledger.seat_locator import (locate_route as _routed, seats_map as _seats_map)

#: 常平仓（石）—— 与州仓 `storage` 分离、不参与漕运上供
CHANGPING_KEY = "changping_stock"
#: 州仓/上供仓（石）—— M40b 用
STORAGE_KEY = "storage"

__all__ = [
    "CHANGPING_KEY", "STORAGE_KEY", "is_sunk", "seat_stock", "route_stock_total",
    "aggregate_route_changping", "aggregate_route_storage", "survey_storage",
    "changping_sink_route", "storage_sink_route", "sink_storage_to_seats",
    "sink_state_storage_to_seats", "changping_add", "changping_set", "changping_get",
    "storage_add", "storage_set", "storage_get",
]


def _int_or_none(v) -> Optional[int]:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return int(v)
    return None


# --------------------------------------------------------------------------
# 读侧
# --------------------------------------------------------------------------
def seat_stock(pdata, seat_id: str, key: str = CHANGPING_KEY) -> Optional[int]:
    """某治所的存量（石）；**未登记 ⇒ `None`**（缺失≠0）。"""
    seat = _seats_map(pdata).get(str(seat_id))
    if not isinstance(seat, dict):
        return None
    return _int_or_none(seat.get(key))


def is_sunk(pdata, key: str = CHANGPING_KEY) -> bool:
    """该路是否已下沉：**至少一个治所有数值型该键**。

    （不要求"每个治所都有键"——未登记治所**缺席**才是正确语义：0 石＝「空仓」这一声明。）
    """
    for s in _seats_map(pdata).values():
        if isinstance(s, dict) and _int_or_none(s.get(key)) is not None:
            return True
    return False


def route_stock_total(pdata, key: str = CHANGPING_KEY) -> Optional[int]:
    """**Σ 各治所**（石）；无 `seats` 或一个值都没有 ⇒ `None`（缺失≠0）。"""
    if not _seats_map(pdata):
        return None
    vals = [v for v in (_int_or_none(s.get(key)) for s in _seats_map(pdata).values()
                        if isinstance(s, dict)) if v is not None]
    if not vals:
        return None
    return int(sum(vals))


def aggregate_route_changping(pdata) -> Optional[int]:
    """**常平仓路级派生聚合**：Σ 各治所；未下沉 ⇒ `None`。"""
    if not is_sunk(pdata, CHANGPING_KEY):
        return None
    return route_stock_total(pdata, CHANGPING_KEY)


def aggregate_route_storage(pdata) -> Optional[int]:
    """**州仓路级派生聚合**：Σ 各治所；未下沉 ⇒ `None`。"""
    if not is_sunk(pdata, STORAGE_KEY):
        return None
    return route_stock_total(pdata, STORAGE_KEY)


def survey_storage(state, key: str = CHANGPING_KEY) -> dict:

    """**迁移对账**：逐路比对「路级镜像」与「Σ 治所」。"""
    prefs = getattr(state, "prefectures", {}) or {}
    out = {"键": key, "路由数": len(prefs), "已下沉路由": 0, "未下沉路由": 0, "字段失配": []}
    for route, pdata in prefs.items():
        if not isinstance(pdata, dict):
            continue
        if not is_sunk(pdata, key):
            out["未下沉路由"] += 1
            continue
        out["已下沉路由"] += 1
        mirror = _int_or_none(pdata.get(key))
        total = route_stock_total(pdata, key)
        if mirror is None or total is None or mirror != total:
            out["字段失配"].append({"路": route, "路级": mirror, "Σ治所": total})
    return out


# --------------------------------------------------------------------------
# 下沉 / 写桥
# --------------------------------------------------------------------------
def _capital_of(pdata, route: str) -> Optional[str]:
    """首府治所：复用 `building_bridge.capital_seat_id`（同一判定，避免两套口径）。"""
    try:
        from core.foundation.ledger import building_bridge as bb
        return bb.capital_seat_id(pdata, route)
    except Exception:                                   # noqa: BLE001
        log.warning("storage_bridge: 首府判定失败 route=%s", route, exc_info=True)
        return None


def changping_sink_route(pdata, route: str, value=None, key: str = CHANGPING_KEY) -> bool:
    """把路级存量**全部落到首府治所**并刷新路级 Σ 镜像。已下沉 ⇒ False（不覆盖）。"""
    if not isinstance(pdata, dict) or is_sunk(pdata, key):
        return False
    v = _int_or_none(pdata.get(key) if value is None else value)
    if v is None:
        return False
    cap = _capital_of(pdata, route)
    if not cap:
        log.info("storage_bridge: route=%s 无首府可承载 → 跳过（不臆造）", route)
        return False
    seat = _seats_map(pdata).get(str(cap))
    if not isinstance(seat, dict):
        return False
    seat[key] = int(v)
    pdata[key] = route_stock_total(pdata, key)
    return True


def sink_storage_to_seats(state, routes=None, key: str = CHANGPING_KEY) -> int:
    """**无条件幂等入口**（与 `sink_pops_to_seats` 等同型）：新局与读档共用。

    返回实际下沉的路数。权重/首府不可得 ⇒ 跳过（不臆造归属）。
    """
    prefs = getattr(state, "prefectures", {}) or {}
    names = list(routes) if routes else list(prefs)
    n = 0
    for route in names:
        try:
            if changping_sink_route(prefs.get(route), route, key=key):
                n += 1
        except Exception:                               # noqa: BLE001
            log.warning("storage_bridge: 下沉失败 route=%s key=%s（跳过）", route, key,
                        exc_info=True)
    return n


def changping_get(state, route: str) -> Optional[int]:
    """读该路常平仓（Σ 镜像口径）；未下沉 ⇒ `None`。"""
    pdata = _routed(state, route)
    if pdata is None or not is_sunk(pdata, CHANGPING_KEY):
        return None
    return route_stock_total(pdata, CHANGPING_KEY)


def changping_set(state, route: str, value, seat_id: Optional[str] = None) -> Optional[int]:
    """**写**常平仓为 `value`（默认写首府治所）并刷新路级 Σ 镜像。未下沉 ⇒ `None`。"""
    v = _int_or_none(value)
    pdata = _routed(state, route)
    if v is None or pdata is None or not is_sunk(pdata, CHANGPING_KEY):
        return None
    sid = seat_id or _capital_of(pdata, route)
    seat = _seats_map(pdata).get(str(sid)) if sid else None
    if not isinstance(seat, dict):
        return None
    # 🔴 B-2（2026-10-17）：常平仓 `changping_stock` 与官仓实物
    # `warehouses["public_granary"]["stocks"]["grain"]` 是**两个独立账户**，
    # 不得无对价互相覆盖。此写点只写常平账；公共官仓实物只由真实收/支
    # （仓门入出、平粜/平籴的实际货腿）改动。若将来裁定二者同一权威账，
    # 必须改为单点写入 + 另一侧只读派生（并在此加断言），不得再复制数值。
    _wh = seat.get("warehouses")
    _pub_before = None
    if isinstance(_wh, dict) and isinstance(_wh.get("public_granary"), dict):
        _pub_before = ((_wh["public_granary"].get("stocks") or {}).get("grain"))
    seat[CHANGPING_KEY] = max(0, int(v))
    _pub_after = None
    if isinstance(_wh, dict) and isinstance(_wh.get("public_granary"), dict):
        _pub_after = ((_wh["public_granary"].get("stocks") or {}).get("grain"))
    assert _pub_after == _pub_before, \
        "changping_set 不得改写 public_granary.stocks['grain']（常平账与官仓实物账分离）"
    pdata[CHANGPING_KEY] = route_stock_total(pdata, CHANGPING_KEY)
    return seat[CHANGPING_KEY]


def changping_add(state, route: str, delta, seat_id: Optional[str] = None) -> Optional[int]:
    """**写**常平仓增量（籴入 + / 粜出 −）。未下沉 ⇒ `None`。

    下限 0（原实现粜出侧写 `max(0, x - total)`；桥保持同语义，夹紧时留痕）。
    """
    d = _int_or_none(delta)
    pdata = _routed(state, route)
    if d is None or pdata is None or not is_sunk(pdata, CHANGPING_KEY):
        return None
    sid = seat_id or _capital_of(pdata, route)
    cur = seat_stock(pdata, str(sid), CHANGPING_KEY) if sid else None
    if cur is None:
        return None
    new = cur + int(d)
    if new < 0:
        log.warning("storage_bridge: route=%s 常平仓触零夹紧（cur=%s delta=%s）", route, cur, d)
        new = 0
    return changping_set(state, route, new, seat_id=str(sid))


def storage_sink_route(pdata, route: str, value=None) -> bool:
    """把路级州仓存量**全部落到首府治所**并刷新路级 Σ 镜像。已下沉 ⇒ False。"""
    return changping_sink_route(pdata, route, value=value, key=STORAGE_KEY)


def sink_state_storage_to_seats(state, routes=None) -> int:
    """**无条件幂等入口**：把路级州仓（storage）下沉到治所首府。返回实际下沉路数。"""
    return sink_storage_to_seats(state, routes=routes, key=STORAGE_KEY)


def storage_get(state, route: str) -> Optional[int]:
    """读该路州仓（Σ 镜像口径）；未下沉 ⇒ `None`。"""
    pdata = _routed(state, route)
    if pdata is None or not is_sunk(pdata, STORAGE_KEY):
        return None
    return route_stock_total(pdata, STORAGE_KEY)


def storage_set(state, route: str, value, seat_id: Optional[str] = None) -> Optional[int]:
    """**写**州仓为 `value`（默认写首府治所）并刷新路级 Σ 镜像。未下沉 ⇒ `None`。"""
    v = _int_or_none(value)
    pdata = _routed(state, route)
    if v is None or pdata is None or not is_sunk(pdata, STORAGE_KEY):
        return None
    sid = seat_id or _capital_of(pdata, route)
    seat = _seats_map(pdata).get(str(sid)) if sid else None
    if not isinstance(seat, dict):
        return None
    seat[STORAGE_KEY] = max(0, int(v))
    pdata[STORAGE_KEY] = route_stock_total(pdata, STORAGE_KEY)
    return seat[STORAGE_KEY]


def storage_add(state, route: str, delta, seat_id: Optional[str] = None) -> Optional[int]:
    """**写**州仓增量（征收入库 + / 漕运起运 −）。未下沉 ⇒ `None`。

    下限 0（防止透支触负；夹紧时记录 warning）。
    """
    d = _int_or_none(delta)
    pdata = _routed(state, route)
    if d is None or pdata is None or not is_sunk(pdata, STORAGE_KEY):
        return None
    sid = seat_id or _capital_of(pdata, route)
    cur = seat_stock(pdata, str(sid), STORAGE_KEY) if sid else None
    if cur is None:
        return None
    new = cur + int(d)
    if new < 0:
        log.warning("storage_bridge: route=%s 州仓触零夹紧（cur=%s delta=%s）", route, cur, d)
        new = 0
    return storage_set(state, route, new, seat_id=str(sid))

