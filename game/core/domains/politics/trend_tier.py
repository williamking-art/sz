# -*- coding: utf-8 -*-
"""趋势档位（2026-10-20，天道档位化 batch2）。

用户要求：「能用天道裁决的就用天道裁决，混沌和随机性更能模拟现实」；
边界（Jev A 0.644）：**情境强度类**交天道，统计噪声与税率保留确定性。

本模块覆盖军事/局势三类：
1. 外邦国势 `resolve_power_trend`：剧衰/渐衰/持平/渐涨/剧涨 → 月度国力漂移（程序换算）；
2. 外交态度 `resolve_attitude_shock`：骤恶/渐恶/持平/渐善/骤善 → 态度跳变幅度；
3. 事件压力 `resolve_pressure_level`：平缓/升温/激化 → 压力增幅倍率。

**零行为变更**：天道缺档时返回 `None`，调用方沿用原有随机幅度（不改既有平衡）。

天道槽：
    state._trend_ai = {
        "power": {"金": "剧涨", "辽": "渐衰"},
        "attitude": {"西夏": "渐恶"},
        "pressure": {"方腊起义": "激化"},
    }
也可注册 provider：register_trend_provider(fn)，fn(state) -> dict（同上结构）。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

__all__ = ["POWER_TREND_LEVELS", "ATTITUDE_SHOCK_LEVELS", "PRESSURE_LEVELS",
           "POWER_DELTA", "ATTITUDE_DELTA", "PRESSURE_MULT",
           "resolve_power_trend", "resolve_attitude_shock", "resolve_pressure_level",
           "register_trend_provider"]

POWER_TREND_LEVELS = ("剧衰", "渐衰", "持平", "渐涨", "剧涨")
ATTITUDE_SHOCK_LEVELS = ("骤恶", "渐恶", "持平", "渐善", "骤善")
PRESSURE_LEVELS = ("平缓", "升温", "激化")

#: 档位 → 月度国力漂移（百分点/月）
POWER_DELTA: Dict[str, float] = {
    "剧衰": -1.20, "渐衰": -0.55, "持平": 0.0, "渐涨": 0.55, "剧涨": 1.20,
}
#: 档位 → 态度跳变（点）
ATTITUDE_DELTA: Dict[str, int] = {"骤恶": -15, "渐恶": -7, "持平": 0, "渐善": 7, "骤善": 15}
#: 档位 → 压力增幅倍率
PRESSURE_MULT: Dict[str, float] = {"平缓": 0.5, "升温": 1.0, "激化": 1.8}

_PROVIDERS: List[Callable] = []


def register_trend_provider(fn: Callable) -> None:
    _PROVIDERS.append(fn)


def _slot(state) -> Dict[str, Any]:
    got = getattr(state, "_trend_ai", None)
    return got if isinstance(got, dict) else {}


def _ask(state) -> Dict[str, Any]:
    for fn in reversed(_PROVIDERS):
        try:
            got = fn(state)
            if isinstance(got, dict):
                return got
        except Exception:  # noqa: BLE001 — 天道失败不得阻断
            continue
    return {}


def _pick(state, key: str) -> Dict[str, Any]:
    slot = _slot(state)
    got = slot.get(key)
    if isinstance(got, dict):
        return got
    prov = _ask(state)
    got = prov.get(key)
    return got if isinstance(got, dict) else {}


def resolve_power_trend(state, regime: str) -> Optional[float]:
    """天道国势档位 → 月度漂移；缺档/非法 ⇒ None（调用方沿用原随机）。"""
    level = _pick(state, "power").get(regime)
    if level in POWER_TREND_LEVELS:
        return POWER_DELTA[level]
    return None


def resolve_attitude_shock(state, regime: str) -> Optional[int]:
    """天道外交态度档位 → 跳变点；缺档/非法 ⇒ None。"""
    level = _pick(state, "attitude").get(regime)
    if level in ATTITUDE_SHOCK_LEVELS:
        return ATTITUDE_DELTA[level]
    return None


def resolve_pressure_level(state, category: str) -> Optional[float]:
    """天道事件压力档位 → 增幅倍率；缺档/非法 ⇒ None（沿用原随机）。"""
    level = _pick(state, "pressure").get(category)
    if level in PRESSURE_LEVELS:
        return PRESSURE_MULT[level]
    return None