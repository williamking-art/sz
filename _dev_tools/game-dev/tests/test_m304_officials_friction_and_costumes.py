# -*- coding: utf-8 -*-
"""M304: 北宋官员公服RPG装备系统、中枢四府中继、136州府亲民官知通互掣与案头折子准奏闭环测试套件。"""
import pytest
from types import SimpleNamespace

from game.content.ministers.costumes import (
    EQUIPMENT_TIERS,
    parse_costume_tier,
    get_official_equipment,
    generate_costume_prompt,
    verify_costume_historical_integrity,
)
from game.content.ministers.data import (
    CENTRAL_ORG_INFO,
    AUTHORITY_MATTERS,
    get_minister_equipment,
)
from game.core.domains.administration.prefect_officials import (
    init_all_prefect_officials,
    get_prefect_officials,
    check_countersign,
    appoint_prefect_official,
    dismiss_prefect_official,
    jinshi_to_county,
    trigger_joint_liability,
)
from game.core.commands_decree import (
    accept_memorial,
    dismiss_memorial,
    issue_decree,
)
from game.core.game_state import GameState
from game.memory.memory_graph import get_memory_graph


# ---------------------------------------------------------------------------
# 1. 装备系统结构化与历史合规性测试
# ---------------------------------------------------------------------------
def test_costume_equipment_slots_and_tiers():
    """验证高、中、低三档公服 6 大槽位完备性与历史规制。"""
    # 高品（紫袍金鱼）
    zi_eq = get_official_equipment("正一品")
    assert zi_eq["tier"] == "zi"
    slots = zi_eq["slots"]
    assert "极展长直角" in slots["head"]["name"]
    assert "深绛紫" in slots["robe"]["name"]
    assert "金鱼袋" in slots["fish_pouch"]["name"]
    assert "象牙" in slots["hu_tablet"]["material"]

    # 中品（绯袍银鱼）
    fei_eq = get_official_equipment("知府")
    assert fei_eq["tier"] == "fei"
    assert "朱红" in fei_eq["slots"]["robe"]["name"]
    assert "白银鱼袋" in fei_eq["slots"]["fish_pouch"]["name"]

    # 低品（绿袍无鱼）
    lv_eq = get_official_equipment("知县")
    assert lv_eq["tier"] == "lv"
    assert "碧绿" in lv_eq["slots"]["robe"]["name"]
    assert lv_eq["slots"]["fish_pouch"]["tier"] == "无"
    assert "木" in lv_eq["slots"]["hu_tablet"]["material"]

    # 大臣直接获取装备
    zeng_eq = get_minister_equipment("曾布")
    assert zeng_eq["tier"] == "zi"


def test_costume_historical_integrity_and_prompts():
    """严禁明清补子、龙纹等禁忌元素，生图提示词合规。"""
    assert not verify_costume_historical_integrity("胸前饰五品白鹇补子")
    assert not verify_costume_historical_integrity("团龙纹织金袍")
    assert not verify_costume_historical_integrity("Mandarin Square patch")
    assert verify_costume_historical_integrity("纯色素面无纹圆领大袖襕袍")

    prompt_data = generate_costume_prompt("zi")
    assert "绝无任何胸前补子" in prompt_data["prompt_cn"]
    assert "NO chest patches, NO buzi" in prompt_data["prompt_en"]
    assert "buzi" in prompt_data["negative_en"]
    assert "mandarin square" in prompt_data["negative_en"]
    assert "dragon" in prompt_data["negative_en"]


# ---------------------------------------------------------------------------
# 2. 中枢中继四府挂载测试
# ---------------------------------------------------------------------------
def test_central_relays_registered():
    """验证通进银台司、都进奏院、登闻鼓院正式注册进中央机构与事权归属表。"""
    assert "通进银台司" in CENTRAL_ORG_INFO
    assert "都进奏院" in CENTRAL_ORG_INFO
    assert "登闻鼓院" in CENTRAL_ORG_INFO
    assert "枢密院" in CENTRAL_ORG_INFO

    assert AUTHORITY_MATTERS["奏章进纳"]["owner"] == "通进银台司"
    assert AUTHORITY_MATTERS["邸报通达"]["owner"] == "都进奏院"
    assert AUTHORITY_MATTERS["民隐通达"]["owner"] == "登闻鼓院"


