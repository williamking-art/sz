# -*- coding: utf-8 -*-
"""皇威无上限累积、事权门禁闭环与军队控制权深度耦合测试套件（M325 验收断言）。"""
import pytest
from core.game_state import GameState
from content.data_constants import PRESTIGE_DISPLAY_MAX, INSTITUTION_PARAM_SPEC
from core.domains.administration import institution
from core.decree_confirm import confirm_decree, STATUS_CONFIRMED, STATUS_VETO, STATUS_UNAUTHORIZED
from core.decree_effect import decree_effect_mult
from core.domains.military.army_models import ArmyUnit
from core.settlement_military import _settle_military_diplomacy


def test_prestige_uncapped_and_display_capped():
    """断言 1：皇威物理积累无上限，UI/对外读数严格截断至 100。"""
    state = GameState()
    state.prestige = 90

    # 累加 20 点突破 100
    state.change_prestige(15, "大捷", is_major=True)
    assert state.prestige == 105

    state.change_prestige(15, "开疆", is_major=True)
    assert state.prestige == 120

    # 检验对外信息
    info = state.get_prestige_info()
    assert info["value"] == PRESTIGE_DISPLAY_MAX  # UI 截断为 100
    assert info["raw_value"] == 120               # 物理真账保持 120
    assert info["level"] == "鼎盛"
    assert info["multiplier"] == 1.6


from core.domains.administration.minister_agent import ensure_actor


def test_zhongzhi_prestige_cost_and_menxia_veto():
    """断言 2：中旨扣减皇威，皇威<=40 时门下省李清臣封还词头。"""
    state = GameState()
    state.prestige = 50
    ensure_actor(state, "李清臣", posts=["门下侍郎"], authority=0.8)

    decree = {
        "id": "dec_zhongzhi_01",
        "title": "中旨行方田均税法",
        "category": "变法",
        "is_zhongzhi": True,
        "is_secret": False,
        "effects": {},
    }

    # 1. 皇威 50 时中旨扣除 4 点皇威，勉强放行
    res = confirm_decree(state, "dec_zhongzhi_01", "李清臣", decree=decree, record=True)
    assert state.prestige == 46
    assert res["status"] == STATUS_CONFIRMED

    # 2. 皇威跌至 30（不振），再次下达中旨，李清臣封还词头阻断
    state.prestige = 30
    decree2 = {
        "id": "dec_zhongzhi_02",
        "title": "中旨征发花石纲",
        "category": "征发",
        "is_zhongzhi": True,
        "is_secret": False,
        "effects": {},
    }
    res2 = confirm_decree(state, "dec_zhongzhi_02", "李清臣", decree=decree2, record=True)
    assert res2["status"] == STATUS_VETO
    assert "封还" in res2["message"]

    # 3. 显式降严旨内批强推 (override_by_sovereign)，扣 6 皇威放行
    decree2["override_by_sovereign"] = True
    res3 = confirm_decree(state, "dec_zhongzhi_02", "李清臣", decree=decree2, record=True)
    assert res3["status"] == STATUS_CONFIRMED
    assert res3.get("overridden_by_sovereign") is True
    assert state.prestige == 20  # 30 - 4(中旨) - 6(严旨内批强推) = 20


def test_institutional_params_authority_closure():
    """断言 3：游离编制参数事权门禁闭环（定编归吏部，吏薪归户部）。"""
    state = GameState()

    # 1. 试图由工部修改定编宽严（归吏部）-> 拒绝
    allowed, why = institution.check_authority(state, "posts_quota_mult", "工部")
    assert allowed is False
    assert "不掌「官吏铨选」事权" in why

    # 2. 由吏部（或吏部尚书）修改定编宽严 -> 允许
    allowed2, _ = institution.check_authority(state, "posts_quota_mult", "吏部")
    assert allowed2 is True

    # 3. 试图由吏部修改吏薪（归户部度支调度）-> 拒绝
    allowed3, why3 = institution.check_authority(state, "clerk_pay_mult", "吏部")
    assert allowed3 is False
    assert "不掌「度支调度」事权" in why3

    # 4. 由户部（王古）修改吏薪 -> 允许
    allowed4, _ = institution.check_authority(state, "clerk_pay_mult", "户部")
    assert allowed4 is True


def test_military_authority_and_countersign_coupling():
    """断言 4：调兵必须经枢密院，知通公事连署咬合 decree_effect。"""
    state = GameState()
    ensure_actor(state, "王古", posts=["户部尚书"], authority=0.8)
    ensure_actor(state, "蒋之奇", posts=["知枢密院事"], authority=0.9)

    # 1. 民政诏令调兵强制施行：若承办人为户部（王古）-> 法统门禁阻断
    decree = {
        "id": "dec_mil_01",
        "title": "调兵清丈田亩",
        "enforce_troops": True,
        "effects": {},
    }
    res = confirm_decree(state, "dec_mil_01", "王古", decree=decree, record=True)
    assert res["status"] == STATUS_UNAUTHORIZED
    assert "无调兵权" in res["message"]

    # 2. 若由知枢密院事（蒋之奇）或枢密院签发调兵 -> 放行
    res2 = confirm_decree(state, "dec_mil_01", "蒋之奇", decree=decree, record=True)
    assert res2["status"] == STATUS_CONFIRMED

    # 3. 知通互掣咬合：计算两浙路诏令执行率
    from core.decree_effect import effect_channels
    res_channels = effect_channels(state, kind="民政", route="两浙路")
    assert res_channels["defined"] is True
    assert res_channels["effect_mult"] is not None

    res_mult = decree_effect_mult(state, kind="民政", route="两浙路")
    assert isinstance(res_mult, float)
    assert 0.0 < res_mult <= 1.5


def test_commander_effect_and_arrears_penalty():
    """断言 5：名将提振士气，长期欠饷激化士兵逃亡。"""
    state = GameState()

    # 构造一支军队
    unit = ArmyUnit(
        unit_id="test_army_01",
        name="河北第一军",
        tier="禁军",
        branches={"轻步兵": 5000, "重步兵": 5000},
        station="河北东路",
        defense_line="大名府",
        morale=60,
        training=50,
        commander="章楶",     # 宿将名将 (ability 0.88, corruption 0.20)
        arrears=300000,       # 欠饷 30 万贯（极严重）
    )
    state.army_units = [unit]

    # 执行月度军事结算
    log = []
    _settle_military_diplomacy(state, log)

    # 验证欠饷导致的逃兵扣减与动荡激化
    assert unit.troops < 10000
    assert any("欠饷久滞" in msg and "逃亡" in msg for msg in log)
