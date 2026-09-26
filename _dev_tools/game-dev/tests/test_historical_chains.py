# -*- coding: utf-8 -*-
"""历史压力链回归测试（花石纲→方腊 / 海上之盟→金军南侵）。

覆盖：
  1. 新效果键落地：timeline_set（改写位）、pressure_change（事件压力）、
     imperial_treasury（内帑，守恒划转）；
  2. 有效窗口动态前移：get_historical_event / effective_event_window；
  3. 压力触发窗口扣住：窗口未开不爆发不重置（修复方腊 1105 / 金南侵 1107
     提前爆发的实测 bug），开窗即爆；
  4. 南侵节奏分档：允盟（sea_pact_jin）增速 > 拒盟（liao_buffer）。
"""
import os
import random
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

import core.events as events_mod  # noqa: E402
from core.events import (  # noqa: E402
    HISTORICAL_EVENTS, apply_event_choice, category_window_open,
    effective_event_window, get_historical_event,
)
from core.game_state import GameState  # noqa: E402
from core.settlement_military import _settle_events  # noqa: E402


def _event_by_id(eid):
    return next(e for e in HISTORICAL_EVENTS if e.get("id") == eid)


def _new_state():
    return GameState("史实")


def _apply(state, eid, idx):
    return apply_event_choice(state, _event_by_id(eid), idx)


# ------------------------------------------------------------
# 1) 新效果键落地
# ------------------------------------------------------------
def test_timeline_set_on_sea_alliance():
    st = _new_state()
    st.year = 1119
    log = _apply(st, "sea_alliance", 0)  # 允盟
    assert "sea_pact_jin" in st.timeline
    assert st.timeline["sea_pact_jin"]["year"] == 1119
    assert any("史移" in line for line in log)

    st2 = _new_state()
    st2.year = 1119
    _apply(st2, "sea_alliance", 1)  # 拒绝
    assert "liao_buffer" in st2.timeline
    assert "sea_pact_jin" not in st2.timeline


def test_timeline_set_idempotent():
    """改写位已存在时不覆盖原落档年份。"""
    st = _new_state()
    st.year = 1119
    _apply(st, "sea_alliance", 0)
    st.year = 1121
    _apply(st, "sea_alliance", 0)
    assert st.timeline["sea_pact_jin"]["year"] == 1119


def test_pressure_change_applied_and_clamped():
    st = _new_state()
    st.event_pressure["花石纲"] = 100
    _apply(st, "huashigang", 2)  # 严惩朱勔：-80
    assert st.event_pressure["花石纲"] == pytest.approx(20)

    st.event_pressure["花石纲"] = 30
    _apply(st, "huashigang", 2)  # 再 -80 → 不得穿底
    assert st.event_pressure["花石纲"] == 0


def test_imperial_treasury_effect_conservative():
    """花石纲「默许」：贡入御前 → 内帑 +200000、国库不动（民间→库→帑成对划转）。"""
    st = _new_state()
    st.year = 1106
    before_treasury = st.treasury
    before_imperial = st.imperial_treasury
    log = _apply(st, "huashigang", 0)  # 默许
    assert st.imperial_treasury - before_imperial == 200000
    assert st.treasury == before_treasury
    assert any("内帑" in line for line in log)


def test_huashigang_indulgence_raises_uprising_pressure():
    st = _new_state()
    _apply(st, "huashigang", 0)  # 默许：方腊 +15 / 宋江 +8
    assert st.event_pressure["方腊起义"] == pytest.approx(15)
    assert st.event_pressure["宋江起义"] == pytest.approx(8)


# ------------------------------------------------------------
# 2) 有效窗口动态前移
# ------------------------------------------------------------
def test_effective_window_static_without_state():
    ev = _event_by_id("jin_invasion")
    assert effective_event_window(ev, None) == (1125, 1127)


