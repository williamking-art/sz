# -*- coding: utf-8 -*-
"""质量放行门 · 载具/夫役字段与**派生运力**（P3，2026-10-18）。

运力不是常量：`min(载具上限, 人力上限) × 可用率`，其中载具上限按**官私载具数 × 真实载重 × 月趟数**。

本门钉住：
1. 开局有 carriage/transport_labor 字段（官私分开）；
2. 官私载具**相加**（不是覆盖）；载具上限乘月趟数；
3. 三方式瓶颈符合设计：水运/海运/驿传=载具卡，陆运=人力卡；
4. 漕淤提高 ⇒ 水运运力下降（可用率）；
5. 占用/剩余/清空闭环；不足时**截断不拒办**；
6. 无载具无夫役 ⇒ 运力 0 且 bottleneck=none（不臆造）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.transport import (  # noqa: E402
    transport_capacity, transport_consume, transport_remaining, transport_reset_month)


def _state():
    from core.commands import new_game

    return new_game()


def test_fields_initialized():
    s = _state()
    assert isinstance(s.carriage, dict) and s.carriage.get("official")
    assert isinstance(s.carriage.get("private"), dict) and s.carriage["private"]
    assert isinstance(s.transport_labor, dict) and s.transport_labor.get("official")
    assert isinstance(s.transport_used, dict)


def test_official_and_private_are_summed():
    s = _state()
    cap = transport_capacity(s, "waterway")
    boats = int(s.carriage["official"]["boat"]) + int(s.carriage["private"]["small_boat"])
    assert cap["vehicles"]["boat"] + cap["vehicles"]["small_boat"] == boats, cap


def test_capacity_matches_design_scale():
    s = _state()
    w = transport_capacity(s, "waterway")
    m = transport_capacity(s, "maritime")
    o = transport_capacity(s, "overland")
    p = transport_capacity(s, "post")
    assert 500_000 <= w["capacity"] <= 800_000, w
    assert 30_000 <= m["capacity"] <= 60_000, m
    assert 150_000 <= o["capacity"] <= 250_000, o
    assert 10_000 <= p["capacity"] <= 30_000, p


def test_bottleneck_flags():
    s = _state()
    assert transport_capacity(s, "waterway")["bottleneck"] == "vehicles"