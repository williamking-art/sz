# -*- coding: utf-8 -*-
"""地方府库（treasury）州府级真账桥接 —— 主线 B「地方府库下沉」第一片。

口径（与 POP 下沉同型，见 AGENTS.md §3-1）
------------------------------------------
* **真账**：`prefectures[路]["seats"][治所]["treasury"]`（标量，与 `"pops"` 平级）。
* **派生镜像**：路级 `prefectures[路]["treasury"]` 恒等于 Σ 治所；**直写路级 = 写丢失**。
* **写点必须走桥**：`treasury_set / treasury_add(..., state)`；**未下沉 ⇒ 返回 `None`**，
  调用方保持原写法回落（惯例 `if treasury_add(...) is None: <原写法>`）。
* **缺失 ≠ 0**：无 `seats` / 未下沉 ⇒ 聚合返回 `None`（界面"未定义"），**不回落 0**。
* **不新增平行账户**：本模块只搬运既有 `treasury`；`imperial_treasury`（中央内帑）不在此范围。
* **不臆造归属**：治所权重取 `pop_bridge.seat_pop_weights`（按治所人口）；它返回 `[]`
  ⇒ **该路整体跳过**（宁可不拆，也不编造府库归属）。

分摊依据属**推演**（按治所人口加权），非史料；登记见
`_dev_tools/handover/decisions/local-treasury-share-basis.json`。

守恒：`split_int` 保证 **Σ 治所 精确等于**路级原值（尾差归权重最大者）。
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

#: 治所真账里承载地方府库的键名（与 `"pops"` 平级）
SEAT_KEY = "treasury"

__all__ = [
    "SEAT_KEY", "aggregate_seat_treasury", "survey_treasury",
    "is_sunk", "sink_route_treasury", "sink_treasury_to_seats",
    "treasury_set", "treasury_add", "seat_treasury_total",
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
    """该路是否已下沉：**每个治所都有 `treasury` 键**才算（部分缺失视为未下沉，可重沉修复）。"""
    seats = _seats_map(pdata)
    if not seats:
        return False
    return all(isinstance(s, dict) and SEAT_KEY in s for s in seats.values())


def seat_treasury_total(pdata) -> Optional[float]:
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


def aggregate_seat_treasury(pdata) -> Optional[float]:
    """**派生聚合**：Σ 治所 ⇒ 路级镜像。未下沉 ⇒ `None`（不回落 0）。"""
    if not is_sunk(pdata):
        return None
    return seat_treasury_total(pdata)


def survey_treasury(state) -> dict:
    """**迁移对账**：逐路比对「路级 treasury」与「Σ 治所」，返回失配清单。"""
    prefs = getattr(state, "prefectures", {}) or {}
    out = {"路由数": len(prefs), "已下沉路由": 0, "未下沉路由": 0, "字段失配": []}
    for route, pdata in prefs.items():
        if not isinstance(pdata, dict):
            continue
        if not is_sunk(pdata):
            out["未下沉路由"] += 1
            continue
        out["已下沉路由"] += 1
        total = seat_treasury_total(pdata)
        mirror = pdata.get(SEAT_KEY)
        if not isinstance(mirror, (int, float)) or isinstance(mirror, bool):
            out["字段失配"].append({"路": route, "路级": mirror, "Σ治所": total,
                                    "原因": "路级 treasury 缺失或非数值（镜像未刷新）"})
        elif float(mirror) != float(total):
            out["字段失配"].append({"路": route, "路级": float(mirror), "Σ治所": float(total),
                                    "原因": "路级 != Σ治所"})
    return out


# --------------------------------------------------------------------------
# 权重
# --------------------------------------------------------------------------
def _default_weights(route: str) -> List[tuple]:
    """默认分摊依据：`pop_bridge.seat_pop_weights`（按治所 `demog.population` 加权）。

    取模块属性（`pop_bridge.seat_pop_weights`）而非直接 import 名字，便于测试打桩。
    """
    try:
        from core.foundation.ledger import pop_bridge
        return list(pop_bridge.seat_pop_weights(route) or [])
    except Exception:                                   # noqa: BLE001
        log.warning("treasury_bridge: 取治所权重失败 route=%s", route, exc_info=True)
        return []


#: 可替换的分摊依据。**Jev 裁定（2026-10-13）**：制度上更优的是「按行政等级/编制」，
#: 但当前应以人口权数落地（P=0.988）、并把等级版留作**目标**——
#: 届时只需 `set_weights_provider(按等级的实现)`，本模块其余逻辑不动。
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
    """把 `total` 按权重拆到治所，返回 `{sid: 值}`（含权重为 0 的治所 = 0）。

    用 `pop_bridge.split_int` 的守恒语义（Σ 精确等于 total），但 treasury 是**贯/两的标量**，
    故先按整数拆分再补回小数：整数部分走 split_int，余数给权重最大者。
    """
    from core.foundation.ledger.pop_bridge import split_int
    seats = _seats_map(pdata)
    t_int = int(total)
    alloc = split_int(t_int, weights)
    frac = float(total) - t_int
    if frac and weights:
        top = max(weights, key=lambda kv: kv[1])[0]
        alloc[top] = alloc.get(top, 0) + frac
    # 权重未覆盖的治所（人口缺）记 0，保证 Σ治所 覆盖全部 seats
    for sid in seats:
        alloc.setdefault(str(sid), 0)
    return {str(k): float(v) for k, v in alloc.items()}


def sink_route_treasury(pdata, route: str, value=None) -> bool:
    """把某路 treasury 真账落到治所，并刷新路级镜像。**已下沉 ⇒ 不覆盖，返回 False**。"""
    if not isinstance(pdata, dict):
        return False
    if is_sunk(pdata):
        return False                                    # 已下沉：绝不覆盖（沿用 POP 同型纪律）
    weights = _weights(route)
    if not weights:
        log.info("treasury_bridge: route=%s 无治所权重 → 跳过（不臆造归属）", route)
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


def sink_treasury_to_seats(state, routes=None) -> int:
    """**无条件幂等入口**：新局与读档共用（与 `sink_pops_to_seats` 同型）。

    ⚠️ 必须在 `sink_pops_to_seats` **之后**调用——分摊权重取自治所人口。
    返回实际下沉的路数。权重不可得的路跳过。
    """
    prefs = getattr(state, "prefectures", {}) or {}
    names = list(routes) if routes else list(prefs)
    n = 0
    for route in names:
        pdata = prefs.get(route)
        try:
            if sink_route_treasury(pdata, route):
                n += 1
        except Exception:                               # noqa: BLE001
            log.warning("treasury_bridge: 下沉失败 route=%s（跳过，不影响其他路）", route,
                        exc_info=True)
    return n


def _locate(state, route: str):
    prefs = getattr(state, "prefectures", None)
    if not isinstance(prefs, dict):
        return None
    pdata = prefs.get(route)
    return pdata if isinstance(pdata, dict) else None


def treasury_set(state, route: str, value) -> Optional[float]:
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


def treasury_add(state, route: str, delta) -> Optional[float]:
    """**写**真账增量。**未下沉 ⇒ `None`**。下限 0（field_registry 里 treasury 是 `non_neg`），
    夹紧时留痕（不静默）。"""
    if not isinstance(delta, (int, float)) or isinstance(delta, bool):
        return None
    pdata = _locate(state, route)
    if pdata is None or not is_sunk(pdata):
        return None
    cur = seat_treasury_total(pdata)
    if cur is None:
        return None
    new = float(cur) + float(delta)
    if new < 0:
        log.warning("treasury_bridge: route=%s treasury 触零夹紧（cur=%s delta=%s）",
                    route, cur, delta)
        new = 0.0
    return treasury_set(state, route, new)
