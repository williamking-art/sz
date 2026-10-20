# -*- coding: utf-8 -*-
"""质量放行门 · 邸报「在办案卷」小节（2026-10-20）。

钉住：
1. 已案卷化事务 ⇒ 邸报「长期局势」章出现案卷行（案号/标题/阶段/进度/承办/专款余额）；
2. 未案卷化事务 ⇒ 不出现（旧行为零变更）；
3. 派生出错不中断邸报（章仍有默认行）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.domains.administration.monthly_gazette import build_monthly_gazette  # noqa: E402


class _S:
    year = 1630
    month = 7
    treasury = 100000
    prestige = 50
    population_satisfaction = 50
    longterm_secret = []

    def __init__(self, tasks):
        self.longterm_public = tasks
        self.situations = []


def _chapter(state, name="长期局势"):
    g = build_monthly_gazette(state)
    return next(c for c in g["chapters"] if c["title"] == name)["lines"]


def test_cased_task_appears():
    t = {"id": "ltp1", "case_no": "#426", "task_name": "整饬海防", "progress": 82,
         "phase": "终前", "minister": "郑芝龙",
         "budget": {"total": 50, "remaining": 30, "pool": "treasury"}}
    lines = _chapter(_S([t]))
    text = "\n".join(lines)
    assert "案卷#426" in text and "整饬海防" in text
    assert "终前" in text and "承办 郑芝龙" in text and "专款余 30/50" in text


def test_uncased_task_absent():
    lines = _chapter(_S([{"id": "ltp1", "task_name": "普通事务", "progress": 10}]))
    assert not any("案卷" in ln for ln in lines)
    assert lines, "章不应为空"