# -*- coding: utf-8 -*-
"""决策日志**落盘**（schema v5）：存档/读档往返、旧档兼容、脏档降级、只读性。

背景（Lead 实测的现状）：`state.decision_log` 原本只是内存 list
（`game/core/game_state.py:588`，上限 `tiandao_decision.MAX_LOG = 200`），
`core/save_load.py` **完全没有**该字段 ⇒ 读档即清零。本批把它做成**只读观测副本**
随档持久化：不参与结算、不改任何数值。

覆盖：
1. 新局跑 `observe_monthly` 后存档 → 读档：`decision_log` 非空且条数/内容一致
   （对 `tmp_path` 写**真实档**，并核对磁盘 JSON 里确实有该键）；
2. **旧档兼容**：手工构造不含 `decision_log` 的 v4 存档 ⇒ `[]` 且不拒档；
3. **脏数据**：`decision_log: "not-a-list"` ⇒ `[]` + warning 留痕；
   list 内非 dict 条目 ⇒ 隔离丢弃 + warning；
4. **只读性**：存档/读档前后 `treasury` 等关键数值不变、内存日志不被存档改动。

注：`SAVE_DIR` 由 conftest 的 autouse fixture 重定向到 `tmp_path`，不会写真实存档。
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.ai.tiandao_facade import TianDaoFacade  # noqa: E402
from core.commands import new_game  # noqa: E402
from core.save_load import _slot_path, load_game, save_game  # noqa: E402

#: 测试隔离槽（>5 是仓库既有的"测试/临时槽"惯例）
_SLOT = 7


def _read_slot(slot: int) -> dict:
    with open(_slot_path(slot), "r", encoding="utf-8") as f:
        return json.load(f)


def _write_slot(slot: int, data: dict) -> None:
    with open(_slot_path(slot), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════════════════════
# 1) 新档：存档 → 读档 条数与内容一致
# ══════════════════════════════════════════════════════════════════════════
def test_new_game_decision_log_roundtrip(tmp_path):
    s = new_game("史实")
    TianDaoFacade.observe_monthly(s)

    n = len(s.decision_log)
    assert n == len(TianDaoFacade.OBSERVE_OBJECTIVES), "前置：本月应写入 10 条裁决"
    before = [dict(r) for r in s.decision_log]

    assert save_game(s, _SLOT) is True

    # ① 磁盘上真的写了该键（不是只在内存里对得上）
    disk = _read_slot(_SLOT)
    assert disk["schema_version"] == 5, "本批把随档 schema 升到 v5（决策日志落盘）"
    assert len(disk["decision_log"]) == n
    assert disk["decision_log"] == before

    # ② 读档后条数与内容一致（JSON 往返应保真）
    s2 = load_game(_SLOT)
    assert s2 is not None, "带 decision_log 的新档必须能读回"
    assert len(s2.decision_log) == n
    assert s2.decision_log == before
    assert {r["objective"] for r in s2.decision_log} == set(TianDaoFacade.OBSERVE_OBJECTIVES.values())


# ══════════════════════════════════════════════════════════════════════════
# 2) 旧档兼容：无 decision_log 键 ⇒ []，不拒档
# ══════════════════════════════════════════════════════════════════════════
def test_old_save_without_decision_log_loads_as_empty_list(tmp_path):
    s = new_game("史实")
    assert save_game(s, _SLOT) is True

    data = _read_slot(_SLOT)
    data.pop("decision_log", None)      # 模拟本程序上一版（v4）写出的旧档
    data["schema_version"] = 4
    _write_slot(_SLOT, data)

    s2 = load_game(_SLOT)
    assert s2 is not None, "旧档缺 decision_log 键**不得**拒档"
    assert s2.decision_log == []

    # 再存一次 ⇒ 新档自动带上该键（增量迁移，无需任何显式转换）
    assert save_game(s2, _SLOT) is True
    assert _read_slot(_SLOT)["decision_log"] == []


def test_future_schema_version_still_rejected(tmp_path):
    """版本门只有**上界**：v5 支持 v1…v5；v6（未来档）仍拒载（证明没退化成"任意版本都读"）。"""
    s = new_game("史实")
    assert save_game(s, _SLOT) is True
    data = _read_slot(_SLOT)
    data["schema_version"] = 6
    _write_slot(_SLOT, data)

    assert load_game(_SLOT) is None


# ══════════════════════════════════════════════════════════════════════════
# 3) 脏数据降级：非 list ⇒ [] + warning（不静默 pass、也不因单字段坏值丢整档）
# ══════════════════════════════════════════════════════════════════════════
def test_dirty_decision_log_not_a_list_degrades_to_empty_with_warning(tmp_path, caplog):
    s = new_game("史实")
    assert save_game(s, _SLOT) is True
    data = _read_slot(_SLOT)
    data["decision_log"] = "not-a-list"
    _write_slot(_SLOT, data)

    with caplog.at_level(logging.WARNING, logger="save_load"):
        s2 = load_game(_SLOT)

    assert s2 is not None, "单个脏字段不得让整档读失败"
    assert s2.decision_log == []
    messages = [r.getMessage() for r in caplog.records]
    assert any("decision_log" in m for m in messages), \
        "脏 decision_log 必须 logging.warning 留痕，不许静默 pass：%r" % (messages,)


def test_dirty_non_dict_entries_are_dropped_with_warning(tmp_path, caplog):
    s = new_game("史实")
    assert save_game(s, _SLOT) is True
    data = _read_slot(_SLOT)
    data["decision_log"] = [{"turn": 0, "objective": "synthetic"}, "junk", 42]
    _write_slot(_SLOT, data)

    with caplog.at_level(logging.WARNING, logger="save_load"):
        s2 = load_game(_SLOT)

    assert s2 is not None
    assert s2.decision_log == [{"turn": 0, "objective": "synthetic"}]
    assert any("decision_log" in r.getMessage() for r in caplog.records)


# ══════════════════════════════════════════════════════════════════════════
# 4) 只读性：不参与结算、不改任何数值
# ══════════════════════════════════════════════════════════════════════════
def test_save_load_is_read_only_for_numbers_and_log(tmp_path):
    s = new_game("史实")
    TianDaoFacade.observe_monthly(s)

    keys = ("treasury", "imperial_treasury", "granary", "prestige", "turn", "year", "month")
    before = {k: getattr(s, k) for k in keys}
    log_before = [dict(r) for r in s.decision_log]

    assert save_game(s, _SLOT) is True
    # 存档是"只读观测副本"：不许回写/清空内存里的日志
    assert [dict(r) for r in s.decision_log] == log_before

    s2 = load_game(_SLOT)
    assert s2 is not None
    after = {k: getattr(s2, k) for k in keys}
    assert after == before, "存档/读档改变了关键数值：%r -> %r" % (before, after)
    assert s2.decision_log == log_before


# ══════════════════════════════════════════════════════════════════════════
# 5) 容量：随档日志截断到写入端同源上限（MAX_LOG = 200）
# ══════════════════════════════════════════════════════════════════════════
def test_save_truncates_decision_log_to_writer_cap(tmp_path):
    from core.ai.tiandao_decision import MAX_LOG

    s = new_game("史实")
    s.decision_log = [
        {"turn": i, "objective": "synthetic", "verdict": bool(i % 2),
         "probability": 0.5, "defined": True, "provider": "tiandao_local",
         "seed": i, "cached": False, "facts_digest": None}
        for i in range(MAX_LOG + 37)
    ]
    assert save_game(s, _SLOT) is True

    disk = _read_slot(_SLOT)
    assert len(disk["decision_log"]) == MAX_LOG, "随档日志必须截断到写入端上限"
    assert disk["decision_log"] == s.decision_log[-MAX_LOG:], "截断须保留最新（尾部）记录"

    s2 = load_game(_SLOT)
    assert len(s2.decision_log) == MAX_LOG
