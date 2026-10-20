# -*- coding: utf-8 -*-
"""质量放行门 · 天道档位化 batch3：漕运淤塞 / 灾荒减产（2026-10-20）。

钉住：
1. 缺档 ⇒ 两个 resolver 均返回 None（调用方沿用原随机 ⇒ 零行为变更）；
2. 淤塞档位 → 增量：无0 / 轻3 / 中5 / 重8 / 极12（三种成因 base/disaster/war）；
3. 减产档位 → 系数：轻0.80 / 中0.70 / 重0.55 / 极重0.40；
4. provider 注入生效；非法档位不崩返回 None；槽位结构坏不崩；
5. 频次与自然疏浚**不**由天道决定（结构性随机，保持可复现）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.domains.events import disaster_tier as dt  # noqa: E402


class _S:
    def __init__(self, canal=None, famine=None):
        if canal is not None:
            self._canal_ai = canal
        if famine is not None:
            self._famine_ai = famine


def test_missing_returns_none():
    s = _S()
    for cause in ("base", "disaster", "war"):
        assert dt.resolve_canal_silt(s, cause) is None
    assert dt.resolve_famine_yield(s) is None


def test_silt_mapping():
    s = _S(canal={"silt": {"base": "轻", "disaster": "重", "war": "极"}})
    assert dt.resolve_canal_silt(s, "base") == 3
    assert dt.resolve_canal_silt(s, "disaster") == 8
    assert dt.resolve_canal_silt(s, "war") == 12
    assert dt.resolve_canal_silt(s, "none_cost") is None


def test_famine_mapping():
    for tier, val in (("轻", 0.80), ("中", 0.70), ("重", 0.55), ("极重", 0.40)):
        assert dt.resolve_famine_yield(_S(famine={"yield": tier})) == val


def test_providers():
    s = _S()
    dt.register_canal_silt_provider(lambda st: {"base": "中"})
    dt.register_famine_provider(lambda st: {"yield": "重"})
    try:
        assert dt.resolve_canal_silt(s, "base") == 5
        assert dt.resolve_famine_yield(s) == 0.55
    finally:
        dt._CANAL_PROVIDERS.clear()
        dt._FAMINE_PROVIDERS.clear()


def test_invalid_levels_are_none():
    s = _S(canal={"silt": {"base": "爆"}}, famine={"yield": "绝收"})
    assert dt.resolve_canal_silt(s, "base") is None
    assert dt.resolve_famine_yield(s) is None


def test_broken_slot_does_not_crash():
    s = _S()
    s._canal_ai = "坏"
    s._famine_ai = 123
    assert dt.resolve_canal_silt(s, "base") is None
    assert dt.resolve_famine_yield(s) is None