# ---------------------------------------------------------------------------
# 3. 136 州府亲民官知通互掣测试
# ---------------------------------------------------------------------------
def test_prefect_officials_136_seats_and_countersign():
    """验证全国 136 州府席位知通底册初始化与公事连署互掣规则。"""
    state = SimpleNamespace(prefect_officials={}, short_term_log=[])
    offs = init_all_prefect_officials(state)
    assert len(offs) == 136

    # 验证知通互掣连署
    sample_key = list(offs.keys())[0]
    sample = offs[sample_key]
    assert "prefect" in sample
    assert "subprefect" in sample
    assert sample["prefect"]["role"] in ("知府", "知州", "知军", "知监")
    assert sample["subprefect"]["role"] == "通判"

    # 模拟知府苛敛、通判刚正拒签
    friction_mock = {
        "prefect": {"name": "贪官某", "integrity": 0.30, "traits": ["聚敛"], "faction": "新党"},
        "subprefect": {"name": "清官某", "integrity": 0.80, "traits": ["刚直"], "faction": "旧党"},
    }
    check_countersign(friction_mock)
    assert friction_mock["countersigned"] is False
    assert friction_mock["efficiency"] == 0.30
    assert "拒签" in friction_mock["friction_reason"]

    # 模拟通判缺员
    empty_vice = {
        "prefect": {"name": "某知府", "integrity": 0.70, "traits": ["老成"], "faction": "中立派"},
        "subprefect": {},
    }
    check_countersign(empty_vice)
    assert empty_vice["countersigned"] is True
    assert empty_vice["efficiency"] == 0.70
    assert "缺员" in empty_vice["friction_reason"]


# ---------------------------------------------------------------------------
# 4. 科举进士知县池与举主连坐测试
# ---------------------------------------------------------------------------
def test_jinshi_county_reservoir_and_joint_liability():
    """验证新科及第授知县进记忆图谱，以及贪墨事发举主保任连坐。"""
    state = SimpleNamespace(
        slot=99,
        turn=5,
        year=1102,
        month=3,
        prestige=100,
        short_term_log=[],
    )
    def fake_change_prestige(d):
        state.prestige += d
    state.change_prestige = fake_change_prestige

    jinshi = [{"name": "范仲淹", "county": "鄞县", "guarantor": "韩忠彦"}]
    res = jinshi_to_county(state, jinshi, slot=99)
    assert res["ok"] is True
    assert res["count"] == 1

    mem = get_memory_graph(99)
    assert "范仲淹" in mem.entities

    # 触发举主连坐
    penalized = trigger_joint_liability(state, "范仲淹", crime="贪墨", slot=99)
    assert "韩忠彦" in penalized
    assert state.prestige < 100
    assert any("举主连坐" in str(x.get("title")) for x in state.short_term_log)


# ---------------------------------------------------------------------------
# 5. 案头折子准奏与留中闭环测试
# ---------------------------------------------------------------------------
def test_accept_and_dismiss_memorial():
    """验证皇帝案头点击准奏转化为三省待签诏草，留中记入怠政档案。"""
    state = GameState()
    state.memorials = [
        {
            "title": "《请修开封漕渠疏》",
            "body": "漕渠淤塞，请发内帑五千贯修治",
            "kind": "finance",
            "source_tag": "通进银台司进呈",
            "official": {"name": "王古", "role": "户部尚书"},
            "guarantor": "曾布",
        },
        {
            "title": "《请停花石纲疏》",
            "body": "江南民怨沸腾，乞罢采运",
            "kind": "governance",
            "source_tag": "登闻鼓院直奏",
        }
    ]

    # 准奏第 1 件
    res_accept = accept_memorial(state, 0)
    assert res_accept["ok"] is True
    assert "准修开封漕渠疏" in res_accept["title"]
    assert len(state.edict_drafts) == 1
    draft = state.edict_drafts[0]
    assert draft["org_hint"] == "户部"
    assert len(state.memorials) == 1

    # 留中第 2 件
    res_dismiss = dismiss_memorial(state, 0)
    assert res_dismiss["ok"] is True
    assert len(state.memorials) == 0
    assert any("留中" in str(x.get("title")) for x in state.short_term_log)


# ---------------------------------------------------------------------------
# 6. 频繁御笔中旨与台谏伏阁请退危机测试
# ---------------------------------------------------------------------------
def test_direct_decree_fu_ge_crisis():
    """一年内连下 3 道御笔直发，引爆【宣德门台谏伏阁请退】危机与政治惩罚。"""
    state = GameState()
    state.direct_decree_used = 0

    # 1st direct decree
    m1 = issue_decree(state, {"title": "特赐近臣金带", "category": "御笔"}, direct=True)
    assert "伏阁" not in m1

    # 2nd direct decree
    state.direct_decree_used = 0  # reset monthly cap for testing
    m2 = issue_decree(state, {"title": "不经中书除授宦官", "category": "御笔"}, direct=True)
    assert "伏阁" not in m2

    # 3rd direct decree in same year
    state.direct_decree_used = 0
    init_prest = state.prestige
    m3 = issue_decree(state, {"title": "御笔亲裁兵饷", "category": "御笔"}, direct=True)
    assert "宣德门台谏伏阁请退" in m3
    assert state.prestige < init_prest
    assert any("台谏伏阁请退" in str(x.get("note", "")) for x in state.short_term_log)
