# -*- coding: utf-8 -*-
"""诏令实际效果口径测试（`core/decree_effect.py`）。

守护用户定稿（2026-09-19）的三条口径——它们纠正了早期"军队督行恒为乘数"的错误：
  ① **吏治是唯一强关联**（会签执行率本身就是吏治的表达）；
  ② 民心 / 文书到账是**弱关联**（幅度 ≤15%）；
  ③ **军队是条件加成而非必须**——只有军政/边事类诏令才吃军队督行，民政诏令与之无关。
"""
import json
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.decree_effect import (  # noqa: E402
    CIVIL_FLOOR, STRONG_CHANNEL, decree_effect_mult, decree_kind, effect_channels,
)
from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402


def _state():
    s = GameState("史实")
    init_legacies(s)
    return s


def test_decree_kind_classification():
    assert decree_kind(None, "赈济陕西流民") == "民政"
    assert decree_kind(None, "清丈田亩、均平赋役") == "民政"
    assert decree_kind("户部", "平抑物价") == "民政"
    assert decree_kind("枢密院", "整饬边备") == "军政"
    assert decree_kind(None, "调兵戍守河北") == "军政"
    # 保守：拿不准就是民政（宁可军队不参与，也不把军队塞进一切诏令）
    assert decree_kind(None, "整饬纲纪") == "民政"


def test_strong_channel_is_clerks_only():
    s = _state()
    ch = effect_channels(s, text="赈济陕西流民")
    assert ch["strong"] == STRONG_CHANNEL == "clerks"
    assert ch["official_support"]["proxy"] is True, "官场配合度只能是代理，不得当执行率"
    assert "clerks_mult" in ch and "civil_mult" in ch


def test_civil_channel_is_weak_clerks_channel_is_strong():
    s = _state()
    base = effect_channels(s, text="清丈田亩")["effect_mult"]
    assert base > 0

    # 弱关联：民心跌到 0，整体系数变化幅度必须很小（≤15%）
    s.population_satisfaction = 0
    weak = effect_channels(s, text="清丈田亩")["effect_mult"]
    assert weak <= base, "民心变差不得使效果上升"
    assert weak / base >= CIVIL_FLOOR - 1e-6, f"弱关联幅度过大：{weak / base:.3f}"

    # 强关联：把持度拉高 → 吏治折扣显著压低整体系数
    for p in s.prefectures.values():
        p.setdefault("clerks_detail", {})["grip"] = 0.9
    strong = effect_channels(s, text="清丈田亩")["effect_mult"]
    assert strong < weak * 0.9, "吏治必须主导（强关联）"


def test_military_is_conditional_bonus_not_mandatory():
    s = _state()
    civil = effect_channels(s, text="赈济陕西流民")
    mil = effect_channels(s, org_hint="枢密院", text="整饬边备")
    assert civil["kind"] == "民政" and civil["military"]["applies"] is False
    assert mil["kind"] == "军政" and mil["military"]["applies"] is True

    for u in s.army_units:
        u.morale = 0
    # 民政诏令且**未调兵**：军心崩坏不得影响其效果
    assert effect_channels(s, text="赈济陕西流民")["effect_mult"] == civil["effect_mult"]
    # 军政诏令：军心崩坏必须压低其效果（加成失效）
    assert effect_channels(s, org_hint="枢密院", text="整饬边备")["effect_mult"] < mil["effect_mult"]


def test_players_can_muster_troops_to_enforce_civil_decrees():
    """用户口径：**民政诏令也可调兵强制施行**（军队是玩家可选杠杆，不是"与民政无关"）。

    军队是**加成**（把因吏治/民心办不到的那部分向上补），故调兵**绝不比不调兵差**；
    军心越可靠，补得越多。
    """
    s = _state()
    plain = effect_channels(s, text="赈济陕西流民")
    assert plain["military"]["applies"] is False

    for u in s.army_units:
        u.morale = 0
    weak = effect_channels(s, text="赈济陕西流民", enforce_troops=True)
    assert weak["military"]["applies"] is True
    assert weak["military"]["enforced"] is True
    assert "调兵强制" in weak["military"]["reason"]
    assert weak["effect_mult"] > plain["effect_mult"], "调兵是加成：不得比不调兵更差"

    for u in s.army_units:
        u.morale = 100
        u.arrears = 0
    strong = effect_channels(s, text="赈济陕西流民", enforce_troops=True)
    assert strong["effect_mult"] > weak["effect_mult"], "军心越可靠，强制施行加成越大"
    assert strong["effect_mult"] <= 1.0, "加成后仍不得超过满额"


def test_troops_mustered_detection_from_journal():
    """调兵判定依据**事务记录**（客观痕迹），不靠诏令自述。"""
    from core.situation_settle import troops_mustered_this_turn
    assert troops_mustered_this_turn([]) is False
    assert troops_mustered_this_turn(
        [{"path": "treasury", "old": 100, "new": 90}]) is False
    assert troops_mustered_this_turn(
        [{"path": "defense_lines.北线_陕西.garrison", "old": 0, "new": 900}]) is True
    assert troops_mustered_this_turn(
        [{"path": "defense_lines.北线_陕西.garrison", "old": 900, "new": 900}]) is False


