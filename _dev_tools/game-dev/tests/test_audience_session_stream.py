# -*- coding: utf-8 -*-
"""召对「会话流」回归测试：两侧落库、只读回放、纪要标注、面板端点会话视图。

背景（实测）：
  ① 对话记忆库 `dialogues` 原先只由 `audience_dialogue_apply` 写入**大臣回奏**，
     `state.dialogue_history` 里的「朕言」从未落库 → 记忆库/召对面板回看只剩单边对白。
  ② 本地预过滤模板与召对缓存复用两条短路分支在 `audience_dialogue_prepare` **之前**
     return，整轮对话既不进对话库也不进后续总结 → 面板回看出现「整轮空缺」。
  ③ 补写「朕」行后，`summarize_dialogues` 若仍不标发言者，陛下口谕会被并入大臣之言
     —— 该概要随即作为「卿前番之言」喂回 AI，等于让大臣把上意记成己见。
  ④ `list_dialogues`/`list_sessions` 为玩家可见回放接口（只读），须不因 `summarized`
     标记而丢行、须按时间正序、须无 minister 时全量。

原则：跑真实代码路径（不伪造成功）；SAVE_DIR 全量改指 tmp_path，绝不触碰真实存档。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

import content.data as cdata  # noqa: E402
import memory.memory_graph as mgmod  # noqa: E402
import core.save_load as slmod  # noqa: E402
from memory.dialogue_memory import DialogueMemory, _dialogue_path, get_dialogue_memory  # noqa: E402
from core.commands import audience_dialogue, new_game  # noqa: E402

_SLOT = 91


@pytest.fixture(autouse=True)
def tmp_saves(tmp_path, monkeypatch):
    """SAVE_DIR 全量改指临时目录（三处绑定都要改，否则真实存档被写）。"""
    monkeypatch.setattr(cdata, "SAVE_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(mgmod, "SAVE_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(slmod, "SAVE_DIR", str(tmp_path), raising=False)
    yield tmp_path


def _state_and_mem():
    state = new_game("史实")
    state.memory_slot = _SLOT
    dm = get_dialogue_memory(state)
    dm.turn = state.turn
    return state, dm


# ---------------------------------------------------------------
# ① 三条召对路径都必须把「朕言 + 回奏」两侧落库
# ---------------------------------------------------------------
def test_prefilter_path_records_both_sides():
    """本地预过滤模板路径（短路在 prepare 之前）也须落库，否则面板整轮空缺。"""
    state, dm = _state_and_mem()
    reply = audience_dialogue(state, "韩忠彦", "赈灾开仓", None)
    assert reply, "预过滤应产出本地模板回复"
    rows = dm.list_dialogues(minister="韩忠彦")
    assert len(rows) == 2, f"应为朕言+回奏两条，实际 {len(rows)}"
    assert rows[0]["speaker"] == "朕" and rows[0]["text"] == "赈灾开仓"
    assert rows[1]["speaker"] == "韩忠彦"
    assert rows[0]["topic"] == rows[1]["topic"], "同一问答应归入同一 topic 组"
    dm.close()


def test_ai_unavailable_path_records_both_sides():
    """AI 未接入的降级路径（prepare → 模板兜底 → apply）两侧落库且顺序正确。"""
    state, dm = _state_and_mem()
    audience_dialogue(state, "韩忠彦", "卿以为盐法可行否", None)
    rows = dm.list_dialogues(minister="韩忠彦")
    assert [r["speaker"] for r in rows] == ["朕", "韩忠彦"], \
        [(r["speaker"], r["text"][:8]) for r in rows]
    dm.close()


def test_cache_reuse_path_records_both_sides():
    """召对缓存复用（第二次同话题）同样落库，不得因短路而丢整轮。"""
    state, dm = _state_and_mem()
    audience_dialogue(state, "韩忠彦", "卿以为盐法可行否", None)
    n = len(dm.list_dialogues(minister="韩忠彦"))
    audience_dialogue(state, "韩忠彦", "卿以为盐法可行否", None)
    rows = dm.list_dialogues(minister="韩忠彦")
    assert state._dialogue_stats["cache_hits"] == 1, "第二次应命中缓存（前提）"
    assert len(rows) == n + 2, f"缓存路径应再落两条，实际 {n} → {len(rows)}"
    dm.close()


def test_dead_minister_records_nothing():
    """已薨/罢黜者不可召对：不得伪造对白落库（提防面板出现凭空奏对）。"""
    state, dm = _state_and_mem()
    state.minister_status = lambda name: "dead"  # type: ignore[assignment]
    before = len(dm.list_dialogues(minister="韩忠彦"))
    audience_dialogue(state, "韩忠彦", "卿尚能视事否", None)
    assert len(dm.list_dialogues(minister="韩忠彦")) == before
    dm.close()


# ---------------------------------------------------------------
# ② list_dialogues / list_sessions：完整、正序、只读
# ---------------------------------------------------------------
def test_list_dialogues_complete_ordered_and_readonly():
    dm = DialogueMemory(slot=_SLOT)
    try:
        dm.add_dialogue("蔡京", 1, "朕", "盐法可行否", topic="盐法")
        dm.add_dialogue("蔡京", 1, "蔡京", "臣以为可行", intent="盐法", stance="支持",
                        topic="盐法")
        dm.add_dialogue("韩忠彦", 2, "朕", "边备如何", topic="边备")
        dm.add_dialogue("韩忠彦", 2, "韩忠彦", "臣请严饬关隘", topic="边备")
        dm.summarize_dialogues(3)      # 全部标记 summarized=1
        rows = dm.list_dialogues(minister="蔡京")
        assert len(rows) == 2, "已总结的留档不得从回放接口消失"
        assert all(r["summarized"] for r in rows), "前提：这两条已被总结"
        assert [r["speaker"] for r in rows] == ["朕", "蔡京"], "须按时间正序（朕前臣后）"
        assert len(dm.list_dialogues()) == 4, "无 minister 时应全量"
        assert len(dm.list_dialogues(limit=3)) == 3, "limit 须生效"
        # 取「最近 3 条」（id 4/3/2）后仍正序返回 → 蔡京第1条、韩忠彦两条
        assert [r["minister"] for r in dm.list_dialogues(limit=3)] == \
            ["蔡京", "韩忠彦", "韩忠彦"], "limit 取最近 N 条后仍按时间正序"
        assert [r["id"] for r in dm.list_dialogues(limit=3)] == [2, 3, 4]
        # 只读：回放调用前后行数不变
        n = dm._conn.execute("SELECT COUNT(*) FROM dialogues").fetchone()[0]
        dm.list_dialogues(minister="蔡京")
        dm.list_sessions()
        assert dm._conn.execute("SELECT COUNT(*) FROM dialogues").fetchone()[0] == n
    finally:
        dm.close()


def test_list_sessions_preview_is_latest_reply():
    dm = DialogueMemory(slot=_SLOT)
    try:
        dm.add_dialogue("蔡京", 1, "朕", "盐法可行否", topic="盐法")
        dm.add_dialogue("蔡京", 1, "蔡京", "臣以为可行", topic="盐法")
        dm.add_dialogue("蔡京", 2, "朕", "再议", topic="盐法")
        dm.add_dialogue("蔡京", 2, "蔡京", "容臣具奏", topic="盐法")
        sess = {s["minister"]: s for s in dm.list_sessions()}
        assert sess["蔡京"]["count"] == 4
        assert sess["蔡京"]["last_turn"] == 2
        assert sess["蔡京"]["last_speaker"] == "蔡京", "末条预览应取大臣回奏而非设问"
        assert "容臣具奏" in sess["蔡京"]["last_text"]
    finally:
        dm.close()


def test_empty_db_returns_empty_not_error():
    """无库/空库时回放接口返回空列表，不得抛异常（面板首开即此状态）。"""
    dm = DialogueMemory(slot=_SLOT + 500)
    try:
        assert dm.list_dialogues(minister="蔡京") == []
        assert dm.list_sessions() == []
        assert dm.list_dialogues() == []
    finally:
        dm.close()
        for suffix in ("", "-wal", "-shm"):
            p = _dialogue_path(_SLOT + 500) + suffix
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


# ---------------------------------------------------------------
# ③ 概要须标注发言者（否则上意被记成大臣己见）
# ---------------------------------------------------------------
def test_summary_labels_emperor_utterance():
    dm = DialogueMemory(slot=_SLOT)
    try:
        dm.add_dialogue("蔡京", 1, "朕", "盐法可行否", topic="盐法")
        dm.add_dialogue("蔡京", 1, "蔡京", "臣以为可行", intent="盐法", stance="支持",
                        topic="盐法")
        out = dm.summarize_dialogues(3)
        assert out, "应有总结产出"
        content = " ".join(o["content"] for o in out)
        assert "朕：" in content, f"陛下之言须标注发言者，实际：{content}"
        assert "蔡京：蔡京" not in content, "大臣之言不应加冗余前缀"
        assert "臣以为可行" in content
    finally:
        dm.close()


# ---------------------------------------------------------------
# ③′ 概要区间须与分组口径同源（面板显示的「第 a–b 回合」）
# ---------------------------------------------------------------
def test_summary_period_range_matches_grouping():
    """第 p 期 = 行按 turn//3 归入的期，区间应恰为 [3p, 3p+2]（原式错开一期）。"""
    dm = DialogueMemory(slot=_SLOT)
    try:
        for t in range(0, 8):                       # 覆盖第 0/1/2 期
            dm.add_dialogue("蔡京", t, "蔡京", f"第{t}回合奏对", topic="盐法")
        dm.summarize_dialogues(7)
        rows = dm.list_summaries(minister="蔡京")
        got = {(r["period"], r["start_turn"], r["end_turn"]) for r in rows}
        assert got == {(0, 0, 2), (1, 3, 5), (2, 6, 8)}, f"区间与分组口径不符：{got}"
    finally:
        dm.close()


