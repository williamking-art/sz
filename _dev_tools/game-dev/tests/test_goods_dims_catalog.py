# -*- coding: utf-8 -*-
"""**G-1 · 全商品目录单点** 定向回归（2026-10-03）。

用户裁定「米麦是原材料啊，可以精加工的」＋「所有商品都州府级、都参与经济流转」，
故立**全商品目录** `GOODS_DIMS` 作为一切商品维度的唯一真源。

本组锁（**纯目录，不改任何行为**——行为改动在 G-2 起的批次）：

1. 目录唯一、无重复登记；
2. 米/麦（粮的品类拆分）已并入目录；
3. 粗粒度「粮」**不得**再作为商品维并存（它只是 `RAW_DIMS_14` 外邦表的粗名）；
4. 目录 = 原料 + 成品 + 米麦，与既有 `RAW_DIMS`/`FINISHED_DIMS` 一致可核。
"""
import os
import sys

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from content.data import FINISHED_DIMS, GOODS_DIMS, GRAIN_DIMS, RAW_DIMS  # noqa: E402


def test_goods_dims_is_unique_and_complete():
    """目录唯一、无重复，且 = 原料 + 成品 + 米麦。"""
    assert len(set(GOODS_DIMS)) == len(GOODS_DIMS), f"目录有重复：{GOODS_DIMS}"
    assert set(GRAIN_DIMS) == {"米", "麦"}, f"粮应拆为米/麦：{GRAIN_DIMS}"
    assert set(GRAIN_DIMS).issubset(set(GOODS_DIMS)), "米/麦须在商品目录内"
    assert "粮" not in GOODS_DIMS, "粗粒度「粮」不应与米/麦并存（外邦表口径，民间已细分）"
    for d in RAW_DIMS:
        assert d in GOODS_DIMS, f"原料 {d} 漏出目录"
    for d in FINISHED_DIMS:
        assert d in GOODS_DIMS, f"成品 {d} 漏出目录"


def test_goods_dims_count_matches_components():
    """目录长度 = 原料 + 成品 + 米麦（不多不少，防将来误并）。"""
    assert len(GOODS_DIMS) == len(RAW_DIMS) + len(FINISHED_DIMS) + len(GRAIN_DIMS)


def test_goods_dims_importable_from_content_data():
    """`content.data` 聚合层能取到（G-1 的对外单点出口）。"""
    from content.data import GOODS_DIMS as G2
    assert G2 == GOODS_DIMS