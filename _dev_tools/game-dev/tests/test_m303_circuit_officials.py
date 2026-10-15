# -*- coding: utf-8 -*-
"""M303 单元测试：省路级主要官员体系（21路四监司与路府知通人事真账）。"""
import pytest

from core.game_state import GameState
from core.domains.economy.macro_climate import ALL_CIRCUITS_21
from core.domains.administration.circuit_officials import (
    init_all_circuit_officials,
    get_circuit_officials,
    appoint_circuit_official,
    dismiss_circuit_official,
    CIRCUIT_OFFICIAL_ROLES,
)
from core.domains.administration.official_appraisal import (
    derive_circuit_intendants,
    derive_prefecture_officials,
)
from core.region_brief import build_region_brief


def test_circuit_officials_coverage_all_21_circuits():
    """验证全国 21 路全部配齐四监司与路府知通，无一遗漏。"""
    s = GameState()
    all_offs = init_all_circuit_officials(s)
    
    assert len(all_offs) == len(ALL_CIRCUITS_21), f"覆盖路数不符：{len(all_offs)}"
    
    expected_roles = {"shuai", "cao", "xian", "cang", "prefect", "vice_prefect"}
    for c in ALL_CIRCUITS_21:
        entry = all_offs[c]
        assert entry["circuit"] == c
        assert "capital" in entry and entry["capital"]
        offs = entry["officials"]
        assert set(offs.keys()) == expected_roles, f"{c} 官员编制缺失：{set(offs.keys())}"
        for r_key, o in offs.items():
            assert o["name"] and len(o["name"]) >= 2
            assert o["faction"] in ("新党", "旧党", "中立派", "军功集团", "皇党集团", "无")
            assert o["official_title"] and len(o["official_title"]) >= 2
            assert 0.0 <= o["effectiveness"] <= 1.0


def test_historical_circuit_officials_placement():
    """验证关键历史名臣精确安置于建中靖国元年史实岗位。"""
    s = GameState()
    
    # 1. 京畿路：知开封府吴居厚、户部尚书/转运使王古
    jingji = get_circuit_officials(s, "京畿路")["officials"]
    assert jingji["prefect"]["name"] == "吴居厚"
    assert jingji["prefect"]["faction"] == "新党"
    assert jingji["cao"]["name"] == "王古"

    # 2. 两浙路：转运使唐恪、安抚使童贯、提刑使江公望
    lz = get_circuit_officials(s, "两浙路")["officials"]
    assert lz["cao"]["name"] == "唐恪"
    assert lz["shuai"]["name"] == "童贯"
    assert lz["xian"]["name"] == "江公望"

    # 3. 河东路：老将种师道领经略安抚使、章楶知太原府
    hd = get_circuit_officials(s, "河东路")["officials"]
    assert hd["shuai"]["name"] == "种师道"
    assert "经略安抚使" in hd["shuai"]["official_title"]
    assert hd["prefect"]["name"] == "章楶"

    # 4. 京东东路：知海州张叔夜、提刑使陈瓘
    jdd = get_circuit_officials(s, "京东东路")["officials"]
    assert jdd["prefect"]["name"] == "张叔夜"
    assert jdd["xian"]["name"] == "陈瓘"


def test_circuit_official_appointment_and_dismissal():
    """验证省路主官的动态任免与调离机制。"""
    s = GameState()
    
    # 1. 调任李纲为两浙路转运使
    ok = appoint_circuit_official(
        s,
        circuit="两浙路",
        role_key="cao",
        official_data={
            "name": "李纲",
            "faction": "军功集团",
            "rank": "从四品",
            "integrity": 0.95,
            "ability": 0.88,
            "traits": ["刚直", "尽节"],
            "historical": True,
        }
    )
    assert ok is True
    lz_new = get_circuit_officials(s, "两浙路")["officials"]["cao"]
    assert lz_new["name"] == "李纲"
    assert lz_new["faction"] == "军功集团"
    assert lz_new["effectiveness"] > 0.85

    # 2. 罢免两浙路帅司
    old_shuai = dismiss_circuit_official(s, "两浙路", "shuai", reason="御史弹劾")
    assert old_shuai["name"] == "童贯"
    
    lz_shuai = get_circuit_officials(s, "两浙路")["officials"]["shuai"]
    assert lz_shuai["vacant"] is True
    assert "权知" in lz_shuai["name"] or "缺员" in lz_shuai["name"]


def test_official_appraisal_and_region_brief_integration():
    """验证考课模型与路级简报自动整合省路长官真账。"""
    s = GameState()
    
    # 1. 验证 official_appraisal 中的 derive_circuit_intendants 携带真账
    intendants = derive_circuit_intendants(s, "河东路")["intendants"]
    assert intendants["帅司"]["name"] == "种师道"
    assert intendants["帅司"]["faction"] == "军功集团"

    pref_info = derive_prefecture_officials(s, "河东路")
    assert pref_info["prefect"]["name"] == "章楶"

    # 2. 验证 build_region_brief 输出中携带完整的 officials 字典
    brief = build_region_brief(s)
    assert "routes" in brief and len(brief["routes"]) > 0
    route_lz = next(r for r in brief["routes"] if r["name"] == "两浙路")
    assert "officials" in route_lz
    offs_map = route_lz["officials"]["officials"]
    assert "cao" in offs_map and offs_map["cao"]["name"]
