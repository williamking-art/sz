# -*- coding: utf-8 -*-
"""M36.7-B3《1101 候选库》契约回归：**三维分离；只登记，不导入在朝名单**。

用户裁定（2026-10-11）：名单含约 200 人，分 A/B/C/D 四组；**不建议批量导入当前在朝名单**；
必须区分 `historical_status_at_1101`（在世）／`office_status`（在任）／`game_domains`（适合领域）；
生卒年与官职须逐人史实校勘，**未核验一律 unknown，不得推定为在任**。
"""
import copy
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.ministers.data import MINISTERS  # noqa: E402
from content.ministers.registry import DOMAIN_ENUM  # noqa: E402
from content.ministers.roster import (GROUP_STATUS, ROSTER_1101,  # noqa: E402
                                      ROSTER_SCHEMA_FIELDS, STATUS_AT_1101,
                                      roster_by_status, roster_candidates_1101,
                                      roster_duplicates, roster_entry, roster_note)
from core.commands import new_game  # noqa: E402


def _names(status):
    return {e["name"] for e in roster_by_status(status)}


# ------------------------------------------------- 契约与三维分离

def test_roster_schema_and_threedim_separation():
    """九字段齐备；三维**互不混用**：领域适配 ≠ 在世 ≠ 在朝。"""
    assert set(ROSTER_SCHEMA_FIELDS) <= set(ROSTER_1101[0]), "字段须齐备"
    for e in ROSTER_1101:
        assert e["historical_status_at_1101"] in STATUS_AT_1101
        assert e["verify"] is True, "一律待逐人史实校勘"
        assert e["death_year"] is None and e["historical_offices"] is None, \
            "未核验字段不得编造（本名册未提供生卒/官职 ⇒ None）"
        assert set(e["game_domains"]) <= set(DOMAIN_ENUM), "领域须在枚举内"
        assert e["source_notes"].startswith("用户名册"), "须保留来源"
    # 三维分离：C/D 组即便有领域，也不因此在世；领域为空者不得推测
    assert all(not e["game_domains"] for e in roster_by_status("pre_deceased")), \
        "已故组不设领域（避免误用）"


def test_groups_and_counts():
    """四组齐备（用户分组语义），且总数与各组计数自洽。"""
    g1 = _names("candidate")
    g2 = _names("not_default_active")
    g3 = _names("pre_deceased")
    g4 = _names("later_era")
    assert len(ROSTER_1101) == len(set(x["name"] for x in ROSTER_1101)) or roster_duplicates()
    assert g1 and g2 and g3 and g4
    # 用户明示：第一组里也有已故者 ⇒ 一律 verify=True，不得据此直接设 in_office
    assert all(e["verify"] for e in ROSTER_1101)
    # 后续时代（D）不得与候选（A）混淆
    assert not (g4 & g1)


def test_duplicates_are_reported_not_merged():
    """用户已提示存在重复：只**报告**，不擅自合并（韩维/文彦博/王安石等）。"""
    dups = roster_duplicates()
    assert dups, "名册确有重复，应被检出"
    assert all(v >= 2 for v in dups.values())
    # 报告而不合并：同一姓名仍各自成entry（分组可能不同）
    for n in dups:
        assert len([e for e in ROSTER_1101 if e["name"] == n]) >= 2
    assert "重复" in roster_note()


def test_no_bulk_import_into_ministers():
    """**不得批量导入**：候选库导入不得改变 `MINISTERS`（人数与在朝标记逐位一致）。"""
    before = (len(MINISTERS),
              {n: bool(f.get("in_office")) for n, f in MINISTERS.items()})
    import importlib
    import content.ministers.roster as r
    importlib.reload(r)
    after = (len(MINISTERS),
             {n: bool(f.get("in_office")) for n, f in MINISTERS.items()})
    assert before == after, "候选库不得写入或在朝名单"
    # C/D 组人物即便在 MINISTERS 中出现，也不得被本模块设为在朝
    for e in r.ROSTER_1101:
        if e["historical_status_at_1101"] in ("pre_deceased", "later_era"):
            assert e["in_office"] is None or e["in_office"] == \
                (MINISTERS.get(e["name"], {}) or {}).get("in_office"), "只读既有值"


