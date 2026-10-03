# -*- coding: utf-8 -*-
"""外邦（辽/西夏/吐蕃/大理）州府级**估算口径**定向回归（2026-10-02）。

用户裁定："夏跟大理就估算"。故本组用例守三件事：

1. **口径必须显式**：州府级数值一律带 `basis="estimate"`，
   **不得**与宋的 `historical` 混称、不得被当成"史实户口"；
2. **守恒**：`Σ(下辖州府) == 该道/区域的 district_base 总量`；
3. **缺失 ≠ 0**：查不到的州府返回 `None`，不回落 0。
"""
import os
import sys

import pytest

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from content.demography import (                                  # noqa: E402
    BASIS_SETTING, regime_prefecture_demog,
)
from content.geo_admin import REGIME_DEMOG, REGIME_PREFECTURES   # noqa: E402
from core.prefecture_entity import BASIS_HISTORICAL                # noqa: E402

_REGIMES = ("辽", "西夏", "吐蕃", "大理")


def test_every_regime_prefecture_carries_estimate_basis():
    """🔴 核心守卫：外邦州府级数值**必须**带 `basis` 且**不得**默认成宋的史料口径。

    设计文档 §验收断言：「史料缺失显示为『玩法设定/未有可靠总量』，
    不会显示为 0 或伪装成史料值」。
    """
    demog = regime_prefecture_demog()
    assert demog, "应产出外邦州府级数值"
    ok = {BASIS_SETTING, "historical_ub"}
    for name, row in demog.items():
        assert row.get("basis") in ok, f"{name} basis 非法：{row.get('basis')}"
        assert row.get("regime") in _REGIMES, f"{name} 未标所属政权"
        assert row.get("basis") != BASIS_HISTORICAL, \
            f"{name} 不得标成 historical——外邦无逐府崇宁户式史料"
        # 必须能回答「谁报告、依据是什么」
        assert row.get("source"), f"{name} 缺 source（无法回答依据是什么）"
        assert "is_historical" in row, f"{name} 缺 is_historical 标志"


def test_regimes_without_history_are_marked_setting():
    """西夏/吐蕃/大理**无可靠总量** ⇒ 必须 `setting` + 明说「未有可靠总量」。"""
    from content.demography import REGIME_SOURCE
    demog = regime_prefecture_demog()
    for r in ("西夏", "吐蕃", "大理"):
        rows = [v for v in demog.values() if v.get("regime") == r]
        assert rows, f"{r} 应有州府级数值"
        for row in rows:
            assert row["basis"] == BASIS_SETTING, f"{r} 应标 setting"
            assert row["is_historical"] is False
            assert "未有可靠总量" in row["source"] or "玩法设定" in row["source"], \
                f"{r} source 未说明是玩法设定：{row['source']}"
        assert "未有可靠总量" in REGIME_SOURCE[r]


def test_liao_is_historical_upper_bound_not_per_prefecture():
    """辽：父级总量**有史料上限**，但**逐府是分摊** ⇒ 标 `historical_ub` 且来源写明。"""
    demog = regime_prefecture_demog("辽")
    assert demog
    for name, row in demog.items():
        assert row["basis"] == "historical_ub"
        assert row["is_historical"] is True
        assert "辽史" in row["source"], "辽的 source 必须指明《辽史》"
        assert "分摊" in row["source"] or "按比例" in row["source"], \
            "辽的 source 必须写明逐道/逐府是分摊而非史料"


@pytest.mark.parametrize("regime", _REGIMES)
def test_children_sum_to_district_total(regime):
    """守恒：`Σ(下辖州府) == 该道/区域的 district_base 总量`。"""
    demog = regime_prefecture_demog(regime)
    base = REGIME_DEMOG[regime].get("district_base") or {}
    for district, totals in base.items():
        seats = (REGIME_PREFECTURES.get(regime) or {}).get(district) or []
        if not seats:
            continue
        got = sum(int((demog.get(s) or {}).get("households", 0) or 0) for s in seats)
        want = int(totals.get("households") or 0)
        assert got == want, f"{regime}/{district}: Σ州府 {got} vs 区域总量 {want}"


def test_regimes_have_prefecture_level_entities():
    """四个政权都**已有州府级实体清单**（不只是道/区域层）。"""
    for r in _REGIMES:
        tab = REGIME_PREFECTURES.get(r) or {}
        seats = [s for v in tab.values() for s in v]
        assert seats, f"{r} 无州府级实体"
        assert len(seats) == len(set(seats)), f"{r} 州府名重复：{seats}"


def test_unknown_seat_is_none_not_zero():
    """缺失 ≠ 0：未知政权/空参不抛，也不回落 0。"""
    assert regime_prefecture_demog("不存在的政权") == {}


# ====================================================== 口径锁定：辽 = 55 万户
def test_liao_households_aligned_to_history_550k():
    """🔴 口径锁定：辽五道户口合计 **550,000**，依《辽史·地理志》官方案语
    「各郡县户总计之**不过五十五万有奇**」（用户 2026-10-02 定）。

    原值 1,000,000 户为游戏设定值（约为史料上限的 1.82 倍），**已废弃**。
    本用例锁死该值，防止后续被无意改回。
    """
    base = REGIME_DEMOG["辽"]["district_base"]
    total = sum(int(v["households"]) for v in base.values())
    assert total == 550_000, f"辽户口合计应为 550,000（史料口径），实得 {total}"


@pytest.mark.parametrize("dim", ("population", "households", "land", "grain", "tax"))
def test_liao_dims_are_integers(dim):
    """缩放后各维须为**整数**（避免出现 137499.5 之类浮点，破坏 POP 挂载律）。"""
    base = REGIME_DEMOG["辽"]["district_base"]
    for dk, v in base.items():
        assert float(v[dim]).is_integer(), f"辽/{dk}/{dim} 非整数：{v[dim]}"
        assert v[dim] >= 0, f"辽/{dk}/{dim} 为负"


def test_liao_children_still_conserve_after_rescale():
    """改值后**守恒不得破坏**：`Σ(州府) == 道级总量`（逐维）。"""
    demog = regime_prefecture_demog("辽")
    base = REGIME_DEMOG["辽"]["district_base"]
    for district, totals in base.items():
        seats = (REGIME_PREFECTURES.get("辽") or {}).get(district) or []
        for dim in ("population", "households", "land", "grain"):
            got = sum(int((demog.get(s) or {}).get(dim, 0) or 0) for s in seats)
            want = int(totals.get(dim) or 0)
            assert abs(got - want) <= max(1, want * 0.001), \
                f"辽/{district}/{dim}: Σ州府 {got} vs 道级 {want}"

