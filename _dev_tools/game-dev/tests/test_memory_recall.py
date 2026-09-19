# -*- coding: utf-8 -*-
"""记忆库检索与水位的回归测试：中文关键词检索、未来回合封顶、读档水位对齐。

背景（实测/审查）：
  ① `MemoryGraph.keyword_search` 原按「连续中文/字母数字 ≥2 字」贪婪正则取词 —— 对中文
     等于整段一个 token，`token in blob` 需整段子串精确命中。玩家自然语言（正是
     `ai/client.py` 拟旨注入「既往同类诏令」的入参）因此恒 0 命中，通道静默空转。
  ② 内存 `query`/`keyword_search` 不过滤 `turn > self.turn` 的关系，而 `query_sql`
     有 `r.turn <= cur_turn` 封顶 —— 同一方法两条实现语义不等价，读旧档后会把
     「未发生的回合」当既成事实注入。
  ③ `load_game` 先按主存档对齐 `memory.turn`、随即被 `memory.load()` 用 db 内 turn
     覆盖（审查 B-1/J-10：记忆库每回合落盘、主存档只手动/正月更新）→ 读旧档后 AI
     记得未来。

原则：跑真实代码路径（不伪造成功）；用临时槽位并清理残留文件。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from memory.memory_graph import MemoryGraph, _db_path, _memory_path  # noqa: E402
from memory.dialogue_memory import DialogueMemory, _dialogue_path  # noqa: E402
from core.save_load import _slot_path, save_game, load_game  # noqa: E402
from core.game_state import GameState  # noqa: E402

_SLOT = 87          # 记忆库检索/水位测试槽位（避开真实存档 0-6）
_SLOT_DLG = 88      # 对话记忆库测试槽位


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    for suffix in ("", "-wal", "-shm"):
        p = _db_path(_SLOT) + suffix
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    for suffix in ("", "-wal", "-shm"):
        p = _dialogue_path(_SLOT_DLG) + suffix
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    for p in (_slot_path(_SLOT), _memory_path(_SLOT), _memory_path(_SLOT, archive=True)):
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def _relief_graph(turn=12) -> MemoryGraph:
    """含「赈济京畿灾民」事件的关系图（中文自然语言检索用）。"""
    g = MemoryGraph()
    g.turn = turn
    g.add_entity("minister_蔡京", "minister", "蔡京", {}, turn=0)
    g.add_entity("minister_韩忠彦", "minister", "韩忠彦", {}, turn=0)
    g.add_entity("event_1", "event", "赈济京畿灾民", {}, turn=3)
    g.add_relation("event_1", "minister_蔡京", "involves", weight=1.0, turn=3, note="主持赈济")
    g.add_relation("minister_韩忠彦", "event_1", "opposes", weight=1.0, turn=3, note="以为太滥")
    return g


# ---------------------------------------------------------------
# ① 中文关键词检索（2-gram）
# ---------------------------------------------------------------
def test_keyword_search_natural_language_hits():
    """自然语言长句须能命中（回归：原整段取词实现恒 0 命中）。"""
    g = _relief_graph()
    hits = g.keyword_search("赈济京畿灾民如何施行", top_k=6)
    assert hits, "中文自然语言查询应命中既往同类关系"
    assert any("赈济京畿灾民" in h[0] for h in hits)
    # 同一批数据的短词查询仍应命中（不因换分词而回退）
    assert g.keyword_search("赈济", top_k=6)
    assert g.keyword_search("主持赈济", top_k=6), "带虚词的自然语言亦应命中"


def test_keyword_search_ranks_more_hits_first():
    """命中查询片段更多者排前（多片段重合 = 更相关，优先于权重）。"""
    g = _relief_graph()
    g.add_entity("event_2", "event", "盐法更张", {}, turn=3)
    # 只命中「赈济」1 个片段，但权重远高于命中「赈济+京畿」2 个片段的关系
    g.add_relation("event_2", "minister_蔡京", "involves", weight=9.0, turn=3, note="赈济")
    hits = g.keyword_search("赈济京畿", top_k=6)
    assert hits
    assert "赈济京畿灾民" in (hits[0][0], hits[0][1]), \
        "命中 2 个片段者应排在仅命中 1 个片段的高权重关系之前"


def test_keyword_search_english_and_digits():
    """西文/数字按词切分（大小写不敏感）。"""
    g = MemoryGraph()
    g.turn = 5
    g.add_entity("e1", "event", "Salt Tax", {}, turn=2)
    g.add_entity("m1", "minister", "蔡京", {}, turn=0)
    g.add_relation("e1", "m1", "involves", weight=1.0, turn=2, note="wine tax 20%")
    assert g.keyword_search("salt tax", top_k=5), "英文查询应命中"
    assert g.keyword_search("wine tax 20", top_k=5), "含数字的英文查询应命中"
    assert not g.keyword_search("!!!", top_k=5), "无有效 token 的查询返回空"


# ---------------------------------------------------------------
# ② 未来回合封顶（与 query_sql 同口径）
# ---------------------------------------------------------------
def test_query_and_keyword_exclude_future_turns():
    """self.turn 之后写入的关系不得被检索（读旧档「记得未来」的内存侧根因）。"""
    g = MemoryGraph()
    g.turn = 5
    g.add_entity("minister_蔡京", "minister", "蔡京", {}, turn=0)
    g.add_entity("event_9", "event", "未来之事", {}, turn=9)
    g.add_relation("event_9", "minister_蔡京", "involves", weight=1.0, turn=9, note="未发生")
    assert g.query("蔡京", top_k=10) == [], "query 不得返回未来回合关系"
    assert g.keyword_search("未来之事", top_k=10) == [], "keyword_search 不得返回未来回合关系"
    assert g.query_sql("蔡京", top_k=10) == [], "query_sql 同口径（内存回退分支）"
    # 水位推进到未来之后，同一关系即可见（证明过滤的是水位而非数据丢失）
    g.turn = 9
    assert any(r[1] == "event_9" or r[0] == "event_9" for r in g.query("蔡京", top_k=10))


# ---------------------------------------------------------------
# ③ 读档水位对齐（审查 B-1/J-10）
# ---------------------------------------------------------------
def test_load_game_realigns_memory_turn():
    """主存档 turn=0、记忆库 db turn=20 → 读档后 memory.turn 应为 0，且不检索未来。"""
    s = GameState("史实")
    s.turn = 0
    assert save_game(s, _SLOT), "主存档写入失败"

    # 模拟「记忆库每回合落盘、主存档停在 0 回合」：db 内水位 20 且含未来关系
    g = MemoryGraph()
    g.turn = 20
    g.add_entity("minister_蔡京", "minister", "蔡京", {}, turn=0)
    g.add_entity("event_20", "event", "第二十回合之事", {}, turn=20)
    g.add_relation("event_20", "minister_蔡京", "involves", weight=1.0, turn=20, note="未来")
    assert g.save(_SLOT)

    st = load_game(_SLOT)
    assert st is not None and st.turn == 0
    assert st.memory.turn == 0, "读档后记忆水位须与主存档对齐（原被 db 内 turn 覆盖）"
    assert st.memory.query("蔡京", top_k=10) == [], "读档后不得注入未来回合的史事"
    assert st.memory.keyword_search("第二十回合之事", top_k=10) == []


# ---------------------------------------------------------------
# ④ 对话记忆：过期窗口回补（原实现只处理当前 3 回合窗口）
# ---------------------------------------------------------------
def test_dialogue_summarize_backfills_expired_periods():
    """AI 不可用/读档跳期导致某期未总结时，过期对话须被回补，不得永久滞留。"""
    dm = DialogueMemory(slot=_SLOT_DLG)
    try:
        for i in range(1, 7):
            dm.add_dialogue("蔡京", i, "minister", f"第{i}条：盐法可行，臣愿主持",
                            intent="盐法", stance="支持", topic="盐法")
        out = dm.summarize_dialogues(6)
        assert out, "应有总结产出"
        left = dm._conn.execute(
            "SELECT COUNT(*) FROM dialogues WHERE summarized=0").fetchone()[0]
        assert left == 0, f"所有对话都应被总结，仍滞留 {left} 条（原实现只处理 turn 4-6）"
        periods = [r[0] for r in dm._conn.execute(
            "SELECT DISTINCT period FROM summaries ORDER BY period").fetchall()]
        assert periods == [0, 1, 2], f"应按对话自身 period 分组成 0/1/2，实际 {periods}"
        # 细节注入只走概要下钻通道（无 summarized=0 残留原文）
        q = dm.query_for_dialogue("蔡京", 6, top_k=3)
        assert q["details"], "概要 ref_ids 下钻应能取回原文"
        assert all(d.get("from_summary") for d in q["details"]), \
            "已总结对话只能经 ref_ids 下钻进入 details（而非 summarized=0 通道）"
    finally:
        dm.close()


# ---------------------------------------------------------------
# ⑤ 容量治理：archive 接线（幂等 / 只打标记 / 落盘可查）
# ---------------------------------------------------------------
def test_archive_marks_old_relations_and_is_idempotent():
    """archive：低权重旧史打 archived 标记并从检索消失，重复调用幂等，且随 save 落盘。"""
    g = MemoryGraph()
    g.turn = 40
    g.add_entity("a", "minister", "甲", {}, turn=0)
    g.add_entity("d_old", "decision", "旧政", {}, turn=0)
    g.add_entity("d_new", "decision", "新政", {}, turn=39)
    g.add_relation("a", "d_old", "produces", weight=0.5, turn=0)    # 40 回合 → w_eff < 0.25
    g.add_relation("a", "d_new", "produces", weight=1.0, turn=39)   # 新近 → 不归档
    assert g.save(_SLOT)
    assert g.archive(_SLOT) == 1, "仅低权重旧关系应被归档"
    assert g.archive(_SLOT) == 0, "重复归档须幂等（已归档行不再计数）"
    assert len(g.relations) == 2, "归档只打标记，不物理删除"
    rows = g.query("甲", top_k=10)
    assert all(r[1] != "d_old" for r in rows), "已归档旧史不得再注入检索"
    assert any(r[1] == "d_new" for r in rows), "新近关系应保持可见"
    # 落盘可查：重新 load 后 archived 标记仍在
    g2 = MemoryGraph()
    assert g2.load(_SLOT)
    assert any(r.get("archived") for r in g2.relations)
    # change_log 记下归档动作
    assert any(r["action"] == "archive" for r in g2.query_change_log(slot=_SLOT))


def test_archive_threshold_boundary():
    """w_eff 恰高于阈值的关系不归档（阈值语义 = 严格小于）。"""
    g = MemoryGraph()
    g.turn = 0
    g.add_entity("a", "minister", "甲", {}, turn=0)
    g.add_entity("b", "decision", "事", {}, turn=0)
    g.add_relation("a", "b", "produces", weight=1.0, turn=0)   # w_eff = 1.0
    assert g.archive(_SLOT, weight_below=1.0) == 0


def test_query_falls_back_to_memory_when_db_missing():
    """槽位 db 尚不存在（新开局/换档）时，SQL 路径须回退内存镜像而非返回空。

    原实现只在 slot is None 时回退，db 缺失一律 return [] —— 记忆在内存镜像里却
    「查无此事」，记忆库面板与压缩聚合会显示为空。
    """
    g = MemoryGraph()
    g.turn = 3
    g.add_entity("a", "minister", "甲", {}, turn=0)
    g.add_entity("b", "decision", "事", {}, turn=1)
    g.add_relation("a", "b", "produces", weight=1.0, turn=1)
    g.compress(3)                       # 内存里生成 summary 实体（未落盘）
    missing = _SLOT + 1000
    assert not os.path.exists(_db_path(missing))
    assert g.query_sql(slot=missing, top_k=5), "db 缺失应回退内存镜像"
    assert g.query_summaries(slot=missing), "概要同样应回退内存"


# ---------------------------------------------------------------
# ⑥ 审计与细节下钻：change_log 可读 / ref_ids 可展开
# ---------------------------------------------------------------
def test_change_log_readable():
    """change_log 由「只写不读」补上读接口（审计/回放）。"""
    g = MemoryGraph()
    g.turn = 12
    g.add_entity("a", "minister", "甲", {}, turn=0)
    g.add_entity("b", "decision", "事", {}, turn=0)
    g.add_relation("a", "b", "produces", weight=1.0, turn=0)
    assert g.save(_SLOT)
    g.compress(12, _SLOT)
    rows = g.query_change_log(slot=_SLOT, limit=20)
    actions = {r["action"] for r in rows}
    assert "save_snapshot" in actions and "compress" in actions, f"实际 actions={actions}"
    only_compress = g.query_change_log(action="compress", slot=_SLOT)
    assert only_compress and all(r["action"] == "compress" for r in only_compress)
    assert g.query_change_log(slot=_SLOT + 1000) == [], "库不存在须返回空而非抛异常"


def test_dialogue_drill_down_by_refs():
    """已总结对话的原文可经 ref_ids 下钻取回（原实现只取 summarized=0，取不回）。"""
    dm = DialogueMemory(slot=_SLOT_DLG)
    try:
        for i in range(1, 5):
            dm.add_dialogue("蔡京", i, "minister", f"第{i}条：盐法可行，臣愿主持",
                            intent="盐法", stance="支持", topic="盐法")
        dm.summarize_dialogues(3)            # 总结 turn 1-3，写入 ref_ids
        refs = dm.summary_refs(minister="蔡京")
        assert refs, "概要应记录 ref_ids（原实现只写不读）"
        found = dm.fetch_dialogues_by_ids(refs, top_k=5)
        assert found and all("text" in f for f in found), "应按 id 取回原文"
        q = dm.query_for_dialogue("蔡京", 3, top_k=3)
        assert q["summary"]
        assert any(d.get("from_summary") for d in q["details"]), \
            "已总结原文应能经 ref_ids 下钻补入 details"
        assert dm.list_summaries(minister="蔡京"), "面板/审计用概要列表应可读"
    finally:
        dm.close()


# ---------------------------------------------------------------
# ⑦ 玩家可见：/api/memory 只读薄壳端点
# ---------------------------------------------------------------
class _FakeRequest:
    """最小 Request 替身：仅提供 _require_auth 所需的 client.host 与 headers。"""

    class client:  # noqa: N801
        host = "127.0.0.1"

    headers: dict = {}


def test_api_memory_endpoint_readonly_view():
    """/api/memory 返回记忆库只读视图（实体计数/概要/关系/召对/审计），且不改动记忆。"""
    from backend import server as srv
    from core.commands import new_game

    prev = srv._state
    srv._state = new_game("史实")
    try:
        before = (len(srv._state.memory.entities), len(srv._state.memory.relations))
        out = srv.api_memory(_FakeRequest())
        assert set(out) >= {"turn", "state_turn", "entity_counts", "relation_total",
                            "relation_archived", "summaries", "recent",
                            "dialogue_summaries", "change_log"}
        assert out["entity_counts"].get("minister", 0) > 0, "开局应有大臣实体入库"
        assert out["relation_total"] >= 0 and out["state_turn"] == 0
        after = (len(srv._state.memory.entities), len(srv._state.memory.relations))
        assert before == after, "只读端点不得改动记忆库"
    finally:
        srv._state = prev
