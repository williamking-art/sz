# -*- coding: utf-8 -*-
"""调参定案回归测试（P0 量级 bug / Q2 官僚开局存粮）。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402


def _new_state():
    return GameState("史实")


def test_grain_market_buyer_pool_scale():
    """P0 回归：粮市买方池不饿死——缺粮 POP 有钱有需求、农余粮充足时，
    月撮合成交（grain_market_trade）≥ 200 万石（贯/文换算 ×1000 已修复，防量级 bug 复发）。"""
    s = _new_state()
    # 全国：非农 POP 缺粮且有钱（买方），农余粮充足（卖方）
    for p in s.prefectures.values():
        for k in ("工匠", "商人", "官僚", "兵"):
            p["pops"][k]["grain"] = 0
            p["pops"][k]["wealth"] = 200_000_000
        p["pops"]["农"]["grain"] = 10_000_000_000
        # 士绅无粮可抛（隔离 B1「士绅先售」对买方池的消耗，纯验证粮市撮合本身 P0 量级不饿死买方池）
        p["pops"]["士绅"]["grain"] = 0
    from core.settlement_steps import _settle_granary
    _settle_granary(s, [])
    trade = s.granary_stats.get("grain_market_trade", 0)
    assert trade >= 2_000_000, f"粮市买方池饿死（P0 量级回归？）：月成交 {trade} < 200万石"


def test_gentry_bureaucrat_opening_grain():
    """Q2：官僚开局存粮 = 月产×0.02（≈1~2 月口粮缓冲），非设计残留 0.1（≈4.9石/人）。"""
    s = _new_state()
    for p in s.prefectures.values():
        guan = p["pops"]["官僚"]
        grain_per = guan["grain"] / max(guan["size"], 1)
        # 4.9 石/人 缓冲：1.5 石/月口粮 → 约 3 个月内；旧 0.1 为 24 石/人残留
        assert 1.0 <= grain_per <= 8.0, f"官僚开局存粮异常：{grain_per:.1f} 石/人"
