# -*- coding: utf-8 -*-
"""建筑（`buildings`）州府级真账桥接 —— 主线 B 批次 2（M38a/M38b 前置）。

口径（Jev 裁定 2026-10-13）
--------------------------
* **真账**：`prefectures[路]["seats"][治所]["buildings"]` = `{建筑名: 条目}`。
  条目形态**两种并存**（`building_jobs.building_level` 已兼容）：
    ① 标量（宋侧岗位类，`settlement_tech` 完工登记 `+= _lv` 的写法）；
    ② 字典 `{"lv": n, "built_month": m}`（`civil_building` 非岗位类写法；`built_month` **有读者**
       —— `civil_building` 折旧判据读不到即 `undefined`）。
  另有 `{"closed": true}` ⇒ 等级按 **0**（`building_jobs` 既有语义）。
* **派生镜像**：路级 `prefectures[路]["buildings"]` = **Σ 各治所**（choose A，0.429），
  **保形态**：任一条目是字典 ⇒ 镜像也写字典（`{"lv": Σ, "built_month": 各contributor最老者}` ——
  `built_month` 的路级值属**推演**，逐治所真账各自保留原值）。
* **下沉初始分配**：**首府（路治）承载**（choose A，0.894）——等级最高（`SEAT_LEVELS`：
  京府＞府＞州＞军＞部）、同级取人口权重高者；其余治所空 `{}` ⇒ 迁移后 **路级 Σ 与原值逐字相等**，
  且**原始条目（含 `built_month`）原样搬运**。
* **写点必须走桥**：`building_add`（增量，保形态）/ `building_set`（按原始条目精确写）；
  **未下沉 ⇒ `None`**，调用方回落原写法。

⚠️ **本批仍不开闸（不接 new_game/读档）**——理由
--------------------------------------------------
写点实测**至少 4 处**（非 3 处）：① `game_state:1032` 新局初始化（在 sink 之前，可不桥）；
② `settlement_tech:571-573` 完工登记；③ `civil_building:1064-1073` 民间营造（标量/字典两形态）；
④ **`era_mechanic.damage_buildings:104-111` 战乱灾荒降级**（写回归一化标量，且 `lv==1` 时 `del`）。
M37 实测教训：**开闸必须与「全部写点桥接 + 形态处理」同批**，否则静默漂移/丢形态。本批先把桥
做扎实（form-aware）并用例锁定，接线留到 M38b-2 与消费者一并做。未下沉时全部函数返回 `None`
⇒ **零行为变化**。
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

log = logging.getLogger(__name__)

#: 治所真账里承载建筑的键名（与 `"pops"`/`"local_treasury"` 平级）
SEAT_KEY = "buildings"

__all__ = [
    "SEAT_KEY", "is_sunk", "aggregate_seat_buildings", "seat_buildings_total",
    "survey_buildings", "capital_seat_id", "sink_route_buildings",
    "sink_buildings_to_seats", "building_add", "building_set", "building_level",
    "norm_level",
]


def _seats_map(pdata) -> Dict[str, dict]:
    if not isinstance(pdata, dict):
        return {}
    seats = pdata.get("seats")
    return seats if isinstance(seats, dict) else {}


def norm_level(entry) -> Optional[int]:
    """条目 → **等级**（int）。兼容三种形态；读不出 ⇒ `None`（缺失≠0）。

    * 标量 `2` ⇒ 2；
    * 字典 `{"lv": 2, ...}` ⇒ 2；`{"closed": true}` ⇒ **0**（`building_jobs` 既有语义）；
    * 其它（`None`/字符串/无 `lv` 的字典）⇒ `None`。
    """
    if isinstance(entry, (int, float)) and not isinstance(entry, bool):
        return int(entry)
    if isinstance(entry, dict):
        if entry.get("closed"):
            return 0
        lv = entry.get("lv")
        if isinstance(lv, (int, float)) and not isinstance(lv, bool):
            return int(lv)
    return None


def _levels_of(obj) -> Dict[str, int]:
    """`{建筑名: 条目}` → `{建筑名: 等级}`（读不出的条目**跳过**，不崩）。"""
    if not isinstance(obj, dict):
        return {}
    out: Dict[str, int] = {}
    for k, v in obj.items():
        lv = norm_level(v)
        if lv is not None:
            out[str(k)] = lv
    return out


def _raw_of(obj) -> Dict[str, object]:
    """原始条目（保形态）。非 dict ⇒ 空。"""
    return dict(obj) if isinstance(obj, dict) else {}


def is_sunk(pdata) -> bool:
    """该路是否已下沉：**每个治所都有 dict 型 `buildings` 键**才算。"""
    seats = _seats_map(pdata)
    if not seats:
        return False
    return all(isinstance(s, dict) and isinstance(s.get(SEAT_KEY), dict) for s in seats.values())


def _seat_of(pdata, seat_id: str):
    seat = _seats_map(pdata).get(str(seat_id))
    return seat if isinstance(seat, dict) else None


def seat_buildings_total(pdata) -> Optional[dict]:
    """**Σ 各治所等级**（逐建筑名，归一为 int）。无 `seats` 或一个都读不出 ⇒ `None`（缺失≠0）。"""
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
    """**派生聚合**（保形态）：Σ 治所 ⇒ 路级镜像。未下沉 ⇒ `None`。

    * 全部贡献条目都是标量 ⇒ 镜像写 int Σ；
    * 任一是字典 ⇒ 镜像写 `{"lv": Σ, "built_month": 各贡献者最老者}`（**推演**口径）。
    """
    if not is_sunk(pdata):
        return None
    seats = _seats_map(pdata)
    total = seat_buildings_total(pdata) or {}
    forms: Dict[str, bool] = {}
    months: Dict[str, int] = {}
    for s in seats.values():
        if not isinstance(s, dict):
            continue
        for name, entry in _raw_of(s.get(SEAT_KEY)).items():
            name = str(name)
            if isinstance(entry, dict) and norm_level(entry) is not None:
                forms[name] = True
                bm = entry.get("built_month")
                if isinstance(bm, (int, float)) and not isinstance(bm, bool):
                    months[name] = min(months.get(name, int(bm)), int(bm))
    out: Dict[str, object] = {}
    for name, lv in total.items():
        if forms.get(name):
            entry: Dict[str, object] = {"lv": int(lv)}
            if name in months:
                entry["built_month"] = int(months[name])
            out[name] = entry
        else:
            out[name] = int(lv)
    return out


def survey_buildings(state) -> dict:
    """**迁移对账**：逐路**逐建筑名**比对「路级归一等级」与「Σ 治所」。"""
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
def _seats_of(route: str):
    try:
        from core.foundation.ledger.prefecture_entity import seats_of
        return list(seats_of(route, include_merged=False) or [])
    except Exception:                                   # noqa: BLE001
        log.warning("building_bridge: 取治所实体失败 route=%s", route, exc_info=True)
        return []


def capital_seat_id(pdata, route: str) -> Optional[str]:
    """**首府（路治）治所 id**：`SEAT_LEVELS` 序最优，同级取人口权重高者；判不出退回首键。"""
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
            rank = len(SEAT_LEVELS)
        key = (rank, -weight.get(sid, 0.0), sid)
        if best_key is None or key < best_key:
            best, best_key = sid, key
    if best:
        return best
    return str(next(iter(seats)))


# --------------------------------------------------------------------------
# 下沉 / 写桥
# --------------------------------------------------------------------------
def sink_route_buildings(pdata, route: str, value=None) -> bool:
    """路级建筑**原样搬到首府治所**（其余治所空 `{}`），并刷新路级镜像。

    已下沉 ⇒ 不覆盖返回 False。**条目形态（含 `built_month`）原样保留**。
    """
    if not isinstance(pdata, dict):
        return False
    if is_sunk(pdata):
        return False
    raw = _raw_of(pdata.get(SEAT_KEY) if value is None else value)
    if not _levels_of(raw):
        return False
    cap = capital_seat_id(pdata, route)
    if not cap:
        log.info("building_bridge: route=%s 无治所可承载 → 跳过（不臆造归属）", route)
        return False
    for sid, s in _seats_map(pdata).items():
        if isinstance(s, dict):
            s[SEAT_KEY] = {}
    _seats_map(pdata)[cap][SEAT_KEY] = raw
    pdata[SEAT_KEY] = aggregate_seat_buildings(pdata) or {}
    return True


def sink_buildings_to_seats(state, routes=None) -> int:
    """**无条件幂等入口**（与 `sink_pops_to_seats` 同型）。本批**不接** new_game/读档（见模块头）。"""
    prefs = getattr(state, "prefectures", {}) or {}
    names = list(routes) if routes else list(prefs)
    n = 0
    for route in names:
        try:
            if sink_route_buildings(prefs.get(route), route):
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


def _refresh(pdata) -> None:
    pdata[SEAT_KEY] = aggregate_seat_buildings(pdata) or {}


def building_add(state, route: str, name: str, levels: int,
                 seat_id: Optional[str] = None,
                 built_month: Optional[int] = None) -> Optional[int]:
    """**写**真账增量（完工登记/营造升级用）。**未下沉 ⇒ `None`**（调用方回落原写法）。

    落点：`seat_id`；未指定 ⇒ **首府（路治）**——州级工程只带 `route`，属**推演**口径。
    **保形态**：既有条目是字典 ⇒ 只更新其 `lv`（保留 `built_month`）；给了 `built_month`
    或既有是字典 ⇒ 写字典形态；否则写标量。返回该建筑在该治所的新等级。
    """
    if not isinstance(levels, (int, float)) or isinstance(levels, bool):
        return None
    pdata = _routed(state, route)
    if pdata is None or not is_sunk(pdata):
        return None
    sid = seat_id or capital_seat_id(pdata, route)
    seat = _seat_of(pdata, sid) if sid else None
    if seat is None or not isinstance(seat.get(SEAT_KEY), dict):
        return None
    old = seat[SEAT_KEY].get(name)
    cur = norm_level(old) or 0
    new_lv = int(cur) + int(levels)
    if isinstance(old, dict):
        old = dict(old)
        old["lv"] = new_lv
        if built_month is not None:
            old["built_month"] = int(built_month)
        seat[SEAT_KEY][name] = old
    elif built_month is not None:
        seat[SEAT_KEY][name] = {"lv": new_lv, "built_month": int(built_month)}
    else:
        seat[SEAT_KEY][name] = new_lv
    _refresh(pdata)
    return new_lv


def building_set(state, route: str, name: str, entry,
                 seat_id: Optional[str] = None) -> Optional[object]:
    """**按原始条目精确写**（营造落点用，保 `built_month` 等形态）。未下沉 ⇒ `None`。"""
    pdata = _routed(state, route)
    if pdata is None or not is_sunk(pdata):
        return None
    if isinstance(entry, dict):
        entry = dict(entry)
        if norm_level(entry) is None:
            return None
    elif norm_level(entry) is None:
        return None
    sid = seat_id or capital_seat_id(pdata, route)
    seat = _seat_of(pdata, sid) if sid else None
    if seat is None or not isinstance(seat.get(SEAT_KEY), dict):
        return None
    seat[SEAT_KEY][name] = entry
    _refresh(pdata)
    return entry


def building_level(state, route: str, name: str) -> Optional[int]:
    """读该建筑在路级 **Σ 镜像**中的等级；未下沉 / 无此建筑 ⇒ `None`（缺失≠0）。"""
    pdata = _routed(state, route)
    if pdata is None or not is_sunk(pdata):
        return None
    total = seat_buildings_total(pdata) or {}
    return int(total[name]) if name in total else None
