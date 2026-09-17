# -*- coding: utf-8 -*-
"""脱敏模块回归测试：区间脱敏/机构精度/噪声/滞后/米价趋势。"""
from ai.desensitize import (
    desensitize_band, _org_width, _desensitize_grain_trend, desensitize_state,
)


def test_band_format_wan():
    """区间脱敏：大数用万/亿单位，含「约…至…」结构。"""
    s = desensitize_band(5_000_000, "缗", width_pct=0.20, jitter_pct=0.0)
    assert s.startswith("约") and "至" in s and "万缗" in s


def test_band_width_half():
    """区间半宽 = 值 × width_pct，中心即原值（jitter=0 时）。"""
    s = desensitize_band(1_000_000, "缗", width_pct=0.20, jitter_pct=0.0)
    # 100万 ±20% → 约80万缗至120万缗
    assert "80万缗" in s and "120万缗" in s


def test_band_zero_negative_qualitative():
    """value<=0 不做区间，直接定性。"""
    assert desensitize_band(0, "缗") == "几无余财"
    assert desensitize_band(-5, "石") == "几无石"


def test_band_lag_value_tag():
    """认知层滞后：提供 lag_value 时标注「上月奏报」。"""
    s = desensitize_band(1_000_000, "缗", lag_value=800_000, jitter_pct=0.0)
    assert "上月奏报" in s


def test_org_width_precision():
    """机构信息壁垒：本行领域更窄（准）、跨领域用默认 0.25。"""
    assert _org_width("户部", "treasury") == 0.08
    assert _org_width("枢密院", "army") == 0.06
    assert _org_width("户部", "army") == 0.25      # 户部不懂军务
    assert _org_width("礼部", "exam") == 0.10


def test_grain_trend_absolute():
    """米价趋势：无 prev 时按绝对档位。"""
    assert _desensitize_grain_trend(1.8, None) == "米珠薪桂"
    assert _desensitize_grain_trend(1.3, None) == "粮价渐昂"
    assert _desensitize_grain_trend(1.0, None) == "米价适中"
    assert _desensitize_grain_trend(0.5, None) == "谷贱伤农"


def test_grain_trend_relative():
    """米价趋势：有 prev 时按涨跌比例。"""
    assert _desensitize_grain_trend(1.0, 0.5) == "米价腾涌"   # 涨 2 倍
    assert _desensitize_grain_trend(1.0, 0.96) == "米价渐昂"  # 涨 4%
    assert _desensitize_grain_trend(1.0, 0.98) == "米价持稳"  # 涨 2%
    assert _desensitize_grain_trend(1.0, 1.1) == "米价稍落"   # 跌 9%
    assert _desensitize_grain_trend(1.0, 1.3) == "米价大跌"


def test_desensitize_state_no_raw_leak():
    """完整脱敏不泄精确国库/兵力/流民数字。"""
    summary = {
        "time": "宣和元年正月",
        "prestige": {"level": "中", "desc": "平平"},
        "treasury": {"amount": 5_000_000, "desc": "勉强维持"},
        "imperial_treasury": {"amount": 1_000_000},
        "arrival_rate": {"desc": "不足五成"},
        "factions": {"旧党": {"influence": 60, "sat_desc": "大体认可"}},
        "external": {"金": {"power": 70, "attitude": 30}},
        "refugee_count": 200_000,
        "pop_sat_desc": "大体认可",
        "military": {"armies": {"a": {"troops": 100_000}}},
        "decree_bandwidth": 6, "pending_decrees": 0,
        "granary_amount": 3_000_000, "granary_ext": {"granary": "仓廪未详"},
        "grain_price": 1.0, "grain_price_prev": 0.9,
        "personal": {"art": 85, "taoism": 25, "pleasure": 30},
    }
    ds = desensitize_state(summary, org_name="户部")
    import json
    raw = json.dumps(ds, ensure_ascii=False)
    # 精确大数不得出现在脱敏输出（5000000/100000/200000 等原值）
    assert "5000000" not in raw and "100000" not in raw
    # 定性字段保留
    assert ds["国库定性"] == "勉强维持"
    assert "国库" in ds and "太仓" in ds
