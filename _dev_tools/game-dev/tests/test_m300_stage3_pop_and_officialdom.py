# -*- coding: utf-8 -*-
"""M300 / Stage 3 单元测试：POP 微观生计闭环、历史起义内生化、科举三级御试唱名与官员三级磨勘。"""
import pytest

from core.game_state import GameState
from core.domains.economy.macro_climate import ALL_CIRCUITS_21
from core.domains.economy.pop_livelihood import (
    derive_pop_livelihood,
    settle_pop_livelihood,
    REBELLION_THRESHOLD_FANGLA,
    REBELLION_THRESHOLD_SONGJIANG,
    REBELLION_THRESHOLD_BORDER,
)
from core.domains.administration.imperial_exam import (
    CURRICULUM_POLICY,
    CURRICULUM_POETRY,
    CURRICULUM_BALANCED,
    run_triennial_exam_full,
    derive_exam_status,
    set_exam_curriculum,
    run_three_halls_assessment,
)
from core.domains.administration.official_appraisal import (
    derive_circuit_intendants,
    derive_prefecture_officials,
    run_triennial_appraisal,
    assign_sinecure_retirement,
)


def _make_test_state() -> GameState:
    """构造标准 21 路测试状态。"""
    s = GameState()
    s.year = 1101
    s.month = 1
    s.turn = 1
    s.prestige = 60
    s.statistics = {
        "organic_unrest_pool": {},
        "inner_court_unrest_pool": {},
        "active_rebellions": {},
        "administrative_efficiency": 1.0,
    }
    s.exam = {
        "open": True,
        "curriculum": CURRICULUM_BALANCED,
        "examiner_faction": "新党",
    }
    return s


def test_pop_livelihood_and_organic_rebellions():
    """测试 POP 微观生计结余计算与三大历史危机内生触发。"""
    s = _make_test_state()

    # 1. 验证生计派生
    live_lz = derive_pop_livelihood(s, "两浙路")
    assert live_lz["defined"] is True
    assert "农" in live_lz["pops"]
    assert live_lz["living_cost_basic"] > 0

    # 2. 正常运转月度生计结算
    log = []
    res = settle_pop_livelihood(s, log)
    assert res["total_refugees"] >= 0
    assert "两浙路" in res["circuit_unrest"]

    # 3. 模拟极端盘剥触发内生方腊起义
    s.statistics["organic_unrest_pool"]["两浙路"] = 105.0
    settle_pop_livelihood(s, log)
    assert "方腊起义" in s.statistics["active_rebellions"]
    assert s.statistics["active_rebellions"]["方腊起义"]["origin"] == "两浙路·睦州"

    # 4. 模拟京东流民激增触发内生宋江起义
    s.statistics["organic_unrest_pool"]["京东东路"] = 85.0
    settle_pop_livelihood(s, log)
    assert "宋江起义" in s.statistics["active_rebellions"]
    assert s.statistics["active_rebellions"]["宋江起义"]["origin"] == "京东西路·梁山泊"

    # 5. 模拟边防欠饷触发边军哗变
    s.statistics["organic_unrest_pool"]["河北路"] = 95.0
    settle_pop_livelihood(s, log)
    assert "边军哗变" in s.statistics["active_rebellions"]


def test_imperial_exam_curriculum_and_palace_ranking():
    """测试科举三级大比、命题取向、唱名赐第与 POP 守恒。"""
    s = _make_test_state()

    # 计算取士前全国总人口
    def total_pop():
        return sum(
            sum(int((p.get("pops", {}).get(k, {}) or {}).get("size", 0) or 0)
                for k in ["农", "士绅", "官僚", "商人", "工匠"])
            for p in s.prefectures.values()
        )

    pop_before = total_pop()

    # 1. 设定经义策论命题取士
    set_exam_curriculum(s, CURRICULUM_POLICY)
    status = derive_exam_status(s)
    assert status["curriculum"] == CURRICULUM_POLICY

    log = []
    exam_res = run_triennial_exam_full(s, tier="中", curriculum=CURRICULUM_POLICY, log=log)
    assert exam_res["taken"] > 0
    assert len(exam_res["top_three"]) == 3
    assert exam_res["top_three"][0]["rank"] == "状元及第"

    # 验证 POP 总人口严格守恒（农/士绅减少，官僚待阙增加）
    pop_after = total_pop()
    assert pop_before == pop_after, f"科举入仕前后总 POP 必须守恒: {pop_before} vs {pop_after}"

    # 2. 测试诗赋词章命题取士皇威增益
    prestige_before = s.prestige
    run_triennial_exam_full(s, tier="中", curriculum=CURRICULUM_POETRY, log=log)
    assert s.prestige > prestige_before

    # 3. 测试太学三舍法直接释褐授官
    pop_before_3h = total_pop()
    th_res = run_three_halls_assessment(s, log)
    assert th_res["graduates"] >= 0
    assert total_pop() == pop_before_3h


def test_official_intendants_and_triennial_appraisal():
    """测试 21 路四大监司、知通互掣与三年磨勘考课。"""
    s = _make_test_state()

    # 1. 验证 21 路监司派生
    intendants = derive_circuit_intendants(s, "两浙路")
    assert intendants["defined"] is True
    assert "帅司" in intendants["intendants"]
    assert "漕司" in intendants["intendants"]
    assert "宪司" in intendants["intendants"]
    assert "仓司" in intendants["intendants"]

    # 2. 验证知通互掣
    officials_info = derive_prefecture_officials(s, "京畿路")
    assert officials_info["defined"] is True
    assert "has_vice_prefect" in officials_info

    # 3. 运行三年磨勘考课
    log = []
    appraisal_res = run_triennial_appraisal(s, log)
    assert "promoted_circuits" in appraisal_res
    assert "administrative_efficiency" in appraisal_res

    # 4. 特旨除授宫观祠禄（安全冷冻机制）
    kaifeng_guan = s.prefectures["京畿路"]["pops"]["官僚"]
    on_post_before = kaifeng_guan["on_post"]
    sinecure_before = kaifeng_guan["sinecure"]

    ret = assign_sinecure_retirement(s, "京畿路", 10, reason="政争失势冷冻", log=log)
    assert ret["assigned"] == 10
    assert kaifeng_guan["on_post"] == on_post_before - 10
    assert kaifeng_guan["sinecure"] == sinecure_before + 10
