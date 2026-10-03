# -*- coding: utf-8 -*-
"""`finance_readout()` **会计指标口径**回归（P2-2 会计指标口径核对，2026-09-19）。

背景（实证）：界面曾显示「到账率 128.2%」。成因**不是**重复计入/单位错/累计↔月度混用，
而是**口径/标签不符**：`monthly_in` 是**五项**月度应征（工商·役钱·市舶·二税折色·盐课），
而 `nominal_annual` 只是**三项**账面（工商·役钱·市舶），分母缺了二税折色与盐课——
开局这两项合计 1,578,554 贯/月（占分子 **50.9%**），故旧前端自算的
`monthly_in / (nominal_annual/12) = 3,098,770 ÷ 2,416,672 = 128.2%`；
配套的 `diff = nominal_annual/12 − monthly_in = −682,098/月` 被面板当成「隐漏与拖欠」
输出 → **负的隐漏**，自相矛盾。

本文件是它的**派生契约**回归（按审查基准 §5.1：**不写前端源码文本断言**）：
只断言字段存在、恒等式成立、逐项可加、缺失语义为 `None`、只读纪律与结算侧一致性。
覆盖科目说明的"明写不含二税折色与盐课"也在此断言（属于后端下发的**口径契约**，
不是前端文案）。

方法：无 httpx（本机）→ 直调 `GameState("史实").finance_readout()`（范例
`test_readouts_endpoint.py`）；结算侧直调 `core.settlement_finance._settle_finance`
并解析 `[财政]` 日志里的实收额。
"""
import math
import os
import re
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402

# 本文件新增的派生字段（口径契约的表面积）
_NEW_FIELDS = (
    "nominal_annual_full",
    "monthly_in_taxed",
    "arrival_ratio_taxed",
    "arrival_ratio_full",
    "arrival_ratio_cross_scope",
    "mechanism_arrival_rate",
    "arrival_ratio_scope",
    "arrival_ratio_scope_taxed",
    "arrival_ratio_scope_full",
)
# P2-2 之前既有的字段：口径整改**不得**动它们的取值/语义（抽查关键几项）
_LEGACY_FIELDS = ("nominal_annual", "monthly_in", "commerce", "poll", "maritime",
                  "tax_color", "salt_coin")


@pytest.fixture()
def state():
    return GameState("史实")


@pytest.fixture()
def readout(state):
    return state.finance_readout()


def _pop_total(s):
    """ΣPOP（六类 size 之和）——只读纪律用。"""
    total = 0
    for p in s.prefectures.values():
        for v in (p.get("pops") or {}).values():
            total += int(v.get("size", 0) or 0)
    return total


# ------------------------------------------------------------
# 1) 字段存在 + 恒等式成立（派生契约，不是硬编码值）
# ------------------------------------------------------------
def test_new_derived_fields_exist(readout):
    missing = [k for k in _NEW_FIELDS if k not in readout]
    assert not missing, f"finance_readout 缺 P2-2 派生字段：{missing}"
    for k in _LEGACY_FIELDS:
        assert k in readout, f"既有字段 {k} 不得被整改删掉"


def test_arrival_ratio_taxed_identity(readout):
    """三税口径：`arrival_ratio_taxed` ≡ 三税应征 ÷ (三税账面年额 ÷ 12)，且分子分母同科目。"""
    den = readout["nominal_annual"] / 12
    assert den > 0
    expected = readout["monthly_in_taxed"] / den
    assert abs(readout["arrival_ratio_taxed"] - expected) < 1e-9
    # 三税分子＝工商+役钱+市舶（与面板分项同源，可逐项加总复核）
    parts = readout["commerce"] + readout["poll"] + readout["maritime"]
    assert abs(readout["monthly_in_taxed"] - parts) < 1e-6


def test_arrival_ratio_full_identity(readout):
    """五科目口径：`arrival_ratio_full` ≡ monthly_in ÷ (nominal_annual_full ÷ 12)。"""
    den = readout["nominal_annual_full"] / 12
    assert den > 0
    assert abs(readout["arrival_ratio_full"] - readout["monthly_in"] / den) < 1e-9


def test_cross_scope_ratio_is_the_old_panel_formula(readout):
    """旧面板自算值（跨口径：五科目分子 ÷ 三税分母）必须仍可复现——它是本缺陷的凭证。

    注意：**不断言它 ≤1**（正是因为它可以 >1 才暴露了分母缺项），也不断言具体数值。
    """
    den = readout["nominal_annual"] / 12
    assert abs(readout["arrival_ratio_cross_scope"] - readout["monthly_in"] / den) < 1e-9
    # 跨口径值 = 三税口径值 × (monthly_in / monthly_in_taxed)：两者不是同一个量
    assert readout["arrival_ratio_cross_scope"] != readout["arrival_ratio_taxed"]


