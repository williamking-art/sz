# -*- coding: utf-8 -*-
"""隐户快照脱敏断言（口径闭合：朝廷只知约值、清丈才知真数）。"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from backend.server import _state_to_dict                       # noqa: E402
from application.game_init import new_game
from core.region_brief import build_region_brief, hidden_surveyed  # noqa: E402


def _new_state():
    return new_game()


def test_snapshot_hides_hidden_pop_before_survey():
    """**未清丈**：快照不得含 `prefectures.*.pops.农.hidden`（隐户真值）。"""
    s = _new_state()
    row = build_region_brief(s)["routes"][0]
    assert row["surveyed"] is False, "开局应未清丈"
    d = _state_to_dict(s)
    p = d["prefectures"][row["name"]]
    assert "hidden" not in p["pops"]["农"], "未清丈不得下发隐户真值"
    # 约值仍可得（粗化 5 万），面板据此展示"约 X 口"
    assert isinstance(row["hidden_pop_est"], int) and row["hidden_pop_est"] >= 0
    assert row["hidden_pop_est"] % 50_000 == 0, "约值应粗化到 5 万"


def test_snapshot_exposes_hidden_pop_after_survey():
    """**已清丈**（隐匿率 < 0.2）：快照才含隐户真值。"""
    s = _new_state()
    name = build_region_brief(s)["routes"][0]["name"]
    p = s.prefectures[name]
    p["land"] = 10_000_000
    p["hidden_land"] = 100_000                   # 隐匿率 ≈ 0.99% → 视为已清丈
    pops_hidden = int(p["pops"]["农"].get("hidden", 0) or 0)
    assert pops_hidden > 0, "本用例前提：开局该路有隐户"
    assert hidden_surveyed(p) is True
    d = _state_to_dict(s)
    assert d["prefectures"][name]["pops"]["农"]["hidden"] == pops_hidden


def test_snapshot_desensitization_does_not_mutate_state():
    """脱敏只建副本：调用后 state 内的 `农.hidden` 与家产子池**原样保留**。"""
    s = _new_state()
    name = build_region_brief(s)["routes"][0]["name"]
    before = dict(s.prefectures[name]["pops"]["农"])
    _state_to_dict(s)
    after = s.prefectures[name]["pops"]["农"]
    assert after.get("hidden") == before.get("hidden"), "state 被就地修改（应只建副本）"
    assert "hidden" in after
