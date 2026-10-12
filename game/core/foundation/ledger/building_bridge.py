# -*- coding: utf-8 -*-
"""建筑（`buildings`）州府级真账桥接 —— 主线 B 批次 2（M38a）。

口径（Jev 裁定 2026-10-13）
--------------------------
* **真账**：`prefectures[路]["seats"][治所]["buildings"]` = `{建筑名: 等级}`。
* **派生镜像**：路级 `prefectures[路]["buildings"]` = **Σ 各治所**（choose A，0.429；与既有
  `settlement_tech` 完工登记 `_b[name] += _lv` 的**累加**语义一致）。
* **下沉初始分配**：**首府（路治）承载**（choose A，0.894）——该路等级最高（`SEAT_LEVELS` 序：
  京府＞府＞州＞军＞部）、同级取人口权重高者；其余治所空 `{}` ⇒ 迁移后 **路级 Σ 与原值逐字相等**。
* **写点必须走桥**：`building_add(..., state)`；**未下沉 ⇒ `None`**，调用方回落原写法。

⚠️ **本批不开闸（不接 new_game/读档）——这是刻意的**
------------------------------------------------------------------
等级是**等级**而非数量：Σ 对**可加**读者（岗位 `jobs = 等级 × JOBS_PER_LEVEL`、产出乘数）是正确的，
但对**阈值/乘数**读者（`game_state_econ` 水利等级、`material_tech` 科技覆盖率、`era_mechanic` 时代修正、
`settlement_officialdom` 维持费）会随治所数**放大**。批次 2.2「同步改 4 个消费者」＝ M38b。
M37 实测教训：**开闸必须与全部写点＋消费者处理同批**，否则必然出现漂移/放大
（只下沉不桥 ⇒ 首轮起全路失配；只桥账户层 ⇒ 2× 冲账）。故本批只交付**可验证的桥接层**，
接线动作留给 M38b 一并完成。

未下沉时本模块所有写函数返回 `None`、聚合返回 `None` ⇒ **零行为变化**。
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

#: 治所真账里承载建筑的键名（与 `"pops"`/`"local_treasury"` 平级）
SEAT_KEY = "buildings"

__all__ = [
    "SEAT_KEY", "is_sunk", "aggregate_seat_buildings", "seat_buildings_total",
    "survey_buildings", "capital_seat_id", "sink_route_buildings",
    "sink_buildings_to_seats", "building_add", "building_level",
]


def _seats_map(pdata) -> Dict[str, dict]:
    if not isinstance(pdata, dict):
        return {}
    seats = pdata.get("seats")
    return seats if isinstance(seats, dict) else {}


def _levels_of(obj) -> Dict[str, int]:
    """从 `{建筑名: 等级}` 取出**数值**等级（非数值/非 dict 一律跳过，不崩）。"""
    if not isinstance(obj, dict):
        return {}
    out: Dict[str, int] = {}
    for k, v in obj.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[str(k)] = int(v)
    return out


def is_sunk(pdata) -> bool:
    """该路是否已下沉：**每个治所都有 dict 型 `buildings` 键**才算。"""
    seats = _seats_map(pdata)
    if not seats:
        return False
    return all(isinstance(s, dict) and isinstance(s.get(SEAT_KEY), dict) for s in seats.values())


def seat_buildings_total(pdata) -> Optional[dict]:
    """**Σ 各治所**等级（逐建筑名）。无 `seats` 或一个数值都没有 ⇒ `None`（缺失≠0）。"""
    seats = _seats_map(pdata)
    if not seats:
        return None
    total: Dict[str, int] = {}
    for s in seats.values():
        if not isinstance(s, dict):
            continue
        for name, lv in _levels_of(s.get(SEAT_KEY)).items():
            total[name] = total.get(name, 0) + lv
    return total or None


def aggregate_seat_buildings(pdata) -> Optional[dict]:
    """**派生聚合**：Σ 治所 ⇒ 路级镜像。未下沉 ⇒ `None`（不回落空表）。"""
    if not is_sunk(pdata):
        return None
    return seat_buildings_total(pdata)


def survey_buildings(state) -> dict:
    """**迁移对账**：逐路**逐建筑名**比对「路级」与「Σ 治所」。"""
    prefs = getattr(state, "prefectures", {}) or {}
    out = {"路由数": len(prefs), "已下沉路由": 0, "未下沉路由": 0, "字段失配": []}
    for route, pdata in prefs.items():
        if not isinstance(pdata, dict):
            continue
        if not is_sunk(pdata):
            out["未下沉路由"] += 1
            continue
        out["已下沉路由"] += 1
        mirror = _levels_of(pdata.get(SEAT_KEY))
        total = seat_buildings_total(pdata) or {}
        for name in sorted(set(mirror) | set(total)):
            if int(mirror.get(name, 0)) != int(total.get(name, 0)):
                out["字段失配"].append({"路": route, "建筑": name,
                                        "路级": mirror.get(name, 0), "Σ治所": total.get(name, 0)})
    return out


# --------------------------------------------------------------------------
# 首府（路治）判定
# --------------------------------------------------------------------------
def _seats_of(route: str) -> List[dict]:
    """该路治所实体（可打桩）。取 `prefecture_entity.seats_of`（不含省级归入席）。"""
    try:
        from core.foundation.ledger.prefecture_entity import SEAT_LEVELS, seats_of
        return list(seats_of(route, include_merged=False) or [])
    except Exception:                                   # noqa: BLE001
        log.warning("building_bridge: 取治所实体失败 route=%s", route, exc_info=True)
        return []


def capital_seat_id(pdata, route: str) -> Optional[str]:
    """**首府（路治）治所 id**：`SEAT_LEVELS` 序最优者，同级取人口权重高者。

    都不满足 ⇒ 退回 `seats` 的第一个键（确定性；口径记为**推演**，不臆造地点）。
    """
    seats = _seats_map(pdata)
    if not seats:
        return None
    try:
        from core.foundation.ledger.prefecture_entity import SEAT_LEVELS
    except Exception:                                   # noqa: BLE001
        SEAT_LEVELS = ("京府", "府", "州", "军", "部")
    weight = {}
    try:
        from core.foundation.ledger import pop_bridge
        weight = {str(sid): float(w) for sid, w in (pop_bridge.seat_pop_weights(route) or [])}
    except Exception:                                   # noqa: BLE001
        weight = {}
    best, best_key = None, None
    for ent in _seats_of(route):
        sid = str(ent.get("seat_id") or "")
        if sid not in seats:
            continue
        lvl = str(ent.get("level") or "")
        try:
            rank = SEAT_LEVELS.index(lvl)
        except ValueError:
            rank = len(SEAT_LEVELS)                        # 未知等级排最后
        key = (rank, -weight.get(sid, 0.0), sid)
        if best_key is None or key < best_key:
            best, best_key = sid, key
    if best:
        return best
    return str(next(iter(seats)))                          # 兜底：确定性首键


# --------------------------------------------------------------------------
# 下沉 / 写桥
# --------------------------------------------------------------------------
def sink_route_buildings(pdata, route: str, value=None) -> bool:
    """把路级建筑等级**全部落到首府治所**（其余治所空 `{}`），并刷新路级 Σ 镜像。

    已下沉 ⇒ 不覆盖返回 False（沿用 POP 同型纪律）。无可分配等级 ⇒ False。
    """
    if not isinstance(pdata, dict):
        return False
    if is_sunk(pdata):
        return False
    src = pdata.get(SEAT_KEY) if value is None else value
    levels = _levels_of(src)
    if not levels:
        return False
    cap = capital_seat_id(pdata, route)
    if not cap:
        log.info("building_bridge: route=%s 无治所可承载 → 跳过（不臆造归属）", route)
        return False
    seats = _seats_map(pdata)
    for sid, s in seats.items():
        if isinstance(s, dict):
            s[SEAT_KEY] = {}
    seats[cap][SEAT_KEY] = dict(levels)
    total = seat_buildings_total(pdata) or {}
    pdata[SEAT_KEY] = {k: int(v) for k, v in total.items()}
    return True


def sink_buildings_to_seats(state, routes=None) -> int:
    """**无条件幂等入口**（与 `sink_pops_to_seats` / `sink_local_treasury_to_seats` 同型）。

    返回实际下沉的路数。⚠️ 本批**不接** new_game/读档（见模块头：需与 M38b 消费者处理同批）。
    """
    prefs = getattr(state, "prefectures", {}) or {}
    names = list(routes) if routes else list(prefs)
    n = 0
    for route in names:
        pdata = prefs.get(route)
        try:
            if sink_route_buildings(pdata, route):
                n += 1
        except Exception:                               # noqa: BLE001
            log.warning("building_bridge: 下沉失败 route=%s（跳过）", route, exc_info=True)
    return n


def _routed(state, route: str):
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return None
    pdata = prefs.get(route)
    return pdata if isinstance(pdata, dict) else None


def building_add(state, route: str, name: str, levels: int,
                 seat_id: Optional[str] = None) -> Optional[int]:
    """**写**真账增量（完工登记用）。**未下沉 ⇒ `None`**（调用方回落原写法）。

    落点：`seat_id` 指定治所；未指定 ⇒ **首府（路治）**——州级工程落路治，属**推演**口径
    （工程只带 `route`，不带治所；一旦蓝图带治所，调用方传 `seat_id` 即可精确落位）。
    返回该建筑在该治所的新等级。
    """
    if not isinstance(levels, (int, float)) or isinstance(levels, bool):
        return None
    pdata = _routed(state, route)
    if pdata is None or not is_sunk(pdata):
        return None
    sid = seat_id or capital_seat_id(pdata, route)
    seat = _seats_map(pdata).get(str(sid)) if sid else None
    if not isinstance(seat, dict) or not isinstance(seat.get(SEAT_KEY), dict):
        return None
    lv = int(seat[SEAT_KEY].get(name, 0) or 0) + int(levels)
    seat[SEAT_KEY][name] = lv
    total = seat_buildings_total(pdata) or {}
    pdata[SEAT_KEY] = {k: int(v) for k, v in total.items()}
    return lv


def building_level(state, route: str, name: str) -> Optional[int]:
    """读**该建筑在路级 Σ 镜像**中的等级；未下沉 / 无此建筑 ⇒ `None`（缺失≠0）。"""
    pdata = _routed(state, route)
    if pdata is None or not is_sunk(pdata):
        return None
    total = seat_buildings_total(pdata) or {}
    return int(total[name]) if name in total else None