# ------------------------------------------------- 候选入选规则（C/D 不得入选）

def test_candidates_exclude_dead_and_later_era():
    """**候选入选**：仅 A 组 ∧ 既有登记 ∧ 在朝；C/D/B 与**同名多状态**者一律排除。"""
    s = new_game()
    dead = _names("pre_deceased")
    later = _names("later_era")
    not_active = _names("not_default_active")
    out = roster_candidates_1101(s, ("military", "finance", "personnel", "culture"),
                                 max_n=10 ** 6)
    picked = {p["name"] for p in out["participants"]}
    conflicts = out["conflicts"]
    assert conflicts, "名册重复必然产生同名多状态，应被检出"
    assert not (picked & dead), f"已故者入选：{picked & dead}"
    assert not (picked & later), f"后续时代者入选：{picked & later}"
    assert not (picked & not_active), f"非默认在朝者入选：{picked & not_active}"
    assert not (picked & set(conflicts)), f"同名多状态者入选：{picked & set(conflicts)}"
    blocked_c = {b["name"] for b in out["blocked_by_conflict"]}
    assert set(conflicts) <= blocked_c, "矛盾者须逐一给出阻断记录"
    blocked = {b["name"] for b in out["blocked_by_status"]}
    # 同名多状态者走 conflict 阻断，其余走 status 阻断 —— 二者并集须覆盖全部非候选组
    assert (dead | later | not_active) <= (blocked | blocked_c), \
        "非候选组须逐一给出阻断记录（状态或冲突）"
    # 每位参与者都必须确实在既有登记中且在朝（可核对）
    for p in out["participants"]:
        assert MINISTERS.get(p["name"], {}).get("in_office") is True, \
            f"{p['name']} 并非既有在朝登记者"
    # 领域过滤：换域 ⇒ 结果随规则变化（同一候选集合内）
    mil = {p["name"] for p in roster_candidates_1101(s, ("military",), max_n=10 ** 6)["participants"]}
    fin = {p["name"] for p in roster_candidates_1101(s, ("finance",), max_n=10 ** 6)["participants"]}
    assert mil != fin or not (mil or fin), "换议题域应改变候选"


def test_roster_candidates_readonly_and_bounded():
    """只读＋限员：调用不改状态；`max_n` 生效。"""
    s = new_game()
    before = (copy.deepcopy(s.prefectures), dict(s.statistics or {}),
              copy.deepcopy(getattr(s, "ai_pending_actions", [])),
              len(getattr(s, "discovery_suspicions", []) or []))
    full = roster_candidates_1101(s, (), max_n=10 ** 6)
    one = roster_candidates_1101(s, (), max_n=1)
    assert len(one["participants"]) <= 1
    after = (s.prefectures, dict(s.statistics or {}),
             getattr(s, "ai_pending_actions", []),
             len(getattr(s, "discovery_suspicions", []) or []))
    assert before[0] == after[0] and before[1] == after[1]
    assert before[2] == after[2] and before[3] == after[3]
    assert full["note"] and "不导入" in full["note"]


def test_roster_entry_lookup_and_unknown_fields():
    """按名取档：未提供字段一律 None（**不推定为在任/在世**）。"""
    e = roster_entry("岳飞")
    assert e is not None and e["historical_status_at_1101"] == "later_era"
    assert e["death_year"] is None, "生卒年未核验 ⇒ None（不编造）"
    # `in_office` **只读既有登记**（岳飞既在档案中，其值为既有 False；不在册者才是 None）
    assert e["in_office"] == MINISTERS.get("岳飞", {}).get("in_office"), "不得改写既有值"
    assert roster_entry("不存在的人物") is None
    # A 组中已在既有登记者：birth_year 取自既有（只读），未登记者为 None
    hz = roster_entry("韩忠彦")
    assert hz["birth_year"] == MINISTERS["韩忠彦"]["born"]
    assert roster_entry("王安石")["birth_year"] is None, "未登记 ⇒ None（不编造）"

