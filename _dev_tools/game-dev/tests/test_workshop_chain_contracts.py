# -*- coding: utf-8 -*-
"""G-6 产业链扩充：新增加工链的**口径契约**守护。"""
import sys

sys.path.insert(0, r'D:/codebuddy/sz/game')

from content.data import (FINISHED_DIMS, FINISHED_TAX_DIMS, GOODS_DIMS,
                           MATERIAL_PRICE_BASE, RESOURCE_DIMS,
                           WORKSHOP_RECIPES)


def test_new_chains_registered():
    """麻→纸、蔗→糖 两条链须在册。"""
    assert '造纸坊' in WORKSHOP_RECIPES
    assert '糖坊' in WORKSHOP_RECIPES
    assert WORKSHOP_RECIPES['造纸坊']['output_dim'] == '纸'
    assert WORKSHOP_RECIPES['糖坊']['output_dim'] == '糖'


def test_new_finished_dims_in_finished_catalog():
    for d in ('纸', '糖'):
        assert d in FINISHED_DIMS, d


def test_tradeable_chains_reach_goods_and_resources():
    """两维是**可交易**成品 ⇒ 同时在商品目录与物资仓目录。"""
    for d in ('纸', '糖'):
        assert d in GOODS_DIMS, d
        assert d in RESOURCE_DIMS, d
        assert d not in FINISHED_TAX_DIMS, '不应是即产即销维'


def test_all_tradeable_finished_dims_have_base_price():
    """可交易成品必须有基准价（缺失≠0 ⇒ 不可定价）。"""
    for d in FINISHED_DIMS:
        if d in FINISHED_TAX_DIMS:
            continue
        assert d in MATERIAL_PRICE_BASE, '缺基准价：%s' % d


def test_processing_adds_value_over_input():
    """成品价必须**高于其原料价** —— 否则加工链不成立（加工无增值）。"""
    for name in ('造纸坊', '糖坊'):
        r = WORKSHOP_RECIPES[name]['recipe']
        for dim in r:
            if dim in ('grain_feed', 'ration_weight'):
                continue
            out = WORKSHOP_RECIPES[name]['output_dim']
            assert MATERIAL_PRICE_BASE[out] > MATERIAL_PRICE_BASE[dim], (
                '%s: %s 成品价 %s 须高于原料价 %s' % (
                    name, out, MATERIAL_PRICE_BASE[out], MATERIAL_PRICE_BASE[dim]))


def test_recipes_reference_real_dims():
    """配方原料维须在**原料目录**内（不得臆造未登记的维）。"""
    from content.data import RAW_DIMS
    for name, w in WORKSHOP_RECIPES.items():
        for dim in w['recipe']:
            if dim in ('grain_feed', 'ration_weight'):
                continue
            assert dim in RAW_DIMS, (name, dim)


def test_output_dims_all_in_finished_catalog():
    """契约卡1：`output_dim` **必须**是 `FINISHED_DIMS` 之一。"""
    for name, w in WORKSHOP_RECIPES.items():
        assert w['output_dim'] in FINISHED_DIMS, (name, w['output_dim'])