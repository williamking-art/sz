# -*- coding: utf-8 -*-
"""**卡1 · 成品口径契约** 定向回归（2026-10-04）。

缺陷：此前 `畜栏` 的 `output_dim='meat'` **不在任何目录**，
⇒ 肉无法经 `goods`/州府桶流转（`GOODS_DIMS` 不含、物资仓也不含）。

本组锁三条契约（`content/data_constants` 顶部「成品口径契约」表）：

1. **登记完整**：每个工坊 recipe 的 `output_dim` 必在 `FINISHED_DIMS`（不得有孤儿产出）；
2. **登记 ≠ 可交易**：`wine`/`meat` 在 `FINISHED_TAX_DIMS` 内 ⇒ 即产即销折钱入内帑，
   **不进**物资仓、**不进**工匠货栈；只有 `FINISHED_DIMS − FINISHED_TAX_DIMS` 可交易；
3. **物资仓口径**：进仓的只有 `RESOURCE_DIMS`，不含任何 `FINISHED_TAX_DIMS` 维。
"""
import os
import sys

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from content.data import (FINISHED_DIMS, FINISHED_TAX_DIMS, GOODS_DIMS,  # noqa: E402
                          RESOURCE_DIMS, WORKSHOP_RECIPES)


def test_no_orphan_workshop_output():
    """契约1：每个工坊产出的成品维都必须已登记（无孤儿产出）。"""
    for name, r in WORKSHOP_RECIPES.items():
        out = r.get("output_dim")
        assert out in FINISHED_DIMS, f"工坊 {name} 产出未登记：{out!r}"


def test_tax_dims_are_registered_but_not_tradeable():
    """契约2：即产即销维已登记，但**不在商品目录**内（登记 ≠ 可交易）。"""
    for d in FINISHED_TAX_DIMS:
        assert d in FINISHED_DIMS, f"{d} 应已登记为成品"
        assert d not in RESOURCE_DIMS, f"{d} 走内帑，不应进物资仓"
    # wine 有价格读数故在商品目录；meat 从不以货物流转，故不在。
    assert "wine" in GOODS_DIMS
    assert "meat" not in GOODS_DIMS, "meat 即产即销，不应作为可流转商品"


def test_pool_dims_exclude_tax_dims():
    """契约3：工匠货栈可交易维 = 成品维 − 即产即销维（settlement_econ._POOL_DIMS 口径）。"""
    pool = tuple(d for d in FINISHED_DIMS if d not in FINISHED_TAX_DIMS)
    # 契约守护的是「**排除即产即销维**」，不是固定成员名单
    # （G-6 产业链扩充已新增 纸/糖 两条可交易链，成员名单会随内容扩充增长）。
    assert {"绸", "布", "纸", "糖"} <= set(pool), f"缺少可交易成品维，实得 {pool}"
    assert not (set(pool) & set(FINISHED_TAX_DIMS)), f"即产即销维不得进池：{pool}"
    assert set(pool) == set(FINISHED_DIMS) - set(FINISHED_TAX_DIMS)
    for d in FINISHED_TAX_DIMS:
        assert d not in pool, f"{d} 不得进工匠货栈"


def test_resource_dims_exclude_tax_dims():
    """物资仓维度不得含任何即产即销维。"""
    assert not (set(RESOURCE_DIMS) & set(FINISHED_TAX_DIMS))