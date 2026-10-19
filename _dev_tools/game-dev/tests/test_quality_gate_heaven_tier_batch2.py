# -*- coding: utf-8 -*-
"""质量放行门 · 天道档位化 batch2：国势/外交/事件压力（2026-10-20）。

用户：「能用天道裁决的就用天道裁决」；Jev 边界 A（只改情境强度类）。

钉住：
1. 缺档 ⇒ 全部返回 None（**调用方沿用原随机幅度 ⇒ 零行为变更**）；
2. 国势档位映射：剧衰 −1.20 / 渐衰 −0.55 / 持平 0 / 渐涨 +0.55 / 剧涨 +1.20；
3. 外交态度：骤恶 −15 / 渐恶 −7 / 持平 0 / 渐善 +7 / 骤善 +15；
4. 事件压力倍率：平缓 0.5 / 升温 1.0 / 激化 1.8；
5. provider 注入生效，优先级同槽位；非法档位不崩、返回 None；
6. 槽位结构缺失（None/非 dict）不崩。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.domains.politics import trend_tier as tt  # noqa: E402


class _S:
    def __init__(self, slot=None):
        if slot is not None:
            self._trend_ai = slot


def test_missing_slot_returns_none():
    s = _S()
    assert tt.resolve_power_trend(s, "金") is None
    assert tt.resolve_attitude_shock(s, "西夏") is None
    assert tt.resolve_pressure_level(s, "方腊起义") is None


def test_power_mapping():
    s = _S({"power": {"金": "剧涨", "辽": "渐衰", "西夏": "持平"}})
    assert tt.resolve_power_trend(s, "金") == 1.20
    assert tt.resolve_power_trend(s, "辽") == -0.55
    assert tt.resolve_power_trend(s, "西夏") == 0.0
    assert tt.resolve_power_trend(s, "吐蕃") is None


def test_attitude_mapping():
    s = _S({"attitude": {"西夏": "骤恶", "金": "渐善"}})
    assert tt.resolve_attitude_shock(s, "西夏") == -15
    assert tt.resolve_attitude_shock(s, "金") == 7


def test_pressure_mapping():
    s = _S({"pressure": {"方腊起义": "激化", "宋江起义": "平缓"}})
    assert tt.resolve_pressure_level(s, "方腊起义") == 1.8
    assert tt.resolve_pressure_level(s, "宋江起义") == 0.5


def test_provider_injection():
    s = _S()
    tt.register_trend_provider(lambda st: {"power": {"金": "渐涨"}})
    try:
        assert tt.resolve_power_trend(s, "金") == 0.55
    finally:
        tt._PROVIDERS.clear()


def test_invalid_values_are_none():
    s = _S({"power": {"金": "暴涨"}, "attitude": {"西夏": "巨变"}, "pressure": {"方腊起义": "爆"}})
    assert tt.resolve_power_trend(s, "金") is None
    assert tt.resolve_attitude_shock(s, "西夏") is None
    assert tt.resolve_pressure_level(s, "方腊起义") is None


def test_slot_not_dict_does_not_crash():
    s = _S()
    s._trend_ai = "坏数据"
    assert tt.resolve_power_trend(s, "金") is None