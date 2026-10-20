# -*- coding: utf-8 -*-
"""拆分 / 合并 / 换帅 断言：守恒、结构、守卫，以及"8 键严格对齐参考图"。"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.commands import issue_military_order, _MILITARY_BUTTON_ACTS   # noqa: E402
from core.game_state import GameState                                   # noqa: E402

REFERENCE_EIGHT = {"地图调度", "扩编", "拆分", "合并", "整编", "换帅", "裁撤", "改名"}


def _state():
    s = GameState("史实")
    s.prestige = 999   # 本文件验证编制操作细节，走皇威直行路径
    return s


def _two_same_station(s):
    by = {}
    for u in s.army_units:
        by.setdefault(u.station, []).append(u)
    for _st, us in by.items():
        if len(us) >= 2:
            return us[0], us[1]
    return None, None


def _pool(s, st):
    p = s.prefectures[st]
    return (int(p["pops"]["农"]["size"]) + int(p.get("refugees", 0))
            + int(p["pops"]["兵"]["size"]))


def test_reference_eight_buttons_only():
    """**按钮集合严格等于参考图 8 键**——防"我替用户改需求"（此前多塞过「操练」）。"""
    assert set(_MILITARY_BUTTON_ACTS) == REFERENCE_EIGHT, \
        f"按钮集合与参考图不符：多={set(_MILITARY_BUTTON_ACTS) - REFERENCE_EIGHT} 少={REFERENCE_EIGHT - set(_MILITARY_BUTTON_ACTS)}"
    assert "尚无契约" in issue_military_order(_state(), _state().army_units[0].unit_id, "操练")


def test_split_conserves_troops_pop_and_equipment():
    """拆分：Σ兵额不变、**兵 POP 不变**、ΣPOP 不变、欠饷留原军、新单位番号/军籍/驻地正确。"""
    s = _state()
    a, _b = _two_same_station(s)
    n0, t0 = len(s.army_units), sum(a.branches.values())
    st = a.station
    pop0, pool0 = int(s.prefectures[st]["pops"]["兵"]["size"]), _pool(s, st)
    eq0 = sum(int(v) for v in (a.equip or {}).values())

    msg = issue_military_order(s, a.unit_id, "拆分", new_name="别部试")
    assert "别立一军" in msg, msg

    new = s.army_units[-1]
    assert len(s.army_units) == n0 + 1
    assert new.unit_id != a.unit_id and new.unit_id.startswith(a.unit_id)
    assert new.tier == a.tier and new.station == st and new.army_name == "别部试"
    assert sum(a.branches.values()) + sum(new.branches.values()) == t0, "Σ兵额守恒"
    assert int(s.prefectures[st]["pops"]["兵"]["size"]) == pop0, "兵 POP 是兵额总账，拆分不得改变"
    assert _pool(s, st) == pool0, "Σ(农+流民+兵) 不变"
    assert new.arrears == 0, "欠饷随原番号，不记到新单位"
    assert sum(int(v) for v in (a.equip or {}).values()) + \
        sum(int(v) for v in (new.equip or {}).values()) == eq0, "Σ装备守恒"


def test_split_then_merge_returns_to_original():
    """**拆分 → 合并**往返：兵额与编制单位数回到原状。"""
    s = _state()
    a, _b = _two_same_station(s)
    t0, n0 = sum(a.branches.values()), len(s.army_units)
    issue_military_order(s, a.unit_id, "拆分")
    new = s.army_units[-1]
    issue_military_order(s, a.unit_id, "合并", merge_unit_id=new.unit_id)
    assert len(s.army_units) == n0, "应回到原编制单位数"
    assert sum(a.branches.values()) == t0, "应回到原兵额"


def test_merge_requires_same_route_and_tier():
    """跨路 / 跨军籍合并必须被拒，且零副作用。"""
    s = _state()
    a = s.army_units[0]
    other = next(u for u in s.army_units if u.station != a.station)
    n0 = len(s.army_units)
    msg = issue_military_order(s, a.unit_id, "合并", merge_unit_id=other.unit_id)
    assert "同一路、同一军籍" in msg, msg
    assert len(s.army_units) == n0
    # 同路不同军籍（每路禁/厢/乡各一支）
    pair = _two_same_station(s)
    if pair[0] is not None and pair[0].tier != pair[1].tier:
        msg2 = issue_military_order(s, pair[0].unit_id, "合并", merge_unit_id=pair[1].unit_id)
        assert "同一路、同一军籍" in msg2


def test_merge_sums_arrears_and_troops():
    """合并：兵额与**欠饷相加**（存续番号承接旧欠）。"""
    s = _state()
    a, b = _two_same_station(s)
    # 造两支同路同军籍（拆分一次即得）
    issue_military_order(s, a.unit_id, "拆分")
    other = s.army_units[-1]
    a.arrears, other.arrears = 100, 250
    ta, to = sum(a.branches.values()), sum(other.branches.values())
    issue_military_order(s, a.unit_id, "合并", merge_unit_id=other.unit_id)
    assert a.arrears == 350, "欠饷应相加"
    assert sum(a.branches.values()) == ta + to


def test_commander_is_display_only_with_guards():
    """换帅：指派留痕；**只动展示层**；无此大臣 / 一人领两军 → 拒绝。"""
    s = _state()
    a, b = _two_same_station(s)
    # 在朝大臣名册 = state.loyalty 的键（与 core 侧校验同源）
    name = next(iter(s.loyalty))
    assert name, "前提：存在在朝大臣"

    before = (sum(a.branches.values()), a.morale, a.training, a.station, dict(a.branches))
    msg = issue_military_order(s, a.unit_id, "换帅", commander=name)
    assert "统帅" in msg and a.commander == name, msg
    assert (sum(a.branches.values()), a.morale, a.training, a.station, dict(a.branches)) == before, \
        "换帅不得触及真账（战力/士气/兵额）"

    assert "一人不得领两军" in issue_military_order(s, b.unit_id, "换帅", commander=name)
    assert "无此大臣" in issue_military_order(s, b.unit_id, "换帅", commander="查无此人")
    assert "须指定统帅姓名" in issue_military_order(s, b.unit_id, "换帅")
    assert not getattr(b, "commander", ""), "被拒者不得留下统帅"
