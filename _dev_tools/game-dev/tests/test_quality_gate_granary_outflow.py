# -*- coding: utf-8 -*-
"""质量放行门 · 发仓总闸门（G-3 P2c）。

背景：P2b 把损耗从 outflow 档位剥离后，outflow 一度没有落点（档位失效）。
本批把它接到「本月发仓总闸门」：作用于军粮 + 官俸 + 吏禄的本色支出总量。

实测（new_game 后跑 1 月，读 granary_stats["military"]）：
  无 → 0（停发）｜小 → 799,114（= 旧行为）｜大 → 1,598,231（×2）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


def _run(outflow="小", army="小", use_ai=True):
    from core.commands import new_game, settle_local

    s = new_game()
    if use_ai:
        s._granary_ai = {"granary": {"inflow": "小", "outflow": outflow, "price_stabilize": "小",
                                     "army_supply": army, "storage_loss": "中"},
                         "narrative": ""}
    log = settle_local(s)
    return int(s.granary_stats.get("military", 0)), int(s.granary), log


def test_default_outflow_matches_no_ai_baseline():
    """「小」（倍率 1.0）⇒ 与无 AI 决策时完全一致（零变更基线）。"""
    a = _run("小")
    b = _run(use_ai=False)
    assert a[0] == b[0], f"默认档位改变了本色支出：{a[0]} vs {b[0]}"


def test_zero_outflow_stops_release():
    """「无」档 ⇒ 本色支出 0（天道判停发），且日志留痕。"""
    military, granary, log = _run("无")
    assert military == 0, f"停发档仍有本色支出：{military}"
    assert granary >= 0
    assert any("发仓闸门" in str(x) for x in log), "停发档应留痕"


def test_large_outflow_doubles_release():
    """「大」（×2.0）⇒ 本色支出约为「小」的两倍，且太仓不得为负。"""
    small, _g1, _ = _run("小")
    large, g2, _ = _run("大")
    assert small > 0, "基线支出为 0 ⇒ 门是空转"
    # 取整/截断会带几石误差，按相对容差断言
    assert abs(large - 2 * small) <= max(10, int(0.01 * small)), f"「大」档未按 2 倍放大：{large} vs {small}"
    assert g2 >= 0, "太仓出现负数"


def test_army_supply_still_scales_army():
    """军粮份额仍由 army_supply 决定（与 outflow 闸门相互独立）。"""
    lo, _g1, _ = _run("小", army="微")
    hi, _g2, _ = _run("小", army="大")
    assert hi > lo, f"army_supply 未生效：{hi} vs {lo}"