# ---------------------------------------------------------------
# ④ /api/memory 会话视图（召对面板内嵌记忆库侧栏的数据源）
# ---------------------------------------------------------------
class _FakeRequest:
    """最小 Request 替身：仅提供 _require_auth 所需的 client.host 与 headers。"""

    class client:  # noqa: N801
        host = "127.0.0.1"

    headers: dict = {}


def test_api_memory_minister_view_is_scoped_and_readonly():
    from backend import server as srv

    state, dm = _state_and_mem()
    dm.add_dialogue("蔡京", 1, "朕", "盐法可行否", topic="盐法")
    dm.add_dialogue("蔡京", 1, "蔡京", "臣以为可行", topic="盐法")
    dm.add_dialogue("韩忠彦", 1, "朕", "边备如何", topic="边备")
    dm.add_dialogue("韩忠彦", 1, "韩忠彦", "臣请严饬关隘", topic="边备")
    dm.summarize_dialogues(3)

    prev = srv._state
    srv._state = state
    try:
        before = (len(state.memory.entities), len(state.memory.relations))
        g = srv.api_memory(_FakeRequest())
        m = srv.api_memory(_FakeRequest(), minister="蔡京")
        assert g["dialogues"] == [], "全局视图不得泄漏会话流（面板按人取）"
        assert m["minister"] == "蔡京"
        assert len(m["dialogues"]) == 2, m["dialogues"]
        assert {r["speaker"] for r in m["dialogues"]} == {"朕", "蔡京"}
        assert all(r["minister"] == "蔡京" for r in m["dialogues"]), "会话视图须按人收窄"
        assert len(m["sessions"]) == 2, "会话列表应覆盖所有有留档者"
        assert isinstance(m["minister_relations"], list)
        assert m["state_turn"] == state.turn
        # 旧字段仍在（独立记忆库面板契约不变）
        assert set(g) >= {"turn", "state_turn", "entity_counts", "relation_total",
                          "relation_archived", "summaries", "recent",
                          "dialogue_summaries", "change_log"}
        assert before == (len(state.memory.entities), len(state.memory.relations)), \
            "只读端点不得改动记忆库"
    finally:
        srv._state = prev
        dm.close()
