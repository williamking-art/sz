# -*- coding: utf-8 -*-
"""方案 §3.1 第 1 步断言：军令以**编制单位**为对象（定向 / 向后兼容 / POP 守恒）。"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.commands import _apply_military_dispatch        # noqa: E402
from core.game_state import GameState                     # noqa: E402


def _state():
    return GameState("史实")


def _two_same_tier(s):
    """找同一军籍下的两支编制单位（断言"未选中者不动"需要配对）。"""
    by = {}
    for u in s.army_units:
        by.setdefault(u.tier, []).append(u)
    for tier, us in by.items():
        if len(us) >= 2:
            return tier, us[0], us[1]
    return None, None, None


def test_unit_id_targets_single_unit():
    """带 `unit_id` → **只动这一支**；同军籍的其他编制单位不受影响。"""
    s = _state()
    tier, a, b = _two_same_tier(s)
    assert a is not None, "前提：存在同一军籍的两支编制单位"
    a.training = b.training = 10
    msg = _apply_military_dispatch(
        s, "military_dispatch",
        {"army": tier, "action": "操练", "unit_id": a.unit_id, "scale": 3}, "测")
    assert a.training == 16, f"选中单位应 +6，实得 {a.training}"
    assert b.training == 10, "未选中的同军籍单位不得被动到"
    assert a.name in msg or a.unit_id in msg, "回执应指明实际对象"


def test_tier_sweep_is_backward_compatible():
    """不带 `unit_id` → 维持旧行为（按军籍整批），保证旧 AI 契约不破。"""
    s = _state()
    tier, a, b = _two_same_tier(s)
    a.training = b.training = 10
    _apply_military_dispatch(
        s, "military_dispatch", {"army": tier, "action": "操练", "scale": 1}, "测")
    assert a.training == 12 and b.training == 12, "旧行为应仍为整批 +2"


def test_unknown_unit_id_is_rejected_without_side_effect():
    """无效 `unit_id` → 驳回，且**不动任何单位**（防"定向失败却整批执行"）。"""
    s = _state()
    before = [(u.unit_id, u.training, u.station) for u in s.army_units]
    msg = _apply_military_dispatch(
        s, "military_dispatch",
        {"army": "禁军", "action": "操练", "unit_id": "不存在的编制单位"}, "测")
    assert "无此编制单位" in msg
    assert [(u.unit_id, u.training, u.station) for u in s.army_units] == before


def test_dispatch_move_targets_single_unit():
    """「调赴」：`target` 仍是**目的地路**，定向后只调该一支。"""
    s = _state()
    tier, a, b = _two_same_tier(s)
    dest = next(n for n in s.prefectures if n != a.station)
    b_station = b.station
    _apply_military_dispatch(
        s, "military_dispatch",
        {"army": tier, "action": "调赴", "unit_id": a.unit_id, "target": dest}, "测")
    assert a.station == dest
    assert b.station == b_station, "未选中的编制单位不应被调走"


def test_recruit_conserves_population():
    """增募（**编制单位定向**）：丁口从 `农`/流民出，兵 POP 同额入 —— **Σ不变**。"""
    s = _state()
    tier, a, _b = _two_same_tier(s)
    st = a.station
    if st not in s.prefectures:
        st = next(iter(s.prefectures))
        a.station = st
    p = s.prefectures[st]
    p["refugees"] = 50_000
    p["pops"]["农"]["size"] = max(int(p["pops"]["农"]["size"]), 200_000)
    s.treasury = max(s.treasury, 10_000_000)

    def _pool():
        return (int(p["pops"]["农"]["size"]) + int(p.get("refugees", 0))
                + int(p["pops"]["兵"]["size"]))

    before = _pool()
    before_branches = sum(a.branches.values())
    _apply_military_dispatch(
        s, "military_dispatch",
        {"army": tier, "action": "增募", "unit_id": a.unit_id, "scale": 2}, "测")
    assert _pool() == before, "Σ(农 + 流民 + 兵) 必须不变（POP 挂载律）"
    assert sum(a.branches.values()) == before_branches + 4000, "兵额真账=Σbranches 应 +4000"
    assert a.troops == sum(a.branches.values())