def test_effective_window_shift_by_sea_pact():
    st = _new_state()
    st.timeline["sea_pact_jin"] = {"year": 1118, "label": "t"}
    assert effective_event_window(_event_by_id("jin_invasion"), st) == (1123, 1127)
    assert effective_event_window(_event_by_id("jin_destroys_liao"), st) == (1120, 1125)


def test_effective_window_shift_by_huashigang_indulgence():
    st = _new_state()
    st.event_pressure["花石纲"] = 70
    # 仅有压力、未显式默许 → 不前移（不作为 ≠ 明示默许）
    assert effective_event_window(_event_by_id("fangla_uprising"), st) == (1118, 1121)
    st.timeline["huashigang_indulged"] = {"year": 1106, "label": "t"}
    assert effective_event_window(_event_by_id("fangla_uprising"), st) == (1114, 1121)
    st.event_pressure["花石纲"] = 59
    assert effective_event_window(_event_by_id("fangla_uprising"), st) == (1118, 1121)


def test_huashigang_indulgence_sets_flag():
    st = _new_state()
    _apply(st, "huashigang", 0)  # 默许
    assert "huashigang_indulged" in st.timeline


def test_get_historical_event_shifted_window(monkeypatch):
    """允盟后 1120 年即可能取到金灭辽卡（史实锚点 1122）。"""
    monkeypatch.setattr(events_mod, "HISTORICAL_EVENTS", [_event_by_id("jin_destroys_liao")])
    st = _new_state()
    st.timeline["sea_pact_jin"] = {"year": 1118, "label": "t"}
    monkeypatch.setattr(events_mod.random, "random", lambda: 0.0)  # 必触发
    ev = get_historical_event(1120, 6, st)
    assert ev is not None and ev["id"] == "jin_destroys_liao"
    # 无改写位时 1120 取不到（窗口未开）
    monkeypatch.setattr(events_mod.random, "random", lambda: 0.0)
    assert get_historical_event(1120, 6, _new_state()) is None


# ------------------------------------------------------------
# 3) 压力触发窗口扣住（提前爆发 bug 回归）
# ------------------------------------------------------------
def test_pressure_trigger_held_before_window():
    st = _new_state()
    st.year = 1110  # 方腊窗口未开（史实 1118）
    st.event_pressure["方腊起义"] = 500
    log = []
    _settle_events(st, log)
    assert not any(e["category"] == "方腊起义" for e in st.active_events)
    # 扣住：封顶不重置（开窗即爆）
    assert st.event_pressure["方腊起义"] == pytest.approx(80)


def test_pressure_trigger_fires_at_window():
    st = _new_state()
    st.year = 1118
    st.event_pressure["方腊起义"] = 500
    log = []
    _settle_events(st, log)
    assert any(e["category"] == "方腊起义" for e in st.active_events)
    assert st.event_pressure["方腊起义"] == 0


def test_pressure_trigger_shifted_by_sea_pact():
    st = _new_state()
    st.year = 1123  # 史实锚点 1125，允盟前移至 1123
    st.timeline["sea_pact_jin"] = {"year": 1118, "label": "t"}
    st.event_pressure["金军南侵"] = 500
    _settle_events(st, [])
    assert any(e["category"] == "金军南侵" for e in st.active_events)


def test_category_window_open_unmapped_category_always_open():
    st = _new_state()
    assert category_window_open(st, "灾荒") is True


# ------------------------------------------------------------
# 4) 南侵节奏分档
# ------------------------------------------------------------
def test_jin_invasion_growth_pacing():
    """允盟增速（1.5~3.0/月）显著高于拒盟（0.25~0.75/月）。"""
    def _avg(timeline, trials=200):
        total = 0.0
        for seed in range(trials):
            random.seed(seed)
            st = _new_state()
            st.year = 1121
            st.timeline.update(timeline)
            _settle_events(st, [])
            total += st.event_pressure["金军南侵"]
        return total / trials

    pact = _avg({"sea_pact_jin": {"year": 1118, "label": "t"}})
    buffer_ = _avg({"liao_buffer": {"year": 1118, "label": "t"}})
    assert pact > buffer_ + 0.5
