# -*- coding: utf-8 -*-
"""T7 记忆库数据库化测试：SQLite 后端（五表/事务/去重）、压缩/周期总结、
SQL 精确调动（领域/时间窗/rtype/top_k/层级检索）、旧 JSON 迁移、存档往返。

原则：不伪造成功——每个断言都跑真实代码路径；测试用临时槽位并清理 .db 残留。
"""
import os
import json
import sqlite3
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from memory.memory_graph import (  # noqa: E402
    MemoryGraph, _db_path, _memory_path, _SCHEMA_VERSION,
    _COMPRESS_INTERVAL, _PERIOD_INTERVAL,
)
from content.data import SAVE_DIR  # noqa: E402


# 测试用槽位（避免与真实存档槽位 1-5 冲突）
_SLOT = 77


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
    for p in (_memory_path(_SLOT), _memory_path(_SLOT, archive=True)):
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def _sample_graph(turn=20) -> MemoryGraph:
    """构造含大臣/决策/事件/关系的记忆图。"""
    g = MemoryGraph()
    g.turn = turn
    g.add_entity("minister_蔡京", "minister", "蔡京", {"faction": "新党"}, turn=0)
    g.add_entity("minister_韩忠彦", "minister", "韩忠彦", {}, turn=0)
    g.add_entity("decision_5_崇宁新法", "decision", "崇宁新法", {"effects": {}}, turn=5)
    g.add_entity("decision_15_赈济京畿", "decision", "赈济京畿", {"effects": {}}, turn=15)
    g.add_entity("event_18_河决", "event", "黄河决口", {}, turn=18)
    g.add_relation("minister_蔡京", "decision_5_崇宁新法", "supports", weight=1.2, turn=5)
    g.add_relation("minister_韩忠彦", "decision_5_崇宁新法", "opposes", weight=1.2, turn=5)
    g.add_relation("minister_蔡京", "decision_15_赈济京畿", "supports", weight=1.5, turn=15)
    g.add_relation("event_18_河决", "minister_蔡京", "involves", weight=1.0, turn=18, note="遣使赈济")
    return g


# ---------------------------------------------------------------
# 1. SQLite 后端：五表 / 存档往返 / 原子事务
# ---------------------------------------------------------------
def test_save_creates_five_tables():
    """save() 落盘 slot.db，五张表齐全且索引建立。"""
    g = _sample_graph()
    assert g.save(_SLOT) is True
    assert os.path.exists(_db_path(_SLOT))
    conn = sqlite3.connect(_db_path(_SLOT))
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"state", "entities", "relations", "summaries", "change_log"} <= tables
        # 唯一索引：relations 允许重插同键会冲突（REPLACE 语义由 save 保证）
        idx = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert "idx_entities_type_name" in idx
        assert "idx_relations_turn" in idx and "idx_relations_rtype" in idx
    finally:
        conn.close()


def test_save_load_roundtrip():
    """存档往返：entities/relations/turn/archived 一致。"""
    g = _sample_graph(turn=30)
    g.add_relation("a", "b", "stance", weight=0.05, turn=0)  # 低权重（后续可归档）
    assert g.save(_SLOT)
    g2 = MemoryGraph()
    assert g2.load(_SLOT)
    assert g2.turn == 30
    assert g2.schema_version == _SCHEMA_VERSION
    assert set(g2.entities.keys()) == set(g.entities.keys())
    assert g2.entities["minister_蔡京"]["attrs"]["faction"] == "新党"
    assert len(g2.relations) == len(g.relations)
    # 同 eid 实体名/属性一致
    assert g2.entities["decision_15_赈济京畿"]["name"] == "赈济京畿"


def test_insert_or_replace_dedup():
    """去重：同 eid 实体 / 同 (src,dst,rtype) 关系重复 save 不产生重复行。"""
    g = _sample_graph()
    assert g.save(_SLOT)
    assert g.save(_SLOT)          # 二次快照（镜像未变）→ REPLACE 幂等
    conn = sqlite3.connect(_db_path(_SLOT))
    try:
        n_ent = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        n_rel = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        assert n_ent == len(g.entities) - 0  # summary 类实体不在此表
        assert n_rel == len(g.relations)
        # 同 (src,dst,rtype) 仅一行
        dup = conn.execute(
            "SELECT src,dst,rtype,COUNT(*) c FROM relations GROUP BY src,dst,rtype HAVING c>1"
        ).fetchall()
        assert dup == []
    finally:
        conn.close()


