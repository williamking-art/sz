# -*- coding: utf-8 -*-
"""新兵种（branch_registry）测试：注册门槛/成本守恒/封顶/上限/契约拒绝式。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import BRANCH_SPEC, EQUIP_PRICE, RECRUIT_MONTHS, BRANCH_REGISTRY_MAX  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.registries import (  # noqa: E402
    register_branch, deactivate_branch, build_branch_std, tech_gate_ok,
)


def _new_state():
    return GameState("史实")


def _contract(name="神臂弩"):
    return {"name": name, "base_branch": "弓弩兵", "tier": "禁军", "troops": 10000,
            "spec": {"specialize": "equipment", "tier": "中", "position": "平原",
                     "focus": ""}}   # 默认无科技门槛（基础特化）


def test_constants():
    """BRANCH_SPEC/EQUIP_PRICE/RECRUIT_MONTHS/上限。"""
    assert EQUIP_PRICE["枪刀"] == 5 and EQUIP_PRICE["战马"] == 50
    assert RECRUIT_MONTHS == 6
    assert BRANCH_REGISTRY_MAX == 3
    assert abs(BRANCH_SPEC["specialize"]["equip"](1.0) - 1.67) < 0.01   # 1+0.67×1.0
    assert BRANCH_SPEC["specialize"]["equip"](2.0) == 2.0               # 封顶 2.0
    assert abs(BRANCH_SPEC["despecialize"]["equip"](1.0) - 0.67) < 0.01  # 1−0.33×1.0


def test_register_ok_conservation():
    """注册成功 + 成本守恒：国库 -cost == 兵 POP 粮饷 + 军械库装备。"""
    s = _new_state()
    t0 = s.treasury
    r = register_branch(s, _contract(), created_by="蔡京")
    assert r["ok"] is True
    cost = t0 - s.treasury
    assert cost > 0
    assert s.branch_registry["神臂弩"]["active"] is True
    assert s.branch_registry["神臂弩"]["usage"] == 0
    # 兵 POP 粮饷入账（国库减的至少部分回流）
    pop_gain = sum(p["pops"]["兵"]["wealth"] for p in s.prefectures.values())
    assert pop_gain > 0


def test_register_branch_sunk_seats_conservation():
    """U0001f534 下沉局：`register_branch` 兵粮饷必须落**州府真账**，路级仅派生镜像。

    这是 `test_register_ok_conservation` 的下沉版——后者用未下沉的 `GameState("史实")`，
    路级 `pops` 本身即真账，直写也能"守恒通过"，故缺陷逃逸。本测试跑 `new_game()`（已下沉
    seats）+ `install_all_guards`，证明兵粮饷**进州府账、不进路级直写**，路级镜像与 Σ治所
    恒等，且守卫零直写（否则 `sync_route_pops` 会把直写撤销，粮饷凭空丢失）。
    """
    from core.commands import new_game
    from core.foundation.ledger.pop_bridge import (
        install_all_guards, pops_guard_violations, reset_pops_guard,
    )

    state = new_game()
    assert install_all_guards(state) > 0
    reset_pops_guard()

    # Σ治所兵 wealth（含初始存量）
    def _seat_bing_wealth(s):
        tot = 0
        for pdata in s.prefectures.values():
            for seat in (pdata.get("seats") or {}).values():
                row = (seat.get("pops") or {}).get("兵")
                if isinstance(row, dict):
                    tot += int(row.get("wealth", 0) or 0)
        return tot

    before_seat = _seat_bing_wealth(state)
    before_route = sum(int(p["pops"]["兵"].get("wealth", 0) or 0)
                       for p in state.prefectures.values())
    # 下沉局路级是派生镜像：应等于 Σ治所
    assert before_route == before_seat, "下沉局路级 pops 应为 Σ治所派生镜像"

    state.treasury = max(state.treasury, 10_000_000)
    state.tech["level"] = 70  # 确保科技门槛过（弓弩系）
    r = register_branch(state, _contract(), created_by="枢密院")
    assert r["ok"] is True, r.get("msg")

    after_seat = _seat_bing_wealth(state)
    after_route = sum(int(p["pops"]["兵"].get("wealth", 0) or 0)
                      for p in state.prefectures.values())

    # 1) 州府真账：粮饷确实入账（不减不丢）
    assert after_seat > before_seat, "兵粮饷未进州府真账（下沉桥接失败）"
    # 2) 路级镜像与 Σ治所恒等（直写若残留会被 sync 撤销 → 二者分叉）
    assert after_route == after_seat, (
        "路级兵 wealth 与 Σ治所分叉——存在未桥接直写被 sync_route_pops 撤销")
    # 3) 守卫零直写：全程无绕过桥接的路级写
    v = pops_guard_violations()
    assert not v, v[:5]


def test_register_duplicate_and_cap():
    """重名拒绝 + 软约束（第 N 个成本递增，不硬拒）。"""
    s = _new_state()
    r1 = register_branch(s, _contract("神臂弩"))
    assert r1["ok"] is True
    r2 = register_branch(s, _contract("神臂弩"))
    assert r2["ok"] is False and "已注册" in r2["msg"]
    # 软约束：注册多个兵种不硬拒（成本 ×(1+0.1×(N-1)) 递增）
    assert register_branch(s, _contract("胜捷军"))["ok"] is True
    assert register_branch(s, _contract("水虎翼"))["ok"] is True
    assert register_branch(s, _contract("拐子马"))["ok"] is True   # 第 4 个也允许（去硬上限）
    assert "拐子马" in s.branch_registry


def test_register_tech_gate():
    """科技门槛：弓弩系（archery/level <60）拒绝；火器系 gunpowder 门槛（中档需 65）。"""
    s = _new_state()
    c = _contract("强弩新军")
    c["spec"]["focus"] = "弓弩"
    s.tech["level"] = 30
    r = register_branch(s, c)
    assert r["ok"] is False and "科技不足" in r["msg"]
    # 科技达标
    s.tech["level"] = 70
    r2 = register_branch(s, c)
    assert r2["ok"] is True
    # 火器系（gunpowder 门槛：中档 → 65）
    s2 = _new_state()
    c2 = _contract("突火枪军")
    c2["spec"]["focus"] = "火器"
    s2.tech["gunpowder"] = 20
    assert register_branch(s2, c2)["ok"] is False
    s2.tech["gunpowder"] = 70
    assert register_branch(s2, c2)["ok"] is True


def test_register_cost_insufficient():
    """成本不足拒绝（国库 < 招募费；科技先过）。"""
    s = _new_state()
    s.tech["level"] = 70   # 先过科技
    s.treasury = 100       # 穷国库
    r = register_branch(s, _contract())
    assert r["ok"] is False and "国库不足" in r["msg"]


def test_branch_std_caps():
    """封顶：粮饷 ≤2.0×、装备特化 ≤2.0×（build_branch_std 派生）。"""
    s = _new_state()
    std = build_branch_std(s, "神臂弩", base_branch="弓弩兵",
                           spec={"specialize": "equipment", "tier": "极", "position": "平原"})
    assert std["pay"] <= 2.0 * 1.6     # 弓弩兵 pay 基准 0.40 × 2.0 封顶
    for k, v in std["equip"].items():
        assert v <= 2.0 * 1.6 or k == "战马"


def test_roundtrip_and_deactivate():
    """存档往返 + 裁撤（active=False 保留历史）。"""
    from core.save_load import save_game, load_game, _slot_path
    s = _new_state()
    register_branch(s, _contract("胜捷军"))
    assert save_game(s, slot=3)
    s2 = load_game(3)
    assert s2 is not None
    assert "胜捷军" in s2.branch_registry
    assert deactivate_branch(s2, "胜捷军")["ok"] is True
    assert s2.branch_registry["胜捷军"]["active"] is False
    if os.path.exists(_slot_path(3)):
        os.remove(_slot_path(3))
