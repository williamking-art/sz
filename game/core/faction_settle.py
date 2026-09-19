# -*- coding: utf-8 -*-
"""宋祚 · 利益集团月度派生结算（core/faction_settle.py）—— **state.factions 的唯一写入点**

依据：`_dev_tools/game-docs/analysis/faction_pop_optimization_plan_2026-09-19.md`
（「集团模型与派生」「政策传导顺序」「生命周期与历史门槛」）。本模块 = 方案第 3 步。

## 位置
排在 POP（Step 3~3.5）、制度（Step 3.95~3.97）、财政（Step 4~5）**之后**——
文档要求“满意度在 POP、财政、制度结算后计算”。

## 纪律（政策传导顺序）
- **禁止先改 faction 数值再假设 POP 受益**：本步只**读** POP 与现实变化，再写回三个读数；
- `influence` 每月**由 POP 派生**（人口/资源份额 + 制度/军事杆杆 + 凝聚力），逐月重算；
- `satisfaction`/`cohesion` 向**派生目标缓动**（月走缓动率），并消化 `_event_delta` 冲击
  （事件/诏令/AI 契约的即时效果记在这里，不再直写 satisfaction）；
- **不新增任何人口/钱粮账本**：本步不写 POP、不写国库。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from content.data import FACTION_POP_BASIS
from core.faction_basis import basis_routes, emerging_from_reforms
from core.faction_metrics import all_faction_power, faction_power, faction_slice
from core.faction_split import defect_toward_satisfaction
from core.numeric import clamp as _clamp, parse_number as _num

log = logging.getLogger("faction_settle")

__all__ = ["settle_factions_from_pop", "satisfaction_target", "cohesion_target",
           "SAT_NEUTRAL", "SAT_CONVERGE", "COH_CONVERGE"]

SAT_NEUTRAL = 50.0
SAT_CONVERGE = 0.25      # 满意度每月向派生目标走 25%
COH_CONVERGE = 0.20      # 凝聚力每月向派生目标走 20%

# 三期「转投」：满意度低的派系成员按小比例转向满意度高的派系（零和，Σ=1 不变）。
# 只改 `state.faction_split`（仍经 `core/faction_split.set_split` 唯一写入点），
# 不碰 POP size / 钱粮 —— 人仍在同一 POP 的 size 里。
DEFECT_RATE = 0.02       # 单月每派系最多迁出的占比（小比例：2%）
DEFECT_MIN_GAP = 2.0     # 满意度差 ≤ 此值不动（防噪声驱动无意义漂移）

# 满意度五项权重（文档定稿：和 = 1.00）
W_POLICY_FIT = 0.45
W_INCOME = 0.25
W_SECURITY = 0.15
W_REPRESENT = 0.10
W_EVENT = 0.05


def _policy_fit(state, spec: Any) -> float:
    """政策契合 [-1,1]：**在场改革**对该集团基本盘 POP 的净得失（只读）。"""
    classes = set((spec or {}).get("pop_classes") or [])
    pool = (spec or {}).get("pool")
    if not classes:
        return 0.0
    gain = lose = 0
    try:
        for item in emerging_from_reforms(state):
            for g in (item.get("gain") or []):
                if g.get("class") in classes and (not g.get("pool") or g.get("pool") == pool):
                    gain += 1
            for l in (item.get("lose") or []):
                if l.get("class") in classes and (not l.get("pool") or l.get("pool") == pool):
                    lose += 1
    except Exception as e:  # noqa: BLE001  只读推导失败不得中断结算
        log.warning("faction_settle 取在场改革失败：%s", e)
        return 0.0
    tot = gain + lose
    return (gain - lose) / tot if tot else 0.0


def _income_delta(state, name: str, spec: Any, f: Dict[str, Any]) -> float:
    """真实收入变化 [-1,1]：基本盘 POP 的**人均资源**环比变化。

    基线存在 `factions[name]["_last_per_capita"]`（本步内部审计字段，不是账本）。
    """
    sl = faction_slice(state, spec, name)
    per = (sl["resources"] / sl["population"]) if sl["population"] > 0 else None
    last = f.get("_last_per_capita")
    f["_last_per_capita"] = per
    if per is None or last is None:
        return 0.0
    last = _num(last, 0.0)
    if last <= 0:
        return 0.0
    return _clamp((per - last) / last * 4.0, -1.0, 1.0)


def _security_delta(state, spec: Any) -> float:
    """安全 [-1,1]：基本盘路域动乱越低越安全。"""
    prefs = getattr(state, "prefectures", None) or {}
    vals = []
    for r in basis_routes(spec):
        p = prefs.get(r)
        if isinstance(p, dict):
            vals.append(_num(p.get("unrest"), 0.0))
    if not vals:
        return 0.0
    return _clamp(1.0 - (sum(vals) / len(vals)) / 50.0, -1.0, 1.0)


def _representation(state, name: str, spec: Any, power: Dict[str, Any]) -> float:
    """代表性 [0,1]：该集团在**制度（officials）或军队**中的占比（非官僚/非兵 → 0）。"""
    return _clamp(max(_num(power.get("institutional_access"), 0.0),
                      _num(power.get("military_leverage"), 0.0)), 0.0, 1.0)


def satisfaction_target(state, name: str, spec: Any, f: Dict[str, Any],
                        power: Optional[Dict[str, Any]] = None) -> float:
    """派生满意度目标（0–100）：文档五项加权后映射到 50 中性。"""
    power = power if power is not None else faction_power(state, name, spec)
    ev = _clamp(_num(f.get("_event_delta"), 0.0) / 12.0, -1.0, 1.0)
    d = (W_POLICY_FIT * _policy_fit(state, spec)
         + W_INCOME * _income_delta(state, name, spec, f)
         + W_SECURITY * _security_delta(state, spec)
         + W_REPRESENT * (2.0 * _representation(state, name, spec, power) - 1.0)
         + W_EVENT * ev)
    return _clamp(SAT_NEUTRAL + d * 50.0, 0.0, 100.0)


def cohesion_target(state, name: str, spec: Any, f: Dict[str, Any]) -> float:
    """疑聚力目标（0–100）：共同地域（路程集中）与领袖合法性提高，全国分散降低。"""
    n = len(basis_routes(spec))
    spread = 1.0 if n <= 3 else (0.5 if n <= 8 else 0.2)
    leader = 1.0 if f.get("leader") else 0.0
    return _clamp(40.0 + 30.0 * spread + 20.0 * leader, 0.0, 100.0)


def settle_factions_from_pop(state, log_: Optional[list] = None) -> Dict[str, Any]:
    """月度派生结算（**state.factions 唯一写入点**）。

    顺序：① influence 直接由 POP 派生（逐月重算，不再随机）；
    ② satisfaction / ③ cohesion 向派生目标缓动，并消化 `_event_delta`；
    ④ 转投（三期）：低满意度派系成员零和转向高满意度派系（只写 faction_split）。
    返回 `{name: {...}}` 供日志/面板。
    """
    logs = log_ if isinstance(log_, list) else []
    out: Dict[str, Any] = {}
    facs = getattr(state, "factions", None)
    if not isinstance(facs, dict) or not facs:
        return out
    powers = all_faction_power(state)
    for name, f in facs.items():
        if not isinstance(f, dict):
            continue
        spec = FACTION_POP_BASIS.get(name)
        if spec is None:
            continue
        power = powers.get(name) or faction_power(state, name, spec)

        # ① 影响力：POP 派生（权威，直接覆盖）
        old_inf = _num(f.get("influence"), 0.0)
        f["influence"] = power["influence"]

        # ② 满意度：向派生目标缓动 + 事件冲击
        tgt_sat = satisfaction_target(state, name, spec, f, power)
        cur_sat = _num(f.get("satisfaction"), tgt_sat)
        shock = _clamp(_num(f.pop("_event_delta", 0.0), 0.0), -12.0, 12.0)
        f["satisfaction"] = round(_clamp(
            cur_sat + (tgt_sat - cur_sat) * SAT_CONVERGE + shock, 0.0, 100.0), 2)

        # ③ 凝聚力：向派生目标缓动
        tgt_coh = cohesion_target(state, name, spec, f)
        cur_coh = _num(f.get("cohesion"), tgt_coh)
        f["cohesion"] = round(_clamp(
            cur_coh + (tgt_coh - cur_coh) * COH_CONVERGE, 0.0, 100.0), 2)

        out[name] = {"influence": f["influence"], "satisfaction": f["satisfaction"],
                     "cohesion": f["cohesion"], "influence_was": old_inf,
                     "satisfaction_target": round(tgt_sat, 2), "cohesion_target": tgt_coh}
    if logs and out:
        logs.append(
            "[朝堂] 集团指标由 POP 重算："
            + "、".join(f"{n}影{u['influence']:.0f}/满{u['satisfaction']:.0f}"
                          for n, u in list(out.items())[:3]) + "…")

    # ④ 转投（三期）：用**本步刚缓动后的** satisfaction 驱动，低满意派系成员
    #    零和转向高满意派系；只写 faction_split（经 set_split），Σ=1 不变。
    #    事件侧「贬谪/处死」经既有 faction_change 通道压低满意度 → 在此转为成员退出。
    try:
        moved = defect_toward_satisfaction(
            state, {n: _num((f or {}).get("satisfaction"), SAT_NEUTRAL)
                    for n, f in facs.items()},
            rate=DEFECT_RATE, min_gap=DEFECT_MIN_GAP)
    except Exception as e:  # noqa: BLE001  转投失败不得中断派生结算
        log.warning("faction_settle 转投失败：%s", e)
        moved = {}
    if moved and logs:
        logs.append("[朝堂] 转投："
                    + "、".join(f"{c}(迁{round(v['moved'], 4)})" for c, v in moved.items()))
    return out