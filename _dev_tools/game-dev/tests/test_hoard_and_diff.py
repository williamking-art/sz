# -*- coding: utf-8 -*-
"""封桩分层代价通道 + 月度奏章「推演变更」章回归测试。

覆盖（货币口径规范 §12.2/§12.3 落地）：
  1. hoard_readout：周转金口径（国库 3×、内帑 1×月常费）与封桩额；
  2. C2 侵渔：守恒划转进吏 POP 私囊（Σ 不变）、封顶、低于阈值不侵渔；
  3. C3/C4 帑藏充溢：超阈值压力月增、回落衰减、达阈值触发富事件卡；
  4. inner_to_treasury 效果键：内帑→国库守恒划转；
  5. 月度奏章「推演变更」章：_last_agent_diff → 可读明细。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import MONTHLY_EXP_CIVIL_BASE, FACTION_INIT  # noqa: E402
from core.events import HISTORICAL_EVENTS, apply_event_choice  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.hoard_settle import (  # noqa: E402
    HOARD_K_GUO, HOARD_K_NEI, INVASION_CAP, INVASION_RATE,
    hoard_readout, settle_hoard,
)
from core.monthly_gazette import CHAPTER_ORDER, build_monthly_gazette  # noqa: E402
from core.settlement_military import _settle_events  # noqa: E402

BASE = float(MONTHLY_EXP_CIVIL_BASE)


def _new_state():
    return GameState("史实")


def _money_total(state):
    """Σ(国库+内帑+各路 POP 财货)——侵渔必须是零残差转移。"""
    total = int(state.treasury) + int(state.imperial_treasury)
    for p in state.prefectures.values():
        for pop in (p.get("pops") or {}).values():
            if isinstance(pop, dict):
                total += int(pop.get("wealth", 0) or 0)
    return total


def _event_by_id(eid):
    return next(e for e in HISTORICAL_EVENTS if e.get("id") == eid)


# ------------------------------------------------------------
# 1) 封桩口径
# ------------------------------------------------------------
def test_hoard_readout_below_caps():
    st = _new_state()
    st.treasury = int(2 * BASE)
    st.imperial_treasury = 0
    ro = hoard_readout(st)
    assert ro["treasury_idle"] == 0
    assert ro["hoard_total"] == 0
    assert ro["overflow"] is False


def test_hoard_readout_caps_and_overflow():
    st = _new_state()
    st.treasury = int(4 * BASE)           # 超国库周转金 3×
    st.imperial_treasury = int(13 * BASE)  # 超内帑周转金 1×，且 > 12× → 充溢
    ro = hoard_readout(st)
    assert ro["treasury_idle"] == pytest.approx(BASE)
    assert ro["imperial_idle"] == pytest.approx(12 * BASE)
    assert ro["overflow"] is True


# ------------------------------------------------------------
# 2) C2 侵渔：守恒 + 封顶
# ------------------------------------------------------------
def test_invasion_conserves_money_and_fills_clerks():
    st = _new_state()
    st.treasury = int(100 * BASE)  # 封桩 ≈ 97×BASE → 侵渔触顶 50 万
    before = _money_total(st)

    def _clerk_wealth(s):
        # 吏胥私囊（新局无吏 POP 时回退官僚——监守自盗同义）
        return sum(int((p.get("pops") or {}).get(k, {}).get("wealth", 0) or 0)
                   for p in s.prefectures.values() for k in ("吏", "官僚"))

    clerks_before = _clerk_wealth(st)
    log = []
    settle_hoard(st, log)
    after = _money_total(st)
    assert after == before, "侵渔必须是零残差转移（Σ 不变）"
    assert _clerk_wealth(st) > clerks_before, "侵渔应流入吏胥/官僚私囊"
    assert any("封桩" in x and "侵渔" in x for x in log)


def test_invasion_capped_and_proportional():
    st = _new_state()
    st.treasury = int(1000 * BASE)  # 封桩巨大 → 触顶
    st.imperial_treasury = 0        # 清掉内帑初值，隔离变量
    log = []
    settle_hoard(st, log)
    # 触顶后国库减少量 = 封顶额（无内帑封桩 → 全由国库出）
    drained = int(1000 * BASE) - int(st.treasury)
    assert drained <= int(INVASION_CAP) + 1, "单月侵渔不得突破封顶"
    assert drained > 0


def test_no_invasion_below_caps():
    st = _new_state()
    st.treasury = int(HOARD_K_GUO * BASE)      # 恰在周转金线内
    st.imperial_treasury = int(HOARD_K_NEI * BASE)
    before = _money_total(st)
    settle_hoard(st, [])
    assert _money_total(st) == before
    assert st.treasury == int(HOARD_K_GUO * BASE)


# ------------------------------------------------------------
# 3) C3/C4 帑藏充溢压力 → 事件卡
# ------------------------------------------------------------
def test_overflow_raises_pressure_and_decays():
    st = _new_state()
    st.treasury = int(30 * BASE)
    settle_hoard(st, [])
    p1 = st.event_pressure["帑藏充溢"]
    assert p1 > 0, "帑藏充溢应推升事件压力"
    st.treasury = int(2 * BASE)  # 回落
    settle_hoard(st, [])
    assert st.event_pressure["帑藏充溢"] < p1, "未超阈值压力应衰减"


def test_overflow_card_triggers_via_settle_events():
    st = _new_state()
    st.year = 1110
    st.event_pressure["帑藏充溢"] = 500
    st.active_events.clear()
    _settle_events(st, [])
    assert any(e["category"] == "帑藏充溢" for e in st.active_events), \
        "压力达阈值应触发帑藏充溢富事件卡（窗口恒开）"


def test_overflow_card_registered_prob_zero():
    """prob=0：不走 get_historical_event 概率触发，仅由封桩压力通道触发。"""
    ev = _event_by_id("treasure_overflow")
    assert ev["prob"] == 0.0
    assert ev["category"] == "帑藏充溢"


# ------------------------------------------------------------
# 4) inner_to_treasury 效果键
# ------------------------------------------------------------
def test_inner_to_treasury_conserves():
    st = _new_state()
    st.imperial_treasury = 5_000_000
    st.treasury = 100_000
    before = _money_total(st)
    ev = _event_by_id("treasure_overflow")
    log = apply_event_choice(st, ev, 0)  # 发内帑 300 万充边备
    assert st.treasury == 100_000 + 3_000_000
    assert st.imperial_treasury == 5_000_000 - 3_000_000
    assert _money_total(st) == before
    assert any("拨充国库" in x for x in log)


def test_inner_to_treasury_truncated_when_poor():
    st = _new_state()
    st.treasury = 100_000           # 清掉国库初值，隔离变量
    st.imperial_treasury = 1_000_000  # 不足 300 万 → 截断
    ev = _event_by_id("treasure_overflow")
    apply_event_choice(st, ev, 0)
    assert st.imperial_treasury == 0
    assert st.treasury == 100_000 + 1_000_000


def test_extravagance_choice_raises_huashigang_pressure():
    st = _new_state()
    st.treasury = 50_000_000
    ev = _event_by_id("treasure_overflow")
    apply_event_choice(st, ev, 1)  # 大兴土木
    assert st.event_pressure["花石纲"] == pytest.approx(25)


def test_refusal_upsets_old_party():
    st = _new_state()
    sat0 = st.factions["旧党"]["satisfaction"]
    ev = _event_by_id("treasure_overflow")
    apply_event_choice(st, ev, 2)  # 拒而弗听
    assert st.factions["旧党"]["satisfaction"] == sat0 - 3


# ------------------------------------------------------------
# 5) 月度奏章「推演变更」章
# ------------------------------------------------------------
def test_gazette_has_agent_diff_chapter():
    st = _new_state()
    st._last_agent_diff = [
        {"path": "treasury", "old": 1_000_000, "new": 900_000,
         "reason": "[finance]月度收支", "source_agent": "finance"},
        {"path": "prefectures.*.pops.农.wealth", "old": 5_000_000, "new": 5_100_000,
         "reason": "cascade: 粜粮完税", "source_agent": "cascade"},
    ]
    gaz = build_monthly_gazette(st, 1101, 3)
    assert "推演变更" in CHAPTER_ORDER
    ch = next(c for c in gaz["chapters"] if c["title"] == "推演变更")
    text = "\n".join(ch["lines"])
    assert "国库" in text and "▼" in text
    assert "农户" in text and "▲" in text
    assert "月度收支" in text


def test_gazette_agent_diff_empty():
    st = _new_state()
    st._last_agent_diff = []
    gaz = build_monthly_gazette(st, 1101, 3)
    ch = next(c for c in gaz["chapters"] if c["title"] == "推演变更")
    assert ch["lines"] == ["本月推演未落新变更。"]


def test_gazette_diff_no_number_leak():
    """隐藏数值（满意度等已登记路径除外）不得以英文路径直出。"""
    st = _new_state()
    st._last_agent_diff = [
        {"path": "prefectures.*.pops.士绅.wealth", "old": 100, "new": 500,
         "reason": "测试", "source_agent": "t"},
    ]
    gaz = build_monthly_gazette(st, 1101, 3)
    ch = next(c for c in gaz["chapters"] if c["title"] == "推演变更")
    assert all(".pops" not in ln and "wealth" not in ln for ln in ch["lines"])


# ------------------------------------------------------------
# 6) 既有领袖名不被派系底色误用（防回归护栏）
# ------------------------------------------------------------
def test_overflow_card_faction_names_valid():
    ev = _event_by_id("treasure_overflow")
    for choice in ev["choices"]:
        for fname in (choice["effects"].get("faction_change") or {}):
            assert fname in FACTION_INIT, f"未登记派系：{fname}"
