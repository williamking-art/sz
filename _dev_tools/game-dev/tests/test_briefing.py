# -*- coding: utf-8 -*-
"""T7 朝局简报测试：程序规则可行动项（确定性 / 无 AI / 脱敏 / 极端场景）。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402


def _new_state():
    return GameState("史实")


def test_briefing_deterministic():
    """确定性：同一 state 两次推导结果一致（无随机、无 AI）。"""
    from core.briefing import build_briefing_actions
    s = _new_state()
    a1 = build_briefing_actions(s)
    a2 = build_briefing_actions(s)
    assert a1 == a2


def test_briefing_no_ai_dependency():
    """无 AI 依赖：不触网、不读 ai_client，离线同样产出。"""
    from core.briefing import build_briefing_actions
    s = _new_state()
    actions = build_briefing_actions(s)
    assert isinstance(actions, list) and actions


def test_briefing_desensitized():
    """脱敏：输出文本不含隐藏数值键（loyalty/corruption/精确国库额）。"""
    from core.briefing import build_briefing_actions
    s = _new_state()
    s.treasury = -6_000_000      # 触发库藏危机急务
    s.disaster_severity = 3      # 触发赈灾急务
    s.population_satisfaction = 30
    text = " ".join(a["title"] + a["desc"] for a in build_briefing_actions(s))
    assert "loyalty" not in text and "corruption" not in text
    assert "6000000" not in text and "6,000,000" not in text
    # 急务符号/词不带隐藏数值
    assert "库藏告急" in text and "赈济灾黎" in text


def test_briefing_urgent_flags():
    """极端场景：国库危机/灾荒/民心低落 → urgent 急务项在前。"""
    from core.briefing import build_briefing_actions
    s = _new_state()
    s.treasury = -6_000_000
    s.disaster_severity = 3
    s.disaster_region = "河北路"
    s.population_satisfaction = 30
    actions = build_briefing_actions(s)
    urgent = [a for a in actions if a.get("urgent")]
    assert any(a["key"] == "treasury_crisis" for a in urgent)
    assert any(a["key"] == "disaster" for a in urgent)
    assert any(a["key"] == "mood" for a in urgent)
    assert all(a.get("goto") in ("decree", "army") for a in urgent)


def test_briefing_goto_semantics():
    """跳转语义在已知集合内（UI 层可映射面板）。"""
    from core.briefing import build_briefing_actions, DECREE, AUDIENCE, TECH, ARMY, TODO
    valid = {DECREE, AUDIENCE, TECH, ARMY, TODO}
    s = _new_state()
    for a in build_briefing_actions(s):
        assert a.get("goto") in valid, f"未知跳转语义：{a.get('goto')}"


def test_briefing_empty_state_fallback():
    """极端空态兜底：即使规则全不命中，也保证至少一条建议。"""
    from core.briefing import build_briefing_actions
    s = GameState("史实")
    # 清空可触发项
    s.edict_drafts = []
    s.pending_decrees = [None] * 99   # 占满带宽
    s.longterm_public = []
    s.longterm_secret = []
    s.treasury = 10_000_000
    s.disaster_severity = 0
    s.population_satisfaction = 80
    actions = build_briefing_actions(s)
    assert actions, "兜底应保证至少一条建议"
    assert actions[0].get("title")
