# -*- coding: utf-8 -*-
"""事件民心冲击档 · 结算前预取（2026-10-20，确定性触发）。

为什么需要：
- 结算链禁止同步 HTTP；而「饥荒/乏粮/内卫」的冲击档要在**结算内**被读到；
- 本模块在**结算前**（settle_local）按当前状态**预判可能发生的事件**，让内嵌 Jev 先判档、
  写进 state._<kind>_shock_tier；结算只读槽位。

纪律：
- 只在玩家动作路径调用（结算前一步），不进结算链；
- 失败一律吞掉（不得阻断结算）；
- 预判只是"可能发生"：档位只在对应事件真的触发时才被读取，判错不产生副作用。
"""
from __future__ import annotations

import logging

log = logging.getLogger("shock_prefetch")

__all__ = ["detect_kinds", "prefetch_shock_tiers"]

_GRANARY_LOW_RATIO = 0.15


def detect_kinds(state) -> list:
    """按当前状态预判本月可能触发的民心冲击类型（启发式，宁多不漏）。"""
    kinds = []
    try:
        granary = float(getattr(state, "granary", 0) or 0)
        cap = float(getattr(state, "granary_cap", 0) or 0)
        if cap > 0 and granary / cap < _GRANARY_LOW_RATIO:
            kinds.extend(["granary", "famine"])
        elif granary <= 0:
            kinds.extend(["granary", "famine"])
    except (TypeError, ValueError):
        pass
    try:
        focus = getattr(state, "focus", None)
        if isinstance(focus, dict) and str(focus.get("branch") or "") == "internal":
            kinds.append("focus")
    except Exception:  # noqa: BLE001
        pass
    seen, out = set(), []
    for k in kinds:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def prefetch_shock_tiers(state) -> dict:
    """对预判出的类型各调一次生产者；返回 {kind: tier}（失败项不出现）。"""
    kinds = detect_kinds(state)
    if not kinds:
        return {}
    out = {}
    try:
        from ai.client import AIClient

        client = AIClient()
    except Exception:  # noqa: BLE001
        log.warning("shock_prefetch 取 AIClient 失败（不阻断结算）", exc_info=True)
        return {}
    for kind in kinds:
        try:
            got = client.shock_decide(state, kind)
            if isinstance(got, dict) and got.get("tier"):
                out[kind] = got["tier"]
        except Exception:  # noqa: BLE001
            log.warning("shock_prefetch 判档失败（%s），跳过", kind, exc_info=True)
    return out
