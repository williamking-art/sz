# -*- coding: utf-8 -*-
"""四机制整合测试（言枢密设计 + 蔡权衡数值）：
大臣家产守恒 / 建筑乘数封顶 / 投资四账闭合 / 存档迁移。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import ESTATE_INIT, ESTATE_FLOW, BUILDING_STD, INVEST_BASE  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.estate_mechanic import (  # noqa: E402
    settle_minister_estate, estate_persona_mod, seize_estate,
    building_level_mult, building_cost, pop_building_effect,
    invest, settle_investments,
)


def _new_state():
    return GameState("史实")


def test_estate_constants():
    """ESTATE_INIT（史翰青 1101 基线）/ESTATE_FLOW/BUILDING_STD/INVEST_BASE 表值。"""
    assert ESTATE_INIT["蔡京"]["wealth"] == 30_000        # 1101 殷实起步（崇宁后膨胀）
    assert ESTATE_INIT["蔡京"]["land"] == 800
    assert ESTATE_INIT["朱勔"]["land"] == 1_500           # 苏州富室
    assert ESTATE_INIT["陈瓘"]["wealth"] == 5_000         # 清贫
    assert ESTATE_FLOW["luxury_rate"] == 0.01
    assert ESTATE_FLOW["persona_rich"] == 1_000_000
    assert BUILDING_STD["水利"]["base_cost"] == 200_000
    assert set(INVEST_BASE) == {"农业", "水利", "工坊", "商铺", "漕运", "军器"}


def test_estate_tier_words():
    """家产档位词（脱敏）：清贫/小康/殷实/豪富/巨富——数值程序管、展示管、AI 只叙事。"""
    from core.estate_mechanic import estate_tier
    assert estate_tier(5_000) == "清贫"
    assert estate_tier(20_000) == "小康"
    assert estate_tier(50_000) == "殷实"
    assert estate_tier(300_000) == "豪富"
    assert estate_tier(2_000_000) == "巨富"


def test_estate_growth_jingkang_anchor():
    """膨胀机制：家产随年按 corruption 膨胀（封顶巨富档）；
    靖康籍没锚点——杨戬/朱勔 后期膨胀至高家产（「尚拥万金」「跨连郡县」供后期验证）。"""
    from core.estate_mechanic import settle_minister_estate, estate_tier
    from content.data import ESTATE_WEALTH_CAP
    s = _new_state()
    s._economy_ai = {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中",
                     "窖银": "无", "城市化": "无", "回乡": "无", "科举": "无",
                     "jiaozi_trust": "稳", "shortage": "平", "maritime": "平",
                     "bank": "稳", "price_trend": "平"}
    # 模拟 25 年（300 月）膨胀（杨戬 corruption 高 → 膨胀快）
    for _ in range(300):
        settle_minister_estate(s, [])
    yang = s.minister_estate["杨戬"]["wealth"]
    assert yang > 100_000, f"杨戬应膨胀至豪富以上：{yang}"
    assert yang <= ESTATE_WEALTH_CAP
    assert estate_tier(yang) in ("豪富", "巨富")


def test_estate_conservation():
    """家产守恒：奢侈消费 + 收租 + 聚敛窖藏后 Σ（家产+工匠/商人+gentry_land 增）不变。"""
    s = _new_state()
    e0 = sum(e["wealth"] for e in s.minister_estate.values())
    crafts0 = sum(p["pops"]["工匠"]["wealth"] for p in s.prefectures.values())
    merc0 = sum(p["pops"]["商人"]["wealth"] for p in s.prefectures.values())
    gl0 = sum(p.get("gentry_land", 0) for p in s.prefectures.values())
    r = settle_minister_estate(s, [])
    e1 = sum(e["wealth"] for e in s.minister_estate.values())
    crafts1 = sum(p["pops"]["工匠"]["wealth"] for p in s.prefectures.values())
    merc1 = sum(p["pops"]["商人"]["wealth"] for p in s.prefectures.values())
    gl1 = sum(p.get("gentry_land", 0) for p in s.prefectures.values())
    # 奢侈消费守恒：家产减 == 工匠/商人增
    assert (e0 - e1) >= r["luxury"] + r["hoard"]
    assert abs((crafts1 + merc1) - (crafts0 + merc0) - r["luxury"]) < 10
    # 收租守恒：gentry_land Σ 增 == rent_total
    assert abs((gl1 - gl0) - r["rent"]) <= 12


def test_estate_persona_and_seize():
    """persona 阈值（丰厚 +0.15 危险度 / 清贫敢谏）+ 抄没守恒（钱→国库、田→官田）。"""
    s = _new_state()
    # 1101 基线无人 ≥100万（崇宁后膨胀才触发丰厚）；先人为推高蔡京家产验证阈值
    s.minister_estate["蔡京"]["wealth"] = 2_000_000
    mod_rich = estate_persona_mod(s, "蔡京")
    assert mod_rich["danger_bonus"] == 0.15
    mod_poor = estate_persona_mod(s, "陈瓘")     # 5千 ≤ 5万 → 清贫敢谏
    assert mod_poor["brave_bonus"] == 0.15
    t0, land0 = s.treasury, getattr(s, "official_land", 0)
    we0 = s.minister_estate["蔡京"]["wealth"]
    got = seize_estate(s, "蔡京")
    assert got[0] == we0                          # 全抄没
    assert s.treasury == t0 + we0                 # 钱→国库
    assert getattr(s, "official_land", 0) == land0 + got[1]  # 田→官田
    assert s.minister_estate["蔡京"]["wealth"] == 0


def test_building_mult_and_cost():
    """建筑乘数：政府 ×1.5/级封顶 2.0；POP ×0.05/Lv 封顶 2.0；成本 ×1.8^(Lv-1)。"""
    assert building_level_mult(1) == 1.0
    assert abs(building_level_mult(2) - 1.5) < 1e-9
    assert building_level_mult(3) == 2.0          # 1.5×1.5=2.25 → 封顶 2.0
    assert pop_building_effect({}) == 1.0
    assert abs(pop_building_effect({"农田": 2, "工坊": 1}) - 1.15) < 1e-9
    assert pop_building_effect({"农田": 25}) == 2.0  # 25×0.05=1.25 → 封顶 2.0
    assert building_cost("水利", 1) == 200_000
    assert building_cost("水利", 2) == int(200_000 * 1.8)


def test_invest_four_accounts_closed():
    """投资四账闭合：国库-投入 + 分期回报回流 == 0（无凭空造灭）；贪腐截留入家产守恒。"""
    s = _new_state()
    t0 = s.treasury
    it0 = s.imperial_treasury
    seized0 = s.minister_estate["蔡京"]["wealth"]   # invest 前读（含截留前）
    ret = invest(s, "农业", 1_000_000, fund="treasury", minister="蔡京", months=12)
    assert ret["ok"] is True
    assert s.treasury == t0 - 1_000_000          # 国库减投入
    # 分期回报回流（每次 1/12；12 次后国库回本含回报）
    for _ in range(12):
        settle_investments(s, [])
    back = s.treasury - (t0 - 1_000_000)
    assert back == ret["return_total"]            # 回报全额回流
    assert s.minister_estate["蔡京"]["wealth"] - seized0 == ret["seized"]  # 截留入家产
    # 内帑投入
    it_before = s.imperial_treasury
    ret2 = invest(s, "商铺", 500_000, fund="imperial_treasury", months=6)
    assert s.imperial_treasury == it_before - 500_000
    for _ in range(6):
        settle_investments(s, [])
    assert s.imperial_treasury == it_before - 500_000 + ret2["return_total"]
    # 四账闭合：国库/内帑 Σ变化 == 回报 - 投入（截留已在回报内扣）
    assert abs((s.treasury - t0) + (s.imperial_treasury - it0)
               - (ret["return_total"] + ret2["return_total"] - 1_500_000)) < 10


def test_estate_roundtrip():
    """家产/投资存档往返（迁移缺省默认）。"""
    from core.save_load import save_game, load_game, _slot_path
    s = _new_state()
    invest(s, "工坊", 300_000, fund="treasury", months=6)
    assert save_game(s, slot=2)
    s2 = load_game(2)
    assert s2 is not None
    assert len(s2.investments) == 1
    assert s2.minister_estate["蔡京"]["wealth"] == ESTATE_INIT["蔡京"]["wealth"]
    for p in s2.prefectures.values():
        assert "buildings" in p and p["buildings"] == {}
    if os.path.exists(_slot_path(2)):
        os.remove(_slot_path(2))
