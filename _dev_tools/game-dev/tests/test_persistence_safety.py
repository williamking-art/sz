# -*- coding: utf-8 -*-
"""存档与记忆安全回归（task-3 / 审查 P2-10/11/12/13）。

覆盖：
  - P2-10 存档 schema_version 等数值字段被写坏（字符串/对象/列表/空值）→ 安全解析，
    走损坏档路径（日志 + .corrupt 备份 + None），不得抛未处理异常（→500）。
  - P2-11 全国识字率是 POP 派生视图：载入后**始终**由逐路 POP 加权重算，
    顶层 `literacy` 仅迁移诊断，不得覆盖；旧档逐路补齐后仍与派生值一致。
  - P2-12 对话记忆库跨线程 / 并发访问：连接 check_same_thread=False + 对象锁，
    写事务边界明确，跨线程读写不抛 sqlite3.ProgrammingError、不丢行。
  - P2-13 损坏记忆库（对话库 / 图谱库 / 旧 JSON 迁移源）不得静默变空：
    必须隔离 .corrupt、记录可诊断错误、返回 False，且不重建空库冒充正常。

原则：跑真实代码路径（不伪造成功）；SAVE_DIR 由 conftest 重定向到 tmp_path，
绝不触碰真实玩家存档。
"""
import json
import os
import sys
import threading

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.commands import new_game  # noqa: E402
from core.literacy import national_literacy  # noqa: E402
from core.save_load import _slot_path, load_game, save_game  # noqa: E402
from memory.dialogue_memory import DialogueMemory, _dialogue_path  # noqa: E402
from memory.memory_graph import MemoryGraph, _db_path, _memory_path  # noqa: E402


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def _make_saved_state(slot, turn=5):
    s = new_game("史实")
    s.turn = turn
    assert save_game(s, slot) is True
    return s


