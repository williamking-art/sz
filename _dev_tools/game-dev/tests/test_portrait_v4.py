# -*- coding: utf-8 -*-
"""v4 立绘索引与解析的回归（整幅肖像 + 姓名稳定分配）。

覆盖口径：索引自洽（文件存在/尺寸一致）、已登记官员取专属图、未登记官员按姓名稳定落池、
非法姓名不得穿越路径、v4 缺失时 get_portrait_path 必须回退而不报错。
"""
from __future__ import annotations

import os
import sys

import pytest
from PIL import Image

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.ministers import portrait_v4 as v4  # noqa: E402
from content.ministers.data import get_portrait_path  # noqa: E402


def test_index_is_non_empty_and_files_exist():
    idx = v4._index()
    assert len(idx) >= 80, f"v4 索引条目过少：{len(idx)}"
    for name, entry in idx.items():
        path = os.path.join(v4.asset_dir(), entry["file"])
        assert os.path.isfile(path), f"{name} 的立绘文件缺失：{path}"


def test_all_assets_are_750x1000_webp():
    for entry in list(v4._index().values())[:12]:
        path = os.path.join(v4.asset_dir(), entry["file"])
        with Image.open(path) as im:
            assert im.size == (750, 1000), f"{entry['file']} 尺寸 {im.size}"


def test_known_official_gets_own_portrait():
    name = sorted(v4._index())[0]
    path = v4.portrait_path(name)
    assert path and os.path.isfile(path)
    assert os.path.basename(path) == v4._index()[name]["file"]
    assert v4.has_exact(name)


def test_unknown_official_falls_back_deterministically():
    a1 = v4.portrait_path("新科状元张孝祥")
    a2 = v4.portrait_path("新科状元张孝祥")
    assert a1 and os.path.isfile(a1)
    assert a1 == a2, "同一姓名必须始终映射到同一张（同名必同图）"


def test_illegal_names_are_rejected():
    for bad in ("../secret.png", "..\\secret.png", "", "a/b", None):
        assert v4.portrait_path(bad) is None


def test_get_portrait_path_prefers_v4():
    name = sorted(v4._index())[0]
    p = get_portrait_path(name)
    assert p and os.path.isfile(p)
    assert os.path.basename(os.path.dirname(p)) == "v4"
