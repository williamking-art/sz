# -*- coding: utf-8 -*-
"""2026-10-20 修复批**复审**发现的回归用例（Lead）。

覆盖两处修复副作用：
1. P0-4 `_turn` 严格门控会误伤**跨回合执行**的同一批诏令（复述门挂起 / M2a 待定）：
   槽位带 `_decree_titles` 且诏令仍在待行/执行时，裁决必须保留；不同批诏令必须不采信。
2. `region_admin._deduct_cost` 以路级镜像判余额：镜像与治所真账不一致时会少扣/虚报已付。
   现改为以治所真账为准（未下沉才回落镜像）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.commands import new_game  # noqa: E402
from core.domains.diplomacy import region_admin as RA  # noqa: E402
from core.domains.politics.decree_duration import (  # noqa: E402
    resolve_decree_timing, slot_is_current)


class _SlotState:
    def __init__(self, turn=5, pending=None, active=None):
        self.turn = turn
        self.pending_decrees = list(pending or [])
        self.active_decrees = list(active or [])
        self.pending_secret_decrees = []


# ---------------------------------------------------------------- ① 槽位跨回合
def test_slot_same_decree_across_turns_is_kept():
    s = _SlotState(turn=5, pending=[{"title": "甲令"}])
    slot = {"execution_timing": "长期", "_turn": 4, "_decree_titles": ["甲令"]}
    assert slot_is_current(s, slot), "同一道诏令跨回合执行时不得丢裁决"
    s._decree_ai = slot
    got = resolve_decree_timing(s, "pay_reform")
    assert got["timing"] == "long" and got["source"] == "天道", got


def test_slot_different_decree_still_rejected():
    s = _SlotState(turn=5, pending=[{"title": "乙令"}])
    slot = {"execution_timing": "长期", "_turn": 4, "_decree_titles": ["甲令"]}
    assert not slot_is_current(s, slot), "不同批诏令的旧裁决必须丢弃"
    s._decree_ai = slot
    got = resolve_decree_timing(s, "pay_reform")
    assert got["timing"] == "immediate" and "程序" in got["source"], got


def test_slot_without_titles_keeps_strict_turn_semantics():
    s = _SlotState(turn=5, pending=[{"title": "甲令"}])
    assert not slot_is_current(s, {"execution_timing": "长期", "_turn": 4})
    assert slot_is_current(s, {"execution_timing": "长期", "_turn": 5})


def test_slot_title_collision_rejected_by_decree_id():
    """O6：同名不同诏（题名相同、id 不同）不得互相采信。"""
    s = _SlotState(turn=5, pending=[{"title": "甲令", "decree_id": "D2"}])
    slot = {"execution_timing": "长期", "_turn": 4,
            "_decree_ids": ["D1"], "_decree_titles": ["甲令"]}
    assert not slot_is_current(s, slot), "id 不同即不同批，题名相同也不得采信"


def test_slot_same_decree_id_across_turns_is_kept():
    """O6 正向：id 相同、题名变了（改题）仍算同一道诏。"""
    s = _SlotState(turn=5, pending=[{"title": "改题后的甲令", "decree_id": "D1"}])
    slot = {"execution_timing": "长期", "_turn": 4,
            "_decree_ids": ["D1"], "_decree_titles": ["旧题"]}
    assert slot_is_current(s, slot)


# ---------------------------------------------------------------- ② 地方府库扣款
def _reset_treasury(s, route, seat_value):
    pdata = s.prefectures[route]
    seats = pdata.get("seats") or {}
    for sr in seats.values():
        sr["local_treasury"] = 0
    first = next(iter(seats.values()))
    first["local_treasury"] = seat_value
    from core.foundation.ledger import local_treasury_bridge as LTB
    return pdata, LTB, sum(float(sr.get("local_treasury", 0) or 0) for sr in seats.values())


def test_region_admin_uses_seat_truth_when_mirror_is_stale_high():
    s = new_game("史实")
    route = "京畿路"
    pdata, LTB, seat0 = _reset_treasury(s, route, 200000)
    pdata["local_treasury"] = 600000          # 人为滞后：镜像高于真账
    paid = RA._deduct_cost(s, "宋", 100000)
    seat1 = sum(float(sr.get("local_treasury", 0) or 0)
                for sr in (pdata.get("seats") or {}).values())
    assert paid == 100000, paid
    assert seat0 - seat1 == 100000, "必须从治所真账扣足，不得按镜像虚报"
    assert abs(float(pdata.get("local_treasury") or 0) - seat1) < 1e-6, "镜像应被校正到真账"


def test_region_admin_uses_seat_truth_when_mirror_is_stale_low():
    s = new_game("史实")
    route = "京畿路"
    pdata, LTB, seat0 = _reset_treasury(s, route, 200000)
    pdata["local_treasury"] = 0               # 人为滞后：镜像低于真账
    paid = RA._deduct_cost(s, "宋", 100000)
    seat1 = sum(float(sr.get("local_treasury", 0) or 0)
                for sr in (pdata.get("seats") or {}).values())
    assert paid == 100000, paid
    assert seat0 - seat1 == 100000, "镜像偏低不得导致“不扣款”"
