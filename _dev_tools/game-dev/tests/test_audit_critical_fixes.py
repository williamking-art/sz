# -*- coding: utf-8 -*-
"""2026-10-17 审计必修缺陷验收测试 (M326)。

覆盖：
1. A-4: 皇威无上限后交子发行上限有界截断 (bounded jiaozi ceiling)；
2. A-7: 欠饷逃兵人数与地方民户/流民 POP 人数守恒闭环 (desertion POP conservation)；
3. A-8: 科举殿试唱名皇威变动走 change_prestige 单点与台账留痕。
"""
import pytest
from application.game_init import new_game
from core.domains.administration.imperial_exam import (
    run_triennial_exam_full,
    CURRICULUM_POETRY,
)
from core.settlement_military import _settle_military_diplomacy


def test_a4_jiaozi_ceiling_bounded_by_prestige():
    """验证 A-4: prestige 0/50/100/350/800 时交子发行上限单调不降且有明确上界（3.0倍）。"""
    s = new_game("史实")
    s.jiaozi["reserve"] = 2000000

    # 皇威 0 -> 1.0 倍 = 200 万
    s.prestige = 0
    c0 = s._jiaozi_ceiling()
    assert c0 == 2000000

    # 皇威 50 -> 2.0 倍 = 400 万
    s.prestige = 50
    c50 = s._jiaozi_ceiling()
    assert c50 == 4000000

    # 皇威 100 -> 3.0 倍 = 600 万
    s.prestige = 100
    c100 = s._jiaozi_ceiling()
    assert c100 == 6000000

    # 皇威 350 -> 依然被截断在 3.0 倍 = 600 万（彻底杜绝 1600 万的爆炸放大）
    s.prestige = 350
    c350 = s._jiaozi_ceiling()
    assert c350 == 6000000

    # 皇威 800 -> 依然为 600 万
    s.prestige = 800
    c800 = s._jiaozi_ceiling()
    assert c800 == 6000000

    # 验证单调不降
    assert c0 <= c50 <= c100 <= c350 <= c800


def test_a7_military_desertion_pop_conservation():
    """验证 A-7: 欠饷逃兵从部队编制扣除后，必须严格回流到驻地农 POP / 流民池，人守恒。"""
    s = new_game("史实")
    assert s.army_units, "游戏应有初始军队编制"
    u = s.army_units[0]
    st = u.station
    pdata = s.prefectures[st]
    farmer_pop = pdata["pops"]["农"]

    # 构造欠饷 30 万贯条件（超过 250,000 阈值）
    u.arrears = 300000
    init_troops = u.troops
    init_farmer_size = farmer_pop.get("size", 0)
    init_refugees = pdata.get("refugees", 0)

    log = []
    _settle_military_diplomacy(s, log)

    end_troops = u.troops
    end_farmer_size = farmer_pop.get("size", 0)
    end_refugees = pdata.get("refugees", 0)

    delta_troops = end_troops - init_troops
    delta_pop = (end_farmer_size - init_farmer_size) + (end_refugees - init_refugees)

    # 确实发生了逃兵（欠饷 30 万贯时月逃亡可观测）
    assert delta_troops < 0, "严重欠饷应发生兵变逃亡"
    # 人守恒：部队减少的人丁与 POP/流民增加的人丁精确相加为 0
    assert delta_troops + delta_pop == 0


def test_a8_palace_exam_prestige_through_single_point():
    """验证 A-8: 殿试诗赋唱名提升皇威必须经由 state.change_prestige 单点，并记录历史台账。"""
    s = new_game("史实")
    s.prestige = 60
    hist_len0 = len(getattr(s, "_prestige_history", []))

    # 组织一届诗赋殿试
    log = []
    res = run_triennial_exam_full(s, curriculum=CURRICULUM_POETRY, log=log)

    assert res["taken"] > 0
    # 验证通过 change_prestige 增加了皇威
    assert s.prestige >= 65
    hist = getattr(s, "_prestige_history", [])
    assert len(hist) > hist_len0
    # 验证历史台账里登记了该笔因由
    assert any(h[2] == "殿试唱名" for h in hist)
