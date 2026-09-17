# -*- coding: utf-8 -*-
"""T13 群臣档案测试（Tk 废弃后迁移：面板方法 → core/minister_profile）。

覆盖：
  1) build_minister_profiles：MINISTERS born → 年龄、persona style → 个性、
     A14 简介（缺失时按职司程序生成）；**绝不泄露 loyalty/corruption**；
  2) 全部在册大臣均生成档案（含派系领袖与中枢机构 holders）。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.minister_profile import build_minister_profiles  # noqa: E402


def _new_state():
    return GameState("史实")


def test_minister_profile_basic():
    """档案数据：年龄/职衔/个性/生平齐全，年龄 = 当前年 - born。"""
    s = _new_state()
    prof = build_minister_profiles(s)
    assert "蔡京" in prof
    d = prof["蔡京"]
    assert d["age"] == s.year - 1047          # born 1047
    assert d["role"], "蔡京应有职衔"
    assert d["style"], "蔡京应有性格描述（persona style）"
    assert d["bio"], "蔡京应有生平（A14 简介）"


def test_minister_profile_desensitized():
    """脱敏：档案绝不包含 loyalty/corruption 数值。"""
    s = _new_state()
    prof = build_minister_profiles(s)
    for name in ("蔡京", "韩忠彦", "曾布", "童贯", "种师道"):
        d = prof[name]
        blob = f"{name} {d['role']} {d['style']} {d['bio']}"
        assert "loyalty" not in blob.lower() and "corruption" not in blob.lower()
        assert "0.85" not in blob and "0.78" not in blob   # 蔡京隐藏数值不出现


def test_minister_profile_bio_fallback():
    """无 A14 简介的大臣 → 程序生成生平（职司句），不空。"""
    s = _new_state()
    prof = build_minister_profiles(s)
    d = prof["李清臣"]
    assert d["bio"] and d["bio"].endswith("。")
    assert (d["role"] and d["role"] in d["bio"]) or "门下侍郎" in d["bio"]


def test_minister_profile_covers_all():
    """全部在册大臣均生成档案；派系领袖与中枢 holders 均在档案内。"""
    from content.ministers.data import MINISTERS
    s = _new_state()
    prof = build_minister_profiles(s)
    assert set(prof.keys()) == set(MINISTERS.keys())
    for fn, f in s.factions.items():
        leader = (f or {}).get("leader", "")
        if leader:
            assert leader in prof, f"派系领袖 {leader} 无档案"
    for org, o in (s.central_orgs or {}).items():
        if not isinstance(o, dict) or o.get("abolished"):
            continue
        for title, holder in (o.get("holders") or {}).items():
            if holder:
                assert holder in prof, f"{org}·{title} 持有人 {holder} 无档案"