# ------------------------------------------------------------
# 2) nominal_annual_full：五项全口径，**逐项加总**（不是硬编码常数）
# ------------------------------------------------------------
def test_nominal_annual_full_is_five_item_sum(readout):
    arr = readout["mechanism_arrival_rate"]
    assert arr is not None and arr > 0
    # 二税折色 / 盐课月额已乘 arrival → ÷ arrival × 12 即年度应征额（应征公式反推）
    tax_color_annual = readout["tax_color"] / arr * 12
    salt_annual = readout["salt_coin"] / arr * 12
    expected = readout["nominal_annual"] + tax_color_annual + salt_annual
    assert readout["nominal_annual_full"] == pytest.approx(expected, rel=1e-9, abs=1e-6)
    # 全口径**必须**大于三项账面（差额正是二税折色与盐课）
    assert readout["nominal_annual_full"] > readout["nominal_annual"]
    assert (readout["nominal_annual_full"] - readout["nominal_annual"]) == pytest.approx(
        tax_color_annual + salt_annual, rel=1e-9, abs=1e-6)
    # 既有字段语义不得被改写：nominal_annual 仍是"三项账面"（＝工商+役钱+市舶年额）
    assert readout["nominal_annual"] > 0


def test_nominal_annual_full_grows_with_a_new_subject(readout, state):
    """反硬编码：改动**输入**（盐课基准相关输入：盐产能）后全口径随之变化。"""
    before_full = readout["nominal_annual_full"]
    before_legacy = readout["nominal_annual"]
    # 直接放大盐产能（yields.salt 正是 calc_salt_coin 的输入），不改任何常量
    for p in state.prefectures.values():
        p.setdefault("yields", {})
        p["yields"]["salt"] = float(p["yields"].get("salt", 0) or 0) * 2.0
    after = state.finance_readout()
    assert after["nominal_annual_full"] > before_full
    # 盐课不进 nominal_annual（三项账面）——这正是旧比值 >100% 的原因
    assert after["nominal_annual"] == before_legacy


# ------------------------------------------------------------
# 3) 覆盖科目说明：明写"不含二税折色与盐课"
# ------------------------------------------------------------
def test_scope_strings_state_which_subjects_are_covered(readout):
    for key in ("arrival_ratio_scope", "arrival_ratio_scope_taxed",
                "arrival_ratio_scope_full"):
        s = readout[key]
        assert isinstance(s, str) and s.strip(), f"{key} 必须是非空中文说明串"
        assert "二税折色" in s and "盐课" in s, f"{key} 未明写科目覆盖：{s}"
    assert "工商" in readout["arrival_ratio_scope_taxed"]
    assert "市舶" in readout["arrival_ratio_scope_taxed"]


# ------------------------------------------------------------
# 4) 边界与缺失语义：正有限值或 None；**绝不断言 ≤1**；**绝不断言等于某硬编码值**
# ------------------------------------------------------------
def test_ratios_are_finite_or_none(readout):
    for key in ("arrival_ratio_taxed", "arrival_ratio_full",
                "arrival_ratio_cross_scope", "mechanism_arrival_rate"):
        v = readout[key]
        if v is not None:
            assert isinstance(v, float) and math.isfinite(v), f"{key} 非有限值：{v!r}"


def test_ratios_are_none_when_denominator_missing(monkeypatch, state):
    """分母为 0 → None（缺失语义）；**不得**回落 0 或 1.0 假装无事。

    构造方式：把三项账面年额的三条来源全部归零（工商产值 / 年役钱基准 / 市舶抽解），
    于是 `nominal_annual == 0` 而 `monthly_in > 0`（二税折色与盐课仍在）——
    走的是**真实分支**，不是复刻一份算法。
    """
    import core.game_state_econ as gse

    monkeypatch.setattr(gse, "ANNUAL_TAX_BASE", 0, raising=True)
    monkeypatch.setattr(gse, "POLL_TAX_NOMINAL_SHARE", 0.0, raising=True)
    monkeypatch.setattr(state, "calc_commerce", lambda: 0.0)
    monkeypatch.setattr(state, "maritime", {**state.maritime, "open": False})

    out = state.finance_readout()
    assert out["nominal_annual"] == 0, "构造失败：三项账面未归零"
    assert out["arrival_ratio_taxed"] is None, "分母缺失必须 None（不得回落 0/1）"
    assert out["arrival_ratio_cross_scope"] is None
    assert out["arrival_ratio_taxed"] != 0 and out["arrival_ratio_taxed"] != 1.0
    # 五科目口径分母仍在（二税折色、盐课未归零）→ 仍给出有限值
    assert out["nominal_annual_full"] > 0
    assert out["arrival_ratio_full"] is not None and math.isfinite(out["arrival_ratio_full"])


