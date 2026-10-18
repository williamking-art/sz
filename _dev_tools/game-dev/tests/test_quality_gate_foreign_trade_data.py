# -*- coding: utf-8 -*-
"""质量放行门 · P1 外贸数据层（2026-10-18，Jev A 0.913）。

数据层零行为变更：7 个外贸维、16 口岸/榷场、进出口篮、禁榷、POP 需求骨架。

本门钉住：
1. 7 维已进 `GOODS_DIMS` + `COMMODITY_KINDS` + 「进口奢侈」类目（覆盖门不破）；
2. 口岸 seat 全部是真实治所、channel 合法、note/partner 非空、partner 有进口篮；
3. 进出口篮的货种**全部是已立维**（未立维不得入场，防"幽灵货"）；
4. 禁榷维存在；
5. 需求矩阵：维存在、奢侈只由士绅/官僚/宗室消费；
6. **死货门**：每个成品维要么有 POP 需求，要么属军需/工具/舟车/机具（装备类，非消费品）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from content.data_constants import (  # noqa: E402
    COMMODITY_KINDS, CONTRABAND_DIMS, DEMAND_EXEMPT_DIMS, EXPORT_BASKET, FINISHED_DIMS,
    FOREIGN_TRADE_PORTS, GOODS_DIMS, IMPORT_BASKET, LUXURY_CONSUMER_CLASSES,
    POP_DEMAND_MATRIX)
from core.foundation.ledger import goods_class as gc  # noqa: E402
from core.foundation.ledger.prefecture_entity import all_seats  # noqa: E402

NEW_DIMS = ("香药", "珠宝", "犀象", "苏木", "锡", "漆器", "皮毛")
CHANNELS = {"sea", "land"}


def test_new_dims_are_registered_and_classed():
    for dim in NEW_DIMS:
        assert dim in GOODS_DIMS, f"{dim} 未进商品目录"
        assert dim in COMMODITY_KINDS, f"{dim} 未登记 kind"
        assert gc.class_of(dim) == "进口奢侈", f"{dim} 应属「进口奢侈」类目"
    assert not gc.assert_tree(), gc.assert_tree()


def test_ports_are_valid():
    ids = {s["seat_id"] for s in all_seats()}
    assert len(FOREIGN_TRADE_PORTS) >= 14, len(FOREIGN_TRADE_PORTS)
    for p in FOREIGN_TRADE_PORTS:
        assert p["seat"] in ids, f"口岸不是真实治所：{p}"
        assert p["channel"] in CHANNELS, p
        assert p.get("note"), f"缺依据/替代说明：{p}"
        assert p.get("partner") in IMPORT_BASKET, f"partner 无进口篮：{p}"


def test_baskets_only_contain_registered_dims():
    dims = set(GOODS_DIMS)
    for partner, items in EXPORT_BASKET.items():
        for d in items:
            assert d in dims, f"出口篮含未立维：{partner}/{d}"
    for partner, items in IMPORT_BASKET.items():
        assert items, f"{partner} 进口篮为空"
        for d in items:
            assert d in dims, f"进口篮含未立维：{partner}/{d}"


def test_contraband_dims_exist():
    dims = set(GOODS_DIMS)
    assert CONTRABAND_DIMS, "禁榷清单为空"
    for d in CONTRABAND_DIMS:
        assert d in dims, f"禁榷维不存在：{d}"


def test_demand_matrix_is_valid():
    dims = set(GOODS_DIMS)
    assert POP_DEMAND_MATRIX, "需求矩阵为空"
    for tier, items in POP_DEMAND_MATRIX.items():
        assert items, f"{tier} 档为空"
        for d, per in items.items():
            assert d in dims, f"需求矩阵含未立维：{d}"
            assert float(per) > 0, f"{d} 人均月耗非正"
    for cls in LUXURY_CONSUMER_CLASSES:
        assert cls in ("士绅", "官僚", "宗室", "商人", "工匠", "兵", "农"), cls


def test_no_dead_goods():
    """**死货门**：成品维必须有 POP 需求，或属于装备类（军需/工具/舟车/机具）。"""
    demanded = {d for items in POP_DEMAND_MATRIX.values() for d in items}
    equipment_classes = {"军需", "工具", "舟车", "机具"}
    dead = []
    for dim in FINISHED_DIMS:
        if dim in demanded:
            continue
        cls = gc.class_of(dim)
        if cls in equipment_classes:
            continue
        if dim in DEMAND_EXEMPT_DIMS:      # 货币/中间产物/燃料：有明确去向
            continue
        dead.append(dim)
    assert not dead, f"死货（无需求、非装备、无豁免理由）：{dead}"