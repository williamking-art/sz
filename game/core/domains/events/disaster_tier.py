# -*- coding: utf-8 -*-
"""灾情档位（2026-10-19，天道档位化第一批）。

用户要求：「能用天道裁决的就用天道裁决，混沌和随机性更能模拟现实」。
Jev 边界裁定 A 只改情境强度类（0.644）——统计噪声与税率/损耗率保留确定性。

口径：
- **是否成灾**仍由频次模型决定（结构性频率，不交给天道）；
- **严重度**由天道出档位：轻 / 中 / 重 / 极重（缺失档 ⇒ 程序按 1–5 均匀兜底并标来源）；
- 档位 → 严重度 1–5 的换算集中本模块（**唯一数字来源**）；
- 受灾路：天道可指定 region，未指定则由程序随机选路（保留混沌）。

天道槽：
    state._disaster_ai = {"severity": "重", "region": "河北", "note": "河朔大水，饿殍载道"}

也可注册 provider：register_disaster_provider(fn)，fn(state) -> {"severity": 档位, "region": 可选}。
"""
from __future__ import annotations

import random
from typing import Any, Callable, Dict, List, Optional

__all__ = ["DISASTER_SEVERITY_LEVELS", "SEVERITY_TO_LEVEL", "resolve_disaster",
           "register_disaster_provider", "DISASTER_REGIONS", "DISASTER_CHANCE",
           "SILT_LEVELS", "SILT_DELTA", "FAMINE_LEVELS", "FAMINE_YIELD",
           "resolve_canal_silt", "resolve_famine_yield",
           "register_canal_silt_provider", "register_famine_provider"]

DISASTER_SEVERITY_LEVELS = ("轻", "中", "重", "极重")

SEVERITY_TO_LEVEL: Dict[str, int] = {"轻": 1, "中": 3, "重": 4, "极重": 5}

DISASTER_REGIONS = ("河北", "京东", "两浙", "陕西", "河东", "荆湖")

DISASTER_CHANCE = 0.03

_PROVIDERS: List[Callable] = []


def register_disaster_provider(fn: Callable) -> None:
    _PROVIDERS.append(fn)


def _slot(state) -> Dict[str, Any]:
    got = getattr(state, "_disaster_ai", None)
    return got if isinstance(got, dict) else {}


def _ask(state) -> Dict[str, Any]:
    for fn in reversed(_PROVIDERS):
        try:
            got = fn(state)
            if isinstance(got, dict) and got.get("severity") in DISASTER_SEVERITY_LEVELS:
                return got
        except Exception:  # noqa: BLE001
            continue
    return {}


def resolve_disaster(state, *, roll: Optional[float] = None) -> Dict[str, Any]:
    """解析本月灾情：{occur, severity(1-5), region, source, note}。"""
    r = random.random() if roll is None else float(roll)
    occur = r < DISASTER_CHANCE
    if not occur:
        return {"occur": False, "severity": 0, "region": None,
                "source": "频次模型", "note": ""}
    slot = _slot(state)
    tier = slot.get("severity")
    source = "天道"
    note = slot.get("note") or ""
    region_hint = slot.get("region")
    if tier not in DISASTER_SEVERITY_LEVELS:
        prov = _ask(state)
        tier = prov.get("severity")
        source = "天道(provider)"
        note = prov.get("note") or ""
        region_hint = prov.get("region")
        if tier not in DISASTER_SEVERITY_LEVELS:
            level = random.randint(1, len(SEVERITY_TO_LEVEL) + 1)
            region = region_hint or random.choice(DISASTER_REGIONS)
            return {"occur": True, "severity": level, "region": region,
                    "source": "程序兜底(天道缺档)", "note": "均匀随机 1–5，非天道裁定"}
    level = SEVERITY_TO_LEVEL.get(tier, 3)
    region = region_hint or random.choice(DISASTER_REGIONS)
    return {"occur": True, "severity": level, "region": region,
            "source": source, "note": note, "tier": tier}


# ============================================================
# batch3（2026-10-20）：漕运淤塞程度 / 灾荒减产幅度
# 口径同 batch1/2：天道出档位，程序换算；**缺档返回 None ⇒ 调用方沿用原随机（零变更）**。
# ============================================================

#: 漕运淤塞档位 → 单次淤积增量（点）
SILT_LEVELS = ("无", "轻", "中", "重", "极")
SILT_DELTA: Dict[str, int] = {"无": 0, "轻": 3, "中": 5, "重": 8, "极": 12}

#: 灾荒减产档位 → 产量系数
FAMINE_LEVELS = ("轻", "中", "重", "极重")
FAMINE_YIELD: Dict[str, float] = {"轻": 0.80, "中": 0.70, "重": 0.55, "极重": 0.40}

_CANAL_PROVIDERS: List[Callable] = []
_FAMINE_PROVIDERS: List[Callable] = []


def register_canal_silt_provider(fn: Callable) -> None:
    _CANAL_PROVIDERS.append(fn)


def register_famine_provider(fn: Callable) -> None:
    _FAMINE_PROVIDERS.append(fn)


def _canal_slot(state) -> Dict[str, Any]:
    got = getattr(state, "_canal_ai", None)
    if isinstance(got, dict):
        sil = got.get("silt")
        if isinstance(sil, dict):
            return sil
    return {}


def _canal_ask(state) -> Dict[str, Any]:
    for fn in reversed(_CANAL_PROVIDERS):
        try:
            got = fn(state)
            if isinstance(got, dict):
                return got
        except Exception:  # noqa: BLE001
            continue
    return {}


def resolve_canal_silt(state, cause: str) -> Optional[int]:
    """漕运淤塞：cause ∈ {base, disaster, war} → 增量；缺档/非法 ⇒ None。"""
    level = _canal_slot(state).get(cause)
    if level not in SILT_LEVELS:
        level = _canal_ask(state).get(cause)
    if level in SILT_LEVELS:
        return SILT_DELTA[level]
    return None


def _famine_slot(state) -> Dict[str, Any]:
    got = getattr(state, "_famine_ai", None)
    return got if isinstance(got, dict) else {}


def _famine_ask(state) -> Dict[str, Any]:
    for fn in reversed(_FAMINE_PROVIDERS):
        try:
            got = fn(state)
            if isinstance(got, dict):
                return got
        except Exception:  # noqa: BLE001
            continue
    return {}


def resolve_famine_yield(state) -> Optional[float]:
    """灾荒减产幅度档位 → 产量系数；缺档/非法 ⇒ None（调用方沿用原 uniform）。"""
    level = _famine_slot(state).get("yield")
    if level not in FAMINE_LEVELS:
        level = _famine_ask(state).get("yield")
    if level in FAMINE_LEVELS:
        return FAMINE_YIELD[level]
    return None