def test_relation_weight_accumulate_then_snapshot():
    """add_relation 同向叠加权重（内存语义），save 后 db 存最终值（非增量）。"""
    g = MemoryGraph()
    g.add_entity("a", "minister", "甲", {}, turn=0)
    g.add_entity("b", "decision", "乙政", {}, turn=0)
    g.add_relation("a", "b", "supports", weight=1.0, turn=0)
    g.add_relation("a", "b", "supports", weight=1.0, turn=0)
    assert g.relations[0]["weight"] == pytest.approx(2.0)
    assert g.save(_SLOT)
    conn = sqlite3.connect(_db_path(_SLOT))
    try:
        w = conn.execute("SELECT weight FROM relations WHERE src='a' AND dst='b'").fetchone()[0]
        assert w == pytest.approx(2.0), "db 存最终叠加值"
    finally:
        conn.close()


def test_transaction_rollback_on_bad_attrs(monkeypatch):
    """事务原子性：事务中途注入失败 → 整个 save 回滚（ROLLBACK），无半写状态。

    注入方式：monkeypatch memory_graph._now_str 抛 TypeError（save() 事务内
    change_log 步骤触发）；由于 save() 用单事务（with conn:），任一语句失败即整体回滚。
    """
    import memory.memory_graph as mmg

    g = _sample_graph()
    assert g.save(_SLOT) is True   # 前置：正常落盘

    def boom():
        raise TypeError("injected failure")

    monkeypatch.setattr(mmg, "_now_str", boom)
    g2 = _sample_graph()
    g2.turn = 40
    assert g2.save(_SLOT) is False, "事务中途失败应返回 False"
    # 回滚：本次写盘未产生半写（turn 仍是旧值，entities 不含新实体）
    conn = sqlite3.connect(_db_path(_SLOT))
    try:
        v = conn.execute("SELECT value FROM state WHERE key='turn'").fetchone()
        assert v is not None and int(v[0]) == 20, "回滚后 state.turn 应保持上次成功值"
        n = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        assert n == len(_sample_graph().entities), "回滚后 entities 应保持上次成功快照"
    finally:
        conn.close()


def test_change_log_written():
    """change_log 表记录写盘动作（审计/回放用）。"""
    g = _sample_graph()
    assert g.save(_SLOT)
    conn = sqlite3.connect(_db_path(_SLOT))
    try:
        rows = conn.execute("SELECT action, turn FROM change_log ORDER BY id").fetchall()
        assert any(a == "save_snapshot" for a, _ in rows)
    finally:
        conn.close()


# ---------------------------------------------------------------
# 2. 压缩（每 6 回合）与周期总结（每 12 回合）
# ---------------------------------------------------------------
def test_compress_every_6_turns():
    """compress(turn)：period=turn//6，聚合近 6 回合关系 → summary 实体。"""
    g = _sample_graph(turn=6)
    g.save(_SLOT)
    eid = g.compress(6, slot=_SLOT)
    assert eid == "summary_1"
    # 内存镜像含 summary 实体
    assert g.entities["summary_1"]["type"] == "summary"
    assert g.entities["summary_1"]["attrs"]["period"] == 1
    # 近 6 回合（turn 1..6）只有 decision_5_崇宁新法 相关关系
    top = g.entities["summary_1"]["attrs"]["top_relations"]
    assert any("崇宁新法" in t for t in top)
    assert not any("赈济京畿" in t for t in top), "15 回合的关系不在近 6 回合窗口内"
    # 落盘 summaries 表
    conn = sqlite3.connect(_db_path(_SLOT))
    try:
        row = conn.execute("SELECT stype, period FROM summaries WHERE eid='summary_1'").fetchone()
        assert row == ("summary", 1)
    finally:
        conn.close()


def test_compress_does_not_touch_old_data():
    """压缩只读聚合：原 entities/relations 数量与内容不变（旧数据不动）。"""
    g = _sample_graph(turn=20)
    g.save(_SLOT)
    n_ent, n_rel = len(g.entities), len(g.relations)
    g.compress(20, slot=_SLOT)
    assert len(g.entities) == n_ent + 1, "仅新增 summary 实体"
    assert len(g.relations) == n_rel, "关系不动"
    assert g.entities["decision_5_崇宁新法"]["attrs"]["effects"] == {}


def test_compress_idempotent():
    """compress 幂等：同 period 重复调用 → summaries 表仅一行（REPLACE）。"""
    g = _sample_graph(turn=12)
    g.save(_SLOT)
    g.compress(12, slot=_SLOT)
    g.compress(12, slot=_SLOT)
    conn = sqlite3.connect(_db_path(_SLOT))
    try:
        n = conn.execute("SELECT COUNT(*) FROM summaries WHERE eid='summary_2'").fetchone()[0]
        assert n == 1
    finally:
        conn.close()


