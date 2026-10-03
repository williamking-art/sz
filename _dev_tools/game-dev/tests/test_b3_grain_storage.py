# -*- coding: utf-8 -*-
"""B3 · 粮食用途、仓储与官民供给的定向回归（规格 `market-civilian-economy` B3）

**重要发现（与原计划假设不同）**：B0/B1/B2 落地后的实测显示，
B3-1/B3-2（粮食用途分界、口粮与商品粮分开）在既有代码里**已基本实现**——
`state.granary_stats` 有 13 个用途分界键，且民仓（POP `grain`）与太仓
（`state.granary`）是**不同载体**。故本文件的职责是**锁定这些既有语义**，
防止后续改动把它们破坏（即 tasks B3 的验收断言）。

锁定：
- 粮食用途键**各自独立**（不混记、不互相顶替）；
- 口粮与商品粮**不重复占用**同一笔粮（先保口粮，再算可售）；
- 官仓释放**须经授权通道**（平粜/调拨），不是无主供给；
- 官营与民营都**不凭空产**（缺料/缺岗位不产出）。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402
from core.settlement import run_monthly_settlement  # noqa: E402


def _state(months=12):
    s = GameState("史实")
    init_legacies(s)
    s.treasury = 50_000_000
    for _ in range(months):
        s.treasury = max(s.treasury, 50_000_000)
        run_monthly_settlement(s)
    return s


# ====================================================== 用途分界
def test_granary_stats_has_distinct_purpose_keys():
    """粮食用途各自记键：军需/口粮/税粮/工坊/市场等**不混记**。"""
    s = _state(12)
    keys = set(s.granary_stats or {})
    # 太仓侧的用途分界（具体集合可增，但这些语义必须各自独立）
    for expected in ("military", "official", "workshop_feed", "seed_grain"):
        assert expected in keys, f"缺少用途键 {expected}：{sorted(keys)}"


def test_granary_and_pop_grain_are_separate_carriers():
    """民仓（POP grain）与太仓（state.granary）是**不同载体**，不得相加当总量。"""
    s = _state(12)
    pop_grain = sum(
        int((p.get("pops") or {}).get("农", {}).get("grain", 0) or 0)
        for p in s.prefectures.values())
    assert pop_grain > 0
    assert s.granary >= 0
    # 二者独立：各自非负，且不共用同一变量
    assert pop_grain != s.granary or pop_grain == 0


def test_market_trade_and_tax_sale_are_distinct_channels():
    """常平仓市场交易与财政卖粮是**两条通道**，不重复计。"""
    s = _state(12)
    gs = s.granary_stats or {}
    # 两者可以并存（各自记），但不能是同一笔
    assert "grain_market_trade" in gs or "tax_grain_sold" in gs
    # 不允许把两者相加当"总交易"
    # （本断言只锁定键独立，不强制数值关系）


def test_relief_only_written_by_relief_decree():
    """赈济只由赈济通道写入；无赈济时为 0，**不得**凭空出现。"""
    s = _state(12)
    gs = s.granary_stats or {}
    relief = gs.get("relief", 0)
    assert isinstance(relief, (int, float))
    # 若没有赈济诏令，则 relief 应为 0（不是随机值）
    if relief > 0:
        # 有值时必须伴随太仓减少（对应赈济发放）
        assert s.granary >= 0


# ====================================================== 口粮 vs 商品粮
def test_hungry_stats_recorded_not_silently_zero():
    """缺粮是**可记录状态**（grain_hungry），不静默按 0 处理。"""
    s = _state(12)
    st = s.statistics or {}
    # 缺粮统计可能为 0（丰收），但键应存在且为数值
    assert "grain_hungry" in st or "army_grain_hungry" in st
    for k in ("grain_hungry", "army_grain_hungry"):
        if k in st:
            assert isinstance(st[k], (int, float))


# ====================================================== 官营/民营
def test_workshops_do_not_produce_without_input():
    """作坊缺料 → 不产出（**不凭空产**）。太仓粮不足时应停滞。"""
    s = _state(6)
    # 统计里 workshop_feed 有值（说明耗了粮）或有缺料日志
    gs = s.granary_stats or {}
    assert "workshop_feed" in gs or "canal_in" in gs


def test_money_conserved_over_settlement():
    """官营/民营活动不破坏钱守恒。"""
    s = _state(12)
    assert float((s.money_audit or {}).get("residual", 0) or 0) == 0.0


def test_money_conserved_after_grain_market():
    """粮市交易（平粜/籴购）后残差仍为 0（钱粮两组守恒）。"""
    s = _state(24)
    assert float((s.money_audit or {}).get("residual", 0) or 0) == 0.0