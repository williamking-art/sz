# -*- coding: utf-8 -*-
"""天道裁决 → 数值效果的**共享读取点**（接线批，2026-10-21）。

为什么单独一个模块
------------------
月度结算里已有 5 个消费方各写一份「读 `state._tiandao_observe` 的裁决」的小函数
（`_tax_stance_factor` / `_granary_corruption_factor` / `_reform_compliance_factor` /
`_changping_sell_allowed` / `_arrears_waiver_active`）。本批要再接 5 个门面（商贾 / 士绅 /
小农 / 漕运 / 募流民），若每处再抄一份读取逻辑，就会撞上「跨文件相同实现」守卫
（`test_duplicate_impl_guard`）。故把**读取与缺失语义**收敛到这里，各消费方只做自己的
「档位 → 数值」映射。

契约
----
1. **只读**：本模块不写 state、不碰账本。
2. **缺失 ⇒ None**：无 `_tiandao_observe` / 无该门面 / 该门面是 error / 值不在白名单
   一律返回 `None`，由调用方按**中性**处理（乘子 1.0 / 不动作）。**不猜、不回落默认档位。**
3. **裁决来源**：`TianDaoFacade.observe_monthly` 每月初（`settlement.run_monthly_settlement`
   Step 0 之前）写入的只读副本 `state._tiandao_observe["decisions"]`。
4. **结算期禁止再调 Jev/引擎**：消费方只读这份副本，不得在结算步骤里重新裁决。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = ["observe_verdict", "observe_bool", "observed_names",
           "observe_strength", "observe_mix", "gate_intensity", "jitter",
           "objective_threshold",
           "FLEE_VERDICT_MULT", "FLEE_JITTER", "MERCHANT_TILT_BOUNDS"]

#: 观测副本的顶层键（`TianDaoFacade.observe_monthly` 写入）
RECORD_ATTR = "_tiandao_observe"
DECISIONS_KEY = "decisions"

#: 「破产小农举家逃亡」档对饥荒逃散人数的放大倍数。
#: **单一出处**：宋侧（`settlement_granary` 口粮不足→农逃荒）与外邦侧
#: （`settlement_econ._ext_econ_phases`）必须用同一个值——同名不同义会让
#: 同一裁决在两处给出不同后果。口径：1.5 倍于「实际吃不上饭的人数」，
#: 仍受 `FLEE_CAP_PER_ROUTE` 与农 POP size 双重约束（不造人）。
FLEE_VERDICT_MULT = 1.5

#: 饥荒逃散的「天意机变」扰子幅度——**单一出处**：宋侧（`settlement_granary`）
#: 与外邦侧（`settlement_econ._ext_econ_phases`）必须一致，否则同一裁决在两侧
#: 幅度不同（审查 D3/遗留 #5：外邦侧曾误用 `MERCHANT_JITTER`）。
FLEE_JITTER = 0.10

#: 商贾档对士绅囤抛力度的乘子钳位（下界, 上界）。防极端乘子把单月囤抛量放大到失真。
MERCHANT_TILT_BOUNDS = (0.85, 1.25)


def _record(state: Any) -> Dict[str, Any]:
    rec = getattr(state, RECORD_ATTR, None)
    return rec if isinstance(rec, dict) else {}


def observed_names(state: Any) -> tuple:
    """本月已记录的门面名（诊断/测试用；缺失 ⇒ 空元组）。"""
    dec = _record(state).get(DECISIONS_KEY)
    return tuple(sorted(dec)) if isinstance(dec, dict) else ()


def _name_keys(name: str) -> tuple:
    """把「门面方法名」与「objective id」互相当作别名。

    🔴 为什么要这层：观测副本里 `decisions` 按**门面方法名**存（`farmer_destitution_path`），
    而 `strengths` / `distributions` 按 **objective id** 存（`farmer_path`）。
    消费方若只按其中一种写法去读，就会**静默读空、效果永不生效**
    （实测过：`observe_strength("recruit_refugees_to_soldiers_gate")` 返回 None，
    因为记录里叫 `recruit_refugees`；结果全月零募兵）。这里统一解析，读两侧都行。
    """
    keys = [str(name)]
    try:
        from core.ai.tiandao_facade import TianDaoFacade as _F
        m2o = getattr(_F, "OBSERVE_OBJECTIVES", {}) or {}
        o2m = {v: k for k, v in m2o.items()}
        for cand in (m2o.get(name), o2m.get(name)):
            if cand and cand not in keys:
                keys.append(cand)
    except Exception:  # noqa: BLE001 —— 解析失败只影响别名，不影响主键
        pass
    return tuple(keys)


def observe_verdict(state: Any, name: str, allowed: tuple) -> Optional[str]:
    """读一个**列举型**门面裁决；不合法/缺失一律 `None`。

    `allowed` 必传：它同时是白名单与文档（避免"改一个选项名就静默改判定"，
    同 `tiandao_engine` 显式 objective 的初衷）。
    """
    if not isinstance(allowed, tuple) or not allowed:
        raise ValueError("observe_verdict: allowed 必须是非空元组")
    dec = _record(state).get(DECISIONS_KEY)
    if not isinstance(dec, dict):
        return None
    raw = None
    for _k in _name_keys(name):
        if _k in dec:
            raw = dec[_k]
            break
    if isinstance(raw, dict):          # 门面记录成 {error: ...} 之类的错误结构
        return None
    if isinstance(raw, bool) or not isinstance(raw, str):
        return None
    return raw if raw in allowed else None


def observe_bool(state: Any, name: str) -> Optional[bool]:
    """读一个**是非型**门面裁决；缺失/非 bool 一律 `None`（不把缺失当 False）。"""
    dec = _record(state).get(DECISIONS_KEY)
    if not isinstance(dec, dict):
        return None
    for _k in _name_keys(name):
        if _k in dec:
            raw = dec[_k]
            return raw if isinstance(raw, bool) else None
    return None


# ---------------------------------------------------------------------------
# 强度（概率）—— 天道的「不定数」在这里，不在固定倍率表里
# ---------------------------------------------------------------------------
DIST_KEY = "distributions"
STRENGTH_KEY = "strengths"


def objective_threshold(objective: str) -> float:
    """某 gate objective 的判定阈值——**唯一出处** = `tiandao_decision.THRESHOLDS`。

    🔴 为什么要有这层（审查 D-1 / E4）：阈值曾有三处来源——`decision_log`/`strengths`
    走 `THRESHOLDS`、门面 gate 方法让引擎用默认 0.50、消费方 `observe_strength` 又硬编码
    0.5。三者当前都等于 0.50 所以看不出问题，**一旦有人按注释改 `THRESHOLDS`，日志记的
    裁决与实际结算行为就会分叉**（回测校准的是"没发生的判定"）。
    现统一从这里取；表里没有的仍回引擎默认 0.50。
    """
    try:
        from core.ai.tiandao_decision import THRESHOLDS
        return float(THRESHOLDS.get(objective, 0.5))
    except Exception:  # noqa: BLE001 —— 常量导入失败不得阻断结算
        return 0.5


def gate_intensity(probability: Optional[float], threshold: float = 0.5) -> Optional[float]:
    """门闸的**超阈强度** ∈ [0, 1]：刚过线 ≈ 0，逼近 1 时 → 1。

    为什么不用 `p` 本身：`p=0.51` 只是"刚过判定线"，若直接拿 0.51 当强度，
    效果会永远≥半个满额，档位与幅度脱钩。用「超出阈值的那部分」归一化，
    才能让 0.51 与 0.95 **在幅度上真的不同**。
    """
    if probability is None:
        return None
    try:
        p = float(probability)
    except (TypeError, ValueError):
        return None
    if p != p:                      # NaN
        return None
    if p < float(threshold):
        return 0.0
    span = 1.0 - float(threshold)
    if span <= 0:
        return 0.0
    return min(1.0, (p - float(threshold)) / span)


def observe_strength(state: Any, objective: str,
                     threshold: float = 0.5) -> Optional[float]:
    """读一个 **gate** 的裁决强度（超阈归一）；缺失 ⇒ `None`（调用方按中性处理）。"""
    raw = _record(state).get(STRENGTH_KEY)
    if not isinstance(raw, dict):
        return None
    for _k in _name_keys(objective):
        if _k in raw:
            return gate_intensity(raw[_k], threshold)
    return None


def observe_mix(state: Any, objective: str,
                allowed: tuple) -> Optional[Dict[str, float]]:
    """读一个 **choose** 的概率分布（只保留 `allowed`，余额归零不重分）。

    * 缺失/非 dict ⇒ `None`；
    * 只输出白名单内的键，且**不把缺失选项补 0 当成"确定不选"**——调用方应把它
      当作"未观测到该选项"，因此返回的 dict 只含**实际出现**的选项；
    * 各值钳到 [0,1]。
    """
    if not isinstance(allowed, tuple) or not allowed:
        raise ValueError("observe_mix: allowed 必须是非空元组")
    raw = _record(state).get(DIST_KEY)
    if not isinstance(raw, dict):
        return None
    dist = None
    for _k in _name_keys(objective):
        if _k in raw:
            dist = raw[_k]
            break
    if not isinstance(dist, dict):
        return None
    out: Dict[str, float] = {}
    for k, v in dist.items():
        if k not in allowed:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f == f:
            out[str(k)] = max(0.0, min(1.0, f))
    return out or None


def jitter(state: Any, objective: str, route: Any, entropy: float = 0.12) -> float:
    """**天意机变**：由 (回合, 裁决目标, 地点) 派生的确定性扰动乘子 ∈ [1−e, 1+e]。

    这是"同一档位在不同地方/不同月份幅度不同"的来源，且**完全可回放**：
    同种子同结果（`TianDaoEngine.dice` 的 splitmix64），不引入真随机、不破确定性回放。
    `entropy<=0` ⇒ 返回 1.0（零扰动）。
    """
    try:
        e = float(entropy)
    except (TypeError, ValueError):
        return 1.0
    if e <= 0.0:
        return 1.0
    import zlib

    from core.ai.tiandao_engine import TianDaoEngine

    turn = int(getattr(state, "turn", 0) or 0)
    seed = ((turn * 1_000_003)
            ^ (zlib.crc32(str(objective).encode("utf-8")) * 1009)
            ^ (zlib.crc32(str(route).encode("utf-8")) * 31))
    return 1.0 + TianDaoEngine.dice(seed, 1.0) * min(1.0, e)

