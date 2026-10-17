# -*- coding: utf-8 -*-
"""度量衡统一转换引擎测试（M324 验收）。

⚠️ 本文件为**regenerated**：原文件于 2026-10-17 被 DSH 误删（清理 `sz/tests/`
时连带删除 antigravity 名下 M323/M324 的产物），本文件据
`_dev_tools/handover/tasks/M324-metrology-engine-and-reforms.json` 的描述与
`game/core/foundation/metrology.py` 的实际 API 重新编写，覆盖同样四类验收：
① 宋制↔公制双向转换；② 换算比可动态注入（不写死死数）；③ 三档体制收益/代价；
④ 变法落地（核销经费 / 参数切换 / 吏胥抗拒）。
"""
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "game") not in sys.path:
    sys.path.insert(0, str(_ROOT / "game"))

from core.foundation.metrology import (  # noqa: E402
    METROLOGY_SYSTEMS,
    SYSTEM_MODERN_METRIC,
    SYSTEM_SONG_TRADITIONAL,
    SYSTEM_SONG_UNIFIED,
    MetrologyEngine,
)


# =============================================================================
# 1. 四维双向转换
# =============================================================================
def test_volume_conversion():
    eng = MetrologyEngine()
    res = eng.to_metric(1, "volume", "shi")
    assert res["dimension"] == "volume"
    assert res["liters"] == pytest.approx(66.4)
    assert res["cubic_meters"] == pytest.approx(0.0664, abs=1e-4)
    assert eng.to_metric(1, "volume", "dou")["liters"] == pytest.approx(6.64)


def test_weight_conversion():
    eng = MetrologyEngine()
    assert eng.to_metric(1, "weight", "shi_weight")["kg"] == pytest.approx(76.8)
    assert eng.to_metric(1, "weight", "jin")["kg"] == pytest.approx(0.64)
    assert eng.to_metric(16, "weight", "liang")["kg"] == pytest.approx(0.64)


def test_length_conversion():
    eng = MetrologyEngine()
    assert eng.to_metric(1, "length", "zhang")["meters"] == pytest.approx(3.12)
    assert eng.to_metric(10, "length", "cun")["meters"] == pytest.approx(0.312)


def test_area_conversion():
    eng = MetrologyEngine()
    res = eng.to_metric(1, "area", "qing")
    assert res["sq_meters"] == pytest.approx(58400.0)
    assert res["hectares"] == pytest.approx(5.84)


def test_roundtrip_is_stable():
    eng = MetrologyEngine()
    for dim, unit in (("volume", "shi"), ("weight", "jin"),
                      ("length", "zhang"), ("area", "mu")):
        metric = eng.to_metric(3, dim, unit)
        key = {"volume": "liters", "weight": "kg",
               "length": "meters", "area": "sq_meters"}[dim]
        back = eng.from_metric(metric[key], dim, unit)
        assert back == pytest.approx(3.0, abs=1e-2), f"{dim}/{unit} 往返失真：{back}"


def test_unknown_dimension_returns_error():
    eng = MetrologyEngine()
    res = eng.to_metric(1, "bogus", "x")
    assert "error" in res


# =============================================================================
# 2. 换算比可动态注入（绝不写死单一死数）
# =============================================================================
def test_custom_specs_override_defaults():
    eng = MetrologyEngine({
        "volume": {"sheng_to_liter": 1.0, "dou_to_sheng": 10.0, "shi_to_sheng": 100.0},
    })
    assert eng.to_metric(1, "volume", "shi")["liters"] == pytest.approx(100.0)
    # 默认引擎不受影响（不是改全局）
    assert MetrologyEngine().to_metric(1, "volume", "shi")["liters"] == pytest.approx(66.4)


# =============================================================================
# 3. 三档体制的收益/代价单调
# =============================================================================
def test_system_effects_ladder():
    trad = MetrologyEngine.get_system_effects(SYSTEM_SONG_TRADITIONAL)
    unified = MetrologyEngine.get_system_effects(SYSTEM_SONG_UNIFIED)
    modern = MetrologyEngine.get_system_effects(SYSTEM_MODERN_METRIC)

    assert trad["manufacturing_mult"] == 1.0
    assert unified["manufacturing_mult"] == pytest.approx(1.10)
    assert modern["manufacturing_mult"] == pytest.approx(1.30)

    assert trad["reform_cost"] < unified["reform_cost"] < modern["reform_cost"]
    assert modern["tax_leakage_resistance"] > unified["tax_leakage_resistance"] > 0
    # 砸特权必有代价：体制越先进，吏胥抗拒与短期民怨越高
    assert modern["clerk_grip_resistance"] > unified["clerk_grip_resistance"] > 0
    assert modern["gentry_unrest_spike"] > unified["gentry_unrest_spike"] > 0


def test_active_system_defaults_to_traditional():
    assert MetrologyEngine.get_active_system(None) == SYSTEM_SONG_TRADITIONAL


# =============================================================================
# 4. 变法落地：核销经费 / 切换参数 / 吏胥抗拒
# =============================================================================
def _state(treasury=1_000_000):
    from application.game_init import new_game
    st = new_game("史实")
    st.treasury = treasury
    return st


def test_reform_rejects_unknown_system():
    ok, msg, _ = MetrologyEngine.apply_reform(_state(), "nope")
    assert ok is False and "未知" in msg


def test_reform_requires_treasury():
    st = _state(treasury=0)
    ok, msg, _ = MetrologyEngine.apply_reform(st, SYSTEM_MODERN_METRIC)
    assert ok is False
    assert st.treasury == 0, "经费不足时不得扣款"


def test_reform_applies_costs_and_switches_system():
    st = _state(treasury=1_000_000)
    grip_before = getattr(st, "clerk_grip", 0.3)
    ok, msg, effects = MetrologyEngine.apply_reform(st, SYSTEM_MODERN_METRIC)
    assert ok is True
    assert st.treasury == 1_000_000 - int(effects["reform_cost"])
    assert MetrologyEngine.get_active_system(st) == SYSTEM_MODERN_METRIC
    assert getattr(st, "clerk_grip") > grip_before, "改制须体现吏胥抗拒上升"

    from core.domains.administration import institution
    assert institution.get(st, "metrology_system_id", None) == pytest.approx(2.0)


def test_format_quantity_follows_active_system():
    assert "石" in MetrologyEngine.format_quantity(1000, "grain", SYSTEM_SONG_TRADITIONAL)
    metric_text = MetrologyEngine.format_quantity(1000, "grain", SYSTEM_MODERN_METRIC)
    assert "吨" in metric_text


def test_system_enum_complete():
    assert set(METROLOGY_SYSTEMS) == {
        SYSTEM_SONG_TRADITIONAL, SYSTEM_SONG_UNIFIED, SYSTEM_MODERN_METRIC}