def test_zero_subject_contributes_zero(state):
    """某科目为 0 → 该项贡献 0（不做无意义反推、不产生 NaN/Inf）。"""
    for p in state.prefectures.values():
        p.setdefault("yields", {})
        p["yields"]["salt"] = 0.0
    out = state.finance_readout()
    assert out["salt_coin"] == 0 or out["salt_coin"] == 0.0
    # 盐课为 0 时反推项必须是 0（不允许 0/arr 之外的意外）
    arr = out["mechanism_arrival_rate"]
    assert arr and arr > 0
    expected_full = out["nominal_annual"] + out["tax_color"] / arr * 12 + 0.0
    assert out["nominal_annual_full"] == pytest.approx(expected_full, rel=1e-9, abs=1e-6)


# ------------------------------------------------------------
# 5) 结算侧一致性：本月应征(预估) ≥ 结算实收（保底豁免/欠税使实收更少）
# ------------------------------------------------------------
def test_monthly_in_not_less_than_settled_actual_tax(state):
    """真跑一次结算：`[财政] 货币月入 X贯` 即实收（POP 扣缴后），须 ≤ 面板应征。"""
    from core.settlement_finance import _settle_finance

    forecast = state.finance_readout()["monthly_in"]
    log = []
    _settle_finance(state, log)
    line = next((x for x in log if "[财政]" in x and "货币月入" in x), None)
    assert line, f"结算未产出 [财政] 货币月入 日志：{log}"
    m = re.search(r"货币月入\s*([0-9]+)\s*贯", line)
    assert m, f"[财政] 日志格式变化，无法解析实收：{line}"
    actual_tax = int(m.group(1))
    assert actual_tax > 0
    # 应征（未扣 POP 支付力与欠税）≥ 实收；本例差距来自保底豁免/欠税
    assert forecast >= actual_tax, (
        f"应征 {forecast} 竟小于结算实收 {actual_tax}（口径又漂了）")


# ------------------------------------------------------------
# 6) 只读纪律：finance_readout() 不得改 state.treasury / ΣPOP
# ------------------------------------------------------------
def test_finance_readout_is_read_only(state):
    before_treasury = state.treasury
    before_imperial = state.imperial_treasury
    before_pop = _pop_total(state)
    state.finance_readout()
    state.finance_readout()          # 幂等：连调两次读数也不得漂移
    assert state.treasury == before_treasury, "finance_readout 改了国库（应纯派生）"
    assert state.imperial_treasury == before_imperial
    assert _pop_total(state) == before_pop, "finance_readout 改了 ΣPOP（应纯派生）"


# ------------------------------------------------------------
# 7) 链路：/api/readouts 薄壳不得漏字段（前端直读的就是这层；无 httpx → 直调端点函数）
# ------------------------------------------------------------
class _FakeRequest:
    """最小 Request 替身（范例 test_readouts_endpoint.py：本机回环视为已鉴权）。"""

    class _Client:
        host = "127.0.0.1"

    client = _Client()
    headers = {}
    method = "GET"
    url = "http://127.0.0.1:8000/api/readouts"


def test_readouts_endpoint_ships_scope_fields(monkeypatch):
    import json

    import backend.server as S

    s = GameState("史实")
    monkeypatch.setattr(S, "_state", s, raising=False)
    data = S.api_readouts(_FakeRequest())
    fin = data["finance"]
    assert isinstance(fin, dict) and fin
    missing = [k for k in _NEW_FIELDS if k not in fin]
    assert not missing, f"/api/readouts::finance 漏 P2-2 派生字段：{missing}"
    # 薄壳序列化后不得出现非有限值（None 是合法缺失语义，NaN/Infinity 不是）
    text = json.dumps(data, ensure_ascii=False, default=str)
    assert "NaN" not in text and "Infinity" not in text
    assert fin["arrival_ratio_scope_taxed"].count("二税折色") >= 1
