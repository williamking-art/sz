# -*- coding: utf-8 -*-
"""民怨动力学（2026-10-22 新增）+ 奏报事实签阈值重标。

背景（实测，写进测试当判据）：
- 改前：民怨只会被治安支出单向抵减（按军费份额）⇒ 有军之地一年归零；
  **无实体军的 8 地永久冻结在初始值 ≤24**（利州路/广南西路 24 个月恒 24）。
- 结果：`situation_seeds`(>=30/85) 与 `local_agent_decisions`(>=30/45/60/85) 的档位
  **永不可达**；财政签「民怨>40 AND 府库<5万」两条件从不同时成立 ⇒ 结构性死签。
- 现在：民怨向**压力目标**（粮价/灾情/流民/治理）月度缓动 ⇒ 太平回落、危机可升到 50~90；
  财政签改按「府库不足 0.1 月本地月税」触发，民怨只作严重度修饰。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.ai.tiandao_facade import (  # noqa: E402
    SEED_FIN_TREASURY_TAX_MONTHS, SEED_FIN_UNREST, SEED_REFUGEE_POP_RATIO,
    SEED_UNREST_ALERT, TianDaoFacade,
)
from core.commands import new_game  # noqa: E402
from core.settlement import run_monthly_settlement  # noqa: E402
from core.settlement_econ import (  # noqa: E402
    UNREST_DRIFT_RATE, _unrest_pressure_target,
)


def _months(n, *, crisis=False, seed=20261021):
    random.seed(seed)
    s = new_game("史实")
    for _ in range(n):
        if crisis:
            s.disaster_severity = 5
            for p in s.prefectures.values():
                p["grain_price"] = 3.0
        run_monthly_settlement(s)
    return s


def _unrest(s):
    return {n: float(p.get("unrest") or 0) for n, p in s.prefectures.items()}


# ---------------------------------------------------------------- 压力目标
def test_pressure_target_scales_with_readings():
    """压力目标随粮价/灾情/治理单调上升；太平年景接近低位。"""
    s = new_game("史实")
    p = dict(s.prefectures["京畿路"])
    p["grain_price"] = 1.0
    low = _unrest_pressure_target(s, p)
    p2 = dict(p, grain_price=3.0)
    assert _unrest_pressure_target(s, p2) > low
    s.disaster_severity = 5
    assert _unrest_pressure_target(s, p2) > _unrest_pressure_target(s, p) + 30
    p3 = dict(p2, govern=20)
    assert _unrest_pressure_target(s, p3) > _unrest_pressure_target(s, p2)


def test_pressure_target_needs_at_least_one_reading():
    """一项读数都取不到 ⇒ None（不动作，**不当作 0 压力**）。"""
    s = SimpleNamespace(grain_price=None, disaster_severity=None)
    assert _unrest_pressure_target(s, {}) is None


def test_pressure_target_is_bounded():
    s = new_game("史实")
    s.disaster_severity = 5
    p = {"grain_price": 99.0, "govern": 0.0, "refugees": 10 ** 9, "population": 1}
    assert 0.0 <= _unrest_pressure_target(s, p) <= 100.0


# ---------------------------------------------------------------- 月度动力学
def test_peaceful_year_pulls_unrest_down():
    """太平 12 月：民怨整体回落（多数地趋近低位），且恒在 [0,100]。"""
    s = _months(12)
    vals = _unrest(s)
    assert max(vals.values()) <= 100.0 and min(vals.values()) >= 0.0
    s0 = _unrest(new_game("史实"))
    assert sum(vals.values()) < sum(s0.values()), "太平年景民怨应整体下降"


def test_frozen_routes_are_unfrozen():
    """改前「无实体军 ⇒ 民怨永久冻结」的 8 地，现在必须有变化。"""
    s = _months(6)
    units = {u.station for u in s.army_units}
    frozen = [n for n in s.prefectures if n not in units]
    assert frozen, "本局应存在无实体军的地"
    base = _unrest(new_game("史实"))
    moved = [n for n in frozen if abs(_unrest(s)[n] - base[n]) > 1e-9]
    assert len(moved) == len(frozen), f"仍未解冻: {set(frozen) - set(moved)}"


def test_crisis_raises_unrest_above_content_tiers():
    """持续危机（灾 5 + 粮价×3）能把民怨推到 30/45 档以上（内容档位不再死）。"""
    s = _months(12, crisis=True)
    vals = sorted(_unrest(s).values(), reverse=True)
    assert vals[0] >= 45, f"危机 12 月最高民怨仅 {vals[0]:.1f}"
    assert sum(1 for v in vals if v >= 30) >= 5


def test_drift_rate_is_gradual_not_jump():
    """单月变化不超过 RATE×100（缓动，不跳变）。"""
    random.seed(7)
    s = new_game("史实")
    s.disaster_severity = 5
    for p in s.prefectures.values():
        p["grain_price"] = 3.0
    before = _unrest(s)
    run_monthly_settlement(s)
    after = _unrest(s)
    for n in before:
        assert abs(after[n] - before[n]) <= UNREST_DRIFT_RATE * 100 + 1e-6, n


def test_unrest_dynamics_deterministic():
    a = _unrest(_months(4))
    b = _unrest(_months(4))
    assert a == b, "同种子必须逐地一致（确定性回放）"


# ---------------------------------------------------------------- 奏报签可达性
def _seeds(s, limit=5):
    return [x["seed_id"].rsplit("_", 1)[-1] for x in
            TianDaoFacade.scan_memorial_seeds(s, limit=limit)]


def test_routine_seed_when_all_calm():
    s = new_game("史实")
    for p in s.prefectures.values():
        p["unrest"] = 0.0
        p["local_treasury"] = int(p.get("monthly_tax", 1) or 1) * 10
        p["refugees"] = 0
    assert _seeds(s) == ["gov"]          # routine 的 id 后缀也是 gov，但前缀是 routine
    assert TianDaoFacade.scan_memorial_seeds(s, limit=1)[0]["seed_id"].endswith("routine_gov")


def test_finance_seed_fires_on_deep_depletion():
    """府库不足 0.1 月月税 ⇒ 出财政签；民怨低也照样出（不再是 AND 门槛）。"""
    s = new_game("史实")
    p = s.prefectures["京畿路"]
    p["monthly_tax"] = 1_000_000
    p["local_treasury"] = 50_000            # 0.05 月 ⇒ 深度 0.95
    p["unrest"] = 0.0
    ids = [x["seed_id"] for x in TianDaoFacade.scan_memorial_seeds(s, limit=3)]
    assert any(x.endswith("_fin") for x in ids), ids


def test_finance_seed_silent_when_treasury_healthy():
    s = new_game("史实")
    for p in s.prefectures.values():
        p["monthly_tax"] = 1_000_000
        p["local_treasury"] = 900_000       # 0.9 月 ⇒ 未达见底线
        p["unrest"] = 0.0
        p["refugees"] = 0
    ids = [x["seed_id"] for x in TianDaoFacade.scan_memorial_seeds(s, limit=3)]
    assert not any(x.endswith("_fin") for x in ids), ids


def test_finance_seed_ignores_route_without_tax_reading():
    """缺月税读数 ⇒ 该地不计（缺失≠0，不臆造"见底"）。"""
    s = new_game("史实")
    for p in s.prefectures.values():
        p.pop("monthly_tax", None)
        p["local_treasury"] = 1
        p["unrest"] = 0.0
        p["refugees"] = 0
    ids = [x["seed_id"] for x in TianDaoFacade.scan_memorial_seeds(s, limit=3)]
    assert not any(x.endswith("_fin") for x in ids), ids


def test_military_seed_uses_population_ratio():
    """流民按**占本地人口比例**判：占比 0.4% 以上触发；缺人口读数不触发。"""
    s = new_game("史实")
    for p in s.prefectures.values():
        p["monthly_tax"] = 1_000_000
        p["local_treasury"] = 900_000
        p["unrest"] = 0.0
        p["population"] = 1_000_000
        p["refugees"] = 0
    target = s.prefectures["京畿路"]
    target["refugees"] = int(1_000_000 * SEED_REFUGEE_POP_RATIO) + 1
    ids = [x["seed_id"] for x in TianDaoFacade.scan_memorial_seeds(s, limit=3)]
    assert any(x.endswith("_mil") for x in ids), ids

    s2 = new_game("史实")
    for p in s2.prefectures.values():
        p["monthly_tax"] = 1_000_000
        p["local_treasury"] = 900_000
        p["unrest"] = 0.0
        p["refugees"] = 999_999
        p.pop("population", None)
    ids2 = [x["seed_id"] for x in TianDaoFacade.scan_memorial_seeds(s2, limit=3)]
    assert not any(x.endswith("_mil") for x in ids2), ids2


def test_governance_seed_fires_only_when_unrest_high():
    """民怨高但府库尚可 ⇒ 政务签（督责监司），且门槛 SEED_UNREST_ALERT 可达。"""
    s = new_game("史实")
    for p in s.prefectures.values():
        p["monthly_tax"] = 1_000_000
        p["local_treasury"] = 900_000
        p["refugees"] = 0
        p["unrest"] = 0.0
    s.prefectures["两浙路"]["unrest"] = SEED_UNREST_ALERT + 5
    ids = [x["seed_id"] for x in TianDaoFacade.scan_memorial_seeds(s, limit=3)]
    assert any(x.endswith("_gov") and "routine" not in x for x in ids), ids
