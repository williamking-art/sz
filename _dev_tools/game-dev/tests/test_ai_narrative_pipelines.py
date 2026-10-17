# -*- coding: utf-8 -*-
"""天道 × 大模型三管道**真实接线**测试（P0 修复批 · 2026-10-17）。

旧版问题：三个管道函数在 `game/` 下 **0 个生产调用**（只有测试调），
等于"写好了没接"。本批把它们分别接进：
· 管道一 → `commands._memorial_posture`（奏折生成入参）；
· 管道二 → `commands.audience_dialogue`（召对 state_summary）；
· 管道三 → `commands.monthly_report_args`（月报 posture）。
"""
import pytest

from application.game_init import new_game
import core.commands as commands
from ai.token_meter import TOKEN_GROUPS, token_group_of


@pytest.fixture()
def state():
    return new_game("史实")


# =============================================================================
# 0. Token 计量：奏折链路必须可见
# =============================================================================
def test_token_meter_memorials_group_registered():
    assert "奏折" in TOKEN_GROUPS
    assert "generate_memorials" in TOKEN_GROUPS["奏折"]
    assert token_group_of("generate_memorials") == "奏折"


# =============================================================================
# 1. 管道一：奏折入参带天道事实签
# =============================================================================
def test_memorial_posture_injects_seed_facts(state):
    posture = commands._memorial_posture(state)
    assert "天道事实签" in posture
    assert "受命大臣" in posture
    # 事实签必须来自真实在任主官
    leads = {str(r.get("lead")) for r in (state.central_orgs or {}).values()
             if isinstance(r, dict) and r.get("lead")}
    assert any(name in posture for name in leads), "事实签没引用任何在任主官"


def test_memorial_posture_degrades_without_orgs(state):
    state.central_orgs = {}
    posture = commands._memorial_posture(state)
    assert "天道事实签" not in posture, "无在任主官时不得编事实签"
    assert isinstance(posture, str)


# =============================================================================
# 2. 管道二：召对摘要带天道定势
# =============================================================================
class _FakeAI:
    available = True

    def __init__(self):
        self.captured = None

    def dialogue(self, *args, **kwargs):
        self.captured = {"args": args, "kwargs": kwargs}
        return {"reply": "臣以为未可轻举。", "mood": "平"}


def test_audience_dialogue_injects_stance(state, monkeypatch):
    # 跳过落定链路（本测试只验"定势是否进了 AI 入参"）
    monkeypatch.setattr(commands, "audience_dialogue_apply", lambda *a, **k: "臣以为未可轻举。")
    fake = _FakeAI()
    commands.audience_dialogue(state, "蔡京", "卿以为青苗新法如何", fake)
    assert fake.captured is not None, "召对未被调用（预过滤/缓存拦截？）"
    summary = fake.captured["args"][8]
    assert "天道定势" in summary
    assert "立场=" in summary


# =============================================================================
# 3. 管道三：月报入参带月度天机实录
# =============================================================================
def test_monthly_report_args_inject_omen(state):
    _y, _m, _era, posture = commands.monthly_report_args(state)
    assert "天道月度实录" in posture
    assert "气数" in posture


def test_monthly_report_args_survive_missing_omen(state, monkeypatch):
    """天道实录失败不得阻断月报（纯装饰层）。"""
    from core.ai import tiandao_facade

    def _boom(*a, **k):
        raise RuntimeError("demo")

    monkeypatch.setattr(tiandao_facade.TianDaoFacade, "summarize_monthly_omen",
                        classmethod(lambda cls, s: _boom()))
    _y, _m, _era, posture = commands.monthly_report_args(state)
    assert isinstance(posture, str) and posture
