# -*- coding: utf-8 -*-
"""new_vector_modular 纸娃娃资产契约测试。

只验证资产与打包/忽略契约，不接生产合成器：
- 31 个 PNG 全部存在、可解码、800x1000、RGBA（或可转 RGBA）；
- 10 个关键槽位目录非空；
- SongZuo.spec 含 assets/paperdoll/new_vector_modular 的 datas 条目；
- 该资产目录不是 .gitignore 忽略项。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from PIL import Image

REPO = Path(__file__).resolve().parents[3]
ASSET_DIR = REPO / "game" / "assets" / "paperdoll" / "new_vector_modular"
SPEC_PATH = REPO / "game" / "SongZuo.spec"
EXPECTED_COUNT = 31
EXPECTED_SIZE = (800, 1000)
KEY_DIRS = (
    "accessories", "bases", "beards", "brows", "eyes",
    "faces", "hats", "mouth", "nose", "robes",
)


def test_new_vector_modular_asset_contract():
    assert ASSET_DIR.is_dir(), f"资产目录不存在: {ASSET_DIR}"
    files = sorted(p for p in ASSET_DIR.rglob("*") if p.is_file())
    assert len(files) == EXPECTED_COUNT, f"文件数应为 {EXPECTED_COUNT}，实际 {len(files)}"

    for path in files:
        assert path.suffix.lower() == ".png", f"非 PNG 文件: {path}"
        assert path.stat().st_size > 0, f"空文件: {path}"
        with Image.open(path) as im:
            assert im.size == EXPECTED_SIZE, f"尺寸错误: {path} -> {im.size}"
            assert im.mode == "RGBA" or im.convert("RGBA").mode == "RGBA", (
                f"模式不可转 RGBA: {path} -> {im.mode}"
            )
            im.verify()

    for dirname in KEY_DIRS:
        d = ASSET_DIR / dirname
        assert d.is_dir(), f"关键目录缺失: {d}"
        assert any(p.is_file() for p in d.iterdir()), f"关键目录为空: {d}"


def test_spec_has_new_vector_modular_datas_entry():
    text = SPEC_PATH.read_text(encoding="utf-8")
    assert "assets/paperdoll/new_vector_modular" in text, "SongZuo.spec 缺少 datas 目标路径"
    assert "os.path.join(_ROOT, 'assets', 'paperdoll', 'new_vector_modular')" in text, (
        "SongZuo.spec 缺少 new_vector_modular 的 source 路径"
    )


def test_new_vector_modular_is_not_gitignored():
    rel = "game/assets/paperdoll/new_vector_modular"
    proc = subprocess.run(
        ["git", "-C", str(REPO), "check-ignore", "-q", "--", rel],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0, f"资产目录被 .gitignore 忽略: {rel}"
