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
from core.military_order import settle_military_orders    # noqa: E402


def _state():
    s = GameState("史实")
    s.prestige = 999   # 本文件验证军令落地细节，走皇威直行路径
    return s


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


def test_unknown_button_is_refused_without_side_effect():
    """**未知**按钮名：明确拒绝且零副作用（8 个参考图键已于 2026-09-27 全部实现）。"""
    s = _state()
    a, _b = _two_same_tier(s)
    before = [(u.unit_id, u.training, u.station, dict(u.branches)) for u in s.army_units]
    n0 = len(s.ai_pending_actions)
    for btn in ("操练", "子虚乌有"):                      # 8 键已实现；非参考图键须拒绝
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
    s.turn = 2
    settle_military_orders(s)
    assert a.station == dest and b.station == b_station


def test_disband_conserves_population_and_troops():
    """**裁撤**：兵额减 N 且**恰为**档位值；Σ(农+流民+兵) 不变；兵种不为负。"""
    s = _state()
    a, _b = _two_same_tier(s)
    st = a.station if a.station in s.prefectures else next(iter(s.prefectures))
    a.station = st
    p = s.prefectures[st]
    p["pops"]["兵"]["size"] = max(20_000, int(p["pops"]["兵"].get("size", 0) or 0))

    def pool():
        return (int(p["pops"]["农"]["size"]) + int(p.get("refugees", 0))
                + int(p["pops"]["兵"]["size"]))

    before, troops0 = pool(), sum(a.branches.values())
    pop0, farm0 = int(p["pops"]["兵"]["size"]), int(p["pops"]["农"]["size"])
    msg = issue_military_order(s, a.unit_id, "裁撤", scale=1)
    assert "裁减 2000 人" in msg, f"应按档位裁 2000，实得：{msg}"
    assert pool() == before, "POP 挂载律：Σ(农+流民+兵) 不变"
    assert sum(a.branches.values()) == troops0 - 2000, "兵额真账 = Σbranches，应恰减 2000"
    assert a.troops == sum(a.branches.values())
    assert int(p["pops"]["兵"]["size"]) == pop0 - 2000 and int(p["pops"]["农"]["size"]) == farm0 + 2000
    assert all(v > 0 for v in a.branches.values()), "不得把某兵种扣成负/零残留"


def test_disband_only_touches_selected_unit():
    """裁撤同样**编制定向**：同军籍的其他编制单位不动。"""
    s = _state()
    a, b = _two_same_tier(s)
    st = a.station if a.station in s.prefectures else next(iter(s.prefectures))
    a.station = st
    s.prefectures[st]["pops"]["兵"]["size"] = max(20_000, int(s.prefectures[st]["pops"]["兵"].get("size", 0) or 0))
    b0 = sum(b.branches.values())
    issue_military_order(s, a.unit_id, "裁撤", scale=1)
    assert sum(b.branches.values()) == b0, "未选中的编制单位不得被裁"


def _two_same_station(s):
    by = {}
    for u in s.army_units:
        by.setdefault(u.station, []).append(u)
    for _st, us in by.items():
        if len(us) >= 2:
            return us[0], us[1]
    return None, None


def test_rename_touches_display_layer_only():
    """**改名**：番号（展示层）变，**兵额/兵种/士气/训练/驻地/欠饷一律不动**。"""
    s = _state()
    a, _b = _two_same_tier(s)
    before = [(u.troops, tuple(sorted(u.branches.items())), u.morale, u.training,
               u.station, u.arrears) for u in s.army_units]
    msg = issue_military_order(s, a.unit_id, "改名", new_name="殿前神卫军")
    assert "改称" in msg and "殿前神卫军" in msg
    assert a.army_name == "殿前神卫军"
    assert a.name.endswith("·殿前神卫军") or a.name == "殿前神卫军", "完整番号应同步军号段"
    after = [(u.troops, tuple(sorted(u.branches.items())), u.morale, u.training,
              u.station, u.arrears) for u in s.army_units]
    assert after == before, "改名只动展示层，不得触及真账"


def test_rename_rejects_empty_long_and_duplicate():
    """番号校验：空白 / 超 12 字 / 同路重名 → 明确驳回，且**不改动任何单位**。"""
    s = _state()
    a, b = _two_same_station(s)
    assert a is not None, "前提：同路存在两支编制单位"
    names0 = [(u.unit_id, u.army_name, u.name) for u in s.army_units]
    assert "1–12 字" in issue_military_order(s, a.unit_id, "改名", new_name="   ")
    assert "1–12 字" in issue_military_order(s, a.unit_id, "改名", new_name="号" * 13)
    assert "1–12 字" in issue_military_order(s, a.unit_id, "改名")          # 未给新名
    # 先给 a 起名，再让同路 b 撞名
    issue_military_order(s, a.unit_id, "改名", new_name="试号军")
    b0 = (b.army_name, b.name)
    assert "已有番号" in issue_military_order(s, b.unit_id, "改名", new_name="试号军")
    assert (b.army_name, b.name) == b0, "驳回不得留下半改状态"


def test_command_channel_dispatch_reaches_player_order():
    """**通道验证**：前端 `action("issue_military_order", …)` 经 `LocalBackend.action`
    分派表 → `commands.issue_military_order`（HttpBackend 走 /api/action → 同一实现）。"""
    from backend.client import LocalBackend

    s = _state()
    a, b = _two_same_tier(s)
    a.training = b.training = 10
    backend = LocalBackend()
    msg, s2 = backend.action(
        s, "issue_military_order",
        {"unit_id": a.unit_id, "button": "整编", "scale": 3}, None)
    assert s2 is s, "本地模式应返回同一 state 对象"
    assert "批红" in msg, f"应走批红通道，实得：{msg}"
    assert a.training == 16 and b.training == 10, "分派后仍须定向生效"
    assert s.ai_pending_actions[-1]["proposer"] == "玩家", "审计须留痕"
