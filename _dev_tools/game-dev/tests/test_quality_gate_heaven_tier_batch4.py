# -*- coding: utf-8 -*-
"""质量放行门 · 天道档位化 batch4：诏令生效月数（2026-10-20）。

用户裁定：「多方面因素影响，天道，主持官员能力，皇威，后续跟进等等」。

钉住：
1. **纯函数**（不耗随机数）；同一输入必得同一月数；
2. 天道节奏 速/常/缓 → 基础 6/12/18（`_decree_ai.pace` 或任务 priority 推导）；
3. 能力：<40 ×1.25 / 40–69 ×1.00 / ≥70 ×0.80，未指定 ⇒ 1.00 且注明原因；
4. 皇威：<40 ×1.20 / 40–79 ×1.00 / ≥80 ×0.85；
5. 跟进：0 ×1.10 / 1 ×0.95 / ≥2 ×0.85；
6. 月数夹在 3–36；breakdown 记录每项系数与来源；
7. 缺天道档 ⇒ 常（12 月）且 source 明示缺档。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.domains.politics.decree_duration import (  # noqa: E402
    MONTHS_MAX, MONTHS_MIN, resolve_decree_duration)


class _S:
    def __init__(self, prestige=55, pace=None, priorities=None):
        self.prestige = prestige
        if pace:
            self._decree_ai = {"pace": pace}
        if priorities:
            self._decree_execute_ai = {"tasks": [{"priority": p} for p in priorities]}


def test_deterministic_no_random():
    s = _S()
    a = resolve_decree_duration(s, ability=55, followup=1)
    b = resolve_decree_duration(s, ability=55, followup=1)
    assert a == b


def test_pace_mapping():
    assert resolve_decree_duration(_S(pace="速"))["base"] == 6
    assert resolve_decree_duration(_S(pace="常"))["base"] == 12
    assert resolve_decree_duration(_S(pace="缓"))["base"] == 18


def test_priority_derives_pace():
    got = resolve_decree_duration(_S(priorities=["低", "高"]))
    assert got["pace"] == "速" and "任务优先级" in got["source"]


def test_ability_effect():
    low = resolve_decree_duration(_S(), ability=20)["breakdown"]["ability"]["mult"]
    mid = resolve_decree_duration(_S(), ability=55)["breakdown"]["ability"]["mult"]
    high = resolve_decree_duration(_S(), ability=85)["breakdown"]["ability"]["mult"]
    assert (low, mid, high) == (1.25, 1.00, 0.80)


def test_prestige_effect():
    weak = resolve_decree_duration(_S(prestige=30))["breakdown"]["prestige"]["mult"]
    mid = resolve_decree_duration(_S(prestige=60))["breakdown"]["prestige"]["mult"]
    strong = resolve_decree_duration(_S(prestige=90))["breakdown"]["prestige"]["mult"]
    assert (weak, mid, strong) == (1.20, 1.00, 0.85)


def test_followup_effect():
    assert resolve_decree_duration(_S(), followup=0)["breakdown"]["followup"]["mult"] == 1.10
    assert resolve_decree_duration(_S(), followup=1)["breakdown"]["followup"]["mult"] == 0.95
    assert resolve_decree_duration(_S(), followup=3)["breakdown"]["followup"]["mult"] == 0.85


def test_months_clamped():
    fast = resolve_decree_duration(_S(prestige=99, pace="速"), ability=99, followup=3)
    slow = resolve_decree_duration(_S(prestige=10, pace="缓"), ability=10, followup=0)
    assert fast["months"] >= MONTHS_MIN
    assert slow["months"] <= MONTHS_MAX


def test_missing_ai_defaults_and_marks_source():
    got = resolve_decree_duration(_S())
    assert got["pace"] == "常" and got["base"] == 12
    assert "缺档" in got["source"]


def test_unset_ability_is_documented():
    got = resolve_decree_duration(_S(), ability=None)
    assert got["breakdown"]["ability"]["mult"] == 1.00
    assert "未指定" in got["breakdown"]["ability"]["note"]