# -*- coding: utf-8 -*-
"""M34-④ 财政面板读数口径统一（D1=甲 / D2=保留为诊断 / D3=显式命名）契约回归。

依据：《宋代财政流向_上供留州与贪吏做账系统设计终稿_V1.3.md》§5.3 与
`_dev_tools/game-docs/specs/economy/读数口径统一_开工门台账.md` §3-§4
（2026-10-11 用户裁决：**甲＋乙**，D2 保留诊断、D3 改名）。

背景：结算侧自 P1 起田赋折色走**新模型**（应征＝全额税基×征收率，无 arrival 折扣），
而面板 `finance_readout` / `region_brief` 仍走**旧径**（arrival 乘进税基）——
两侧口径分叉：面板 `tax_color` 少算 ≈1/arrival 倍，年应征还用 `/arrival×12` 反推。

本文件覆盖（不写前端源码文本断言，只断言派生契约）：
1. `tax_color` ≡ 新模型应征（`calc_land_tax_channels().assessed_total`），旧径单列 `tax_color_legacy`；
2. 年应征 = 月应征×12（**禁**旧径 `/arrival×12` 反推式）；
3. 乙组新增只读字段齐备且缺失语义为 `None`（未月结不得伪造 0/1.0）；
4. 月结写本月快照 `statistics["land_tax_last"]`，与 `_settle_land_tax_color` 返回逐项对账；
5. 州路简报逐路税与面板**同源**（`tax_month` ≡ 面板 `tax_color`）；
6. 比率家族 scope 串明写"诊断口径"（防再被当成精确到账率）；
7. 只读纪律：`finance_readout()` / `build_region_brief()` 不改动任何账本。
"""
import copy
import sys

sys.path.insert(0, r'D:/codebuddy/sz/game')

import pytest

from core.commands import new_game
from core.region_brief import build_region_brief
from core.settlement_finance import _settle_land_tax_color

# M34-④ 新增字段（口径契约表面积；既有字段不得被删，另见 test_finance_readout_scope）
_M34_FIELDS = ("tax_color_legacy", "assessed_total", "collection_rate_avg",
               "transfer_rate_avg", "land_tax_last", "land_tax_cum",
               "legacy_arrival_rate")


def _snapshot(s):
    return {
        "treasury": int(getattr(s, "treasury", 0) or 0),
        "stats": copy.deepcopy(dict(s.statistics)),
        "prefs": copy.deepcopy(s.prefectures),
    }


# ---------------- 1) 面板主口径切换（甲①） ----------------

def test_tax_color_is_new_model_assessed():
    """`tax_color` 必须是新模型**应征**；旧径值单列保留（兼容/回归锚）。"""
    s = new_game()
    out = s.finance_readout()
    ch = s.calc_land_tax_channels()
    assert out["tax_color"] == ch["assessed_total"] == out["assessed_total"]
    assert out["tax_color_legacy"] == pytest.approx(s.calc_monthly_tax_income()[0], abs=1.0)
    # 新径无 arrival 折扣 → 应征 ≥ 旧径到库（arrival<1 时严格大于）
    assert out["tax_color"] >= out["tax_color_legacy"]
    # D3：旧口径显式命名（新键与旧键同值，旧键保留兼容一版）
    assert out["legacy_arrival_rate"] == out["mechanism_arrival_rate"]


# ---------------- 2) 年应征去反推（甲②） ----------------

def test_annual_assessed_has_no_arrival_reverse_derivation():
    s = new_game()
    out = s.finance_readout()
    arr = out["mechanism_arrival_rate"]
    assert arr and arr > 0
    new = out["tax_color"] * 12.0
    old = out["tax_color"] / arr * 12.0            # 旧径反推式（本次明令禁用）
    if arr < 0.999:
        assert new < old, "旧反推式会放大 1/arrival，新式必须更小"
    salt_annual = out["salt_coin"] / arr * 12.0    # 盐课仍走旧径（反推有效）
    assert out["nominal_annual_full"] == pytest.approx(
        out["nominal_annual"] + new + salt_annual, rel=1e-9, abs=1e-6)


# ---------------- 3) 乙组字段齐备 + 缺失语义 ----------------

def test_m34_new_readonly_fields_present():
    s = new_game()
    out = s.finance_readout()
    missing = [k for k in _M34_FIELDS if k not in out]
    assert not missing, f"M34-④ 缺字段：{missing}"
    # 未月结：本月快照**不得**伪造为 0（缺失即 None）；累计三分尚未发生 → 0
    assert out["land_tax_last"] is None
    assert out["land_tax_cum"] == {"assessed": 0, "collected": 0,
                                   "central": 0, "local": 0, "diverted": 0}
    assert 0.0 < out["collection_rate_avg"] <= 1.0
    assert 0.0 < out["transfer_rate_avg"] <= 1.0


def test_last_snapshot_is_defensive_copy():
    """`land_tax_last` 必须是快照拷贝——调用方改动不得污染 `statistics`。"""
    s = new_game()
    _settle_land_tax_color(s, [])
    out = s.finance_readout()
    out["land_tax_last"]["collected"] = -1
    assert s.finance_readout()["land_tax_last"]["collected"] >= 0


# ---------------- 4) 月结写本月快照（乙） ----------------

def test_settlement_writes_last_month_snapshot():
    s = new_game()
    ret = _settle_land_tax_color(s, [])
    out = s.finance_readout()
    last = out["land_tax_last"]
    assert isinstance(last, dict)
    for k in ("assessed", "collected", "central", "local", "diverted"):
        assert last[k] == ret[k], f"快照 {k} 与结算返回不一致"
    assert last["central"] + last["local"] + last["diverted"] == last["collected"]
    assert last["turn"] == int(getattr(s, "turn", 0) or 0)
    # 累计三分与快照同源（同一口径单点）
    cum = out["land_tax_cum"]
    for k in ("assessed", "collected", "central", "local", "diverted"):
        assert cum[k] == ret[k]


# ---------------- 5) 州路简报同源（甲① 逐路） ----------------

def test_region_brief_tax_same_caliber_as_panel():
    s = new_game()
    b = build_region_brief(s)
    out = s.finance_readout()
    ch = s.calc_land_tax_channels()
    assert abs(b["nation"]["tax_month"] - out["tax_color"]) < 0.01, \
        "州路简报全国税与面板 tax_color 必须同源（新模型应征）"
    by_route = {r["name"]: r["tax_month"] for r in b["routes"]}
    for rk, row in ch["by_route"].items():
        assert by_route.get(rk) == pytest.approx(row["assessed"], abs=0.01), \
            f"{rk} 逐路税必须等于新模型应征"
    # 逐路求和 = 权威值（同源后差额应为 0）
    assert b["nation"]["tax_month_routes_sum"] == pytest.approx(
        b["nation"]["tax_month"], abs=0.01)


# ---------------- 6) 诊断口径标注（D2） ----------------

def test_ratio_scope_strings_declare_diagnostic():
    out = new_game().finance_readout()
    for key in ("arrival_ratio_scope_taxed", "arrival_ratio_scope_full"):
        s = out[key]
        assert "诊断口径" in s, f"{key} 必须明写诊断口径"
        assert "二税折色" in s and "盐课" in s
    assert "工商" in out["arrival_ratio_scope_taxed"]
    assert "市舶" in out["arrival_ratio_scope_full"]


# ---------------- 7) 只读纪律 ----------------

def test_readouts_are_readonly_after_m34():
    s = new_game()
    before = _snapshot(s)
    s.finance_readout()
    build_region_brief(s)
    assert _snapshot(s) == before, "读数必须只读：不得改动国库/statistics/州县账本"
