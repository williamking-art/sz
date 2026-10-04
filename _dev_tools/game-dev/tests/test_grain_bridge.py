# -*- coding: utf-8 -*-
"""**G-3 读写桥** 定向回归（2026-10-04）。

桥接层存在的理由：`pops[].grain` 写入 262 / 读取 128 处，逐点改会在某个中间态
出现「写 goods、读 .grain」的双源不一致，余额静默漂移无人察觉。
过渡期用桥保证：**同一载体二选一，绝不双写**。
"""
import os
import sys

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from core.grain_bridge import (grain_add, grain_get,        # noqa: E402
                              grain_set, grain_target)


def test_legacy_carrier_reads_grain_field():
    """未迁移载体：读旧 `.grain` 字段。"""
    p = {"grain": 100}
    assert grain_target(p) == "legacy"
    assert grain_get(p) == 100


def test_migrated_carrier_reads_goods_bucket():
    """已迁移载体：读 `goods[米]`。"""
    p = {"goods": {"米": 100, "麦": 30}, "grain": 999}
    assert grain_target(p) == "goods"
    assert grain_get(p) == 130, "已迁移时应读 goods 米+麦，不读旧字段"


def test_never_double_writes():
    """🔴 核心：任一次写只落一个载体，绝不同改两者。"""
    # 未迁移：写只动 .grain，不建 goods
    p = {"grain": 100}
    grain_add(p, 50)
    assert p["grain"] == 150 and "米" not in p.get("goods", {})
    # 已迁移：写只动 goods，不动 .grain
    q = {"goods": {"米": 100}, "grain": 5}
    grain_set(q, 77)
    assert q["goods"]["米"] == 77 and q["grain"] == 5, "已迁移载体不得回写 .grain"


def test_get_returns_none_when_absent():
    """缺失 ≠ 0：两载体皆无粮 ⇒ 返回 `None` 而非 0。"""
    assert grain_get({"goods": {"木": 5}}) is None
    assert grain_get({}) is None
    assert grain_get(None) is None


def test_add_creates_carrier_and_floors_at_zero():
    """无基线时从 0 起算并如实建载体；扣减不为负。"""
    p = {}
    assert grain_add(p, 10) == 10 and grain_target(p) == "legacy"
    assert grain_add(p, -999) == 0, "扣减不得为负"
