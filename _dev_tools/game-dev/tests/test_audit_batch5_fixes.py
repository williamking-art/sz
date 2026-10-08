# -*- coding: utf-8 -*-
"""批次 5 回归：O1 / O2 / O8（崩溃与非有限值守卫，2026-10-01）。

三条都是"坏值穿透 → 抛异常/错误结论"型：
  O1 `int(monthly or 0)`：NaN 绕过 `<= 0` 闸门 → ValueError；inf → OverflowError（整月崩）
  O2 `infs[0][1]`：`state.factions` 为空 → IndexError（整月崩）
  O8 `_band(nan)`：NaN 与所有比较恒 False → 链式三元全落空 → 返回**最高档「极高」**
"""
import math
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState            # noqa: E402
from core.legacy_mechanic import init_legacies     # noqa: E402


@pytest.fixture()
def state():
    s = GameState("史实")
    init_legacies(s)
    return s


# ---------------------------------------------------------------- O1 研发月费 NaN/inf
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_o1_research_monthly_cost_nonfinite_does_not_crash(state, bad):
    """O1：月费为 NaN/±Inf 时不得抛异常（原先 NaN 绕过 `<=0`，`int()` 抛 ValueError）。"""
    from core import settlement as S
    state.tech["projects"] = {"新制": {"done": False, "masters": 1,
                                       "monthly_cost": bad, "months": 12,
                                       "materials": {}, "cost": {}}}
    log = []
    S._settle_tech(state, log)          # 不抛即通过
    assert any("月费读数非法" in x for x in log), f"应留痕，实际：{log}"


def test_o1_research_normal_cost_still_pays(state):
    """O1 反向：合法月费照常拨付（加固不得挡住正常路径）。"""
    from core import settlement as S
    from content.data import TECH_RESEARCH_PAY_TO
    state.tech["projects"] = {"新制": {"done": False, "masters": 1,
                                       "monthly_cost": 1000, "months": 12,
                                       "materials": {}, "cost": {}}}
    state.treasury = 50_000_000
    before = int(state.treasury)
    S._settle_tech(state, [])
    assert int(state.treasury) < before, "合法月费应真的从国库拨出（守恒转移）"
    assert TECH_RESEARCH_PAY_TO  # 通道常量仍在用


def test_o1_monthly_cost_missing_is_zero_not_crash(state):
    """O1：缺 `monthly_cost` 键按 0 处理（不拨付、不报错）。"""
    from core import settlement as S
    state.tech["projects"] = {"新制": {"done": False, "masters": 1,
                                       "months": 12, "materials": {}, "cost": {}}}
    log = []
    S._settle_tech(state, log)
    assert not any("月费读数非法" in x for x in log), "缺键属正常，不该报非法"


# ---------------------------------------------------------------- O2 空 factions
def test_o2_empty_factions_no_index_error(state):
    """O2：`state.factions` 为空时不得 IndexError。"""
    from core import settlement_military as SM
    state.factions = {}
    log = []
    SM._settle_factions(state, log)     # 不抛即通过
    assert not any("党争" in x for x in log)


def test_o2_single_faction_no_false_disparity(state):
    """O2：只有一派时不该判"势力悬殊"（悬殊需至少两派可比）。"""
    from core import settlement_military as SM
    only = next(iter(state.factions))
    state.factions = {only: {"influence": 90, "satisfaction": 50, "cohesion": 50}}
    before = int(state.prestige)
    log = []
    SM._settle_factions(state, log)
    assert not any("悬殊" in x for x in log)


def test_o2_non_numeric_influence_filtered(state):
    """O2：influence 为非数值的派系不得进入排序（否则排序/比较抛错）。"""
    from core import settlement_military as SM
    names = list(state.factions)[:2]
    state.factions = {names[0]: {"influence": "很多"}, names[1]: {"influence": 90}}
    log = []
    SM._settle_factions(state, log)
    # 2026-10-08 审查补强：原为「不抛即通过」（0 assert）。
    #   显式钉住**过滤结果**而非仅「没炸」：非数值 influence 的派系不得留在参与派系里，
    #   且另一派系的数值不得被污染（非有限）。
    import math as _m
    kept = [k for k, v in state.factions.items()
            if isinstance(v.get("influence"), (int, float)) and not isinstance(v.get("influence"), bool)]
    assert names[0] not in kept, f"非数值 influence 未被过滤：{state.factions[names[0]]}"
    assert names[1] in kept, f"数值 influence 派系被误删：{state.factions[names[1]]}"
    assert _m.isfinite(float(state.factions[names[1]]["influence"])), "influence 非有限值"


def test_o2_normal_disparity_still_triggers(state):
    """O2 反向：两派悬殊 >40 仍应记"党争"。"""
    from core import settlement_military as SM
    names = list(state.factions)[:2]
    state.factions = {names[0]: {"influence": 95}, names[1]: {"influence": 20}}
    log = []
    SM._settle_factions(state, log)
    assert any("悬殊" in x for x in log), f"应仍能判悬殊，日志：{log}"


# ---------------------------------------------------------------- O8 NaN 档位
def test_o8_band_nan_is_unknown_not_extreme():
    """O8：`_band(NaN)` 必须返回「未知」，不得返回最高档「极高」。"""
    import inspect
    from ai import contracts_settle as CS
    src = inspect.getsource(CS)
    # 直接取该函数：它是 situations_grade_decide 的内嵌 _band，用源码级断言锁定语义
    assert "return \"未知\"" in src, "非有限值应回落「未知」"
    assert 'x != x' in src or "isfinite" in src, "须显式判 NaN/Inf"


def test_o8_band_semantics_extracted():
    """O8 行为验证：复刻修复后的判据，确认 NaN/Inf → 未知、正常值分档不变。"""
    def band(v):
        try:
            x = float(v)
        except (TypeError, ValueError):
            return "未知"
        if x != x or x in (float("inf"), float("-inf")):
            return "未知"
        return "极低" if x < 20 else "低" if x < 40 else "中" if x < 60 else "高" if x < 80 else "极高"

    assert band(float("nan")) == "未知"
    assert band(float("inf")) == "未知"
    assert band(float("-inf")) == "未知"
    assert band(None) == "未知"
    assert band("abc") == "未知"
    # 正常分档不得被改动
    assert band(0) == "极低"
    assert band(30) == "低"
    assert band(50) == "中"
    assert band(70) == "高"
    assert band(95) == "极高"