# -*- coding: utf-8 -*-
"""**G-3 迁移基座** 定向回归（2026-10-04）。

本组只锁**纯函数**与**对账口径**；
迁移本身尚未接入调用点（`pops[].grain` 仍有写入 262 / 读取 128 处），
必须分片推进、每片单独对账。
"""
import os
import sys

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from core.game_state import GameState                    # noqa: E402
from core.grain_ledger import (GRAIN_MIGRATION_DIM,      # noqa: E402
                               grain_of, has_grain_bucket, survey_grain)


def test_grain_of_returns_none_when_not_migrated():
    """缺失 ≠ 0：迁移前 `goods` 无米麦 ⇒ 派生读口返回 `None` 而**不是 0**。"""
    s = GameState("史实")
    p = next(iter(next(iter(s.prefectures.values())).get("pops", {}).values()))
    assert isinstance(p.get("grain"), (int, float)), "前置：旧账应仍有 grain 字段"
    assert grain_of(p) is None, "未迁移时不得回落成 0（那是伪造成有粮）"
    assert has_grain_bucket(p) is False


def test_grain_of_sums_bucket():
    """派生读口 = goods[米] + goods[麦]。"""
    p = {"goods": {"米": 100, "麦": 30, "木": 5}}
    assert grain_of(p) == 130
    assert has_grain_bucket(p) is True
    assert grain_of({"goods": {"木": 5}}) is None
    assert grain_of(None) is None


def test_survey_reports_unmigrated_state():
    """对账口径：迁移前应报「未迁移」且 Σgoods[米麦]==0。"""
    s = GameState("史实")
    r = survey_grain(s)
    assert r["迁移状态"] == "未迁移", r
    assert r["Σgoods[米麦]"] == 0
    assert r["Σpops[].grain"] > 0
    assert r["路由数"] > 0 and r["POP数"] > 0


def test_migration_dim_is_documented_assumption():
    """迁移目标维固定为「米」，理由是**口径假设**而非史料依据。"""
    assert GRAIN_MIGRATION_DIM == "米", (
        "grain 是单一无单位总量、无米麦分项史料；改维须同步改文档与理由")


def test_survey_is_consistent_after_manual_bucket():
    """手工在 goods 放粮后，对账应识别为「部分迁移」并计入 Σgoods[米麦]。"""
    s = GameState("史实")
    p = next(iter(next(iter(s.prefectures.values())).get("pops", {}).values()))
    p.setdefault("goods", {})[GRAIN_MIGRATION_DIM] = 777
    r = survey_grain(s)
    assert r["Σgoods[米麦]"] == 777, r
    assert r["迁移状态"] == "部分迁移", r


# ====================================================== 迁移批次验收（阶段 2 · 第六包 · 2026-10-06）
def test_stub_reexports_same_objects_as_new_module():
    """旧路径为**薄转发**：每个符号与新实现**同一对象**（无复制实现）。"""
    from core import grain_ledger as OLD
    from core.foundation.ledger import grain_ledger as NEW
    assert OLD.__file__ != NEW.__file__
    names = sorted(n for n in dir(NEW) if not n.startswith('__'))
    assert len(names) == 7, f"dir() 符号数变化（迁移桩需同步）：{len(names)}"
    for n in names:
        assert getattr(OLD, n) is getattr(NEW, n), f"符号 {n} 非同一实现（疑似副本）"


def test_grain_bridge_imports_ledger_via_new_path():
    """`grain_bridge` 的顶层 import 已改指新路径：模块可导入且引用同一实现。

    顶层 import 断链会在 collection 期直接炸（非静默），此处再锁**对象同一性**。
    """
    from core.foundation.ledger import grain_bridge as GB
    from core.foundation.ledger import grain_ledger as NEW
    assert GB.GRAIN_MIGRATION_DIM is NEW.GRAIN_MIGRATION_DIM
    assert GB.has_grain_bucket is NEW.has_grain_bucket
