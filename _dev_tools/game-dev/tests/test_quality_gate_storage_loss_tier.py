# -*- coding: utf-8 -*-
"""质量放行门 · 仓储损耗档位（天道裁决，G-3 P2a）。

用户 2026-10-18：「粮的损耗不是有天道系统来裁决多寡吗」
⇒ 天道只出档位（无/轻/中/重），程序按表换算率（AI 不给数）。

本门钉住：表自洽 / 「中」== 既有 SPARROW_RAT（默认零变更）/ 缺档回落默认 / 单调性 / 注入即红。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from content.data import SPARROW_RAT, STORAGE_LOSS_TIER_MULT  # noqa: E402
from core.foundation.ledger.grain_ledger import (  # noqa: E402
    STORAGE_LOSS_TIERS, assert_loss_tiers_sane, storage_loss_rate)


def test_tiers_are_sane():
    assert assert_loss_tiers_sane() == [], f"档位表问题：{assert_loss_tiers_sane()}"
    assert set(STORAGE_LOSS_TIERS) == set(STORAGE_LOSS_TIER_MULT), "档位与倍率表键不一致"


def test_default_tier_equals_existing_rate():
    """「中」档必须等于既有 SPARROW_RAT ⇒ 默认行为零变更。"""
    assert abs(storage_loss_rate("中") - SPARROW_RAT) < 1e-12
    assert abs(storage_loss_rate() - SPARROW_RAT) < 1e-12, "缺档应按默认「中」"
    assert abs(storage_loss_rate("未知档") - SPARROW_RAT) < 1e-12, "未知档不得归零"


def test_tier_monotonicity():
    """档位越高损耗越大；「无」为 0（天道判无损耗）。"""
    rates = [storage_loss_rate(t) for t in STORAGE_LOSS_TIERS]
    assert rates[0] == 0.0, "「无」档应为 0"
    assert rates == sorted(rates), f"档位率未单调：{dict(zip(STORAGE_LOSS_TIERS, rates))}"


def test_rate_scales_baseline():
    """实际率 = 基准 × 倍率（程序算，不让 AI 给数）。"""
    for t in STORAGE_LOSS_TIERS:
        assert abs(storage_loss_rate(t) - SPARROW_RAT * STORAGE_LOSS_TIER_MULT[t]) < 1e-12


def test_guard_detects_tampered_table():
    """反例（注入即红）：把「重」倍率改到比「中」还低，自检必须报错。"""
    import core.foundation.ledger.grain_ledger as gl
    import content.data as cd

    orig = dict(cd.STORAGE_LOSS_TIER_MULT)
    try:
        cd.STORAGE_LOSS_TIER_MULT["重"] = 0.1
        issues = gl.assert_loss_tiers_sane()
        assert issues, "倍率乱序未被自检发现 ⇒ 判据是空的"
    finally:
        cd.STORAGE_LOSS_TIER_MULT.clear()
        cd.STORAGE_LOSS_TIER_MULT.update(orig)