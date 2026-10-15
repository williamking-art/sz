# -*- coding: utf-8 -*-
"""官员量化五维（三国志风格）与全战式特质动态演进系统测试。

覆盖：
1. 五维三国志风格数字排列展示与口径
2. 43位中枢历史名臣考据五维覆盖与潜质上限
3. 历练经验累积与属性突破成长（潜质受限）
4. 全战式将领特性演进（行为计数触发新特质，洗去互斥对立特质）
5. 科举及第知县生成器杜绝白板
6. 136州府亲民官初始化量化与任免联动
7. 三年磨勘考课驱动监司知通属性与特质成长
8. 存档序列化反序列化无损往返
"""
import os
import pytest
from game.content.ministers.stats import (
    ATTRIBUTE_NAMES,
    HISTORICAL_MINISTER_STATS,
    TRAIT_EVOLUTION_RULES,
    format_official_stats,
    init_official_profile,
    get_or_create_official_stats,
    add_official_experience,
    record_official_action,
    check_and_evolve_traits,
    generate_jinshi_official,
)
from game.core.game_state import GameState
from game.core.save_load import save_game, load_game
from game.core.domains.administration.prefect_officials import (
    init_all_prefect_officials,
    appoint_prefect_official,
    jinshi_to_county,
)
from game.core.domains.administration.official_appraisal import run_triennial_appraisal


def test_stats_format_and_names():
    """验证五维名称与三国志风格排列格式。"""
    assert ATTRIBUTE_NAMES["governance"] == "政略"
    assert ATTRIBUTE_NAMES["finance"] == "财计"
    assert ATTRIBUTE_NAMES["military"] == "军略"
    assert ATTRIBUTE_NAMES["strategy"] == "谋断"
    assert ATTRIBUTE_NAMES["reputation"] == "风望"

    sample = {
        "attrs": {
            "governance": 88,
            "finance": 92,
            "military": 40,
            "strategy": 85,
            "reputation": 70,
        }
    }
    fmt = format_official_stats(sample)
    assert "政略 88" in fmt
    assert "财计 92" in fmt
    assert "军略 40" in fmt
    assert "谋断 85" in fmt
    assert "风望 70" in fmt
    assert " | " in fmt


def test_historical_ministers_stats_coverage():
    """验证43位中枢历史名臣史实五维配置与潜质上限。"""
    assert len(HISTORICAL_MINISTER_STATS) >= 40

    for name, data in HISTORICAL_MINISTER_STATS.items():
        assert "attrs" in data, f"{name} 缺少 attrs"
        assert "potential" in data, f"{name} 缺少 potential"
        attrs = data["attrs"]
        pot = data["potential"]
        for dim in ATTRIBUTE_NAMES:
            assert dim in attrs, f"{name} 缺少维度 {dim}"
            assert dim in pot, f"{name} 缺少潜质 {dim}"
            assert 1 <= attrs[dim] <= 100, f"{name} {dim} 超出范围 1~100"
            assert 1 <= pot[dim] <= 100, f"{name} potential {dim} 超出范围 1~100"
            assert attrs[dim] <= pot[dim], f"{name} 初始值大于潜质上限！"

    # 抽样典型名臣史实特质
    cai_jing = HISTORICAL_MINISTER_STATS["蔡京"]
    assert cai_jing["attrs"]["finance"] >= 95
    assert cai_jing["attrs"]["strategy"] >= 90
    assert cai_jing["attrs"]["reputation"] <= 40

    yue_fei = HISTORICAL_MINISTER_STATS["岳飞"]
    assert yue_fei["attrs"]["military"] >= 95
    assert yue_fei["attrs"]["reputation"] >= 95

    zhong_shi_dao = HISTORICAL_MINISTER_STATS["种师道"]
    assert zhong_shi_dao["attrs"]["military"] >= 90


