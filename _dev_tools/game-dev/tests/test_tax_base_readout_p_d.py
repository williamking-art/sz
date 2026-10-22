# -*- coding: utf-8 -*-
"""P-D 首批 · 应税产值分解（**只读**）定向回归（规格 `specs/economy/produce-space-price`）

锁定：
1. **覆盖诚实**：只有「有静态年产量（治所 yields）」的维参与计算；成品维（绸/布等）
   无年产量源 ⇒ 必须落在 `no_yield_dims`，**不是 0 产、不算进产值**；
2. **缺失 ≠ 0**：有产量但无基准价的维（金/银/麦 类）进 `undefined_dims`，不记 0；
3. **只读**：跑完后 `prefectures[*].seats` / `resources` / `treasury` / `tax_breakdown` 逐字不变；
4. **读数可观察**：`readout_hub` 里有 `tax_base_value`，`display` 非 undefined，`drill_down` 是 dict
   且含按品目明细。
"""
import copy
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core import commands  # noqa: E402
from core.domains.economy import readout_hub as rh  # noqa: E402
from core.domains.economy.tax_base_readout import (  # noqa: E402
    readout_tax_base, survey_tax_base,
)


def _state():
    return commands.new_game()


def test_survey_uses_only_dims_with_yields_and_marks_rest():
    rep = survey_tax_base(_state())
    assert rep["readonly"] is True
    assert rep["total_value"] is not None and rep["total_value"] > 0
    # 实测只有 9 个原料维有 yields；成品维（绸/布）必须进 no_yield_dims
    assert rep["dims_with_yield"] >= 5
    assert "绸" in rep["no_yield_dims"] and "布" in rep["no_yield_dims"]
    # 有产量的维若都可就价，则 undefined 应为空；若出现，必须是"有产量但无价"
    assert set(rep["undefined_dims"]).isdisjoint(rep["no_yield_dims"])


def test_unit_conversion_wen_to_guan():
    """单位口径：对外是**贯**，内部是**文**；两者恒差 1000 倍（宋制 1 贯=1000 文）。"""
    from core.domains.economy.tax_base_readout import WEN_PER_GUAN

    rep = survey_tax_base(_state())
    assert WEN_PER_GUAN == 1000.0
    assert rep["total_wen"] == pytest.approx(rep["total_value"] * 1000.0, rel=1e-6)
    # 量级护栏：年应税产值（原料口径）应在「万～千万贯」区间；
    # 若不换算直接当贯，会大 1000 倍（首版实测 7.6e10）——此断言专抓该回归。
    assert 1e4 < rep["total_value"] < 1e9, rep["total_value"]


def test_category_aggregation_closes():
    """按品目合计 == 总和（逐值可加：非 None 品目之和 == total_value）。"""
    rep = survey_tax_base(_state())
    parts = [v["value"] for v in rep["by_category"].values() if v["value"] is not None]
    assert abs(sum(parts) - rep["total_value"]) < 0.01


def test_readonly_no_state_mutation():
    s = _state()
    before_seats = copy.deepcopy({r: p.get("seats") for r, p in s.prefectures.items()})
    before_res = copy.deepcopy(getattr(s, "resources", None))
    before_treasury = copy.deepcopy(getattr(s, "treasury", None))
    before_tax = copy.deepcopy(getattr(s, "tax_breakdown", None))
    before_stats = copy.deepcopy(getattr(s, "statistics", None))

    survey_tax_base(s)
    readout_tax_base(s)

    assert {r: p.get("seats") for r, p in s.prefectures.items()} == before_seats
    assert getattr(s, "resources", None) == before_res
    assert getattr(s, "treasury", None) == before_treasury
    assert getattr(s, "tax_breakdown", None) == before_tax
    assert getattr(s, "statistics", None) == before_stats


def test_readout_is_registered_and_has_drill_down():
    s = _state()
    keys = [r["key"] for r in rh.READOUTS]
    assert "tax_base_value" in keys
    row = rh.collect(s, keys=["tax_base_value"])["readouts"]["tax_base_value"]
    assert row["value"] is not None
    assert row["display"] != "undefined"
    dd = row["drill_down"]
    assert isinstance(dd, dict) and "按品目" in dd
    assert isinstance(dd["按品目"], dict) and dd["按品目"]


def test_readout_undefined_not_zero_when_no_price_data(monkeypatch):
    """无任何可定价维时：value=None + display=undefined（绝不显示 0）。"""
    import core.domains.economy.tax_base_readout as tbr

    monkeypatch.setattr(tbr, "_yield_by_dim", lambda: {})
    value, reason, drill = tbr.readout_tax_base(_state())
    assert value is None
    assert reason
    assert isinstance(drill, dict)
