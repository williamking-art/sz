# -*- coding: utf-8 -*-
"""**卡1.4 · 《宋史》州级贡物差异化** 定向回归（2026-10-04）。

把 195 条州级贡物接进州府桶权重，使各地**真的产出不同的物料**。

口径（本组一并锁住）：
1. 映射表**无拼写错误**（validate_map() 空）；
2. 贡物是**存在性证据**，无记录 ≠ 不产 ⇒ **不归零**，只作权重增强；
3. 差异化**现阶段只到路级**（治所级精确匹配仅 7/126，子串匹配已否决）；
4. 数据缺失**不崩**，退回纯人口权重。
"""
import os
import sys

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

import core.material_holding as mh                      # noqa: E402
from content.seat_products import (SEAT_PRODUCT_MAP,     # noqa: E402
                                   validate_map)


def test_mapping_table_has_no_typos():
    """映射表目标维必须都在目录内 —— 否则拼写错误会落到不存在的维上。"""
    bad = validate_map()
    assert not bad, "非法映射项：%s" % bad


def test_mapping_covers_significant_share():
    """映射表非空且覆盖多个维（防止将来被清空）。"""
    assert len(SEAT_PRODUCT_MAP) >= 50
    dims = set()
    for v in SEAT_PRODUCT_MAP.values():
        dims.update(v)
    assert len(dims) >= 8, "映射应覆盖多个物料维，实得 %s" % sorted(dims)


def test_circuit_tribute_index_loaded():
    """贡物索引应从入库的 JSON 载入（`_dev_tools/sources/songshi/`）。"""
    _TRIB = mh.tribute_circuits()
    assert _TRIB, "贡物索引为空 —— 数据文件缺失或路径错"
    assert len(_TRIB) >= 10


def test_absent_record_is_not_zero():
    """缺失 ≠ 0：无贡物记录的维度不得把权重压成 0。"""
    rt = next(iter(mh.tribute_circuits()))
    w = mh.seat_weights_for(None, rt, "药材")
    if not w:
        return
    assert all(x > 0 for _s, x in w), "权重不得为 0（无贡物记录只代表无证据）"


def test_differentiation_actually_differs():
    """有贡物证据的路，权重应高于同路无证据的维（差异化真实生效）。"""
    found = False
    for rt, dims in mh.tribute_circuits().items():
        if "药材" not in dims:
            continue
        hit = mh.seat_weights_for(None, rt, "药材")
        miss = mh.seat_weights_for(None, rt, "盐")
        if not hit or not miss:
            continue
        assert max(x for _s, x in hit) > max(x for _s, x in miss), (
            "%s 有药材贡物记录，权重应高于无记录的盐" % rt)
        found = True
        break
    assert found, "未找到可用于验证差异化的路"