def test_official_experience_growth_and_caps():
    """验证官员经历累积经验满100成长突破，且受潜质上限约束。"""
    state = GameState()
    # 新建测试官员
    prof = init_official_profile(
        name="测试巡抚",
        rank="正四品",
        custom_attrs={"governance": 60, "finance": 60, "military": 50, "strategy": 50, "reputation": 50},
    )
    prof["potential"]["governance"] = 62  # 仅能升2级
    state.official_stats = {"测试巡抚": prof}

    # 累加50点经验，不足100点不升级
    add_official_experience(state, "测试巡抚", "governance", amount=50)
    assert prof["attrs"]["governance"] == 60
    assert prof["exp"]["governance"] == 50

    # 再累加60点，共110点，升1级，余10点
    add_official_experience(state, "测试巡抚", "governance", amount=60)
    assert prof["attrs"]["governance"] == 61
    assert prof["exp"]["governance"] == 10

    # 再累加100点，升到上限62
    add_official_experience(state, "测试巡抚", "governance", amount=100)
    assert prof["attrs"]["governance"] == 62

    # 再累加200点，受潜质上限约束，不再增加
    add_official_experience(state, "测试巡抚", "governance", amount=200)
    assert prof["attrs"]["governance"] == 62


def test_total_war_traits_evolution():
    """验证全战式特质动态演进：行为计数触发新特质，洗去对立互斥特质。"""
    state = GameState()
    state.short_term_log = []
    
    prof = init_official_profile(
        name="王介甫门生",
        rank="从五品",
        traits=["阿附"],
        custom_attrs={"governance": 75, "finance": 80, "military": 40, "strategy": 75, "reputation": 75},
    )
    state.official_stats = {"王介甫门生": prof}

    # 1. 验证【理财】特质演变：连续执掌财计 12 个月
    record_official_action(state, "王介甫门生", "fiscal_months", amount=12, exp_dim="finance")
    assert "理财" in prof["traits"]

    # 2. 验证【刚直】特质演变与洗去互斥【阿附】：谏诤 3 次
    assert "阿附" in prof["traits"]
    record_official_action(state, "王介甫门生", "remonstrance_count", amount=3, exp_dim="strategy")
    assert "刚直" in prof["traits"]
    assert "阿附" not in prof["traits"], "获得【刚直】后应当冲抵互斥特性【阿附】"

    # 3. 验证【聚敛】冲抵【清正】
    prof["traits"].append("清正")
    assert "清正" in prof["traits"]
    record_official_action(state, "王介甫门生", "corrupt_acts", amount=3)
    assert "聚敛" in prof["traits"]
    assert "清正" not in prof["traits"], "获得【聚敛】后应当冲抵互斥特性【清正】"

    # 检查政务日志沉淀
    assert len(state.short_term_log) >= 2
    titles = [x["title"] for x in state.short_term_log]
    assert any("王介甫门生获得【理财】" in t for t in titles)
    assert any("王介甫门生获得【刚直】" in t for t in titles)


def test_jinshi_generation_no_blank_officials():
    """验证科举新进士生成器：一甲/二甲/三甲绝非白板，具备全量五维、资质、初始特质与计数器。"""
    # 状元（一甲）
    zhuang_yuan = generate_jinshi_official("王十朋", exam_rank_type="一甲", curriculum="策论经义")
    assert zhuang_yuan["name"] == "王十朋"
    assert zhuang_yuan["rank"] == "从八品"
    assert zhuang_yuan["costume_tier"] == "lv"
    assert len(zhuang_yuan["attrs"]) == 5
    assert len(zhuang_yuan["potential"]) == 5
    for dim in ATTRIBUTE_NAMES:
        assert zhuang_yuan["attrs"][dim] >= 60, f"一甲进士 {dim} 属性应优良"
        assert zhuang_yuan["potential"][dim] >= zhuang_yuan["attrs"][dim]
    assert len(zhuang_yuan["traits"]) >= 1
    assert "triggers" in zhuang_yuan
    assert zhuang_yuan["triggers"]["fiscal_months"] == 0

    # 探花（诗赋词章）
    shi_fu = generate_jinshi_official("张孝祥", exam_rank_type="一甲", curriculum="诗赋词章")
    assert shi_fu["attrs"]["reputation"] >= 80
    assert shi_fu["triggers"]["literary_works"] == 1

    # 三甲同进士出身
    san_jia = generate_jinshi_official("李及第", exam_rank_type="三甲", curriculum="经律兼治")
    for dim in ATTRIBUTE_NAMES:
        assert 40 <= san_jia["attrs"][dim] <= 85
        assert san_jia["potential"][dim] >= san_jia["attrs"][dim]


