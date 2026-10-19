# -*- coding: utf-8 -*-
"""质量放行门 · 行政区划骨架 P1（2026-10-19）。

P1 只做**只读骨架**：登记宋 117 治所 + 外邦六国省/州府，不写人口、不改结算。
本门钉住：
1. 新局 `regions` 已建：宋 T2=20 路、T1=117 治所；外邦六国省/州府齐（与静态表一致）；
2. 不变量为空（无孤儿/无环/深度≤3/父子 owner 一致）；
3. `init_regions` **幂等**（二次调用 created=0）；
4. 缺失≠0：T1 人口未分解 ⇒ `pop_total=None` + reason；
5. 宋 T1 都带 `prefecture_ref`（详账指针，不复制详账）；
6. **零行为变更**：删除 regions 前后跑一个月结算，国库/地方府库/日志行数逐字相同。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from content.data_external_admin import REGIME_SEATS, REGIME_TIER1  # noqa: E402
from core.foundation.ledger.region_registry import (  # noqa: E402
    aggregate_by_owner, init_regions, regions_by_owner, verify_region_invariants)


def _state():
    from core.commands import new_game

    return new_game()


def test_skeleton_counts():
    s = _state()
    song = regions_by_owner(s, "宋")
    t2 = [r for r in song if r["level"] == "T2"]
    t1 = [r for r in song if r["level"] == "T1"]
    assert len(t2) == len(s.prefectures), (len(t2), len(s.prefectures))
    assert len(t1) == sum(len(p.get("seats") or {}) for p in s.prefectures.values())
    assert len(t1) == 117, len(t1)


def test_foreign_seven_registered_with_static_table():
    """七国 T1 与静态表（= 舆图切分）逐国相等；T2 等于运行态 provinces 数。"""
    s = _state()
    assert len(REGIME_TIER1) == 7, REGIME_TIER1
    for name in REGIME_TIER1:
        rows = regions_by_owner(s, name)
        assert rows, f"{name} 未登记"
        t1 = [r for r in rows if r["level"] == "T1"]
        t2 = [r for r in rows if r["level"] == "T2"]
        expect = sum(len(v) for v in (REGIME_SEATS.get(name) or {}).values())
        assert len(t1) == expect, (name, len(t1), expect)
        provs = (s.external_regimes.get(name) or {}).get("provinces") or []
        assert len(t2) >= len(provs), (name, len(t2), len(provs))


def test_invariants_clean():
    s = _state()
    assert verify_region_invariants(s) == [], verify_region_invariants(s)


def test_idempotent():
    s = _state()
    before = dict(s.regions)
    out = init_regions(s)
    assert out["created"] == 0 and out["reason"] == "already"
    assert s.regions == before


def test_missing_pop_is_none_with_reason():
    """P4 后：有省级 pops 的国（辽）已分解；缺数据的国（吐蕃）仍为 None + reason。"""
    s = _state()
    assert isinstance(aggregate_by_owner(s, "辽")["pop_total"], dict)
    agg = aggregate_by_owner(s, "吐蕃")
    assert agg["pop_total"] is None
    assert agg["pop_reason"], "缺失必须给 reason"


def test_song_t1_has_prefecture_ref_only():
    s = _state()
    t1 = [r for r in regions_by_owner(s, "宋") if r["level"] == "T1"]
    assert t1
    for r in t1:
        ref = r.get("prefecture_ref")
        assert isinstance(ref, dict) and ref.get("route") and ref.get("seat"), r
        assert "pops" not in r and "grain" not in r, "宋 T1 不得复制详账"


def test_zero_behavior_change():
    """删除 regions 前后跑一个月结算：关键数字与日志行数必须逐字相同。"""
    from core.settlement import run_monthly_settlement

    s1 = _state()
    log1 = run_monthly_settlement(s1)
    base = (int(s1.treasury),
            int(sum(int(p.get("local_treasury", 0) or 0) for p in s1.prefectures.values())),
            len(log1))

    s2 = _state()
    s2.regions = {}
    log2 = run_monthly_settlement(s2)
    got = (int(s2.treasury),
           int(sum(int(p.get("local_treasury", 0) or 0) for p in s2.prefectures.values())),
           len(log2))
    assert got == base, (got, base)


def test_every_foreign_t1_has_map_province():
    """每个外邦 T1 必须带 `map_province`，且属于该国静态表的省键（面 ↔ 账可追溯）。"""
    s = _state()
    for name in REGIME_TIER1:
        allowed = set((REGIME_SEATS.get(name) or {}).keys())
        for r in regions_by_owner(s, name):
            if r["level"] != "T1":
                continue
            mp = r.get("map_province")
            assert mp in allowed, (name, r.get("name"), mp)


def test_t2_counts_match_runtime_provinces():
    """T2 至少覆盖运行态 provinces 数（缺图省另挂 map_ 节点，记 note）。"""
    s = _state()
    for name in REGIME_TIER1:
        provs = (s.external_regimes.get(name) or {}).get("provinces") or []
        t2 = [r for r in regions_by_owner(s, name) if r["level"] == "T2"]
        assert len(t2) >= len(provs), (name, len(t2), len(provs))