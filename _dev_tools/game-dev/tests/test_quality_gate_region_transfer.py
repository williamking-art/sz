# -*- coding: utf-8 -*-
"""质量放行门 · P5 归属变更（2026-10-19）。

设计稿 §7：`transfer_regions` **只改 owner 与 territory**；
人口/土地/建筑逐字不变；政权字段（treasury/armies/tech/attitude）不随地域走。

本门钉住：
1. T2 级联：辽 南京道 → 金 ⇒ 1 个 T2 + 3 个 T1 同属金；
2. T1 独立改属：平州 → 金 ⇒ 父节点换成金名下 T2，不变量仍空；
3. **地域逐字不变**：转移前后 T1 的 `pop` JSON 完全相等；
4. **政权字段不随地域走**：辽 treasury 不变；新建的金 treasury=0（不继承）；
5. territory 同步（辽去掉、金加上）；
6. `revert_change` 后 owner 完全复原（逐 region 比较）；
7. 转移后 `verify_region_invariants` 为空；`unallocated_provinces` 显式登记被割走州府的省；
8. overlay `owner_changed` 由 0 变正（可视化能感知）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.domains.diplomacy.map_overlay import map_overlay  # noqa: E402
from core.domains.diplomacy.regime_transfer import (  # noqa: E402
    regime_territory, revert_change, transfer_regions)
from core.foundation.ledger.region_registry import (  # noqa: E402
    regions_by_owner, unallocated_provinces, verify_region_invariants)


def _state():
    from core.commands import new_game

    return new_game()


def _owners(s):
    return {rid: (r or {}).get("owner") for rid, r in s.regions.items()}


def test_t2_transfer_cascades():
    s = _state()
    out = transfer_regions(s, "辽", "金", ["辽_p0"], create_to=True, reason="测试占领")
    assert out["ok"], out
    owners = [rid for rid in out["moved"]]
    assert len(owners) == 4, owners  # 1 T2 + 3 T1
    for rid in owners:
        assert s.regions[rid]["owner"] == "金", rid
    assert len([r for r in regions_by_owner(s, "金") if r["level"] == "T1"]) == 3


def test_single_t1_transfer_reparents():
    s = _state()
    rid = next(r for r in regions_by_owner(s, "辽")
               if r["level"] == "T1" and r["name"] == "平州")
    out = transfer_regions(s, "辽", "金", [rid["region_id"]], create_to=True, reason="单块")
    assert out["ok"], out
    r = s.regions[rid["region_id"]]
    assert r["owner"] == "金"
    parent = s.regions[str(r["parent"])]
    assert parent["owner"] == "金", parent
    assert verify_region_invariants(s) == [], verify_region_invariants(s)[:3]


def test_region_data_unchanged():
    s = _state()
    t1 = [r for r in regions_by_owner(s, "辽") if r["level"] == "T1"]
    before = {r["region_id"]: json.dumps(r.get("pop"), sort_keys=True) for r in t1}
    # 纯归属变更不碰数据（打残/掠夺是占领的另一副作用，单测）
    transfer_regions(s, "辽", "金", ["辽_p0"], create_to=True, devastate=False, reason="数据不变")
    after = {rid: json.dumps(s.regions[rid].get("pop"), sort_keys=True) for rid in before}
    assert before == after, "人口不得因改属而变化"


def test_regime_fields_do_not_follow():
    s = _state()
    before = s.external_regimes["辽"].get("treasury")
    out = transfer_regions(s, "辽", "金", ["辽_p0"], create_to=True, reason="政权字段")
    assert s.external_regimes["辽"].get("treasury") == before   # 源政权不因失地而变化
    loot = int(((out.get("damage") or {}).get("loot") or 0))
    # 新建政权**不继承**辽的 treasury：只有本次掠夺所得
    assert int(s.external_regimes["金"].get("treasury") or 0) == loot


def test_territory_updated():
    s = _state()
    before = set(regime_territory(s, "辽"))
    transfer_regions(s, "辽", "金", ["辽_p0"], create_to=True, reason="territory")
    after = set(regime_territory(s, "辽"))
    jin = set(regime_territory(s, "金"))
    assert "辽_p0" not in after, after
    assert "辽_p0" in jin and "辽_p0_析津府" in jin, jin
    assert after < before


def test_revert_restores_owners():
    s = _state()
    before = _owners(s)
    out = transfer_regions(s, "辽", "金", ["辽_p0"], create_to=True, reason="和议")
    assert out["ok"]
    assert _owners(s) != before
    rev = revert_change(s, out["change_id"])
    assert rev["ok"], rev
    assert _owners(s) == before, "撤销后 owner 必须逐块复原"


def test_invariants_and_unallocated_after_transfer():
    s = _state()
    transfer_regions(s, "辽", "金", ["辽_p0"], create_to=True, reason="不变量")
    assert verify_region_invariants(s) == []
    un = unallocated_provinces(s)
    assert any(u["owner"] == "辽" and u["province"] == "南京道" for u in un), un


def test_overlay_detects_owner_change():
    s = _state()
    assert sum(1 for r in map_overlay(s) if r["owner_changed"]) == 0
    transfer_regions(s, "辽", "金", ["辽_p0"], create_to=True, reason="overlay")
    changed = [r for r in map_overlay(s) if r["owner_changed"]]
    assert changed, "占领后 overlay 必须报 owner_changed"
    assert any(r["owner"] == "金" for r in changed)

def test_placeholders_absent_at_start():
    """金开局**不存在**（只是史实占位）；不得预置进 external_regimes。"""
    from core.domains.diplomacy.regime_transfer import PLACEHOLDER_REGIMES, is_placeholder_regime

    s = _state()
    assert "金" in PLACEHOLDER_REGIMES
    assert is_placeholder_regime("金")
    assert "金" not in (s.external_regimes or {}), "金不得在开局政权表里"


def test_transfer_to_unknown_regime_is_rejected():
    """目标政权不存在 ⇒ 默认拒绝（未登场政权必须显式 create_to=True 占位）。"""
    s = _state()
    out = transfer_regions(s, "辽", "西夏2", ["辽_p0"], reason="不存在")
    assert out["ok"] is False
    assert "create_to" in out["reason"], out
    assert s.regions["辽_p0"]["owner"] == "辽", "拒绝时不得改动"


def test_created_placeholder_marked():
    """显式占位建政权 ⇒ 标记 placeholder=True（政权字段从零起）。"""
    s = _state()
    out = transfer_regions(s, "辽", "金", ["辽_p0"], create_to=True, reason="占位")
    assert out["ok"], out
    jin = s.external_regimes["金"]
    assert jin.get("placeholder") is True, jin
    assert int(jin.get("treasury") or 0) >= 0 and "population" in jin