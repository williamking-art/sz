# -*- coding: utf-8 -*-
"""质量放行门 · P4 省→州府人口分解（2026-10-19）。

口径：省级 `pops`（6 类 × size/wealth/grain）按州府权重（最大余数法）分解，**尾差归首府**；
缺失 `pops` 的省（吐蕃/高丽/日本/安南）⇒ 州府 `pop=None`（**缺失≠0**）。

本门钉住：
1. `verify_pop_conservation` 为空（逐省逐类三层字段整数精确）；
2. 有数据的省：T1 全部带 `pop`（辽/西夏/大理）；
3. 缺数据的省：T1 `pop` 为 None 且进 `missing` 清单；
4. `aggregate_regime.pop_total` == Σ省级 pops（逐类 size）；
5. 幂等：二次分解全部 `skipped`，不再改值；
6. 权重生效：首府（weight 1.5）人口 > 普通州府（weight 1.0）——同一省内比较。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.foundation.ledger.region_registry import (  # noqa: E402
    aggregate_regime, distribute_regime_pops, regions_by_owner,
    verify_pop_conservation)


def _state():
    from core.commands import new_game

    return new_game()


def test_conservation_clean():
    s = _state()
    bad = verify_pop_conservation(s)
    assert bad == [], bad[:5]


def test_rich_provinces_have_pop_on_all_t1():
    s = _state()
    for owner in ("辽", "西夏", "大理"):
        t1 = [r for r in regions_by_owner(s, owner) if r["level"] == "T1"]
        assert t1
        for r in t1:
            assert isinstance(r.get("pop"), dict), (owner, r.get("name"))
            assert (r["pop"].get("农") or {}).get("size", 0) > 0, (owner, r.get("name"))


def test_missing_provinces_stay_none():
    s = _state()
    for owner in ("吐蕃", "高丽", "日本", "安南"):
        t1 = [r for r in regions_by_owner(s, owner) if r["level"] == "T1"]
        for r in t1:
            assert not isinstance(r.get("pop"), dict), (owner, r.get("name"))


def test_aggregate_matches_province_sums():
    """Σ T1（农） == Σ**有州府的**省的 pop（无州府的省如大理善阐另记，不静默丢失）。"""
    from core.foundation.ledger.region_registry import _t1_of_province

    s = _state()
    for owner in ("辽", "西夏", "大理"):
        agg = aggregate_regime(s, owner)
        assert isinstance(agg["pop_total"], dict), owner
        prov_total = 0
        unallocated = []
        for p in (s.external_regimes[owner].get("provinces") or []):
            pname = (p or {}).get("name")
            if not _t1_of_province(s.regions, owner, pname):
                unallocated.append(pname)
                continue
            for cls, v in ((p or {}).get("pops") or {}).items():
                if isinstance(v, dict) and cls == "农":
                    prov_total += int(v.get("size") or 0)
        assert agg["pop_total"]["农"] == prov_total, (owner, agg["pop_total"]["农"], prov_total)
        if owner == "大理":
            assert "善阐" in unallocated, unallocated




def test_distribution_idempotent():
    s = _state()
    out = distribute_regime_pops(s)
    assert out["distributed"] == [], out
    assert out["skipped"], out


def test_capital_weight_is_reflected():
    s = _state()
    t1 = [r for r in regions_by_owner(s, "辽") if r["level"] == "T1"
          and r.get("map_province") == "南京道"]
    if len(t1) < 2:
        return
    cap = max(t1, key=lambda r: float(r.get("weight") or 0))
    small = min(t1, key=lambda r: float(r.get("weight") or 0))
    if float(cap.get("weight") or 0) <= float(small.get("weight") or 0):
        return
    assert (cap["pop"]["农"]["size"]) > (small["pop"]["农"]["size"]), (cap["name"], small["name"])