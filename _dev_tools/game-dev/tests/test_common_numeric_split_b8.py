# -*- coding: utf-8 -*-
"""第八包回归：`_safe_int` / `_safe_float` 从 `core/save_load_util.py` 原文迁入
`core/foundation/common/numeric.py` 后的不变量。

四条各挡一种"看起来成功实则已断"：
 ① 三条旧路径的 `dir()` 公开面与符号同一性（转发桩没换成第二份实现）；
 ② 语义真值表——这三个函数与 `parse_number` 的**实测差异**必须原样保持
    （其中"`_safe_int('2.7')` → `None`"就是"缺失值不作 0"的体现，最容易被顺手'优化'掉）；
 ③ **真实通道非空**：损坏字段经 `load_game` 走的是这两个函数，断的是"读档不炸 + 回落默认"，
    只断 `callable()` 证明不了接通；
 ④ 新路径**没有**被塞进 `__all__` / `core.numeric` 公开面（防止悄悄扩大 API）。
"""
import json
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

import core.foundation.common.numeric as NU      # noqa: E402
import core.numeric as CORE_NUMERIC              # noqa: E402
import core.save_load as SL                      # noqa: E402
import core.save_load_util as SLU                # noqa: E402
from core.game_state import GameState            # noqa: E402

MOVED = ["_safe_int", "_safe_float"]


# ── ① 旧路径公开面 + 同一性 ────────────────────────────────────
def test_old_paths_still_expose_moved_symbols():
    for mod, label in ((SLU, "core.save_load_util"), (SL, "core.save_load")):
        missing = [n for n in MOVED if not hasattr(mod, n)]
        assert not missing, f"{label} 丢了符号：{missing}"


def test_forwards_are_same_objects_not_copies():
    """三条路径必须指向**同一个函数对象**；复制实现会各自漂移，本批就白拆了。"""
    bad = [n for n in MOVED
           if not (getattr(SLU, n) is getattr(NU, n) is getattr(SL, n))]
    assert not bad, f"以下名字旧路径与新实现不是同一对象：{bad}"


def test_util_keeps_its_full_surface():
    """`save_load_util` 的公开面一个都不能少（含 `math`——它现在只为公开面留着）。"""
    expected = {"FACTION_NAMES", "FACTION_NAME_SET", "_safe_float", "_safe_int",
                "_strip_unknown_faction_keys", "annotations", "math",
                "migrate_army_units"}
    now = {n for n in dir(SLU) if not n.startswith("__")}
    assert expected <= now, f"公开面缩水，缺：{sorted(expected - now)}"


# ── ② 语义真值表（与 parse_number 的差异必须原样保留）────────────
@pytest.mark.parametrize("value,expected", [
    (None, None), (True, 1), (False, 0), ("", None), ("  ", None),
    ("42", 42), (42, 42), (2.7, 2),
    ("2.7", None),                       # int('2.7') 抛 ValueError ⇒ **判为缺失，不是截断**
    ([1], None), ({"a": 1}, None), (b"x", None),
    (float("nan"), None), (float("inf"), None),
])
def test_safe_int_semantics_locked(value, expected):
    assert SL._safe_int(value) == expected, f"_safe_int({value!r}) 语义变了"
    assert type(SL._safe_int(value)) is type(expected), f"_safe_int({value!r}) 返回类型变了"


@pytest.mark.parametrize("value,expected", [
    (None, None), (True, 1.0), ("", None), ("2.7", 2.7), (2.7, 2.7),
    ([1], None), (float("nan"), None), (float("inf"), None),
])
def test_safe_float_semantics_locked(value, expected):
    got = SL._safe_float(value)
    assert got == expected, f"_safe_float({value!r}) 语义变了：{got!r}"


def test_differs_from_parse_number_by_design():
    """登记在册的**近重复但不合并**：默认值与小数串判定都不同（合并＝口径变更）。"""
    assert NU.parse_number(None) == 0.0 and NU._safe_int(None) is None
    assert NU.parse_number("2.7") == 2.7 and NU._safe_int("2.7") is None
    assert NU.parse_number(2.7) == 2.7 and NU._safe_int(2.7) == 2


# ── ③ 真实通道：损坏字段经 load_game 落到这两个函数 ─────────────
def _write_broken_slot(tmp_path, monkeypatch, mutator):
    """写真档到 tmp，再按 `mutator` 破坏指定字段，返回槽文件路径。

    槽位落盘目录由**属主模块** `foundation/persistence/slots.SAVE_DIR` 决定（第七包实测），
    所以这里 patch 它，不 patch `core.save_load`。
    """
    monkeypatch.setattr("core.foundation.persistence.slots.SAVE_DIR", str(tmp_path))
    s = GameState("史实")
    assert SL.save_game(s, 8), "前置：存档写入失败"
    path = os.path.join(str(tmp_path), "slot_8.json")
    assert os.path.isfile(path), f"前置：槽文件不在预期位置（{tmp_path}）"
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    mutator(raw)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)
    return path


def test_broken_turn_falls_back_instead_of_raising(tmp_path, monkeypatch):
    """`turn` 被写坏成对象 ⇒ `_safe_int(..., 0)` 回落 0，读档**不得**抛异常。

    这条就是 P2-10 的原意：把"档损坏"交给既有兜底，而不是让 `int()` 冒泡成 500。
    """
    _write_broken_slot(tmp_path, monkeypatch, lambda d: d.__setitem__("turn", {"坏": "对象"}))
    loaded = SL.load_game(8)
    assert loaded is not None, "字段坏不该让整个档读不出来"
    assert loaded.turn == 0, f"应回落 0，实际 {loaded.turn!r}"


def test_illegal_schema_version_goes_corrupt_path(tmp_path, monkeypatch):
    """`schema_version` 非法 ⇒ `_safe_int(_ver_raw, default=None)` 返回 None
    ⇒ 走损坏档路径（改名 .corrupt 并返回 None）。**这里 default 必须是 None**，
    若被'优化'成 0 就会把损坏档当旧版档继续装配。"""
    path = _write_broken_slot(tmp_path, monkeypatch,
                              lambda d: d.__setitem__("schema_version", "不是数字"))
    assert SL.load_game(8) is None
    assert not os.path.exists(path), "损坏档应被改名移走，而不是留在原槽"
    assert os.path.isfile(path + ".corrupt"), (
        f"应留下 .corrupt 备份（实际目录：{sorted(os.listdir(str(tmp_path)))}）")


def test_official_rank_index_uses_safe_float_channel(tmp_path, monkeypatch):
    """`official_rank_index` 经 `_safe_float`：坏值回落默认、好值原样读回。"""
    _write_broken_slot(tmp_path, monkeypatch,
                       lambda d: d.__setitem__("official_rank_index", [1, 2]))
    loaded = SL.load_game(8)
    assert loaded is not None
    assert isinstance(loaded.official_rank_index, float), (
        f"回落值类型应仍是浮点，实际 {type(loaded.official_rank_index).__name__}")


# ── ④ 公开面未被悄悄扩大 ──────────────────────────────────────
def test_not_added_to_numeric_public_api():
    """刻意不进 `__all__`、不进 `core.numeric` 转发面（下划线名按模块私有处理）。"""
    assert "_safe_int" not in NU.__all__ and "_safe_float" not in NU.__all__
    leaked = [n for n in MOVED if hasattr(CORE_NUMERIC, n)]
    assert not leaked, f"`core.numeric` 公开面被扩大：{leaked}"
