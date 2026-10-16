# -*- coding: utf-8 -*-
"""M304: 北宋官员公服RPG装备系统、中枢四府中继、136州府亲民官知通互掣与案头折子准奏闭环测试套件。"""
import os
import sys

_CUR = os.path.dirname(os.path.abspath(__file__))
_SZ = os.path.normpath(os.path.join(_CUR, "..", "..", ".."))
for _p in [_SZ, os.path.join(_SZ, "game"), os.path.normpath(os.path.join(_SZ, ".."))]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
from types import SimpleNamespace

from game.content.ministers.costumes import (
    EQUIPMENT_TIERS,
    FAVOR_BESTOWALS,
    parse_costume_tier,
    get_official_equipment,
    get_or_init_minister_equipment,
    refresh_minister_equipment_on_reassignment,
    bestow_costume_item,
    generate_costume_prompt,
    verify_costume_historical_integrity,
)
from game.content.ministers.data import (
    CENTRAL_ORG_INFO,
    AUTHORITY_MATTERS,
    MINISTERS,
    get_minister_equipment,
    minister_tier,
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


# ---------------------------------------------------------------------------
# 7. 大臣机制特质与中枢六部、中继四府初任主官考据测试
# ---------------------------------------------------------------------------
def test_minister_traits_and_central_org_holders_completed():
    """验证 7 位核心人物特质补齐（赵桓幼龄显式为空），及六部尚书与四府中继主官考据就位。"""
    # 6 位大臣机制特质非空，赵桓为幼龄显式空列表
    assert MINISTERS["赵挺之"]["trait_ids"] == ["刚直"]
    assert MINISTERS["童贯"]["trait_ids"] == ["军略", "阿附"]
    assert MINISTERS["唐恪"]["trait_ids"] == ["理财", "调停"]
    assert MINISTERS["聂昌"]["trait_ids"] == ["刚直"]
    assert MINISTERS["何执中"]["trait_ids"] == ["阿附", "调停"]
    assert MINISTERS["岳飞"]["trait_ids"] == ["忠勇", "军略"]
    assert MINISTERS["赵桓"]["trait_ids"] == []

    # 六部尚书初任考据就位（尚书省下实际执行部门）
    assert CENTRAL_ORG_INFO["吏部"]["holders"]["吏部尚书"] == "邓洵武"
    assert CENTRAL_ORG_INFO["户部"]["holders"]["户部尚书"] == "王古"
    assert CENTRAL_ORG_INFO["礼部"]["holders"]["礼部尚书"] == "陆佃"
    assert CENTRAL_ORG_INFO["兵部"]["holders"]["兵部尚书"] == "章楶"
    assert CENTRAL_ORG_INFO["刑部"]["holders"]["刑部尚书"] == "陈次升"
    assert CENTRAL_ORG_INFO["工部"]["holders"]["工部尚书"] == "蒋之奇"

    # 中继四府初任主官考据就位
    assert CENTRAL_ORG_INFO["通进银台司"]["holders"]["知通进银台司事"] == "丰稷"
    assert CENTRAL_ORG_INFO["都进奏院"]["holders"]["都进奏院提辖官"] == "唐恪"
    assert CENTRAL_ORG_INFO["登闻鼓院"]["holders"]["判登闻鼓院"] == "陈师锡"
    assert CENTRAL_ORG_INFO["枢密院"]["holders"]["知枢密院事"] == "蒋之奇"


# ---------------------------------------------------------------------------
# 8. 官员独立公服部件、皇帝特赐与职位变动自动更新测试
# ---------------------------------------------------------------------------
def test_minister_equipment_dynamic_bestowals_and_reassignment():
    """验证皇帝恩赏特赐部件无感覆盖、职位变动自动刷新公服但保留特赐件。"""
    state = GameState()
    minister_name = "唐恪"

    # 1. 初始状态：从三品，自然服色为紫/绯中坚（从三品按紫）
    init_eq = get_minister_equipment(minister_name, state)
    assert init_eq["slots"]["head"]["tier"] in ("高品", "中品")

    # 2. 模拟官员调任地方为知县（七品，按自然官阶应为绿袍、角带、无鱼袋）
    refresh_minister_equipment_on_reassignment(state, minister_name, "从七品知县")
    county_eq = get_minister_equipment(minister_name, state)
    assert county_eq["tier"] == "lv"
    assert "碧绿" in county_eq["slots"]["robe"]["name"]
    assert county_eq["slots"]["fish_pouch"]["tier"] == "无"
    assert "黑角" in county_eq["slots"]["belt"]["name"]

    # 3. 皇帝特赐「赐玉带」与「赐金鱼袋」
    loyalty_before = state.loyalty[minister_name]
    prestige_before = state.prestige
    # 审查修复：原写 `state.inner_treasury` —— 该属性**不存在**。内帑的权威字段是
    # `imperial_treasury`（见 core/game_state.change_imperial_treasury，前端
    # gameStore.tsx 亦注明「内帑 ← imperial_treasury」）。当时 costumes.py 误读同名，
    # 二者恰好对上故测试通过 —— 即**测试把 bug 编码进了断言**。现同步更正。
    state.imperial_treasury = 2000

    r1 = bestow_costume_item(state, minister_name, "赐玉带")
    assert r1["ok"] is True
    r2 = bestow_costume_item(state, minister_name, "赐金鱼袋")
    assert r2["ok"] is True

    # 忠诚度与皇威成长，内帑扣除
    assert state.loyalty[minister_name] > loyalty_before
    assert state.prestige > prestige_before
    assert state.imperial_treasury == 2000 - 800 - 150

    # 检查装备槽位被特赐部件覆盖
    favored_eq = get_minister_equipment(minister_name, state)
    assert favored_eq["tier"] == "lv"  # 官品仍为七品绿袍
    assert "御赐羊脂白玉带" in favored_eq["slots"]["belt"]["name"]
    assert favored_eq["slots"]["belt"]["tier"] == "特赐"
    assert "鎏金金鱼袋" in favored_eq["slots"]["fish_pouch"]["name"]
    assert favored_eq["slots"]["fish_pouch"]["tier"] == "高品"
    assert "御赐十三銙羊脂白玉带" in favored_eq["bestowals"]
    assert "特赐鎏金金鱼袋" in favored_eq["bestowals"]

    # 4. 职位变动：拔擢升任知州（五品朱红公服）
    # 职位升降自动改变基础部件（绿袍 -> 绯袍、平展幞头、象笏），但皇帝特赐的玉带与金鱼袋持续保留！
    refresh_minister_equipment_on_reassignment(state, minister_name, "正五品知州")
    promoted_eq = get_minister_equipment(minister_name, state)
    assert promoted_eq["tier"] == "fei"
    assert "朱红" in promoted_eq["slots"]["robe"]["name"]
    # 特赐部件独立保留并覆盖
    assert "御赐羊脂白玉带" in promoted_eq["slots"]["belt"]["name"]
    assert "鎏金金鱼袋" in promoted_eq["slots"]["fish_pouch"]["name"]

    # 5. 皇帝进一步加恩「赐紫金鱼袋」（借紫）
    r3 = bestow_costume_item(state, minister_name, "赐紫")
    assert r3["ok"] is True
    borrow_purple_eq = get_minister_equipment(minister_name, state)
    assert borrow_purple_eq["tier"] == "zi"
    assert "深绛紫" in borrow_purple_eq["slots"]["robe"]["name"]
    # 立绘服色联动确认
    assert minister_tier(minister_name, state) == "zi"

    # 6. 最终拜相：升任尚书右仆射（正一品）
    # 自然官阶已达一品，自然服色即为紫袍，特赐玉带依然保留
    refresh_minister_equipment_on_reassignment(state, minister_name, "正一品尚书右仆射")
    prime_eq = get_minister_equipment(minister_name, state)
    assert prime_eq["tier"] == "zi"
    assert "御赐羊脂白玉带" in prime_eq["slots"]["belt"]["name"]


def test_bestow_costume_item_insufficient_funds():
    """库藏与内帑空虚时，御赐重典拦截并提示。"""
    state = GameState()
    # 审查修复：同上，内帑权威字段是 imperial_treasury（原写 inner_treasury 使
    # 本用例看似通过却未真正把内帑清零 —— 拦截其实是靠国库为 0 侥幸成立）。
    state.imperial_treasury = 0
    state.treasury = 0
    res = bestow_costume_item(state, "曾布", "赐玉带")
    assert res["ok"] is False
    assert "库藏空虚" in res["msg"]

