# -*- coding: utf-8 -*-
"""质量放行门 · P3 行政区划迁移幂等（2026-10-19）。

旧档无 `regions` ⇒ 读档迁移；新档已建 ⇒ 幂等跳过；迁移后不变量必须为空。

本门钉住：
1. 新局已有 regions（new_game 入口）；
2. 删除 regions 后 `migrate_regions` 重建 **225** 个且 `migrated=True`；
3. 再调 `migrate_regions` ⇒ `migrated=False, created=0`（幂等）；
4. 迁移后 `verify_region_invariants` 为空；
5. 序列化往返（dict JSON）后迁移判定为「已有」（读档等价）；
6. 读档入口（`application.load_game`）确实调用迁移（静态检查）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.foundation.ledger.region_registry import (  # noqa: E402
    migrate_regions, verify_region_invariants)


def _state():
    from core.commands import new_game

    return new_game()


def test_new_game_has_regions():
    s = _state()
    assert len(s.regions) == 225, len(s.regions)


def test_migrate_after_delete():
    s = _state()
    s.regions = {}
    out = migrate_regions(s)
    assert out["migrated"] is True and out["created"] == 225, out
    assert verify_region_invariants(s) == []


def test_migrate_is_idempotent():
    s = _state()
    out = migrate_regions(s)
    assert out["migrated"] is False and out["created"] == 0, out


def test_serialization_roundtrip_treated_as_existing():
    s = _state()
    blob = json.dumps({k: dict(v) for k, v in s.regions.items()}, ensure_ascii=False)
    s.regions = json.loads(blob)
    out = migrate_regions(s)
    assert out["migrated"] is False and out["total"] == 225, out


def test_load_game_calls_migration():
    import inspect

    from application import load_game as lg

    src = inspect.getsource(lg)
    assert "migrate_regions" in src, "读档入口必须调用行政区划迁移"