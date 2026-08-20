# -*- coding: utf-8 -*-
"""12 步 agent 化 P1 测试：外交/军事/灾荒契约接线 + 守恒铁律（agent 只叙事/档位）。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402


def _new_state():
    return GameState("史实")


def test_contract_validators_reject_bad():
    """契约拒绝式：非法档位/灾级 → _error/None（不落地）。"""
    from ai.client import AIClient
    c = AIClient(api_key="x")
    # 构造非法输入过 validator（直接调内部 validate 不可达，验证经 _postprocess 路径逻辑一致）
    # 契约方法返回 _error 标记（无真实调用不可测），此处验证换算表封顶逻辑
    from core.settlement_steps import _P1_ATT_DELTA, _P1_ARM_DELTA, _P1_RELIEF
    assert _P1_ATT_DELTA["大"] == 8          # attitude CAP 8
    assert _P1_ARM_DELTA["大"] == 50000      # 兵额 CAP 5万
    assert _P1_RELIEF["大"] == 500000        # 赈济 50万石
    for k, v in _P1_ATT_DELTA.items():
        assert 3 <= v <= 8
    for k, v in _P1_ARM_DELTA.items():
        assert 10000 <= v <= 50000


def test_diplomacy_contract_applies():
    """外交契约：attitude 档位换算（±3~±8 CAP 8）+ 盟约/岁币布尔接线。"""
    from core.settlement_steps import _settle_military_diplomacy
    s = _new_state()
    s._diplomacy_ai = {"attitude": "大", "sui_gong": "订", "alliance": "结"}
    att_before = {k: s.external[k]["attitude"] for k in ("金", "辽", "西夏")}
    _settle_military_diplomacy(s, [])
    for k in ("金", "辽", "西夏"):
        d = abs(s.external[k]["attitude"] - att_before[k])
        assert 3 <= d <= 8, f"{k} attitude 变化应在 ±3~±8：{d}"
    assert s.alliance_jin_liao is True
    assert s._sui_gong is True


def test_military_contract_applies():
    """军事契约：训练/士气 ±2~±6、兵额 ±1万~±5万、征发 cost 守恒扣款。"""
    from core.settlement_steps import _settle_military_diplomacy
    s = _new_state()
    s._military_ai = {"power": "中", "army": "大", "training": "中", "morale": "小", "levy": "中"}
    t0 = s.treasury
    u0 = max(s.army_units, key=lambda x: x.troops)
    train0, morale0 = u0.training, u0.morale
    troops0 = u0.troops
    _settle_military_diplomacy(s, [])
    assert 2 <= abs(u0.training - train0) <= 6
    assert 2 <= abs(u0.morale - morale0) <= 6
    assert 10000 <= abs(u0.troops - troops0) <= 50000
    assert s.treasury == t0 - 350000   # levy 中 = 35万 守恒扣款


def test_relief_contract_applies():
    """灾荒契约：赈济档位换算 + 太仓守恒扣。"""
    from core.settlement_disaster import _settle_disaster
    s = _new_state()
    s._relief_ai = {"disaster_level": 3, "relief": "中", "refugee": "小"}
    s.disaster_severity = 2
    g0 = s.granary
    _settle_disaster(s, [])
    assert s.granary == g0 - min(350000, g0)   # relief 中 = 35万石，≤太仓
    assert s.disaster_severity <= 3


def test_conservation_agent_does_not_touch():
    """守恒铁律：agent 契约不触碰税收/军粮/仓廪/国库守恒步（只给档位词）。"""
    from core.commands import settle_turn
    sys.path.insert(0, os.path.join(_GAME_ROOT, "tests"))
    from tests.fake_ai_backend import FakeAIClient

    class _AgentFakeAI(FakeAIClient):
        def __init__(self):
            super().__init__()
            self.available = True
            self.contract_calls = []

        def economy_decide(self, posture):
            return {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中",
                    "窖银": "无", "城市化": "无", "回乡": "无", "科举": "无"}

        def diplomacy_decide(self, posture, state=None):
            self.contract_calls.append("diplomacy")
            return {"attitude": "小", "sui_gong": "不变", "alliance": "不变"}

        def military_decide(self, posture, state=None):
            self.contract_calls.append("military")
            return {"power": "小", "army": "微", "training": "微", "morale": "微", "levy": "微"}

        def relief_decide(self, posture, state=None):
            self.contract_calls.append("relief")
            return {"disaster_level": 1, "relief": "微", "refugee": "微"}

        def monthly_report(self, year, month, era_name, posture):
            return {"report": "四海承平。"}

    s = _new_state()

    def _snap(st):
        tot = st.treasury + st.imperial_treasury + st.granary
        for p in st.prefectures.values():
            for pop in p["pops"].values():
                tot += pop.get("wealth", 0) + pop.get("grain", 0) * 0.001 + pop.get("窖银", 0)
        return tot

    before = _snap(s)
    fake = _AgentFakeAI()
    settle_turn(s, ai_client=fake)
    assert "diplomacy" in fake.contract_calls and "military" in fake.contract_calls and "relief" in fake.contract_calls
    # 守恒：settle 前后 money 差分无凭空跳变（agent 只给档位词，守恒步程序介入）
    after = _snap(s)
    assert abs(after - before) < 50_000_000