def test_prefect_officials_integrated_with_stats():
    """验证136州府知通量化五维与科举进士出仕蓄水池全覆盖。"""
    state = GameState()
    state.official_stats = {}
    
    # 1. 136 州府亲民官初始化
    prefects = init_all_prefect_officials(state)
    assert len(prefects) == 136

    # 抽查州府亲民官
    sample_seat = next(iter(prefects.values()))
    assert "attrs" in sample_seat["prefect"]
    assert "stats_summary" in sample_seat["prefect"]
    assert "政略" in sample_seat["prefect"]["stats_summary"]
    assert sample_seat["prefect"]["name"] in state.official_stats
    assert "attrs" in sample_seat["subprefect"]
    assert sample_seat["subprefect"]["name"] in state.official_stats

    # 2. 科举放榜授官知县蓄水池（jinshi_to_county）
    jinshi_sample = [
        {"name": "欧阳澈", "county": "阳信县", "exam_rank_type": "一甲"},
        {"name": "胡铨", "county": "新昌县", "exam_rank_type": "二甲"},
    ]
    res = jinshi_to_county(state, jinshi_sample)
    assert res.get("ok") is True
    assigned = res.get("assigned", [])
    assert len(assigned) == 2
    for item in assigned:
        assert "attrs" in item
        assert "stats_summary" in item
        assert "potential" in item
        assert item["name"] in state.official_stats
        # 验证五维不是空，也不是白板
        assert all(item["attrs"][k] > 0 for k in ATTRIBUTE_NAMES)


def test_triennial_appraisal_drives_evolution():
    """验证三年大考磨勘驱动监司知通历练累加与特质演化。"""
    state = GameState()
    state.turn = 36
    state.year = 1104
    state.short_term_log = []
    
    # 初始化监司与州府官
    init_all_prefect_officials(state)
    
    log = []
    res = run_triennial_appraisal(state, log=log)
    assert "promoted_circuits" in res
    assert "demoted_circuits" in res
    
    # 验证有官员累加了历练并产生了行为记录
    has_triggers = False
    for name, prof in state.official_stats.items():
        trig = prof.get("triggers", {})
        if (trig.get("fiscal_months", 0) > 0 or
            trig.get("governance_months", 0) > 0 or
            trig.get("military_border_months", 0) > 0):
            has_triggers = True
            break
    assert has_triggers, "三年考课未能驱动监司/知通的历练经历计数器累加"


def test_save_load_roundtrip_official_stats():
    """验证 official_stats 存档序列化与反序列化完整往返。"""
    state = GameState()
    state.turn = 12
    state.official_stats = {
        "蔡京": {
            "name": "蔡京",
            "rank": "尚书左丞",
            "faction": "变法派",
            "attrs": {"governance": 90, "finance": 96, "military": 40, "strategy": 93, "reputation": 32},
            "potential": {"governance": 95, "finance": 99, "military": 50, "strategy": 98, "reputation": 45},
            "exp": {"governance": 10, "finance": 20, "military": 0, "strategy": 5, "reputation": 0},
            "traits": ["理财", "权谋", "聚敛"],
            "triggers": {"fiscal_months": 24, "corrupt_acts": 5},
            "loyalty": 0.85,
            "corruption": 0.70,
        }
    }

    try:
        ok = save_game(state, slot=99)
        assert ok is True

        new_state = load_game(slot=99)
        assert new_state is not None
        assert hasattr(new_state, "official_stats")
        cai = new_state.official_stats["蔡京"]
        assert cai["attrs"]["finance"] == 96
        assert cai["traits"] == ["理财", "权谋", "聚敛"]
        assert cai["triggers"]["fiscal_months"] == 24
    finally:
        from core.foundation.persistence.slots import _slot_path
        p = _slot_path(99)
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