def test_summarize_period_every_12_turns():
    """summarize_period(turn)：period=turn//12，聚合本轮决策/事件 → period_summary。"""
    g = _sample_graph(turn=18)
    g.save(_SLOT)
    eid = g.summarize_period(18, slot=_SLOT)
    assert eid == "period_summary_1"
    attrs = g.entities[eid]["attrs"]
    assert attrs["period"] == 1
    # 本轮 (7..18]：决策 1（赈济京畿）+ 事件 1（河决）；崇宁新法(turn=5) 不在本轮
    assert attrs["decision_count"] == 1
    assert attrs["event_count"] == 1
    conn = sqlite3.connect(_db_path(_SLOT))
    try:
        row = conn.execute("SELECT stype, period FROM summaries WHERE eid='period_summary_1'").fetchone()
        assert row == ("period_summary", 1)
    finally:
        conn.close()


def test_summarize_period_idempotent_and_interval_constants():
    """周期总结幂等；间隔常量符合派单（6 回合压缩 / 12 回合周期总结）。"""
    assert _COMPRESS_INTERVAL == 6
    assert _PERIOD_INTERVAL == 12
    g = _sample_graph(turn=24)
    g.save(_SLOT)
    g.summarize_period(24, slot=_SLOT)
    g.summarize_period(24, slot=_SLOT)
    conn = sqlite3.connect(_db_path(_SLOT))
    try:
        n = conn.execute("SELECT COUNT(*) FROM summaries WHERE eid='period_summary_2'").fetchone()[0]
        assert n == 1
    finally:
        conn.close()


# ---------------------------------------------------------------
# 3. SQL 精确调动：领域/时间窗/rtype/top_k/权重排序 + 层级检索
# ---------------------------------------------------------------
def test_query_sql_domain_and_rtype_filter():
    """query_sql：按 subject 实体 + rtype 过滤，走 SQL（先落盘）。"""
    g = _sample_graph(turn=20)
    g.save(_SLOT)
    rows = g.query_sql("蔡京", rtypes=("supports",), top_k=10, slot=_SLOT)
    assert rows and all(r[2] == "supports" for r in rows)
    assert all(r[0] == "minister_蔡京" or r[1] == "minister_蔡京" for r in rows)
    # 权重排序：赈济京畿(1.5, turn15) 应排在崇宁新法(1.2, turn5) 前（衰减后仍成立）
    assert rows[0][1] == "decision_15_赈济京畿"


def test_query_sql_time_window():
    """query_sql：time_window 过滤近期关系（> 窗口的旧史不返回）。"""
    g = _sample_graph(turn=20)
    g.save(_SLOT)
    rows = g.query_sql("蔡京", rtypes=("supports",), time_window=10, top_k=10, slot=_SLOT)
    assert rows and all(20 - g.entities[r[1]]["created_turn"] <= 10 for r in rows)
    # 近 10 回合内仅 赈济京畿（turn15）；崇宁新法（turn5）超窗
    assert all(r[1] == "decision_15_赈济京畿" for r in rows)


def test_query_sql_min_weight_and_top_k():
    """query_sql：min_weight 过滤 + top_k 截断。"""
    g = _sample_graph(turn=20)
    g.save(_SLOT)
    rows = g.query_sql("蔡京", top_k=1, slot=_SLOT)
    assert len(rows) == 1
    # supports λ=0.02，1.5×exp(-0.02×5)=1.357>1.3；1.2×exp(-0.02×15)=0.89<1.3
    rows_heavy = g.query_sql("蔡京", min_weight=1.3, top_k=10, slot=_SLOT)
    assert rows_heavy and all(r[3] >= 1.3 for r in rows_heavy)
    assert all(r[1] == "decision_15_赈济京畿" for r in rows_heavy), "仅重权重关系过阈值"


def test_query_sql_memory_fallback():
    """query_sql 未落盘时回退内存等价实现（接口一致，供运行早期使用）。"""
    g = _sample_graph(turn=20)
    assert g._slot is None, "未 save/load 前不应绑定任何槽位（避免误读真实存档）"
    rows = g.query_sql("蔡京", rtypes=("supports",), top_k=10)  # 未 save → 内存回退
    assert rows and all(r[2] == "supports" for r in rows)
    assert rows[0][1] == "decision_15_赈济京畿"


def test_query_summaries_and_hierarchical_retrieve():
    """层级检索：先 summaries 概要（level=1），未命中再下钻细节（level=2）。"""
    g = _sample_graph(turn=18)
    g.save(_SLOT)
    g.compress(18, slot=_SLOT)        # period = 18//6 = 3
    g.summarize_period(18, slot=_SLOT)  # period = 18//12 = 1

    su = g.query_summaries(period=None, slot=_SLOT)
    assert len(su) == 2, "全量含 summary_3 与 period_summary_1"
    assert {s["stype"] for s in su} == {"summary", "period_summary"}
    # 按 period 精确命中
    su1 = g.query_summaries(period=1, slot=_SLOT)
    assert len(su1) == 1 and su1[0]["stype"] == "period_summary"
    su3 = g.query_summaries(period=3, stype="summary", slot=_SLOT)
    assert len(su3) == 1 and su3[0]["eid"] == "summary_3"

    # 指定 period → 概要层
    r1 = g.retrieve_hierarchical("蔡京", period=3, slot=_SLOT)
    assert r1["level"] == 1 and r1["source"] == "summary"
    assert "第3期概要" in r1["summary"]

    # 未指定 period → 细节层（query 下钻）
    r2 = g.retrieve_hierarchical("蔡京", slot=_SLOT)
    assert r2["level"] == 2 and r2["source"] == "detail"
    assert any(row[2] == "supports" for row in r2["rows"])
    assert "蔡京" in r2["summary"]