def test_channels_readout_is_readonly():
    s = _state()
    before = (json.dumps(s.prefectures, sort_keys=True, ensure_ascii=False, default=str),
              json.dumps([vars(u) for u in s.army_units], sort_keys=True, default=str),
              s.treasury, s.prestige, s.population_satisfaction)
    for txt, org in (("赈济", None), ("整饬边备", "枢密院"), ("清丈田亩", "户部")):
        effect_channels(s, org_hint=org, text=txt)
        decree_effect_mult(s, org_hint=org, text=txt)
    after = (json.dumps(s.prefectures, sort_keys=True, ensure_ascii=False, default=str),
             json.dumps([vars(u) for u in s.army_units], sort_keys=True, default=str),
             s.treasury, s.prestige, s.population_satisfaction)
    assert before == after


def test_missing_army_reading_is_not_faked_as_one():
    """军政类但无驻军读数 → 军队项缺失并说明（**不**回落 1.0 假装无事）。"""
    s = _state()
    s.army_units = []
    ch = effect_channels(s, org_hint="枢密院", text="整饬边备")
    assert ch["military"]["applies"] is True
    assert ch["military"]["mult"] is None
    assert "无驻军读数" in ch["military"]["reason"]
    assert "未计入" in ch["note"]


def test_effect_mult_matches_channels():
    s = _state()
    ch = effect_channels(s, org_hint="兵部", text="增修城防")
    assert decree_effect_mult(s, org_hint="兵部", text="增修城防") == pytest.approx(ch["effect_mult"])


def test_military_mult_is_clamped_for_display(monkeypatch):
    """显示值与公式值**同源**：军队可靠度越界时必须先钳位（否则面板显示 ×1.4 对不上账）。"""
    import core.army_models as am

    s = _state()
    monkeypatch.setattr(am, "military_channels",
                        lambda st, r=None: {"enforcement_mult": 1.4, "morale": 60, "arrears": 0})
    ch = effect_channels(s, org_hint="枢密院", text="整饬边备")
    assert ch["military"]["mult"] == 1.0, "越界读数必须钳到 1.0"

    monkeypatch.setattr(am, "military_channels",
                        lambda st, r=None: {"enforcement_mult": -0.3, "morale": 0, "arrears": 0})
    ch2 = effect_channels(s, org_hint="枢密院", text="整饬边备")
    assert ch2["military"]["mult"] == 0.0, "负读数必须钳到 0.0"


def test_army_bonus_capped_at_thirty_percent(monkeypatch):
    """军队**补缺口**上限：`base + (1−base)×30%×可靠度`，不得变成独立倍率。"""
    import core.army_models as am
    from core.decree_effect import ARMY_ENFORCE_BONUS

    s = _state()
    assert ARMY_ENFORCE_BONUS == 0.30
    monkeypatch.setattr(am, "military_channels",
                        lambda st, r=None: {"enforcement_mult": 1.0, "morale": 100, "arrears": 0})
    plain = effect_channels(s, text="赈济陕西流民")["effect_mult"]
    forced = effect_channels(s, text="赈济陕西流民", enforce_troops=True)["effect_mult"]
    assert forced - plain <= (1.0 - plain) * ARMY_ENFORCE_BONUS + 1e-3, \
        "军队补缺不得超过 30% 缺口（容差含 4 位小数舍入）"
    assert forced > plain


def test_official_support_proxy_never_enters_calculation():
    """会签执行率的**盘面代理**只作展示与 AI 权衡，**不得**进入 effect_mult。

    逐诏真实执行率由 `GameState.calc_decree_execution_rate`（需该诏派系立场）计算；
    盘面拿不到立场，故用满意度加权作代理 —— 若代理进了公式，就等于"用代理冒充执行率"。
    """
    s = _state()
    before = effect_channels(s, text="清丈田亩")["effect_mult"]
    ch_before = effect_channels(s, text="清丈田亩")
    assert ch_before["official_support"]["proxy"] is True
    for f in s.factions.values():
        f["satisfaction"] = 1          # 官场配合度代理剧变
    after = effect_channels(s, text="清丈田亩")["effect_mult"]
    assert after == before, "代理进入计算 → 等于伪造执行率"


def test_army_bonus_never_reduces_effect(monkeypatch):
    """军队是**加成**：无论可靠度多低，调兵后的效果都不得低于不调兵。"""
    import core.army_models as am

    s = _state()
    plain = effect_channels(s, text="赈济陕西流民")["effect_mult"]
    for m in (0.0, 0.35, 0.8, 1.0):
        monkeypatch.setattr(am, "military_channels",
                            lambda st, r=None, _m=m: {"enforcement_mult": _m, "morale": 50,
                                                      "arrears": 0})
        forced = effect_channels(s, text="赈济陕西流民", enforce_troops=True)["effect_mult"]
        assert forced >= plain, f"军队可靠度 {m} 时调兵反而更差（应恒为加成）"


def test_missing_clerks_never_means_perfect_execution(monkeypatch):
    """吏治读数缺失 → `defined=False` 且 `effect_mult=None`（**不得**回落 1.0 假装完美）。"""
    import core.clerks as ck

    s = _state()

    def boom(state):
        raise RuntimeError("clerks 不可用")
    monkeypatch.setattr(ck, "decree_execution_mult", boom)
    ch = effect_channels(s, text="清丈田亩")
    assert ch["defined"] is False
    assert ch["effect_mult"] is None, "缺吏治读数不得回落 1.0（那等于默认吏治完美）"
    assert ch["clerks_mult"] is None
    # 调用方（局势推进）必须显式选择"无折扣"策略 —— 该入口不得抛异常
    from core.situation_settle import current_execution_mult
    assert current_execution_mult(s, "清丈田亩") is None
