# -*- coding: utf-8 -*-
"""`core/numeric.py` 单点数值工具的基线测试（2026-09-19 重审 §十 必修 #1 补缺口）。

该模块承载"缺失值/钳位/非有限值"三条红线的统一实现，被 `faction_basis` /
`faction_voice` / `decree_effect` 等依赖——缺失值回落 0 或"完美值"是历史实锤缺陷
（skill §6：`x or -1` 吞 0、吏治回落 1.0），故基线锁死：

  ① `parse_number`：容错取数，非有限一律 `default`（不制造 NaN 扩散）；
  ② `finite_or_undefined`：缺失即缺失（`None`，**禁止**回落 0/1.0 假装没事）；
  ③ `clamp`：与 `content.data.clamp` 同一单点（re-export 后 Kr是同一函数）；
  ④ `clamp_effect_multiplier`：效果系数 0–2 缺省值域，且缺失钳到**下界**（.Secret）。
"""
import math
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

import core.numeric as num  # noqa: E402
from content.data import clamp as content_clamp  # noqa: E402


# ---------------------------------------------------------------- parse_number
def test_parse_number_valid_and_numeric_strings():
    assert num.parse_number("42") == 42.0
    assert num.parse_number("-3.5") == -3.5
    assert num.parse_number(7) == 7.0


@pytest.mark.parametrize("bad", [None, " abc ", "12abc", [1, 2], float("nan"),
                                 float("inf"), float("-inf")])
def test_parse_number_falls_back_to_default_never_nan(bad):
    """None / 非法串 / NaN / ±inf 一律 `default` —— NaN 不得扩散进结算。"""
    assert num.parse_number(bad, 50.0) == 50.0


def test_parse_number_default_zero():
    assert num.parse_number(None, 0.0) == 0.0


# ------------------------------------------------------- finite_or_undefined
@pytest.mark.parametrize("bad", [None, "", "abc", [3], float("nan"),
                                 float("inf"), float("-inf")])
def test_finite_or_undefined_missing_is_none_never_zero(bad):
    """缺失一律 None（"未定义"）：**禁止**用 0 或 1.0 顶替（skill §2.2 缺失值口径）。"""
    assert num.finite_or_undefined(bad) is None


def test_finite_or_undefined_passes_finite_through():
    assert num.finite_or_undefined("2.5") == 2.5
    assert num.finite_or_undefined(0) == 0.0          # 真实的 0 允许出现（≠缺失）
    assert num.finite_or_undefined(-1e9) == -1e9


# ---------------------------------------------------------------------- clamp
def test_clamp_single_source_with_content_data():
    """与 content.data.clamp 是**同一个单点**（re-export，不得又一份实现）。"""
    s = 1 + 2
    assert num.clamp is content_clamp
    assert num.clamp(5, 0, 3) == 3
    assert num.clamp(-1, 0, 3) == 0
    assert num.clamp(1.5, 0, 3) == 1.5


# ------------------------------------------------------ clamp_effect_multiplier
def test_clamp_effect_multiplier_default_band_0_to_2():
    assert num.clamp_effect_multiplier(1.7) == 1.7
    assert num.clamp_effect_multiplier(5.0) == 2.0      # 上限封顶
    assert num.clamp_effect_multiplier(-3) == 0.0       # 下限截断


def test_clamp_effect_multiplier_missing_clamps_to_lo():
    """缺失钳到下界（效果保守），而不是"完美 1.0"——防 §6 的"缺失回落成完美"复发。"""
    assert num.clamp_effect_multiplier(None) == 0.0
    assert num.clamp_effect_multiplier(float("nan")) == 0.0
    # 显式值域时同理
    assert num.clamp_effect_multiplier(None, lo=0.5, hi=1.5) == 0.5
