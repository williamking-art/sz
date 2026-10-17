# -*- coding: utf-8 -*-
"""测试朝廷层民间 POP 模糊账目与信息摩擦建模。

验证目标：
1. 朝廷视角所见民间 POP 必须为带区间的模糊账目，绝不能直接拿到上帝视角真账；
2. 簿籍申报人丁估算上限 < 系统物理真实人口（存在结构性逃丁与未登籍隐户）；
3. 申报税基财富估算上限 < 系统物理真实 POP 财富（豪强瞒报、诡名寄产）；
4. 吏员把持度 grip 驱动信息摩擦：把持度恶化导致在籍率走低、瞒报率走高、版籍失真；
5. readout_hub 注册完备，纯派生只读不改物理 state。
"""
import pytest
from application.game_init import new_game
from core.domains.economy import spatial_warehouse_readout as swr
from core.domains.economy import readout_hub


def test_court_blurred_pop_readout_structure():
    """验证朝廷民间模糊账目结构与区间属性。"""
    state = new_game()
    rep = swr.court_blurred_pop_ledger(state)

    assert rep["scope"] == "court_blurred_perspective"
    assert rep["display"] != "undefined"
    assert rep["clarity_level"] in ("较为明晰", "版籍模糊", "严重失真")

    # 区间属性
    h_min, h_max = rep["reported_headcount_range"]
    assert 0 < h_min < h_max

    w_min, w_max = rep["reported_wealth_range"]
    assert 0 < w_min < w_max

    # 比率属性
    assert 0.50 <= rep["in_register_ratio"] <= 0.95
    assert 0.10 <= rep["concealment_ratio"] <= 0.60


def test_reported_vs_physical_ground_truth():
    """核心断言：朝廷簿籍奏报必定小于底层物理真账（信息摩擦与隐匿）。"""
    state = new_game()
    rep = swr.court_blurred_pop_ledger(state)

    # 1. 物理真账人丁与财富
    real_size = sum(pop["size"] for p in state.prefectures.values() for pop in p["pops"].values())
    real_wealth = sum(pop["wealth"] for p in state.prefectures.values() for pop in p["pops"].values())

    h_min, h_max = rep["reported_headcount_range"]
    w_min, w_max = rep["reported_wealth_range"]

    # 朝廷奏报的最高上限依然无法穿透底层全部真账（必有隐匿逃户）
    assert h_max < real_size, f"朝廷在籍奏报上限 ({h_max}) 不应超过或等于底层真丁口 ({real_size})"
    assert w_max < real_wealth, f"朝廷申报财富上限 ({w_max}) 不应超过或等于底层真实财富 ({real_wealth})"


def test_grip_drives_information_friction():
    """验证官吏把持度升高加深信息模糊与隐匿。"""
    state = new_game()

    # 模拟把持度恶化（吏强官弱，把持度推到 0.85）
    for p in state.prefectures.values():
        p["clerks_detail"] = {"grip": 0.85}

    rep_bad = swr.court_blurred_pop_ledger(state)
    assert rep_bad["clarity_level"] == "严重失真"
    assert rep_bad["concealment_ratio"] > 0.40
    assert rep_bad["in_register_ratio"] < 0.75


def test_readout_hub_blurred_pop_entry():
    """验证 readout_hub 成功聚合 court_blurred_pop_ledger。"""
    state = new_game()
    hub_rep = readout_hub.collect(state)

    item = hub_rep["readouts"].get("court_blurred_pop_ledger")
    assert item is not None
    assert item["display"] != "undefined"
    assert "在籍约" in item["display"]
    assert "申报财富" in item["display"]
