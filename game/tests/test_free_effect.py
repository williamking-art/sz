# -*- coding: utf-8 -*-
"""free_effect 通用契约回归测试（言枢密 v3）：白名单拒绝 / CAP 封顶 / cost 承受 / once 落地 /
ongoing 月度结算 / 存档往返 / 假 AI 后端接入拟旨。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.free_effect import (  # noqa: E402
    validate_free_effect, _apply_free_effect, _settle_free_effects,
)
from core.game_state import GameState  # noqa: E402


def _new_state():
    return GameState("史实")


def test_validate_whitelist_reject():
    """白名单拒绝式：非白名单字段 → 整单拒绝（不落地）。"""
    contract = {"mode": "once", "effects": {"magic_power": "大"}}
    err = validate_free_effect(contract)
    assert "不在白名单" in err
    s = _new_state()
    log = _apply_free_effect(s, contract)
    assert "契约拒绝" in log[0]


def test_cap_and_cost_reject():
    """CAP 封顶 + cost 超存量整单不执行。"""
    s = _new_state()
    t0 = s.treasury
    # treasury 档位 "大" → 800000×1.5=120 万（CAP 300 万内）
    log = _apply_free_effect(s, {"mode": "once", "effects": {"treasury": "大"}})
    assert s.treasury == t0 + 1_200_000
    # cost 超存量 → 整单不执行
    t1 = s.treasury
    log2 = _apply_free_effect(s, {"mode": "once", "effects": {"prestige": "中"},
                                  "cost": {"treasury": t1 * 10}})
    assert "成本不足" in log2[0]
    assert s.treasury == t1  # 未扣成本


def test_once_apply():
    """once 契约即时落地（prestige + cost 守恒）。"""
    s = _new_state()
    p0, t0 = s.prestige, s.treasury
    log = _apply_free_effect(s, {"mode": "once", "effects": {"prestige": "中"},
                                 "cost": {"treasury": 100000}})
    assert s.prestige == min(100, p0 + 4)
    assert s.treasury == t0 - 100000
    assert any("皇威" in x or "prestige" in x for x in log)


def test_ongoing_monthly_settlement():
    """ongoing 契约入队列，月度结算：effects/cost 每月 apply、duration 递减、到期核销。"""
    s = _new_state()
    t0 = s.treasury
    log = _apply_free_effect(s, {"mode": "ongoing", "name": "宽恤民力", "duration": 2,
                                 "effects": {"population_satisfaction": "微"},
                                 "cost": {"treasury": 10000}})
    assert "长期制度" in log[0]
    assert len(s.longterm_effects) == 1
    # 第 1 月结算
    _settle_free_effects(s, [])
    assert s.longterm_effects[0]["duration"] == 1
    assert s.treasury == t0 - 10000
    # 第 2 月结算 → 到期核销
    _settle_free_effects(s, [])
    assert s.longterm_effects == []
    assert s.treasury == t0 - 20000


def test_ongoing_permanent_duration_zero():
    """duration=0 → 永久（不核销）。"""
    s = _new_state()
    _apply_free_effect(s, {"mode": "ongoing", "name": "永制", "duration": 0,
                           "effects": {"tech": "微"}, "cost": {}})
    _settle_free_effects(s, [])
    _settle_free_effects(s, [])
    assert len(s.longterm_effects) == 1


def test_longterm_roundtrip():
    """存档往返 longterm_effects 不丢。"""
    s = _new_state()
    _apply_free_effect(s, {"mode": "ongoing", "name": "常平新制", "duration": 6,
                           "effects": {"treasury": "微"}, "cost": {"treasury": 5000}})
    from core.save_load import save_game, load_game, _slot_path
    assert save_game(s, slot=5)
    s2 = load_game(5)
    assert s2 is not None
    assert len(s2.longterm_effects) == 1
    assert s2.longterm_effects[0]["name"] == "常平新制"
    if os.path.exists(_slot_path(5)):
        os.remove(_slot_path(5))


def test_fake_ai_issue_free_decree():
    """假 AI 后端接入拟旨：free_edict 经 free_effect_decide → _apply_free_effect 落地。"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from tests.fake_ai_backend import FakeAIClient
    from core.commands_decree import issue_free_decree
    s = _new_state()
    fake = FakeAIClient(free_effect_contract={
        "mode": "once", "name": "赈济新令",
        "effects": {"treasury": "微", "population_satisfaction": "小"},
        "cost": {"treasury": 100000},
    })
    # 替换 AIClient.load_saved 返回替身（patch 临时）
    import ai.client as _aic
    _orig = _aic.AIClient.load_saved
    _aic.AIClient.load_saved = staticmethod(lambda: fake)
    try:
        parse = {"category": "free_edict", "exec_mode": "longterm", "title": "赈济新令", "body": "发帑赈济"}
        t0 = s.treasury
        line = issue_free_decree(s, parse, "蔡京")
        assert s.treasury == t0 - 100000 + 800000 * 0.25   # cost -10 万 + treasury 微 +20 万
        assert "自由" in line or "国帑" in line or "treasury" in line
    finally:
        _aic.AIClient.load_saved = _orig