def _write_corrupt(path, raw=b"this is not a sqlite database \x00\x01\x02"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(raw)
    return raw


# =====================================================================
# P2-10 存档 schema / 数值字段安全解析
# =====================================================================
@pytest.mark.parametrize("bad_value", ["不是数字", {}, [], ["x"], None, ""])
def test_schema_version_illegal_is_quarantined_not_500(bad_value):
    """schema_version 为非法字符串/对象/列表/空值时：不抛异常，隔离 .corrupt 并返回 None。"""
    slot = 310
    _make_saved_state(slot)
    path = _slot_path(slot)
    data = _read_json(path)
    data["schema_version"] = bad_value
    _write_json(path, data)
    with open(path, "rb") as f:
        tampered = f.read()

    result = load_game(slot)  # 不得抛（原实现 int(对象/乱码) → 未处理异常 → 500）

    assert result is None
    assert not os.path.exists(path), "非法 schema_version 的档应被隔离，不得原地冒充"
    backup = path + ".corrupt"
    assert os.path.exists(backup)
    with open(backup, "rb") as f:
        assert f.read() == tampered, "备份必须保留损坏原档现场"


def test_schema_version_missing_old_save_still_loads():
    """旧档无 schema_version 键（合法迁移场景）仍按 v1 正常载入。"""
    slot = 311
    _make_saved_state(slot, turn=7)
    path = _slot_path(slot)
    data = _read_json(path)
    data.pop("schema_version", None)
    _write_json(path, data)

    st = load_game(slot)
    assert st is not None
    assert st.turn == 7


def test_schema_version_too_new_rejected():
    """版本高于支持上限：拒绝加载（返回 None），不伪装成正常档。"""
    slot = 312
    _make_saved_state(slot)
    path = _slot_path(slot)
    data = _read_json(path)
    data["schema_version"] = 99
    _write_json(path, data)

    assert load_game(slot) is None


def test_corrupt_numeric_fields_do_not_crash_load():
    """turn/财政/官制/军额等 int()/float() 同类风险：坏值一律安全回落默认值，不抛异常。"""
    slot = 315
    _make_saved_state(slot, turn=5)
    path = _slot_path(slot)
    data = _read_json(path)
    data["turn"] = "第5回合"
    data["treasury_deficit"] = {"坏": 1}
    data["silver_stock"] = ["x"]
    data["posts_quota"] = "abc"
    data["official_rank_index"] = "??"
    data["imperial_micro_count"] = {"x": 1}
    # 旧版军队字段（无 branches，用 branch/troops）的 troops 被写坏
    if data.get("army_units"):
        unit = data["army_units"][0]
        unit.pop("branches", None)
        unit["branch"] = "轻步兵"
        unit["troops"] = "坏值"
    _write_json(path, data)

    st = load_game(slot)

    assert st is not None
    assert st.turn == 0, "非法 turn 应回落 0，而不得泄漏原始字符串"
    assert st.treasury_deficit == 0
    assert st.silver_stock == 0
    assert st.posts_quota == 0
    assert st.official_rank_index == pytest.approx(1.0)
    assert st.imperial_micro_count == 0
    assert st.army_units, "军队单位仍须构建（兵额回落到 0，不得整档失败）"
    assert all(u.troops >= 0 for u in st.army_units)


# =====================================================================
# P2-11 识字率：POP 派生为唯一权威
# =====================================================================
def test_top_level_literacy_cannot_override_pop_derived():
    """顶层 literacy 被篡改也不能覆盖派生值（POP 挂载律）。"""
    slot = 320
    _make_saved_state(slot)
    path = _slot_path(slot)
    data = _read_json(path)
    data["literacy"] = 99.9
    _write_json(path, data)

    st = load_game(slot)

    assert st is not None
    derived = national_literacy(st)
    assert derived is not None
    assert st.literacy == pytest.approx(derived, abs=1e-9)
    assert st.literacy < 90.0, "99.9 只可能来自顶层字段，说明派生值被覆盖"


def test_literacy_after_load_is_pop_weighted_consistency():
    """加权一致性：篡改逐路 POP 结构与 literacy 后，载入值与手工加权/派生口径一致。"""
    slot = 321
    _make_saved_state(slot)
    path = _slot_path(slot)
    data = _read_json(path)
    data["literacy"] = 1.0                      # 顶层错误值不得生效
    route = "京畿路"
    pops = data["prefectures"][route]["pops"]
    pops["士绅"]["literacy"] = 95.0
    pops["士绅"]["size"] = int(pops["士绅"]["size"]) * 20 + 50000
    _write_json(path, data)

    st = load_game(slot)
    assert st is not None

    num = den = 0.0
    for _route, p in st.prefectures.items():
        for _cls, pop in (p.get("pops") or {}).items():
            if pop.get("literacy") is None:
                continue
            size = max(0.0, float(pop.get("size", 0) or 0))
            num += float(pop["literacy"]) * size
            den += size
    manual = num / den
    assert st.literacy == pytest.approx(manual, abs=0.01)
    assert st.literacy == pytest.approx(national_literacy(st), abs=1e-9)
    # 单路派生读数也随 POP 结构变化（士绅拉高）
    from core.literacy import route_literacy
    sizes = [max(0.0, float(p.get("size", 0) or 0)) for p in pops.values()]
    weighted = sum(float(p["literacy"]) * max(0.0, float(p.get("size", 0) or 0))
                   for p in pops.values()) / sum(sizes)
    assert route_literacy(st, route) == pytest.approx(weighted, abs=0.01)


def test_old_save_without_literacy_is_backfilled_and_consistent():
    """旧档（无顶层 literacy、逐路 POP 无 literacy）→ 幂等补齐后全国值仍为派生值。"""
    slot = 322
    _make_saved_state(slot)
    path = _slot_path(slot)
    data = _read_json(path)
    data.pop("literacy", None)
    for p in data["prefectures"].values():
        for pop in (p.get("pops") or {}).values():
            pop.pop("literacy", None)
    _write_json(path, data)

    st = load_game(slot)

    assert st is not None
    derived = national_literacy(st)
    assert derived is not None
    assert st.literacy == pytest.approx(derived, abs=1e-9)
    for route, p in st.prefectures.items():
        for cls, pop in (p.get("pops") or {}).items():
            assert pop.get("literacy") is not None, f"{route}|{cls} 未补齐 POP 派生读数"


# =====================================================================
# P2-12 对话记忆库线程与并发
# =====================================================================
def test_dialogue_memory_cross_thread_read_write():
    """主线程建连、子线程读写：不得抛 sqlite3.ProgrammingError（check_same_thread）。"""
    slot = 330
    dm = DialogueMemory(slot=slot)
    try:
        errors = []

        def worker(i):
            try:
                dm.turn = i
                dm.add_dialogue("蔡京", i, "蔡京", f"第{i}条奏对", topic="盐法")
                dm.list_dialogues(minister="蔡京")
                dm.summarize_dialogues(i)
            except Exception as e:  # noqa: BLE001
                errors.append(repr(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(1, 9)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"跨线程访问报错：{errors}"
        assert len(dm.list_dialogues(minister="蔡京", limit=100)) == 8
    finally:
        dm.close()


def test_dialogue_memory_concurrent_writes_all_persisted():
    """并发写：对象锁 + 事务边界下，所有写入都必须落库（一条不丢）。"""
    slot = 331
    dm = DialogueMemory(slot=slot)
    try:
        errors = []

        def writer(i):
            try:
                dm.add_dialogue("韩忠彦", i, "韩忠彦", f"第{i}条", topic="边备")
            except Exception as e:  # noqa: BLE001
                errors.append(repr(e))

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(60)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        rows = dm.list_dialogues(minister="韩忠彦", limit=200)
        assert len(rows) == 60, f"并发写入丢失：{len(rows)}/60"
        assert len({r["text"] for r in rows}) == 60
    finally:
        dm.close()


# =====================================================================
# P2-13 损坏记忆库必须隔离而非静默变空
# =====================================================================
def test_corrupt_dialogue_load_quarantines_not_silently_empty():
    """对话库损坏：load() 隔离 .corrupt、返回 False，且不重建空库冒充正常。"""
    slot = 340
    path = _dialogue_path(slot)
    raw = _write_corrupt(path)
    dm = DialogueMemory(slot=None)
    try:
        assert dm.load(slot) is False
        assert dm.load_error, "必须给出可诊断错误"
        assert dm._conn is None
        assert not os.path.exists(path), "损坏库不得原地留作正常空库"
        backup = path + ".corrupt"
        assert os.path.exists(backup)
        with open(backup, "rb") as f:
            assert f.read() == raw, "备份须保留损坏原文件"
        # 损坏态下写操作拒绝惰性重建新库（返回 -1），继续暴露损坏
        assert dm.add_dialogue("蔡京", 1, "蔡京", "x") == -1
        assert not os.path.exists(path)
    finally:
        dm.close()


def test_corrupt_dialogue_constructor_quarantines():
    """生产路径（get_dialogue_memory → 构造器）同样不得静默重建空库。"""
    slot = 341
    path = _dialogue_path(slot)
    raw = _write_corrupt(path)
    dm = DialogueMemory(slot=slot)
    try:
        assert dm._conn is None
        assert dm.load_error
        assert not os.path.exists(path)
        backup = path + ".corrupt"
        assert os.path.exists(backup)
        with open(backup, "rb") as f:
            assert f.read() == raw
        assert dm.list_dialogues() == []
        assert dm.save(slot) is False
    finally:
        dm.close()


def test_corrupt_memory_graph_db_quarantined_not_silently_empty():
    """图谱 db 损坏：load() 隔离 .corrupt、记录 load_error、返回 False。"""
    slot = 350
    path = _db_path(slot)
    raw = _write_corrupt(path)
    g = MemoryGraph()

    assert g.load(slot) is False
    assert g.entities == {} and g.relations == []
    assert g.load_error, "必须给出可诊断错误"
    assert not os.path.exists(path)
    backup = path + ".corrupt"
    assert os.path.exists(backup)
    with open(backup, "rb") as f:
        assert f.read() == raw
    # 隔离后是库缺失的新局，与损坏可区分（load_error 清空）
    g2 = MemoryGraph()
    assert g2.load(slot) is False
    assert g2.load_error is None


def test_corrupt_memory_json_backed_up_and_diagnosed():
    """旧 JSON 迁移源损坏：保留原现场 + 另存 .corrupt + load_error + 返回 False。"""
    slot = 351
    jpath = _memory_path(slot)
    os.makedirs(os.path.dirname(jpath), exist_ok=True)
    with open(jpath, "w", encoding="utf-8") as f:
        f.write("{ 这是坏 JSON !!!")
    g = MemoryGraph()

    assert g.load(slot) is False
    assert g.entities == {} and g.relations == []
    assert g.load_error, "必须给出可诊断错误"
    assert os.path.exists(jpath), "既有约定：损坏 JSON 原现场保留供人工诊断"
    assert os.path.exists(jpath + ".corrupt"), "必须另存 .corrupt 备份"
    assert not os.path.exists(_db_path(slot)), "不得产生半写 / 空库冒充"

def test_locked_memory_db_is_not_quarantined(monkeypatch):
    """database is locked 属暂时不可用，不得误当损坏隔离（有效数据安全）。"""
    import sqlite3 as _sqlite3
    from memory import memory_graph as mgmod

    slot = 352
    g = MemoryGraph()
    g.turn = 1
    g.add_entity("a", "minister", "甲", {}, turn=0)
    assert g.save(slot) is True
    path = _db_path(slot)
    assert os.path.exists(path)

    def _boom(_slot):
        raise _sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(mgmod.MemoryGraph, "_connect", staticmethod(_boom))
    g2 = MemoryGraph()
    assert g2.load(slot) is False
    assert g2.load_error and "不可用" in g2.load_error
    assert os.path.exists(path), "锁冲突不得隔离有效库"
    assert not os.path.exists(path + ".corrupt")


def test_locked_dialogue_db_is_not_quarantined(monkeypatch):
    """对话库被锁时保留原文件、记录不可用，不得冒充损坏隔离。"""
    import sqlite3 as _sqlite3
    from memory import dialogue_memory as dmmod

    slot = 353
    dm = DialogueMemory(slot=slot)
    dm.close()
    path = _dialogue_path(slot)
    assert os.path.exists(path)

    def _boom(_path):
        raise _sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(dmmod.DialogueMemory, "_connect", staticmethod(_boom))
    dm2 = DialogueMemory(slot=slot)
    assert dm2._conn is None
    assert dm2.load_error and "不可用" in dm2.load_error
    assert os.path.exists(path), "锁冲突不得隔离有效对话库"
    assert not os.path.exists(path + ".corrupt")
