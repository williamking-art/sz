# -*- coding: utf-8 -*-
"""新旧产业规模化 + AI/大臣感知测试（用户指示）：产业属性/规模统计/认知层档位/大臣立场。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import INDUSTRY_CLASS, INDUSTRY_SHARE_TIERS  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.era_mechanic import (  # noqa: E402
    calc_industry_scale, industry_share_word, industry_brief, settle_industry_shift,
)


def _new_state():
    return GameState("史实")


def test_industry_class():
    """产业属性：旧产业（农田/磨坊/手工作坊/传统织坊/木帆船）+ 新产业（重工业/铁路/商船货运/机器局等）。"""
    assert "农田" in INDUSTRY_CLASS["old"] and "磨坊" in INDUSTRY_CLASS["old"]
    assert "手工作坊" in INDUSTRY_CLASS["old"] and "传统织坊" in INDUSTRY_CLASS["old"]
    assert "木帆船" in INDUSTRY_CLASS["old"]
    assert "重工业" in INDUSTRY_CLASS["new"] and "铁路" in INDUSTRY_CLASS["new"]
    assert "商船货运" in INDUSTRY_CLASS["new"] and "机器局" in INDUSTRY_CLASS["new"]
    assert "火器作坊" in INDUSTRY_CLASS["new"]   # 科技解锁（火药→火器作坊）


def test_industry_scale():
    """产业规模化：旧/新规模 = Σ(建筑数量×等级)、结构 = 新产业占比。"""
    s = _new_state()
    s.projects = [{"type": "农田", "level": 3}, {"type": "机器局", "level": 2}]
    s.prefectures["河北路"]["buildings"] = {"重工业": 2, "传统织坊": 1}
    sc = calc_industry_scale(s)
    assert sc["old_scale"] == 3 + 1          # 农田 3 + 织坊 1
    assert sc["new_scale"] == 2 + 2          # 机器局 2 + 重工业 2
    assert abs(sc["share"] - 4 / 8.0) < 1e-9


def test_industry_share_word():
    """产业结构认知层档位词（脱敏）：纯旧产业/新芽初萌/新旧并立/新产业主导。"""
    assert industry_share_word(0.0) == "纯旧产业"
    assert industry_share_word(0.15) == "新芽初萌"
    assert industry_share_word(0.3) == "新旧并立"
    assert industry_share_word(0.6) == "新产业主导"


def test_industry_brief_and_memory():
    """认知层感知（AI/大臣可见，脱敏）+ 记忆图谱记录产业变迁（新旧并存才记转型）。"""
    s = _new_state()
    s.projects = [{"type": "机器局", "level": 2}, {"type": "农田", "level": 1}]
    brief = industry_brief(s)
    assert "产业：" in brief and "新" in brief
    sc = settle_industry_shift(s, [])
    assert sc["new_scale"] == 2 and sc["old_scale"] == 1
    assert any(k.startswith("industry_") for k in s.memory.entities)


def test_persona_industry_stance():
    """大臣立场反映：守旧大臣抵制新产业、开明大臣力推——立场随产业结构调制（仅在朝生效）。"""
    from content.ministers.persona import stance_evolution
    s = _new_state()
    # 已故大臣（司马光/王安石 1086 年卒）不参与演化（史实修复）
    assert stance_evolution(s, "司马光", turn=1)["score"] == 50
    assert stance_evolution(s, "王安石", turn=1)["score"] == 50
    # 在朝大臣：蔡京（变法·开明）、韩忠彦（守旧）
    base_cai = stance_evolution(s, "蔡京", turn=1)["score"]
    base_han = stance_evolution(s, "韩忠彦", turn=1)["score"]
    # 加入新产业（机器局 2 级）
    s.projects = [{"type": "机器局", "level": 2}]
    s.prefectures["河北路"]["buildings"] = {"重工业": 1}
    after_cai = stance_evolution(s, "蔡京", turn=1)["score"]
    after_han = stance_evolution(s, "韩忠彦", turn=1)["score"]
    assert after_han < base_han, "守旧大臣应抵制新产业（立场降）"
    assert after_cai > base_cai, "开明大臣应力推新产业（立场升）"
