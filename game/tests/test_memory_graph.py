# -*- coding: utf-8 -*-
"""Phase 3a 记忆知识库测试：写入/检索/衰减/摘要/存档重建/开局基线/召对注入。"""
import os
import json
import sys

import pytest

_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from memory.memory_graph import MemoryGraph  # noqa: E402
from content.data import SAVE_DIR  # noqa: E402
from core.game_state import GameState  # noqa: E402


def _new_state():
    return GameState("史实")


def _mem_path(slot, archive=False):
    return os.path.join(SAVE_DIR, f"slot_{slot}_memory{'_archive' if archive else ''}.json")


def test_write_and_query():
    """写入决策/事件，query 检索（BFS + 衰减排序）。"""
    g = MemoryGraph()
    g.turn = 10
    g.add_entity("minister_蔡京", "minister", "蔡京", {"faction": "新党"}, turn=0)
    g.add_entity("minister_韩忠彦", "minister", "韩忠彦", {}, turn=0)
    g.add_entity("decision_1", "decision", "崇宁新法", {}, turn=5)
    g.add_relation("minister_蔡京", "decision_1", "supports", weight=1.2, turn=5)
    g.add_relation("minister_韩忠彦", "decision_1", "opposes", weight=1.2, turn=5)
    # query(蔡京) 应返回 supports decision_1（返回 eid，名称经 entities 映射）
    rows = g.query("蔡京", top_k=10)
    assert any(r[0] == "minister_蔡京" and r[1] == "decision_1" and r[2] == "supports" for r in rows)
    rows2 = g.query("minister_蔡京", rtypes=("supports",), top_k=5)
    assert rows2 and rows2[0][2] == "supports"


def test_decay():
    """衰减：w_eff = w_base × exp(-λ×Δturn)，旧关系权重更低但物理保留。"""
    g = MemoryGraph()
    g.add_entity("a", "minister", "甲", {}, turn=0)
    g.add_entity("b", "decision", "旧事", {}, turn=0)
    g.add_entity("c", "decision", "新事", {}, turn=9)
    g.add_relation("a", "b", "involves", weight=1.0, turn=0)   # 10 回合前
    g.add_relation("a", "c", "involves", weight=1.0, turn=9)   # 1 回合前
    g.turn = 10
    rows = g.query("a", top_k=10)
    w_old = next(r[3] for r in rows if r[1] == "b")
    w_new = next(r[3] for r in rows if r[1] == "c")
    assert w_old < w_new, "旧关系应衰减得更弱"
    assert len(g.relations) == 2, "衰减不物理删除"


def test_keyword_and_summarize():
    """keyword_search 与 summarize 紧凑中文摘要。"""
    g = MemoryGraph()
    g.add_entity("e1", "event", "崇宁党禁", {}, turn=1)
    g.add_entity("minister_陈瓘", "minister", "陈瓘", {}, turn=0)
    g.add_relation("e1", "minister_陈瓘", "involves", turn=1, note="被贬")
    g.turn = 3
    hits = g.keyword_search("党禁")
    assert any("崇宁党禁" in h[0] for h in hits)
    summ = g.summarize(g.query("崇宁党禁", top_k=5), max_chars=80)
    assert "崇宁党禁" in summ and "陈瓘" in summ


def test_save_load_and_archive():
    """存档往返 + 归档（低权重旧史移入 archive，不物理删除）。"""
    g = MemoryGraph()
    g.turn = 20
    g.add_entity("a", "minister", "甲", {}, turn=0)
    g.add_entity("d1", "decision", "旧政", {}, turn=0)
    g.add_relation("a", "d1", "produces", weight=0.1, turn=0)  # 低权重 → 归档
    assert g.save(3)
    g2 = MemoryGraph()
    assert g2.load(3)
    assert g2.turn == 20
    moved = g2.archive(3)  # w_eff 0.1×e^-0.6 < 0.25 → 归档
    assert moved >= 1
    assert os.path.exists(_mem_path(3, archive=True))
    if os.path.exists(_mem_path(3)):
        os.remove(_mem_path(3))
    if os.path.exists(_mem_path(3, archive=True)):
        os.remove(_mem_path(3, archive=True))


def test_corrupt_rebuild():
    """损坏 → load 重建空图（不阻断游戏）。"""
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(_mem_path(4), "w", encoding="utf-8") as f:
        f.write("{ 损坏 json !!!")
    g = MemoryGraph()
    ok = g.load(4)
    assert ok is False
    assert g.entities == {} and g.relations == []
    if os.path.exists(_mem_path(4)):
        os.remove(_mem_path(4))


def test_new_game_baseline():
    """开局基线：大臣/派系/机构/外部政权实体入库。"""
    from core.commands import new_game
    s = new_game("史实")
    assert any(k.startswith("minister_") for k in s.memory.entities)
    assert any(k.startswith("faction_") for k in s.memory.entities)
    assert any(k.startswith("org_") for k in s.memory.entities)
    assert any(k.startswith("external_") for k in s.memory.entities)


def test_dialogue_memory_inject():
    """召对注入：query(大臣) → summarize 进 state_summary（假 AI 验证注入内容）。"""
    sys.path.insert(0, _GAME_ROOT)
    sys.path.insert(0, os.path.join(_GAME_ROOT, "tests"))
    from tests.fake_ai_backend import FakeAIClient
    from core.commands import audience_dialogue

    class _FakeDialogueAI(FakeAIClient):
        def __init__(self):
            super().__init__()
            self.captured_summary = ""
            self.available = True

        def dialogue(self, minister_name, faction, stance, traits, role, era, history,
                     player_input, state_summary, state=None):
            self.captured_summary = state_summary
            return {"reply": "臣谨奏。", "mood": "中", "intent_hint": ""}

    s = _new_state()
    s.memory.turn = s.turn
    s.memory.record_decision("宽恤民力", {"treasury": 0}, minister="蔡京", turn=0)
    fake = _FakeDialogueAI()
    audience_dialogue(s, "蔡京", "卿近来如何？", fake)
    assert "相关历史" in fake.captured_summary, "召对应注入该大臣相关历史摘要"


def test_issue_decision_recorded():
    """御笔直发决策写入图谱。"""
    from core.commands_decree import issue_decree
    s = _new_state()
    issue_decree(s, {"title": "赈济京畿", "category": "财政"}, direct=True)
    decisions = [e for e in s.memory.entities.values() if e["type"] == "decision"]
    assert any("赈济京畿" in d["name"] for d in decisions)
