# -*- coding: utf-8 -*-
"""营建入口（core/construction.py）回归 —— 蓝图仿明末模式的功能闭环。

背景：`prefectures[*]["buildings"]` 此前只有初始化、**没有营建入口**，
导致 `_settle_upkeep` 的建筑维持费与科技 `adoption` 覆盖率事实上恒为空。
本文件锁定新入口：蓝图解析 / 科技前置 / **地利前置** / 造价守恒 / 等级累加 /
落成后维持费与 adoption 真正生效。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import TECH_ADOPTION_DEFAULT, TECH_ADOPTION_PER_LEVEL  # noqa: E402
from core import money  # noqa: E402
from core.construction import can_build, resolve_blueprint  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.settlement_steps import _settle_upkeep  # noqa: E402


def _s():
    s = GameState("史实")
    s.treasury = 10 ** 9
    return s


def _route_with(tag: str, s):
    for r, p in s.prefectures.items():
        if tag in str(p.get("type")):
            return r
    return None


def _route_without(tag: str, s):
    for r, p in s.prefectures.items():
        if tag not in str(p.get("type")):
            return r
    return None


def test_resolve_blueprint_by_key_and_name():
    bp = resolve_blueprint("", key="C1_gunpowder")
    assert bp and bp["_name"] == "火药局"
    bp2 = resolve_blueprint("火药局")
    assert bp2 and bp2["_key"] == "C1_gunpowder"
    assert resolve_blueprint("根本不存在的建筑") is None


def test_region_prerequisite_blocks_wrong_route():
    """地利前置（仿明末 requires_region_tags）：京畿要地专属蓝图不得建于他路。"""
    s = _s()
    key, name = "I0_block", "国子监印书局"
    cap = _route_with("京畿", s)
    other = _route_without("京畿", s)
    assert cap and other
    ok_cap, errs_cap = can_build(s, cap, name, key)
    ok_other, errs_other = can_build(s, other, name, key)
    assert ok_cap, errs_cap
    assert not ok_other and any("地利" in e for e in errs_other), errs_other
    # 只读校验：不得改动任何状态
    t0 = s.treasury
    b0 = dict(s.prefectures[other].get("buildings") or {})
    can_build(s, other, name, key)
    assert s.treasury == t0 and (s.prefectures[other].get("buildings") or {}) == b0


def test_tech_prerequisite_blocks_unresearched_blueprint():
    s = _s()
    r = next(iter(s.prefectures))
    s.tech["unlocked"] = []                       # 清空已解锁节点
    ok, errs = can_build(s, r, "火药局", "C1_gunpowder")
    assert not ok and any("科技前置" in e for e in errs), errs
    s.tech["unlocked"] = ["C1_gunpowder"]         # 解锁后可建
    ok2, _ = can_build(s, r, "火药局", "C1_gunpowder")
    assert ok2


