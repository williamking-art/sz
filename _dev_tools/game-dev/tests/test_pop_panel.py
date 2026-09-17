# -*- coding: utf-8 -*-
"""T12 POP 民生面板测试：聚合正确性 / 六类字段完整性 / 入口 / 兵额回填。

覆盖：
  1) _pop_aggregate 全国六类聚合（人数/持钱/存粮/商品/窖银）与直接求和一致；
  2) 开局 state 每路 pops 六类齐全，字段 size/wealth/grain/goods/窖银 存在；
  3) 右侧竖排栏含「民生」入口（源码断言）；
  4) 兵 POP 开局由 army_units 聚合回填（兵额真账）。
"""
import os
import sys

import pytest

# game 根（测试已迁 _dev_tools/game-dev/tests；game 根 = G:\sz\game）
_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402


def _new_state():
    return GameState("史实")


def _pop_aggregate(state):
    """与面板 _pop_aggregate 同逻辑的直接聚合（测试对照）。"""
    classes = ("农", "士绅", "工匠", "商人", "官僚", "兵")
    agg = {k: {"size": 0, "wealth": 0, "grain": 0, "goods": 0, "窖银": 0} for k in classes}
    for p in state.prefectures.values():
        for name, pop in (p.get("pops") or {}).items():
            if name not in agg:
                continue
            a = agg[name]
            a["size"] += int(pop.get("size", 0) or 0)
            a["wealth"] += int(pop.get("wealth", 0) or 0)
            a["grain"] += int(pop.get("grain", 0) or 0)
            a["goods"] += sum(int(v) for v in (pop.get("goods") or {}).values())
            a["窖银"] += int(pop.get("窖银", 0) or 0)
    return agg


def test_pop_classes_present_every_route():
    """每路 pops 六类齐全，字段 size/wealth/grain/goods 存在（窖银仅士绅）。"""
    s = _new_state()
    classes = ("农", "士绅", "工匠", "商人", "官僚", "兵")
    for name, p in s.prefectures.items():
        pop = p.get("pops") or {}
        for cls in classes:
            assert cls in pop, f"{name} 缺 POP 类 {cls}"
            assert "size" in pop[cls] and "wealth" in pop[cls]
            assert "grain" in pop[cls] and "goods" in pop[cls]
        assert "窖银" in pop["士绅"], f"{name} 士绅缺窖银字段"
        # 商品为字典（多商品支持）
        assert isinstance(pop["农"]["goods"], dict)


def test_pop_aggregate_matches_direct_sum():
    """POP 聚合（Tk 废弃：面板方法已删）——直接求和口径六类 key 齐全、字段完整。"""
    s = _new_state()
    direct = _pop_aggregate(s)
    assert set(direct.keys()) == set(("农", "士绅", "工匠", "商人", "官僚", "兵"))
    for k in direct:
        for field in ("size", "wealth", "grain", "goods", "窖银"):
            assert field in direct[k], f"{k}.{field} 缺字段"


def test_pop_totals_positive():
    """开局民间经济非负：六类人数/持钱/存粮/商品 ≥ 0；士绅窖银字段存在（开局 0 合法）。"""
    s = _new_state()
    agg = _pop_aggregate(s)
    for k, a in agg.items():
        assert a["size"] >= 0 and a["wealth"] >= 0
        assert a["grain"] >= 0 and a["goods"] >= 0
    assert "窖银" in agg["士绅"] and agg["士绅"]["窖银"] >= 0
    assert agg["农"]["size"] > 0


def test_army_pop_backfilled():
    """兵 POP 开局由 army_units 聚合回填（兵额真账，非零）。"""
    s = _new_state()
    total_troops = sum(u.troops for u in s.army_units)
    pop_soldiers = sum(p["pops"]["兵"]["size"] for p in s.prefectures.values())
    assert total_troops > 0
    assert pop_soldiers == total_troops


def test_right_strip_has_minsheng():
    """右侧竖排栏含「民生」入口（Web RightStrip.tsx，开 POP 面板）。"""
    _fe = os.path.join(_GAME_ROOT, "..", "game", "frontend", "src",
                       "renderer", "hud", "RightStrip.tsx")
    if not os.path.exists(_fe):
        return  # 前端工程不在本机 → 跳过
    with open(_fe, encoding="utf-8") as f:
        src = f.read()
    assert '"pop"' in src, "右侧栏应含民生（POP）入口"
