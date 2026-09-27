# -*- coding: utf-8 -*-
"""方案 B 断言：**玩家亲裁军令**（编制定向 + 审计留痕 + 未实现按钮明确拒绝）。"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.commands import issue_military_order            # noqa: E402
from core.game_state import GameState                     # noqa: E402


def _state():
    return GameState("史实")


def _two_same_tier(s):
    by = {}
    for u in s.army_units:
        by.setdefault(u.tier, []).append(u)
    for _tier, us in by.items():
        if len(us) >= 2:
            return us[0], us[1]
    return None, None


def test_player_order_targets_single_unit_and_leaves_audit():
    """整编：只动选中编制单位；且在 `ai_pending_actions` 留下**玩家亲裁**审计（approved）。"""
    s = _state()
    a, b = _two_same_tier(s)
    a.training = b.training = 10
    n0 = len(s.ai_pending_actions)
    msg = issue_military_order(s, a.unit_id, "整编", scale=3)
    assert a.training == 16, f"选中单位应 +6，实得 {a.training}"
    assert b.training == 10, "同军籍其他编制单位不得被动到"
    assert "批红" in msg
    assert len(s.ai_pending_actions) == n0 + 1, "应留一条审计条目"
    rec = s.ai_pending_actions[-1]
    assert rec["kind"] == "military_dispatch" and rec["proposer"] == "玩家"
    assert rec["status"] == "approved", "即时批红后应标记 approved（可回溯）"
    assert rec["payload"]["unit_id"] == a.unit_id


def test_player_order_recruit_conserves_population():
    """扩编（→增募）：Σ(农 + 流民 + 兵) 不变；兵额真账 Σbranches +4000（scale=2）。"""
    s = _state()
    a, _b = _two_same_tier(s)
    st = a.station if a.station in s.prefectures else next(iter(s.prefectures))
    a.station = st
    p = s.prefectures[st]
    p["refugees"] = 50_000
    p["pops"]["农"]["size"] = max(int(p["pops"]["农"]["size"]), 200_000)
    s.treasury = max(s.treasury, 10_000_000)

    def pool():
        return (int(p["pops"]["农"]["size"]) + int(p.get("refugees", 0))
                + int(p["pops"]["兵"]["size"]))

    before, branches = pool(), sum(a.branches.values())
    issue_military_order(s, a.unit_id, "扩编", scale=2)
    assert pool() == before, "POP 挂载律：Σ不变"
    assert sum(a.branches.values()) == branches + 4000


def test_unimplemented_button_is_refused_without_side_effect():
    """拆分/合并/裁撤/换帅/改名：**明确拒绝**且零副作用（不静默、不假装成功）。"""
    s = _state()
    a, _b = _two_same_tier(s)
    before = [(u.unit_id, u.training, u.station, dict(u.branches)) for u in s.army_units]
    n0 = len(s.ai_pending_actions)
    for btn in ("拆分", "合并", "裁撤", "换帅", "改名"):
        msg = issue_military_order(s, a.unit_id, btn)
        assert "尚无契约" in msg, f"{btn} 应明确拒绝"
    assert len(s.ai_pending_actions) == n0, "拒绝不得留审计（未成形）"
    assert [(u.unit_id, u.training, u.station, dict(u.branches)) for u in s.army_units] == before


def test_unknown_unit_and_bad_destination_refused():
    """无效编制单位 / 非法目的地：拒绝且不入队。"""
    s = _state()
    n0 = len(s.ai_pending_actions)
    assert "无此编制单位" in issue_military_order(s, "不存在", "整编")
    a, _b = _two_same_tier(s)
    assert "不在本朝州路中" in issue_military_order(s, a.unit_id, "地图调度", target="不存在的路")
    assert len(s.ai_pending_actions) == n0


def test_player_order_move_targets_single_unit():
    """地图调度（→调赴）：定向调走选中单位，`target` 仍为目的地路。"""
    s = _state()
    a, b = _two_same_tier(s)
    dest = next(n for n in s.prefectures if n != a.station)
    b_station = b.station
    issue_military_order(s, a.unit_id, "地图调度", target=dest)
    assert a.station == dest and b.station == b_station
