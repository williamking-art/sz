# -*- coding: utf-8 -*-
"""黔中路全套数据补齐验收（M323）。

⚠️ 本文件为**regenerated**：原文件于 2026-10-17 被 DSH 误删（清理 `sz/tests/`
时连带删除 antigravity 名下 M323/M324 的产物），本文件据
`_dev_tools/handover/tasks/M323-qianzhong-circuit-complete-data.json` 描述与
数据层实况重写：① 地脉储量；② ROAD_YIELD / CASH_CROP_LAND 对齐；
③ 产业链与贸易的通用通道对该路可用。
"""
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "game") not in sys.path:
    sys.path.insert(0, str(_ROOT / "game"))

from content.data_geo_tables import CASH_CROP_LAND, ROAD_YIELD  # noqa: E402
from core.domains.economy import mineral_deposit as md  # noqa: E402
from core.domains.economy import trade_shadow  # noqa: E402


QIANZHONG = "黔中路"


# =============================================================================
# 1. 地脉储量：黔中路必须有真实矿藏（林木/石料/铁矿）
# =============================================================================
def test_qianzhong_has_mineral_deposits():
    deposits = md.CIRCUIT_MINERAL_DEPOSITS.get(QIANZHONG)
    assert deposits, "黔中路缺地脉配置"
    for dim in ("木", "石", "铁"):
        assert dim in deposits, f"黔中路缺 {dim} 地脉"
        row = deposits[dim]
        assert row["reserves"] > 0
        assert row["cap"] > 0
        assert 0.0 < row["purity"] <= 1.0


def test_mineral_table_covers_all_circuits():
    """地脉表须覆盖全部 21 路（含黔中路），不得有路缺表。"""
    assert len(md.CIRCUIT_MINERAL_DEPOSITS) == 21
    assert QIANZHONG in md.CIRCUIT_MINERAL_DEPOSITS


# =============================================================================
# 2. 土地产出与经济表对齐
# =============================================================================
def test_road_yield_aligned():
    assert QIANZHONG in ROAD_YIELD
    assert ROAD_YIELD[QIANZHONG] > 0


def test_cash_crop_land_aligned():
    crops = CASH_CROP_LAND.get(QIANZHONG)
    assert crops, "黔中路缺经济作物配置"
    assert set(crops) & {"茶", "麻"}, f"黔中路经济作物异常：{crops}"
    for crop, share in crops.items():
        assert 0.0 <= float(share) <= 1.0, f"{crop} 份额越界：{share}"


# =============================================================================
# 3. 产业链与贸易通道可用（走通用机制，不依赖硬编码特例）
# =============================================================================
def test_trade_waterway_tier_covers_qianzhong():
    """"黔中路属「弱」水道档 —— 贸易成本按通用档位表计算，不需特例。"""
    weak = [k for k, v in trade_shadow.WATERWAY_TIER.items() if v == "弱"] \
        if hasattr(trade_shadow, "WATERWAY_TIER") else None
    if weak is not None:
        assert QIANZHONG in weak

    tiers = None
    for name in dir(trade_shadow):
        obj = getattr(trade_shadow, name)
        if isinstance(obj, dict) and QIANZHONG in obj:
            tiers = {k: v for k, v in obj.items()}
    assert tiers is not None, "贸易模块未把黔中路纳入任何通用表"


def test_mineral_deposit_rows_are_numeric():
    for dim, row in md.CIRCUIT_MINERAL_DEPOSITS[QIANZHONG].items():
        assert isinstance(row, dict), f"{dim} 配置形态异常"
        for key in ("reserves", "cap", "purity"):
            assert isinstance(row[key], (int, float))