def test_query_summaries_memory_fallback():
    """query_summaries 未落盘时从内存 entities 过滤 summary 类实体。"""
    g = _sample_graph(turn=6)
    g.compress(6)   # 未 save：内存镜像
    su = g.query_summaries(period=1)
    assert len(su) == 1 and su[0]["stype"] == "summary"


# ---------------------------------------------------------------
# 4. 旧 JSON 迁移 / 损坏重建 / 存档兼容
# ---------------------------------------------------------------
def test_migrate_old_json():
    """旧 slot_{slot}_memory.json → SQLite 迁移：数据完整 + 旧 JSON 保留。"""
    old = {
        "schema_version": 1, "turn": 30, "archived": 2,
        "entities": {
            "minister_蔡京": {"eid": "minister_蔡京", "type": "minister", "name": "蔡京",
                              "attrs": {"faction": "新党"}, "created_turn": 0},
            "decision_1_旧政": {"eid": "decision_1_旧政", "type": "decision", "name": "旧政",
                                "attrs": {}, "created_turn": 1},
        },
        "relations": [
            {"src": "minister_蔡京", "dst": "decision_1_旧政", "rtype": "supports",
             "turn": 1, "weight": 1.2, "note": "赞同"},
        ],
    }
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(_memory_path(_SLOT), "w", encoding="utf-8") as f:
        json.dump(old, f, ensure_ascii=False)

    g = MemoryGraph()
    ok = g.load(_SLOT)
    assert ok is True
    assert g._migrated is True
    assert g.turn == 30 and g.archived == 2
    assert g.entities["minister_蔡京"]["attrs"]["faction"] == "新党"
    assert len(g.relations) == 1 and g.relations[0]["rtype"] == "supports"
    # 迁移后 SQLite 为权威（可再 load）
    assert os.path.exists(_db_path(_SLOT))
    g2 = MemoryGraph()
    assert g2.load(_SLOT) and g2.turn == 30
    # 旧 JSON 保留（安全回退）
    assert os.path.exists(_memory_path(_SLOT))


def test_migrate_old_json_with_archive():
    """旧 archive JSON（若有）并入 db 的 archived 标记。"""
    old = {
        "schema_version": 1, "turn": 5, "archived": 0,
        "entities": {"a": {"eid": "a", "type": "minister", "name": "甲", "attrs": {}, "created_turn": 0}},
        "relations": [],
    }
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(_memory_path(_SLOT), "w", encoding="utf-8") as f:
        json.dump(old, f, ensure_ascii=False)
    with open(_memory_path(_SLOT, archive=True), "w", encoding="utf-8") as f:
        json.dump([{"src": "a", "dst": "b", "rtype": "involves", "turn": 1,
                    "weight": 0.1, "note": "旧史"}], f, ensure_ascii=False)

    g = MemoryGraph()
    assert g.load(_SLOT) is True
    archived_rels = [r for r in g.relations if r.get("archived")]
    assert len(archived_rels) == 1
    assert g.archived >= 1


def test_load_missing_db_no_json():
    """无 db 且无旧 JSON → load 返回 False，空图（开局新记忆库）。"""
    g = MemoryGraph()
    assert g.load(_SLOT) is False
    assert g.entities == {} and g.relations == []


def test_save_load_separate_from_main_save():
    """主存档 JSON + 记忆 .db 同槽位分离（互不干扰，不写同一文件）。"""
    from core.save_load import save_game, load_game
    from core.commands import new_game
    s = new_game("史实")
    s.turn = 3
    assert save_game(s, slot=_SLOT) is True
    main_path = os.path.join(SAVE_DIR, f"slot_{_SLOT}.json")
    assert os.path.exists(main_path), "主存档仍为 JSON"
    assert os.path.exists(_db_path(_SLOT)), "记忆库为独立 .db"
    # 主存档 JSON 不含记忆图内容（分离），记忆从 db 恢复
    with open(main_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "entities" not in data
    s2 = load_game(_SLOT)
    assert s2 is not None
    assert s2.memory.turn == 3
    # 清理
    for p in (main_path, _db_path(_SLOT)):
        if os.path.exists(p):
            os.remove(p)
