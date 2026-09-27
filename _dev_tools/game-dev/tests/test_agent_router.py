# -*- coding: utf-8 -*-
"""T3 测试：agent_router 按需唤醒（military/relief 真实军情/灾荒唤醒，economy 必醒）。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.agent_router import route_agents, inject_woken_agents  # noqa: E402


def _new_state():
    return GameState("史实")


def test_economy_always_woken():
    """economy 始终唤醒（核心推演）；无军情/灾荒时 military/relief 不唤醒（省 token）。"""
    s = _new_state()
    woken = route_agents(player_input="", state=s)
    assert "economy" in woken
    assert "narrative" in woken
    assert "military" not in woken
    assert "relief" not in woken


def test_military_woken_on_crisis():
    """军事：军队 morale<30 或 敌军入侵事件 → 唤醒。"""
    s = _new_state()
    # morale<30
    for u in s.army_units[:1]:
        u.morale = 20
    woken = route_agents(player_input="", state=s)
    assert "military" in woken
    # 无军情不唤醒
    s2 = _new_state()
    assert "military" not in route_agents(player_input="", state=s2)
    # 敌军入侵事件
    s3 = _new_state()
    s3.active_events.append({"category": "金兵入侵", "turn": 1, "message": "x"})
    assert "military" in route_agents(player_input="", state=s3)


def test_relief_woken_on_disaster():
    """灾荒：灾荒类事件 / disaster_severity>0 / 流民 refugees>8000 → 唤醒。"""
    s = _new_state()
    # 流民异常
    s.prefectures["河北路"]["refugees"] = 10000
    woken = route_agents(player_input="", state=s)
    assert "relief" in woken
    # disaster_severity
    s2 = _new_state()
    s2.disaster_severity = 2
    assert "relief" in route_agents(player_input="", state=s2)
    # 无灾荒不唤醒
    s3 = _new_state()
    assert "relief" not in route_agents(player_input="", state=s3)


def test_wake_by_keywords():
    """关键词唤醒：玩家输入含领域词 → 唤醒对应 agent。"""
    s = _new_state()
    assert "military" in route_agents(player_input="调兵守边", state=s)
    assert "relief" in route_agents(player_input="赈济灾民", state=s)


def test_finance_is_not_woken_until_wired():
    """`finance` 已于 2026-09-27 置 `wired: False`：结算侧不消费 `_finance_ai`，唤醒＝白烧 token。

    回归锁定：即使玩家输入命中其关键词、或国库为负（原先的状态触发条件），
    `route_agents` 也必须因 `wired is False` 守卫而跳过它。
    """
    s = _new_state()
    s.treasury = -50_000                                  # 原本触发 finance 状态唤醒
    woken = route_agents(player_input="税银钱粮商盐市舶交子钱荒", state=s)
    assert "finance" not in woken, "finance 未接线却仍被唤醒（白烧 token）"
    # 其它 agent 不受影响（economy 必醒）
    assert "economy" in woken
    # **两个入口都守 `wired`**：即便显式把 finance 放进 woken 列表，注入侧同样跳过
    # （2026-09-27 实测：`inject_woken_agents` 亦守 `wired is False`，无法被绕开）
    class _Fake:
        available = True
        def finance_decide(self, posture, state=None):      # pragma: no cover - 不应被调用
            raise AssertionError("未接线 agent 不应被调用")
    assert inject_woken_agents(s, _Fake(), ["finance"]) == []
    assert not hasattr(s, "_finance_ai")
