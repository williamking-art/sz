# -*- coding: utf-8 -*-
"""P-B0 · 商品品目层定向回归（规格 `specs/economy/produce-space-price`）

锁定：
1. **覆盖精确**：`GOODS_CATEGORY` 的键集 == `GOODS_DIMS`（不多不少），`validate()` 返回空；
2. **一维一品目 + 品目非空**：每个品目下都有维，且反向映射一致；
3. **缺失 ≠ "其他"**：未知维 `category_of` 返回 `None`（不臆造归类）；
4. **运行时新增维只告警、不拒绝**：`register_raw_material` 仍返回 dim，且留下 WARNING。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data_constants import GOODS_DIMS  # noqa: E402
from content.goods_category import (  # noqa: E402
    CATEGORY_ORDER, GOODS_CATEGORY, category_goods, category_of, note_new_dim, validate,
)


def test_coverage_is_exact():
    """键集必须与 GOODS_DIMS 完全相等；validate 必须零问题。"""
    assert set(GOODS_CATEGORY) == set(GOODS_DIMS), (
        "品目表与商品目录不一致：多=%s 缺=%s" % (
            sorted(set(GOODS_CATEGORY) - set(GOODS_DIMS)),
            sorted(set(GOODS_DIMS) - set(GOODS_CATEGORY))))
    assert validate() == []


def test_every_category_declared_and_nonempty():
    for c in CATEGORY_ORDER:
        dims = category_goods(c)
        assert dims, "空品目：%s" % c
        assert all(category_of(d) == c for d in dims), c


def test_no_duplicate_category_names():
    assert len(CATEGORY_ORDER) == len(set(CATEGORY_ORDER))


def test_unknown_dim_returns_none_not_other():
    """缺失≠其它：未登记维返回 None，绝不臆造归入「其他」。"""
    assert category_of("这不是一个商品维") is None
    assert note_new_dim("这不是一个商品维") is None      # 只告警，不抛


def test_runtime_registration_warns_but_does_not_raise(caplog):
    """`register_raw_material` 遇未登记品目的新维：仍注册成功，但留 WARNING。"""
    from content import data_constants as dc

    dim = "P_B0测试新维"
    try:
        with caplog.at_level("WARNING"):
            got = dc.register_raw_material(dim, "斤", 10)
        assert got == dim
        assert any("未登记品目" in (r.getMessage() or "") for r in caplog.records), \
            "未登记的品目未产生 WARNING（静默 = 违反项目禁区）"
        # 注册后仍无品目（不是自动塞进「其他」）
        assert category_of(dim) is None
    finally:
        # 清理模块级表，避免污染其它用例
        for name, seq in (("RAW_DIMS", dc.RAW_DIMS), ("RESOURCE_DIMS", dc.RESOURCE_DIMS)):
            if dim in seq:
                seq.remove(dim)
        dc.MATERIAL_PRICE_BASE.pop(dim, None)
        dc.RAW_UNITS.pop(dim, None)


def test_validate_accepts_extra_dims():
    """`validate(extra_dims=...)` 能把运行时新维纳入校验（供启动自检用）。"""
    problems = validate(extra_dims=["P_B0待验新维"])
    assert problems and any("P_B0待验新维" in p for p in problems)
