# -*- coding: utf-8 -*-
"""天道业务门面契约测试（P0 修复批 · 2026-10-17）。

覆盖：
1. 三大 AI 管道函数**真实接线**所需契约（事实签用真在任主官、不编人；月报档位；召对定势）；
2. 动态财政安全垫线：**真有写入方**才算动态（旧实现读一个全库没人写的字段）；
3. 门面方法不再恒定档位（见 test_tiandao_engine_core）。
"""
import pytest

from application.game_init import new_game
from core.ai.tiandao_facade import (MEMORIAL_DOMAINS, TianDaoFacade)


@pytest.fixture()
def state():
    return new_game("史实")


# =============================================================================
# 1. 管道一：奏折事实签
# =============================================================================
def test_memorial_seeds_use_real_in_office_minister(state):
    seeds = TianDaoFacade.scan_memorial_seeds(state, limit=3)
    assert seeds, "常态下也应有事实签（否则奏折面板仍可能空）"
    leads = set()
    for row in (getattr(state, "central_orgs", {}) or {}).values():
        if not isinstance(row, dict):
            continue
        if row.get("lead"):
            leads.add(str(row["lead"]))
        holders = row.get("holders") or {}
        if isinstance(holders, dict):
            leads.update(str(v) for v in holders.values() if v)
    for s in seeds:
        assert s["matter_domain"] in MEMORIAL_DOMAINS
        assert s["target_minister"] in leads, (
            f"受命大臣 {s['target_minister']} 不在任（旧实现硬编码历史人名）")
        assert s["trigger_fact"]


def test_memorial_seed_picks_worst_crisis_not_first_dict_key(state):
    """多路同时告急时取**最激化**的一条，而不是 dict 里第一个 key。"""
    prefs = state.prefectures
    for name in list(prefs)[:3]:
        prefs[name]["unrest"] = 41.0
        prefs[name]["local_treasury"] = 1000
    worst = list(prefs)[-1]
    prefs[worst]["unrest"] = 95.0
    prefs[worst]["local_treasury"] = 10
    seeds = TianDaoFacade.scan_memorial_seeds(state, limit=3)
    fin = [s for s in seeds if s["matter_domain"] == "finance"]
    assert fin, "现金告急应产出 finance 事实签"
    assert worst in fin[0]["trigger_fact"]


def test_memorial_seed_does_not_invent_minister_when_orgs_empty(state):
    state.central_orgs = {}
    seeds = TianDaoFacade.scan_memorial_seeds(state, limit=3)
    assert seeds == [], "取不到在任主官时不得编一个人名出来"


# =============================================================================
# 2. 管道二：召对定势
# =============================================================================
def test_stance_undefined_for_unknown_minister():
    res = TianDaoFacade.derive_dialogue_stance("查无此人", "新法如何")
    assert res["defined"] is False
    assert res["stance"] is None, "不得静默冒充『赞同』"


def test_stance_new_party_supports_reform(state):
    res = TianDaoFacade.derive_dialogue_stance("蔡京", "推行青苗保甲新法", state)
    assert res["defined"] is True
    assert res["stance"] in ("力赞", "赞同")
    assert res["intensity"] >= 0.70
    assert res["argument_anchor"]


def test_stance_old_party_opposes_reform(state):
    res = TianDaoFacade.derive_dialogue_stance("陈瓘", "推行青苗保甲新法", state)
    assert res["defined"] is True
    assert res["stance"] in ("力谏", "反对")
    assert res["intensity"] >= 0.80


def test_stance_has_position_on_non_reform_topics(state):
    """非变法议题也要有定势（旧实现对任何非变法话题一律"赞同"）。"""
    cases = {
        "请榷东南盐利以佐国用": "finance",
        "西夏压境当如何措置边事": "military",
        "两浙流民就食当如何赈济": "relief",
        "黄河堤防当如何修筑": "water",
    }
    for topic, kind in cases.items():
        res = TianDaoFacade.derive_dialogue_stance("蔡京", topic, state)
        assert res["defined"] is True
        assert res["topic_kind"] == kind
        assert res["argument_anchor"], f"{topic} 没有论据锚点"


# =============================================================================
# 3. 管道三：月报天机实录
# =============================================================================
def test_omen_is_three_level_and_marks_missing_efficiency(state):
    omen = TianDaoFacade.summarize_monthly_omen(state)
    assert omen["omen_level"] in (None, "吉", "平", "凶")
    assert omen["provider"] == "tiandao_local"
    # 新局未跑过磨勘 ⇒ 无行政效能读数：**必须是 None**（旧实现回落 1.0 = 假装完美）
    if "administrative_efficiency" not in (state.statistics or {}):
        assert omen["admin_efficiency"] is None
        assert omen["admin_efficiency_defined"] is False
    # 民怨告警逐路列出（旧字段名 famine 与数据源不符）
    assert omen["unrest_circuits"] == omen["famine_circuits"]


def test_omen_reports_unrest_circuits(state):
    state.prefectures["两浙路"]["unrest"] = 88.0
    omen = TianDaoFacade.summarize_monthly_omen(state)
    assert "两浙路" in omen["unrest_circuits"]
    assert omen["omen_level"] in ("平", "凶")


# =============================================================================
# 4. 动态财政安全垫线（去魔数）：必须有真实写入方
# =============================================================================
def test_crisis_line_is_calibration_base_without_reading(state):
    line = TianDaoFacade.dynamic_treasury_crisis_line(state)
    src = TianDaoFacade.crisis_line_source(state)
    assert line == 5_000_000
    assert src["source"] == "calibration_base", "无读数时必须如实标注是校准基准"


def test_crisis_line_dynamic_with_reading(state):
    state.statistics["last_monthly_expense"] = 800_000
    assert TianDaoFacade.dynamic_treasury_crisis_line(state, safety_months=3) == 2_400_000
    assert TianDaoFacade.crisis_line_source(state)["source"] == "dynamic"
    state.statistics["last_monthly_expense"] = 5_000_000
    assert TianDaoFacade.dynamic_treasury_crisis_line(state) == 10_000_000   # 上限钳位
    state.statistics["last_monthly_expense"] = 100_000
    assert TianDaoFacade.dynamic_treasury_crisis_line(state) == 1_000_000    # 下限保护


# =============================================================================
# 5. 门面口径：遵从度单列，不改 clerks_mult 本体
# =============================================================================
def test_compliance_returns_documented_multipliers(state):
    res = TianDaoFacade.circuit_decree_compliance(
        {"gov": {"integrity": 0.9, "diligence": 0.8}, "treasury": 20000})
    assert res["verdict"] in ("vigorous", "compliant", "passive", "defiant")
    assert res["mult"] in (1.05, 0.90, 0.65, 0.40)
    assert sum(res["probabilities"].values()) == pytest.approx(1.0, abs=1e-6)
