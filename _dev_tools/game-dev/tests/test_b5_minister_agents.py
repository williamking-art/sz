# -*- coding: utf-8 -*-
"""B5 · 官员个体 Agent 的定向回归（规格 `market-civilian-economy` B5-1/2/3）

对应《建议》§3.3 七项最小状态、§7.1「人是主体」、§7.2「逐人意图」、
§7.6「记忆不跨人物混用」、R7.7「批量与逐人在身份/记忆/归因上**等价**」。

锁定：
- 逐人隔离（甲的私话不是乙亲闻）；
- 权限**未定义 ≠ 无权**（`None` 单独判定，不擅自归 0 或有权）；
- 沉默/无意图**不得**冒充"忠诚支持"；
- 换职改权限与信息可见，**不换人格、不抹记忆**；
- 读档后记忆仍在，且**不伪造他人记忆**。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402
from core.minister_agent import (  # noqa: E402
    ACTOR_MIN_FIELDS, MINISTER_STATUS_OUT, actor_ids_of, actor_view, can_act,
    ensure_actor, intents_of, recall, record_intent, remember,
)


def _state():
    s = GameState("史实")
    init_legacies(s)
    return s


# ====================================================== 身份与最小状态
def test_actor_has_seven_minimum_fields():
    """§3.3 七项最小状态齐全。"""
    s = _state()
    a = ensure_actor(s, "文彦博", authority=0.8)
    for f in ACTOR_MIN_FIELDS:
        assert f in a, f"缺少最小状态字段 {f}"
    assert actor_ids_of(s) == ["文彦博"]


def test_empty_actor_id_is_rejected():
    """拒绝式：空 id 不新建"无名官员"。"""
    s = _state()
    with pytest.raises(ValueError):
        ensure_actor(s, "  ")
    assert actor_ids_of(s) == []


def test_unknown_actor_view_is_none_not_empty_shell():
    """未建立 → `None`（缺失≠0，不用空壳冒充存在）。"""
    s = _state()
    assert actor_view(s, "不存在") is None


def test_ensure_actor_does_not_overwrite_memory():
    """重复 ensure **不覆盖**已有记忆/意图。"""
    s = _state()
    ensure_actor(s, "A")
    remember(s, "A", kind="召对", text="臣附议")
    record_intent(s, "A", intent="加税")
    ensure_actor(s, "A")            # 幂等再调
    assert len(recall(s, "A")) == 1
    assert len(intents_of(s, "A")) == 1


# ====================================================== 权限
def test_authority_undefined_is_not_zero_or_full():
    """权限未定义（None）→单独判定，不按"无权"也不按"有权"。"""
    s = _state()
    ensure_actor(s, "A")            # authority 未给
    r = can_act(s, "A")
    assert r["ok"] is False
    assert r["reason"] == "authority_undefined"
    v = actor_view(s, "A")
    assert v["has_undefined_authority"] is True


def test_out_of_office_cannot_act():
    s = _state()
    ensure_actor(s, "A", authority=0.9)
    s.minister_agents["A"]["status"] = MINISTER_STATUS_OUT
    r = can_act(s, "A")
    assert r["ok"] is False and r["reason"] == "not_in_office"


def test_in_office_with_authority_can_act():
    s = _state()
    ensure_actor(s, "A", authority=0.5)
    r = can_act(s, "A")
    assert r["ok"] is True and r["authority"] == 0.5


# ====================================================== 记忆隔离
def test_memory_is_private_per_person():
    """§7.6：甲的私下谈话不是乙亲闻。"""
    s = _state()
    ensure_actor(s, "甲", authority=0.9)
    ensure_actor(s, "乙", authority=0.9)
    remember(s, "甲", kind="私谈", text="甲告诉乙：此议可行")
    assert len(recall(s, "甲")) == 1
    assert len(recall(s, "乙")) == 0, "乙读到了甲的私谈"
    assert intents_of(s, "乙") == [], "乙的意图被他人污染"


def test_public_info_can_be_shared_with_source():
    """公开信息带 `source` 时非私密（可转述）。"""
    s = _state()
    ensure_actor(s, "甲", authority=0.9)
    ensure_actor(s, "乙", authority=0.9)
    remember(s, "甲", kind="朝议", text="廷议已定", source="朝议")
    pub = recall(s, "甲", include_private=False)
    assert len(pub) == 1


# ====================================================== 意图
def test_intents_are_per_person_and_filterable_by_turn():
    s = _state()
    s.turn = 5
    ensure_actor(s, "A", authority=0.9)
    ensure_actor(s, "B", authority=0.9)
    record_intent(s, "A", intent="加税", action="上疏")
    record_intent(s, "B", intent="反对", action="驳议")
    assert len(intents_of(s, "A")) == 1
    assert len(intents_of(s, "B")) == 1
    assert intents_of(s, "A", turn=99) == []


def test_silence_is_not_loyal_support():
    """§7.5：沉默/无意图**不得**被当作"忠诚支持"——返回空列表而非默认赞成。"""
    s = _state()
    ensure_actor(s, "A", authority=0.9)
    got = intents_of(s, "A")
    assert got == []
    assert got is not None            # 空列表 ≠ "有支持"


def test_intent_starts_as_proposed_not_done():
    """意图初始 `proposed`——**不得由叙事宣称已执行**。"""
    s = _state()
    ensure_actor(s, "A", authority=0.9)
    e = record_intent(s, "A", intent="修渠")
    assert e["status"] == "proposed"


# ====================================================== 换职不换人
def test_post_change_keeps_identity_and_memory():
    """§3.3：换职改权限与信息可见，**不换人格、不抹记忆**。"""
    s = _state()
    ensure_actor(s, "A", posts=["户部"], authority=0.9)
    remember(s, "A", kind="召对", text="臣请先核籍")
    # 换职：改权限与可见
    s.minister_agents["A"]["posts"] = ["工部"]
    s.minister_agents["A"]["authority"] = 0.4
    v = actor_view(s, "A")
    assert v["posts"] == ["工部"]
    assert v["authority"] == 0.4
    assert len(recall(s, "A")) == 1, "换职抹掉了记忆"
    assert can_act(s, "A")["ok"] is True


# ====================================================== 批量 vs 逐人等价
def test_batch_and_individual_intents_are_equivalent():
    """R7.7：批量推理与逐人推理在身份/记忆/归因上**等价**。"""
    s = _state()
    roster = ["A", "B", "C"]
    # 逐人
    for aid in roster:
        ensure_actor(s, aid, authority=0.9)
        record_intent(s, aid, intent=f"议-{aid}", targets=[aid])
    per_person = {aid: intents_of(s, aid) for aid in roster}
    # 批量（一次写入后读出）
    for aid in roster:
        for e in per_person[aid]:
            assert e["actor_id"] == aid, "批量写入后归因串位"
    assert set(per_person) == set(roster)
    assert len(per_person["A"]) == len(per_person["B"]) == len(per_person["C"]) == 1


def test_batch_does_not_merge_into_one_shared_answer():
    """§7.6：不得把多官员压成一个"朝廷综合回答"——逐人可分辨。"""
    s = _state()
    for aid, txt in (("A", "赞成"), ("B", "反对")):
        ensure_actor(s, aid, authority=0.9)
        record_intent(s, aid, intent=txt)
    a_txt = intents_of(s, "A")[0]["intent"]
    b_txt = intents_of(s, "B")[0]["intent"]
    assert a_txt != b_txt
    assert intents_of(s, "A")[0]["actor_id"] == "A"


# ====================================================== 读档
def test_agents_survive_save_load():
    from core.save_load import load_game, save_game
    s = _state()
    ensure_actor(s, "A", authority=0.7)
    remember(s, "A", kind="召对", text="臣附议")
    record_intent(s, "A", intent="修渠")
    assert save_game(s, 98) is True
    s2 = load_game(98)
    assert s2 is not None
    assert "A" in s2.minister_agents
    assert len(recall(s2, "A")) == 1
    assert len(intents_of(s2, "A")) == 1
    # 权限仍定义
    assert can_act(s2, "A")["ok"] is True


def test_load_drops_bad_agents_without_fabricating_memory():
    import json
    from core.save_load import _slot_path, load_game, save_game
    s = _state()
    ensure_actor(s, "A", authority=0.7)
    assert save_game(s, 99) is True
    p = _slot_path(99)
    with open(p, encoding="utf-8") as f:
        raw = json.load(f)
    # 注入一个非法条目：memory 不是列表
    raw["minister_agents"]["坏条目"] = {"actor_id": "坏条目", "memory": "不是列表"}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)
    s2 = load_game(99)
    assert s2 is not None
    assert "坏条目" not in s2.minister_agents, "非法条目被读入"
    assert "A" in s2.minister_agents