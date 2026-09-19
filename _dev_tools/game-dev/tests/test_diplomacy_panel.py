# -*- coding: utf-8 -*-
"""T15 外交数据测试（Tk 废弃后迁移）：名录覆盖 / 省份权重 / 运行态字段 / 入口。

覆盖：
  1) 外交名录覆盖 EXTERNAL_REGIMES 全部 41 势力（前端白名单无遗漏）；
  2) EXTERNAL_PROVINCES 省份权重和 = 1.0（辽 5 道 / 夏 2 府 等）；
  3) 运行态 external_regimes 含面板所需字段（power/attitude/population/monthly_tax）；
  4) Web dock 含「邦交」入口（源码断言）。
"""
import os
import sys

import pytest

# game 根（测试已迁 _dev_tools/game-dev/tests；game 根 = G:\sz\game）
_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from content.data import EXTERNAL_REGIMES, EXTERNAL_PROVINCES  # noqa: E402


def test_diplo_groups_cover_all_regimes():
    """外交名录覆盖全部外部势力（41）。

    Tk 废弃：分组权威源迁至前端 `DiplomacyPanel.tsx`（渲染侧），Python 侧只校验
    数据层完整性 + 前端白名单无遗漏（前端工程不在本机时跳过）。
    """
    assert len(EXTERNAL_REGIMES) == 41
    _fe = os.path.join(_GAME_ROOT, "..", "game", "frontend", "src",
                       "renderer", "panels", "DiplomacyPanel.tsx")
    if not os.path.exists(_fe):
        return  # 前端工程不在本机（可选目录）→ 跳过
    with open(_fe, encoding="utf-8") as f:
        src = f.read()
    missing = [k for k in EXTERNAL_REGIMES if k not in src]
    assert not missing, f"前端外交分组白名单缺：{missing}"


def test_external_provinces_weights_sum_one():
    """省份权重和 = 1.0（辽 5 道 / 西夏 2 府 / 金 2 等）。"""
    assert EXTERNAL_PROVINCES["辽"][0][0] == "南京道"
    assert len(EXTERNAL_PROVINCES["辽"]) == 5
    assert len(EXTERNAL_PROVINCES["西夏"]) == 2
    for key, provs in EXTERNAL_PROVINCES.items():
        total = sum(w for _n, w in provs)
        assert abs(total - 1.0) < 1e-6, f"{key} 省份权重和应=1，实际 {total}"


def test_external_regimes_runtime_fields():
    """运行态 external_regimes 含面板所需字段（power/attitude/population/monthly_tax）。"""
    s = GameState("史实")
    regimes = s.external_regimes
    assert len(regimes) == 41
    for k, r in regimes.items():
        assert "power" in r and "attitude" in r
        assert "population" in r and "monthly_tax" in r
    assert regimes["辽"]["population"] == 380      # 万
    assert regimes["辽"]["monthly_tax"] > 0


# 注（2026-09-19 测试项审查）：原 `test_dock_has_diplomacy`（断言 Dock.tsx 源码里
# 存在 `key: "diplomacy"` 字面量）已删除——它属"前端源码文本断言"：改文案/重构即失败，
# 而真实退化（面板失联）未必被它捕获。该保障已由 **`test_frontend_registry.py`** 以
# 类型契约方式更强地覆盖：Dock 的每个命令键必须 ∈ `gameStore.PanelKind`，且每个
# PanelKind 成员必须在 OverlayStack 中有实现分支（含 `situation`/`diplomacy`）。
