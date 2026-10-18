# -*- coding: utf-8 -*-
"""质量放行门 · 粮载体单一性（B-2b）。

对应设计：`B2_守卫与质量放行门_设计与取证_2026-10-12.md` §4 B-2b 与 N5。

门要回答的问题：**"粮到底只有一种载体吗"**。
取证结论（2026-10-18 实测）：G-3 迁移（H·甲：`pops[].grain` → `goods[米/麦]`）**只写了纯函数、未接线**，
所以当前 702 个 POP 全部走 legacy `.grain`，`goods` 里没有任何米/麦桶 ⇒ **无双源**。
风险不是"现在分叉"，而是"将来迁移做一半"：一半 POP 有桶、一半没有，而 `grain_get` 优先读桶 ⇒ 静默分叉。
故本门的判据是**全体一致性**（0% 或 100%，禁止中间态），而不是"桶数必须为 0"。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.foundation.ledger.grain_ledger import GRAIN_MIGRATION_DIM, has_grain_bucket  # noqa: E402
from core.foundation.ledger.grain_bridge import grain_get  # noqa: E402

MONTHS = 3


def _new_state():
    from core.commands import new_game

    return new_game()


def _pops(state):
    for route, pdata in (state.prefectures or {}).items():
        for sid, srow in ((pdata or {}).get("seats") or {}).items():
            for cls, row in (((srow or {}).get("pops")) or {}).items():
                if isinstance(row, dict):
                    yield route, sid, cls, row


def _carrier_census(state) -> dict:
    total = bucket = both = legacy_field = 0
    for _r, _s, _c, row in _pops(state):
        total += 1
        b = has_grain_bucket(row)
        legacy = row.get("grain")
        if b:
            bucket += 1
        if legacy is not None:
            legacy_field += 1
        goods = row.get("goods") if isinstance(row.get("goods"), dict) else {}
        gv = goods.get(GRAIN_MIGRATION_DIM)
        if b and isinstance(gv, (int, float)) and legacy not in (None, 0):
            both += 1
    return {"total": total, "bucket": bucket, "legacy_field": legacy_field, "both_nonzero": both}


def test_gate_grain_carrier_is_all_or_nothing(monkeypatch):
    """N5：禁止"一半 POP 有米桶、一半没有"的中间态（Σ 相等也不能证明单一载体）。"""
    from core.commands import settle_local

    state = _new_state()
    for _ in range(MONTHS):
        settle_local(state)

    census = _carrier_census(state)
    assert census["total"] > 0, "没有 POP，门是空转"
    if 0 < census["bucket"] < census["total"]:
        raise AssertionError(
            "粮载体处于中间态（部分 POP 有米/麦桶、部分没有）⇒ grain_get 会优先读桶，导致静默分叉："
            f"{census}"
        )
    # 0 或 全量 都算单一载体；当前实测应为 0（G-3 未接线）
    assert census["bucket"] in (0, census["total"]), census


def test_gate_grain_read_path_matches_carrier():
    """迁移未接线时 grain_get 必须读 legacy `.grain`；接了线则必须读桶（缺失≠0）。"""
    state = _new_state()
    checked = 0
    for _r, _s, _c, row in _pops(state):
        legacy = row.get("grain")
        if not isinstance(legacy, (int, float)) or isinstance(legacy, bool):
            continue
        got = grain_get(row)
        checked += 1
        if not has_grain_bucket(row):
            assert got == legacy, f"未迁移时 grain_get 应回落到 .grain：{got} != {legacy}"
        else:
            assert got is not None, "已迁移时 grain_get 不得为 None"
        if checked >= 50:
            break
    assert checked > 0, "没有可核对样本，门是空转"


def test_gate_grain_guards_against_silent_half_migration(monkeypatch):
    """反例（注入即红）：手动给单个 POP 造米桶 ⇒ 上面的一致性判据必须能识别出中间态。"""
    state = _new_state()
    target = None
    for _r, _s, _c, row in _pops(state):
        if not has_grain_bucket(row):
            target = row
            break
    assert target is not None
    target.setdefault("goods", {})[GRAIN_MIGRATION_DIM] = 1  # 只迁一个 POP（模拟做一半）
    census = _carrier_census(state)
    assert 0 < census["bucket"] < census["total"], "注入半迁移后应处于中间态"
    # 门判据本身必须判红
    with_mixed = 0 < census["bucket"] < census["total"]
    assert with_mixed, f"门未能识别中间态：{census}"
