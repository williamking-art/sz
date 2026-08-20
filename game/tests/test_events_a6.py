# -*- coding: utf-8 -*-
"""A6 派单回归测试：5 张新史实事件卡注册、档位 effects 换算与双格式兼容。

覆盖：
  - 新事件卡结构完整、能经既有 get_historical_event 触发链正常取到；
  - 档位词 effects 经换算层落地到 GameState（treasury/population/prestige/tech/派系/军力）；
  - 旧事件数字 effects 直写不动（双格式兼容，既有行为不回归）。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

import core.events as events_mod  # noqa: E402
from core.events import (  # noqa: E402
    HISTORICAL_EVENTS, apply_event_choice, get_historical_event,
)
from core.game_state import GameState  # noqa: E402

A6_IDS = [
    "chongning_party_proscription",  # E1 崇宁党禁
    "school_three_halls",            # E2 学校贡举法
    "recover_hehuang",               # E3 复河湟
    "chongning_coinage",             # E4 铸当十钱
    "fangtian_taxation",             # E5 方田均税
]


def _event_by_id(eid):
    return next(e for e in HISTORICAL_EVENTS if e.get("id") == eid)


def _new_state():
    return GameState("史实")


# ------------------------------------------------------------
# 1) 新事件卡注册与结构
# ------------------------------------------------------------
def test_a6_historical_events_registered():
    ids = [e.get("id") for e in HISTORICAL_EVENTS]
    assert len(HISTORICAL_EVENTS) == 14  # 既有 9 条 + A6 新增 5 条，纯增量
    for eid in A6_IDS:
        assert eid in ids, f"新事件 {eid} 未注册进 HISTORICAL_EVENTS"
        ev = _event_by_id(eid)
        lo, hi = ev["year_range"]
        assert 1101 <= lo <= hi <= 1125
        assert 0 < ev["prob"] <= 1
        assert ev["title"] and ev["desc"] and ev["category"]
        assert ev["choices"] and all(c.get("text") and isinstance(c.get("effects"), dict)
                                     for c in ev["choices"])


def test_a6_get_historical_event_returns_new_card(monkeypatch):
    """新格式事件卡（档位词 effects）能经既有 get_historical_event 触发链正常取到。"""
    monkeypatch.setattr(events_mod, "HISTORICAL_EVENTS", [_event_by_id("fangtian_taxation")])
    monkeypatch.setattr(events_mod.random, "random", lambda: 0.0)  # 必触发
    ev = get_historical_event(1110, 6)
    assert ev is not None and ev["id"] == "fangtian_taxation"


# ------------------------------------------------------------
# 2) 档位 effects 换算落地
# ------------------------------------------------------------
def test_a6_tier_effects_converted_and_applied():
    s = _new_state()
    t0, p0, ps0 = s.treasury, s.prestige, s.population_satisfaction
    e4 = _event_by_id("chongning_coinage")
    log = apply_event_choice(s, e4, 0)  # 改铸当十钱：treasury 中升 / 民心 中降 / 皇威 小降
    assert s.treasury == t0 + 800_000
    assert s.population_satisfaction == max(0, min(100, ps0 - 3))
    assert s.prestige == max(0, min(100, p0 - 2))
    assert log[0].startswith("选择：")


def test_a6_faction_change_tiers_applied():
    s = _new_state()
    e1 = _event_by_id("chongning_party_proscription")
    before = {fn: s.factions[fn]["satisfaction"] for fn in ("新党", "旧党", "清流言官", "东南士人")}
    apply_event_choice(s, e1, 0)  # 颁行党籍：新党 中升 / 旧党 大降 / 清流 小降 / 东南士人 微降
    assert s.factions["新党"]["satisfaction"] == min(100, before["新党"] + 3)
    assert s.factions["旧党"]["satisfaction"] == max(0, before["旧党"] - 4)   # 大=1.5×3=4.5→round 4
    assert s.factions["清流言官"]["satisfaction"] == max(0, before["清流言官"] - 2)
    assert s.factions["东南士人"]["satisfaction"] == max(0, before["东南士人"] - 1)


def test_a6_tech_tier_applied():
    s = _new_state()
    e2 = _event_by_id("school_three_halls")
    apply_event_choice(s, e2, 0)  # 行三舍升贡：tech 中升（开局 tech level=50）
    assert s.tech["level"] == min(100, 50 + 3)


def test_a6_army_tier_maps_to_army_strength():
    s = _new_state()
    e3 = _event_by_id("recover_hehuang")
    u = s.army_units[0]
    tr0, mo0 = u.training, u.morale
    apply_event_choice(s, e3, 0)  # 进讨：army 小升 → 各军训练/士气 +2
    assert u.training == min(100, tr0 + 2)
    assert u.morale == min(100, mo0 + 2)


# ------------------------------------------------------------
# 3) 旧事件数字直写（双格式兼容，行为不回归）
# ------------------------------------------------------------
def test_a6_old_style_digits_passthrough():
    s = _new_state()
    t0, p0 = s.treasury, s.prestige
    hs = _event_by_id("huashigang")
    log = apply_event_choice(s, hs, 0)  # 默许：prestige -1 / population -2 / treasury +200000
    assert s.treasury == t0 + 200_000
    assert s.prestige == max(0, min(100, p0 - 1))
    assert log[0].startswith("选择：")
