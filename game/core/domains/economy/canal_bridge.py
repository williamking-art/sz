# -*- coding: utf-8 -*-
"""漕运淤塞（`canal_block`）**治所级**真账桥接 —— 交通下沉州府级 M39c-1。

现状与口径
----------
`canal_block` 原为**全国单标量**（0~100 淤塞度，`game_state.py:799`）⇒ 表达不了
「某段运河淤塞、别处通畅」。本模块把它下沉到治所：

* **真账**：`prefectures[路]["seats"][治所]["canal_block"]`（**0~100**）。
  迁移按 **首府承载**（Jev 2026-10-13 Q3 0.513：无逐治所来源 ⇒ **不编造**每治所值）；
  **未登记的治所缺席**（`None`，不写 0——0 是「通畅」这一**声明**，不是缺失）。
* **派生聚合**：路级 `prefectures[路]["canal_block"]` 与全国 `state.canal_block`
  = 各治所值的 **按水路档位加权平均**（Jev Q2 choose B **0.502**；
  权重：强 3 / 有 2 / 弱 1，未登记档位 → 1）。**量纲仍是 0~100**。
* **写点必须走桥**：`canal_set_national` / `canal_set` / `canal_add`；**未下沉 ⇒ `None`**，
  调用方保持原写法回落（惯例 `if canal_set_national(...) is None: state.canal_block = v`）。
* **缺失 ≠ 0**：无 `seats` / 未下沉 ⇒ 聚合返回 `None`；无值的治所不参与平均。

⚠️ **本批（M39c-1）只做结构下沉 + 桥 2 个全国级写点，读者一律不改**（Jev Q1 choose A 0.457，
边际薄；理由：规格 ③ 自述「牵动多系统，需单独作业」，且改粮价＝改数值须重新标定）。
⇒ 全国值经派生后与原值**逐字相等** ⇒ **零行为变化**（A/B 对照锁定）。
`game_state_econ:336`（粮价加价）等 9 处读者仍读全国镜像 = M39c-2 的活。
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

log = logging.getLogger(__name__)

#: 治所真账里承载淤塞度的键名；路级同名键是**派生镜像**
SEAT_KEY = "canal_block"

#: 档位权重（强＞有＞弱）；未登记档位按 1 计
TIER_WEIGHT: Dict[str, float] = {"强": 3.0, "有": 2.0, "弱": 1.0}

__all__ = [
    "SEAT_KEY", "TIER_WEIGHT", "is_sunk", "seat_canal_block", "weighted_mean",
    "aggregate_route_canal_block", "aggregate_national_canal_block",
    "survey_canal", "sink_route_canal", "sink_canal_to_seats",
    "canal_set", "canal_add", "canal_set_national",
]


def _seats_map(pdata) -> Dict[str, dict]:
    if not isinstance(pdata, dict):
        return {}
    seats = pdata.get("seats")
    return seats if isinstance(seats, dict) else {}


def _num(v) -> Optional[float]:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return None


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, float(v)))


def seat_canal_block(pdata, seat_id: str) -> Optional[float]:
    """某治所的淤塞度；**未登记 ⇒ `None`**（缺失≠0）。"""
    seat = _seats_map(pdata).get(str(seat_id))
    if not isinstance(seat, dict):
        return None
    return _num(seat.get(SEAT_KEY))


def is_sunk(pdata) -> bool:
    """该路是否已下沉：**至少一个治所有数值型 `canal_block`**。

    （与其他桥不同：不要求"每个治所都有键"——未登记治所**缺席**才是正确语义，
    因为 0 表示「通畅」这一声明，不能拿 0 冒充缺失。）
    """
    for s in _seats_map(pdata).values():
        if isinstance(s, dict) and _num(s.get(SEAT_KEY)) is not None:
            return True
    return False


def _tier_weight(route: str, seat_id: str) -> float:
    """该治所的聚合权重：优先用它自己的水路档位（治所级表 `SEAT_WATERWAY`），
    未知则用所属路的史料档，再未知按 1。"""
    try:
        from core.domains.economy import waterway_seats as ws
        t = ws.waterway_tier_seat(seat_id) or ws.waterway_tier_route(route)
    except Exception:                                   # noqa: BLE001
        t = None
    return TIER_WEIGHT.get(str(t), 1.0)


def weighted_mean(pairs) -> Optional[float]:
    """`[(值, 权重)]` → 加权平均（权重和 ≤0 ⇒ `None`）。"""
    num = sum(float(v) * float(w) for v, w in pairs)
    den = sum(float(w) for _v, w in pairs)
    if den <= 0:
        return None
    return num / den


def aggregate_route_canal_block(pdata, route: str = "") -> Optional[float]:
    """**路级派生聚合**：该路各治所值的按档位加权平均；一个值都没有 ⇒ `None`。"""
    pairs = []
    for sid, s in _seats_map(pdata).items():
        if not isinstance(s, dict):
            continue
        v = _num(s.get(SEAT_KEY))
        if v is None:
            continue
        pairs.append((v, _tier_weight(route, str(sid))))
    return weighted_mean(pairs)


def aggregate_national_canal_block(state) -> Optional[float]:
    """**全国派生聚合**：各路派生值的按档位加权平均（路权重取其首府治所档位）。"""
    prefs = getattr(state, "prefectures", {}) or {}
    pairs = []
    for route, pdata in prefs.items():
        v = aggregate_route_canal_block(pdata, route)
        if v is None:
            continue
        pairs.append((v, _tier_weight(route, route)))
    return weighted_mean(pairs)


def survey_canal(state) -> dict:
    """**迁移对账**：逐路比对「路级镜像」与「Σ→加权平均（治所）」；再比对全国。"""
    prefs = getattr(state, "prefectures", {}) or {}
    out = {"路由数": len(prefs), "已下沉路由": 0, "未下沉路由": 0, "字段失配": [],
           "全国_镜像": _num(getattr(state, "canal_block", None)),
           "全国_派生": aggregate_national_canal_block(state)}
    for route, pdata in prefs.items():
        if not isinstance(pdata, dict):
            continue
        if not is_sunk(pdata):
            out["未下沉路由"] += 1
            continue
        out["已下沉路由"] += 1
        mirror = _num(pdata.get(SEAT_KEY))
        derived = aggregate_route_canal_block(pdata, route)
        if mirror is None or derived is None or abs(mirror - derived) > 1e-6:
            out["字段失配"].append({"路": route, "路级": mirror, "派生": derived})
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
        log.warning("canal_bridge: 首府判定失败 route=%s", route, exc_info=True)
        return None


def sink_route_canal(pdata, route: str, value: Optional[float] = None) -> bool:
    """把某路淤塞度**落到首府治所**并刷新路级镜像。已下沉 ⇒ 不覆盖返回 False。"""
    if not isinstance(pdata, dict):
        return False
    if is_sunk(pdata):
        return False
    v = _num(value)
    if v is None:
        return False
    cap = _capital_of(pdata, route)
    if not cap:
        log.info("canal_bridge: route=%s 无首府可承载 → 跳过（不臆造）", route)
        return False
    seat = _seats_map(pdata).get(str(cap))
    if not isinstance(seat, dict):
        return False
    seat[SEAT_KEY] = _clamp(v)
    pdata[SEAT_KEY] = aggregate_route_canal_block(pdata, route)
    return True


def sink_canal_to_seats(state, routes=None) -> int:
    """**无条件幂等入口**：把**全国** `canal_block` 按路落到各自首府（新局与读档共用）。

    为什么是"全国值 → 每路首府"：淤塞今日是**全国单一事实**，没有逐路来源；
    按路复制是**不编造差异**的最小落法（Jev Q3 0.513），且派生回全国值与原值相等。
    """
    prefs = getattr(state, "prefectures", {}) or {}
    national = _num(getattr(state, "canal_block", None))
    if national is None:
        return 0
    names = list(routes) if routes else list(prefs)
    n = 0
    for route in names:
        try:
            if sink_route_canal(prefs.get(route), route, national):
                n += 1
        except Exception:                               # noqa: BLE001
            log.warning("canal_bridge: 下沉失败 route=%s（跳过）", route, exc_info=True)
    return n


def _routed(state, route: str):
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return None
    pdata = prefs.get(route)
    return pdata if isinstance(pdata, dict) else None


def canal_set(state, route: str, value, seat_id: Optional[str] = None) -> Optional[float]:
    """**写**某治所（默认首府）的淤塞度并刷新路级镜像。未下沉 ⇒ `None`。"""
    v = _num(value)
    pdata = _routed(state, route)
    if v is None or pdata is None or not is_sunk(pdata):
        return None
    sid = seat_id or _capital_of(pdata, route)
    seat = _seats_map(pdata).get(str(sid)) if sid else None
    if not isinstance(seat, dict):
        return None
    seat[SEAT_KEY] = _clamp(v)
    pdata[SEAT_KEY] = aggregate_route_canal_block(pdata, route)
    return float(seat[SEAT_KEY])


def canal_add(state, route: str, delta, seat_id: Optional[str] = None) -> Optional[float]:
    """**写**增量（疏浚 −／灾荒 +）。未下沉 ⇒ `None`。量纲钳到 0~100。"""
    d = _num(delta)
    pdata = _routed(state, route)
    if d is None or pdata is None or not is_sunk(pdata):
        return None
    sid = seat_id or _capital_of(pdata, route)
    cur = seat_canal_block(pdata, str(sid)) if sid else None
    if cur is None:
        return None
    return canal_set(state, route, cur + d, seat_id=str(sid))


def canal_set_national(state, value) -> Optional[float]:
    """**全国级写点**：把新值写到**所有已下沉路的首府**，并刷新路级镜像与 `state.canal_block`。

    **未下沉（一条路都没下沉）⇒ `None`** ⇒ 调用方回落原写法（`state.canal_block = v`）。
    **保持入参数值类型**（`int` 进 ⇒ `int` 出）：`canal_block` 原为 int（0~100 整数淤塞度），
    若桥把它变成 float 就是**静默的类型变更**（存量读点/存档/前端都会跟着变）。返回新的全国值。
    """
    v = _num(value)
    if v is None:
        return None
    keep_int = isinstance(value, int) and not isinstance(value, bool)
    out = int(_clamp(v)) if keep_int else _clamp(v)
    prefs = getattr(state, "prefectures", {}) or {}
    touched = 0
    for route, pdata in prefs.items():
        if isinstance(pdata, dict) and is_sunk(pdata):
            cap = _capital_of(pdata, route)
            seat = _seats_map(pdata).get(str(cap)) if cap else None
            if isinstance(seat, dict):
                seat[SEAT_KEY] = out
                pdata[SEAT_KEY] = aggregate_route_canal_block(pdata, route)
                touched += 1
    if not touched:
        return None
    state.canal_block = out
    return out
