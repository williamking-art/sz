# -*- coding: utf-8 -*-
"""I 项：material_tech 必须是**通用材料注册表**，不得耦合建材维表。

背景：计划列「`material_tech.py` 去建材化（升通用商品解锁注册表）」为未做，
但 2026-10-04 实测该模块**已是通用注册表**（`MATERIAL_TECH_UNLOCKS` +
`register_material_tech`），全文只引用 `PREFECTURE_LIST`/`BUILDING_STD`/`get_tech_node`
做交叉校验，**无任何建材维表耦合** ⇒ 本项实为已完成。

本用例把该性质**锁成可执行断言**，防止日后回归。
"""
import inspect
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'game'))

SRC = str(Path(__file__).resolve().parents[3] / 'game' / 'core' / 'material_tech.py')


def _src():
    return open(SRC, encoding='utf-8').read()


def test_no_material_dim_table_coupling():
    """源码**不得**引用任何建材维表常量 —— 否则就不是通用注册表。"""
    src = _src()
    for bad in ('MATERIAL_DIMS', 'RAW_DIMS_14', 'RAW_DIMS', 'GOODS_DIMS',
                'MATERIAL_SPECS'):
        assert bad not in src, 'material_tech 耦合了 %s —— 应升为通用注册表' % bad


def test_registry_keys_are_not_limited_to_building_materials():
    """注册表的键**不是**建材维的子集 ⇒ 它按「材料」注册，而非按建材枚举。"""
    from core.material_holding import MATERIAL_DIMS
    from core.material_tech import MATERIAL_TECH_UNLOCKS
    keys = set(MATERIAL_TECH_UNLOCKS)
    assert keys, '注册表不应为空'
    assert not (keys <= set(MATERIAL_DIMS)), (
        '注册表键 %s 全落在建材维 %s 内 —— 说明仍按建材枚举' % (
            sorted(keys), sorted(MATERIAL_DIMS)))


def test_registry_api_is_generic():
    """注册/解析入口签名**不含任何维表参数** —— 参数只应是材料 key。"""
    from core.material_tech import register_material_tech, resolve_material_tech
    src = inspect.getsource(register_material_tech) + inspect.getsource(resolve_material_tech)
    for bad in ('MATERIAL_DIMS', 'RAW_DIMS', 'GOODS_DIMS'):
        assert bad not in src, bad


def test_module_is_a_registry_not_a_hardcoded_table():
    """模块须同时具备「注册表 + 注册函数」两个通用入口。"""
    from core.material_tech import MATERIAL_TECH_UNLOCKS, register_material_tech
    assert isinstance(MATERIAL_TECH_UNLOCKS, dict)
    assert callable(register_material_tech)