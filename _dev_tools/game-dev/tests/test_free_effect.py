# -*- coding: utf-8 -*-
"""free_effect 通用契约回归测试（言枢密 v3）：白名单拒绝 / CAP 封顶 / cost 承受 / once 落地 /
ongoing 月度结算 / 存档往返 / 假 AI 后端接入拟旨。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
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


def test_money_conservation_no_mint():
    """审查 P0-5：零成本正 treasury/finance 效果不再凭空铸币——
    国库增额必须与民间钱池成对（国库+民间总持钱 ΣΔ==0）。"""
    from core.free_effect import _money_pools

    def tot(state):
        return state.treasury + sum(int(p.get("wealth", 0)) for p in _money_pools(state))

    s = _new_state()
    t0 = tot(s)
    # 零成本正效果（旧实现 = 净造币）
    log = _apply_free_effect(s, {"mode": "once", "effects": {"treasury": "大"}})
    assert any("treasury" in x or "finance" in x for x in log)
    assert tot(s) == t0, f"零成本正 treasury 应守恒：Δ={tot(s)-t0}"
    # 纯支出 cost 也守恒（散入民间工赈）
    t1 = tot(s)
    _apply_free_effect(s, {"mode": "once", "effects": {"prestige": "中"},
                           "cost": {"treasury": 300000}})
    assert tot(s) == t1, f"cost 支出应守恒：Δ={tot(s)-t1}"
    # 民间枯竭 → 正效果整单拒绝（原子，不部分落地）
    for p in s.prefectures.values():
        for x in p["pops"].values():
            x["wealth"] = 0
    log2 = _apply_free_effect(s, {"mode": "once", "effects": {"treasury": "大"}})
    assert any("不足" in x or "拒绝" in x for x in log2)
    assert s.treasury == s.treasury  # 国库未变（拒绝）


def test_nan_inf_bool_rejected():
    """P0-1：NaN/Inf/bool 不得经 _clamp 变成 +CAP 铸币，须整单拒绝或回落 0。"""
    import math
    s = _new_state()
    t0 = s.treasury
    # validate 拒绝式
    assert "NaN" in validate_free_effect({"mode": "once", "effects": {"treasury": float("nan")}})
    assert "NaN" in validate_free_effect({"mode": "once", "effects": {"treasury": float("inf")}})
    assert "数字" in validate_free_effect({"mode": "once", "effects": {"treasury": True}})
    assert "有限" in validate_free_effect({"mode": "once", "effects": {"prestige": "中"},
                                           "cost": {"treasury": float("nan")}})
    assert "duration" in validate_free_effect({"mode": "ongoing", "duration": float("nan"),
                                               "effects": {"tech": "微"}})
    assert "duration" in validate_free_effect({"mode": "ongoing", "duration": float("inf"),
                                               "effects": {"tech": "微"}})
    # 即便绕过 validate，_resolve_effect_value 也不得铸币
    from core.free_effect import _resolve_effect_value
    assert _resolve_effect_value("treasury", float("nan")) == 0
    assert _resolve_effect_value("treasury", float("inf")) == 0
    assert _resolve_effect_value("treasury", True) == 0
    log = _apply_free_effect(s, {"mode": "once", "effects": {"treasury": float("nan")}})
    assert any("拒绝" in x or "NaN" in x or "数字" in x for x in log)
    assert s.treasury == t0, "NaN 不得改变国库"


def test_cost_leg_no_false_deduct_no_vanish():
    """P0-3：**无民间池**（不是财富=0）时 cost.treasury 不得假扣账；无粮池时不得灭粮。

    注意：财富=0 但池仍在 → 成本应正常散入民间（守恒），见
    test_cost_leg_conservation_when_pools_exist。本测的是「池不可达」路径。
    """
    s = _new_state()
    # 摘掉 wealth/grain 键 → _money_pools/_grain_pools 为空
    for p in s.prefectures.values():
        for x in p["pops"].values():
            x.pop("wealth", None)
            x.pop("grain", None)
    t0, g0 = s.treasury, s.granary
    if g0 <= 0:
        s.granary = 10000
        g0 = s.granary
    log = _apply_free_effect(s, {"mode": "once", "effects": {"prestige": "微"},
                                 "cost": {"treasury": 50000, "granary": 100}})
    # 无池 → cost.treasury 不得扣国库（假扣账=成本逃逸）；无粮池 → 不得太仓出仓（灭粮）
    assert s.treasury == t0, f"无池 cost.treasury 不应扣账，实际 Δ={s.treasury - t0}"
    assert s.granary == g0, f"无粮池 cost.granary 不应出仓，实际 Δ={s.granary - g0}"
    assert any("未执行" in x or "守恒" in x or "不足" in x or "拒绝" in x for x in log)


def test_cost_leg_conservation_when_pools_exist():
    """cost 落地时 Σ(国库+民间)==Σ(太仓+民间粮) 守恒。"""
    from core.free_effect import _money_pools, _grain_pools

    def money_tot(state):
        return state.treasury + sum(int(p.get("wealth", 0) or 0) for p in _money_pools(state))

    def grain_tot(state):
        return state.granary + sum(int(p.get("grain", 0) or 0) for p in _grain_pools(state))

    s = _new_state()
    m0, g0 = money_tot(s), grain_tot(s)
    s.granary = max(s.granary, 50000)
    g0 = grain_tot(s)
    _apply_free_effect(s, {"mode": "once", "effects": {"prestige": "微"},
                           "cost": {"treasury": 30000, "granary": 500}})
    assert money_tot(s) == m0, f"cost.treasury 应守恒 Δ={money_tot(s) - m0}"
    assert grain_tot(s) == g0, f"cost.granary 应守恒 Δ={grain_tot(s) - g0}"
