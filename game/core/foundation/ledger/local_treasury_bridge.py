# -*- coding: utf-8 -*-
"""**地方府库**（`local_treasury`）州府级真账桥接 —— 主线 B「地方府库下沉」第一片。

🔴 **先分清两个不同的东西**（这里踩过，故写在最前）：
  * `state.treasury` / `money.ACCOUNTS["treasury"]` = **中央国库**（`imperial_treasury` 是内帑）；
  * `prefectures[路]["local_treasury"]` = **地方府库**（账户 id `local:<路>`）—— **本模块只管它**。
  两者靠 `state.transfer_money(f"local:{路}", "treasury", amt)` 等成对划转，**不得混用载体**。

口径（与 POP 下沉同型，见 AGENTS.md §3-1 与
`_dev_tools/game-docs/specs/economy/地方府库下沉州府级_阻塞记录.md` §五）
--------------------------------------------------------------------------
* **真账**：`prefectures[路]["seats"][治所]["local_treasury"]`（标量，与 `"pops"` 平级）。
* **派生镜像**：路级 `prefectures[路]["local_treasury"]` 恒等于 Σ 治所；**直写路级 = 写丢失**。
* **写点必须走桥**：`local_treasury_set / local_treasury_add(..., state)`；**未下沉 ⇒ `None`**，
  调用方保持原写法回落（惯例 `if local_treasury_add(...) is None: <原写法>`）。
* **缺失 ≠ 0**：无 `seats` / 未下沉 ⇒ 聚合返回 `None`（界面"未定义"），**不回落 0**。
* **不新增平行账户**：只搬运既有 `local_treasury`；不新建账户体系（账户 id 扩展
  `local:<路>:<治所>` 属阻塞记录 §五-3，另批）。
* **不臆造归属**：治所权重取 `pop_bridge.seat_pop_weights`（按治所人口）；返回 `[]`
  ⇒ **该路整体跳过**（宁可不拆，也不编造府库归属）。

分摊依据属**推演**（按治所人口加权），非史料。Jev 裁定（2026-10-13）：
制度上更优的是「按行政等级/编制」，但当前以人口权数落地（P=0.988），等级版留作**目标**
—— 届时只需 `set_weights_provider(...)`，本模块其余逻辑不动。

守恒：`split_int` 保证 **Σ 治所 精确等于**路级原值（尾差归权重最大者）。
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

#: 治所真账里承载**地方府库**的键名（与 `"pops"` 平级；**不是**中央 `treasury`）
SEAT_KEY = "local_treasury"

__all__ = [
    "SEAT_KEY", "aggregate_seat_local_treasury", "survey_local_treasury",
    "is_sunk", "sink_route_local_treasury", "sink_local_treasury_to_seats",
    "local_treasury_set", "local_treasury_add", "seat_local_treasury_total",
    "seat_local_treasury_get", "seat_local_treasury_set", "seat_local_treasury_writable",
    "set_weights_provider",
]


# --------------------------------------------------------------------------
# 读侧
# --------------------------------------------------------------------------
def _seats_map(pdata) -> Dict[str, dict]:
    """路级 `seats` 映射（非 dict 一律当空）。"""
    if not isinstance(pdata, dict):
        return {}
    seats = pdata.get("seats")
    return seats if isinstance(seats, dict) else {}


def is_sunk(pdata) -> bool:
    """该路是否已下沉：**每个治所都有 `local_treasury` 键**才算。

    部分缺失视为未下沉（可重沉修复）；无 `seats` ⇒ False。
    """
    seats = _seats_map(pdata)
    if not seats:
        return False
    return all(isinstance(s, dict) and SEAT_KEY in s for s in seats.values())


def seat_local_treasury_total(pdata) -> Optional[float]:
    """Σ 治所真账。**无 `seats` 或一个数值都没有 ⇒ `None`**（缺失≠0）。"""
    seats = _seats_map(pdata)
    if not seats:
        return None
    vals = [float(s[SEAT_KEY]) for s in seats.values()
            if isinstance(s, dict) and isinstance(s.get(SEAT_KEY), (int, float))
            and not isinstance(s.get(SEAT_KEY), bool)]
    if not vals:
        return None
    return float(sum(vals))


def aggregate_seat_local_treasury(pdata) -> Optional[float]:
    """**派生聚合**：Σ 治所 ⇒ 路级镜像。未下沉 ⇒ `None`（不回落 0）。"""
    if not is_sunk(pdata):
        return None
    return seat_local_treasury_total(pdata)


def survey_local_treasury(state) -> dict:
    """**迁移对账**：逐路比对「路级 local_treasury」与「Σ 治所」，返回失配清单。"""
    prefs = getattr(state, "prefectures", {}) or {}
    out = {"路由数": len(prefs), "已下沉路由": 0, "未下沉路由": 0, "字段失配": []}
    for route, pdata in prefs.items():
        if not isinstance(pdata, dict):
            continue
        if not is_sunk(pdata):
            out["未下沉路由"] += 1
            continue
        out["已下沉路由"] += 1
        total = seat_local_treasury_total(pdata)
        mirror = pdata.get(SEAT_KEY)
        if not isinstance(mirror, (int, float)) or isinstance(mirror, bool):
            out["字段失配"].append({"路": route, "路级": mirror, "Σ治所": total,
                                    "原因": "路级 local_treasury 缺失或非数值（镜像未刷新）"})
        elif float(mirror) != float(total):
            out["字段失配"].append({"路": route, "路级": float(mirror), "Σ治所": float(total),
                                    "原因": "路级 != Σ治所"})
    return out


# --------------------------------------------------------------------------
# 权重
# --------------------------------------------------------------------------
def _default_weights(route: str) -> List[tuple]:
    """默认分摊依据：`pop_bridge.seat_pop_weights`（按治所 `demog.population` 加权）。

    取模块属性（而非直接 import 名字），便于测试打桩。
    """
    try:
        from core.foundation.ledger import pop_bridge
        return list(pop_bridge.seat_pop_weights(route) or [])
    except Exception:                                   # noqa: BLE001
        log.warning("local_treasury_bridge: 取治所权重失败 route=%s", route, exc_info=True)
        return []


#: 可替换的分摊依据。**Jev 裁定（2026-10-13）**：制度上更优的是「按行政等级/编制」，
#: 但当前应以人口权数落地（P=0.988）、并把等级版留作**目标**。
_WEIGHTS_PROVIDER = None


def set_weights_provider(fn) -> None:
    """替换分摊依据（主线 B 后续切「按行政等级/编制」版时用；`None` 恢复默认）。"""
    global _WEIGHTS_PROVIDER
    _WEIGHTS_PROVIDER = fn


def _weights(route: str) -> List[tuple]:
    """治所权重。返回 `[]` ⇒ 调用方**不做拆分**（不臆造归属）。"""
    fn = _WEIGHTS_PROVIDER or _default_weights
    return list(fn(route) or [])


# --------------------------------------------------------------------------
# 写侧
# --------------------------------------------------------------------------
def _distribute(pdata, weights: List[tuple], total: float) -> Dict[str, float]:
    """把 `total` 按权重拆到治所，返回 `{sid: 值}`（含权重未覆盖的治所 = 0）。

    用 `pop_bridge.split_int` 的守恒语义（Σ 精确等于 total）；整数部分走 split_int，
    余数给权重最大者，保证 Σ治所 精确等于原值。
    """
    from core.foundation.ledger.pop_bridge import split_int
    seats = _seats_map(pdata)
    t_int = int(total)
    alloc = split_int(t_int, weights)
    frac = float(total) - t_int
    if frac and weights:
        top = max(weights, key=lambda kv: kv[1])[0]
        alloc[top] = alloc.get(top, 0) + frac
    for sid in seats:
        alloc.setdefault(str(sid), 0)
    return {str(k): float(v) for k, v in alloc.items()}


def sink_route_local_treasury(pdata, route: str, value=None) -> bool:
    """把某路 `local_treasury` 真账落到治所并刷新路级镜像。

    **已下沉 ⇒ 不覆盖，返回 False**（沿用 POP 同型纪律）；权重不可得 ⇒ 跳过。
    """
    if not isinstance(pdata, dict):
        return False
    if is_sunk(pdata):
        return False
    weights = _weights(route)
    if not weights:
        log.info("local_treasury_bridge: route=%s 无治所权重 → 跳过（不臆造归属）", route)
        return False
    total = pdata.get(SEAT_KEY) if value is None else value
    if not isinstance(total, (int, float)) or isinstance(total, bool):
        return False
    alloc = _distribute(pdata, weights, float(total))
    seats = _seats_map(pdata)
    for sid, s in seats.items():
        if isinstance(s, dict):
            s[SEAT_KEY] = alloc.get(str(sid), 0.0)
    pdata[SEAT_KEY] = float(sum(alloc.get(str(sid), 0.0) for sid in seats))
    return True


def sink_local_treasury_to_seats(state, routes=None) -> int:
    """**无条件幂等入口**：新局与读档共用（与 `sink_pops_to_seats` 同型）。

    ⚠️ 必须在 `sink_pops_to_seats` **之后**调用——分摊权重取自治所人口。
    返回实际下沉的路数；权重不可得或无 `local_treasury` 数值的路跳过。
    """
    prefs = getattr(state, "prefectures", {}) or {}
    names = list(routes) if routes else list(prefs)
    n = 0
    for route in names:
        pdata = prefs.get(route)
        try:
            if sink_route_local_treasury(pdata, route):
                n += 1
        except Exception:                               # noqa: BLE001
            log.warning("local_treasury_bridge: 下沉失败 route=%s（跳过，不影响其他路）",
                        route, exc_info=True)
    return n


def _locate(state, route: str):
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return None
    pdata = prefs.get(route)
    return pdata if isinstance(pdata, dict) else None


def local_treasury_set(state, route: str, value) -> Optional[float]:
    """**写**真账为 `value`（按权重重分摊）。**未下沉 ⇒ `None`**（调用方回落原写法）。"""
    pdata = _locate(state, route)
    if pdata is None or not is_sunk(pdata):
        return None
    weights = _weights(route)
    if not weights:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool) or float(value) < 0:
        return None
    alloc = _distribute(pdata, weights, float(value))
    for sid, s in _seats_map(pdata).items():
        if isinstance(s, dict):
            s[SEAT_KEY] = alloc.get(str(sid), 0.0)
    pdata[SEAT_KEY] = float(sum(alloc.get(str(sid), 0.0) for sid in _seats_map(pdata)))
    return pdata[SEAT_KEY]


def local_treasury_add(state, route: str, delta) -> Optional[float]:
    """**写**真账增量。**未下沉 ⇒ `None`**。下限 0（地方府库不可为负），夹紧时留痕。"""
    if not isinstance(delta, (int, float)) or isinstance(delta, bool):
        return None
    pdata = _locate(state, route)
    if pdata is None or not is_sunk(pdata):
        return None
    cur = seat_local_treasury_total(pdata)
    if cur is None:
        return None
    new = float(cur) + float(delta)
    if new < 0:
        log.warning("local_treasury_bridge: route=%s 触零夹紧（cur=%s delta=%s）",
                    route, cur, delta)
        new = 0.0
    return local_treasury_set(state, route, new)


def _seat_of(pdata, seat_id: str):
    """取某治所 dict；不存在 ⇒ None。"""
    seat = _seats_map(pdata).get(str(seat_id))
    return seat if isinstance(seat, dict) else None


def seat_local_treasury_get(state, route: str, seat_id: str) -> Optional[float]:
    """读**某一个治所**的真账。未下沉 / 治所不存在 / 非数值 ⇒ `None`（缺失≠0）。"""
    pdata = _locate(state, route)
    if pdata is None or not is_sunk(pdata):
        return None
    seat = _seat_of(pdata, seat_id)
    if seat is None:
        return None
    v = seat.get(SEAT_KEY)
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return None
    return float(v)


def seat_local_treasury_set(state, route: str, seat_id: str, value) -> Optional[float]:
    """**精确**写某一个治所的真账，并刷新路级 Σ 镜像；返回新的**路级镜像**值。

    与 `local_treasury_set`（按权重重分摊整路）不同：本函数**只动一个治所**、不重新分摊
    —— 这是账户 id `local:<路>:<治所>`（阻塞记录 §五-3）的写入口。

    **未下沉 / 该治所不存在 / 值为负或非数 ⇒ `None`**（调用方据此拒绝划转，见
    `game_state._writable` 的同名判据——目标不可写时不动 src，避免"钱被销毁仍记已入库"）。
    """
    pdata = _locate(state, route)
    if pdata is None or not is_sunk(pdata):
        return None
    seat = _seat_of(pdata, seat_id)
    if seat is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool) or float(value) < 0:
        return None
    seat[SEAT_KEY] = float(value)
    seats = _seats_map(pdata)
    pdata[SEAT_KEY] = float(sum(float(s.get(SEAT_KEY) or 0) for s in seats.values()
                                if isinstance(s, dict)
                                and isinstance(s.get(SEAT_KEY), (int, float))
                                and not isinstance(s.get(SEAT_KEY), bool)))
    return pdata[SEAT_KEY]


def seat_local_treasury_writable(state, route: str, seat_id: str) -> bool:
    """治所级账户是否**可写**：已下沉 且 该治所存在。否则一律 False（Jev 裁定 P=0.999）。"""
    pdata = _locate(state, route)
    if pdata is None or not is_sunk(pdata):
        return False
    return _seat_of(pdata, seat_id) is not None
