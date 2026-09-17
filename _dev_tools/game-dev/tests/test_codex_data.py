# -*- coding: utf-8 -*-
"""T7 图鉴数据测试：8 类别条目构建（只读常量 / 脱敏 / 关联链接完整性）。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.codex_data import get_codex_data  # noqa: E402  （Tk 废弃：数据迁出 ui）


def test_codex_eight_categories():
    """8 类别全部存在且非空。"""
    data = get_codex_data()
    for key in ("building", "minister", "org", "tech", "branch", "region",
                "mechanism", "event"):
        assert key in data, f"缺类别：{key}"
        assert data[key], f"类别为空：{key}"


def test_codex_minister_desensitized():
    """脱敏：大臣条目字段绝不包含 loyalty/corruption。"""
    data = get_codex_data()
    for e in data["minister"]:
        for lab, _val in e.get("fields", []):
            assert lab not in ("loyalty", "corruption", "贪腐", "忠诚数值"), \
                f"图鉴泄露隐藏字段：{e['name']} -> {lab}"
        assert "loyalty" not in str(e.get("desc", "")).lower()
        assert "corruption" not in str(e.get("desc", "")).lower()


def test_codex_tech_count_matches_source():
    """科技类别条目数 = TECH_NODES 实数 + 1（总览）。"""
    from content.data import TECH_NODES
    data = get_codex_data()
    assert len(data["tech"]) == len(TECH_NODES) + 1


def test_codex_links_targets_exist():
    """关联跳转目标有效：links 中的（类别, 条目 key）必须真实存在。"""
    data = get_codex_data()
    for cat, entries in data.items():
        keys = {e["key"] for e in entries}
        for e in entries:
            for tcat, tkey, _tname in e.get("links", []):
                assert tcat in data, f"{e['name']} 链接到不存在类别 {tcat}"
                assert tkey in {x["key"] for x in data[tcat]}, \
                    f"{e['name']} 链接到不存在条目 {tcat}:{tkey}"


def test_codex_building_tech_links():
    """建筑↔科技关联：科技解锁建筑（火药局/水利等）应链回科技节点。"""
    data = get_codex_data()
    tech_keys = {e["key"] for e in data["tech"]}
    for e in data["building"]:
        for _tcat, tkey, _tname in e.get("links", []):
            assert tkey in tech_keys, f"建筑 {e['name']} 关联科技 {tkey} 不存在"


def test_codex_entries_have_name_desc():
    """条目完整性：每条有 name 与 desc 字段。"""
    data = get_codex_data()
    for cat, entries in data.items():
        for e in entries:
            assert e.get("name"), f"{cat} 条目缺 name"
            assert "desc" in e, f"{cat}:{e.get('name')} 缺 desc"
