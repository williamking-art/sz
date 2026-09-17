# -*- coding: utf-8 -*-
"""T9 Token 计量表测试：按方法分桶计量 / 汇总快照 / 清零 / UI 分组映射。

覆盖：
  1) _add_usage 总桶 + 按方法分桶（默认自动检测调用方）；
  2) meter_summary / reset_meter 往返；
  3) UI Token 计量分组映射（_token_group_of）完整性与「其它」兜底；
  4) HUD 顶栏不再内嵌命中率（回归：命中率只入设置明细表）。
"""
import os
import sys

import pytest

# game 根（测试已迁 _dev_tools/game-dev/tests；game 根 = G:\sz\game）
_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from ai.client import AIClient  # noqa: E402


def test_add_usage_total_and_bucket():
    """总桶与按方法分桶同步累加（分桶键默认自动检测调用方）。"""
    c = AIClient(api_key="x")
    # 直接经 _add_usage：分桶键 = 当前测试函数名（自动检测，非内部名）
    c._add_usage({"prompt_tokens": 100, "completion_tokens": 20})
    c._add_usage({"prompt_tokens": 30, "completion_tokens": 5})
    assert c.token_usage == {"prompt": 130, "completion": 25, "calls": 2}
    assert sum(b["calls"] for b in c._meter.values()) == 2
    assert sum(b["prompt"] for b in c._meter.values()) == 130
    key = next(iter(c._meter))
    assert key == "test_add_usage_total_and_bucket", \
        f"自动检测应取测试函数名，实际 {key}"
    assert c._meter[key]["calls"] == 2


def test_add_usage_explicit_key():
    """显式 meter_key 分桶（_call 内部透传用）。"""
    c = AIClient(api_key="x")
    c._add_usage({"prompt_tokens": 10, "completion_tokens": 0}, meter_key="dialogue")
    c._add_usage({"prompt_tokens": 7, "completion_tokens": 3}, meter_key="polish_decree")
    assert c._meter["dialogue"]["prompt"] == 10
    assert c._meter["polish_decree"] == {"calls": 1, "prompt": 7, "completion": 3}
    assert c.token_usage["calls"] == 2


def test_meter_summary_and_reset():
    """meter_summary 快照（含总桶）+ reset_meter 清零。"""
    c = AIClient(api_key="x")
    c._add_usage({"prompt_tokens": 50, "completion_tokens": 10}, meter_key="monthly_report")
    s = c.meter_summary()
    assert s["total"]["prompt"] == 50
    assert s["by_method"]["monthly_report"]["completion"] == 10
    c.reset_meter()
    assert c.token_usage == {"prompt": 0, "completion": 0, "calls": 0}
    assert c.meter_summary()["by_method"] == {}


def test_token_group_mapping():
    """分组映射（Tk 废弃：映射已下沉 ai/token_meter，单一权威源）：
    常见契约方法归入正确调用类型；未知归「其它」。"""
    from ai.token_meter import token_group_of as g
    assert g("dialogue") == "召对·AI"
    assert g("polish_decree") == "拟旨"
    assert g("parse_decree") == "拟旨"
    assert g("draft_decree") == "拟旨"
    assert g("council_review") == "会签"
    assert g("economy_decide") == "推演"
    assert g("military_decide") == "推演"
    assert g("emperor_personal_decide") == "推演"
    assert g("monthly_report") == "月报叙事"
    assert g("event_narrative") == "月报叙事"
    assert g("final_eval") == "月报叙事"
    assert g("some_future_method") == "其它"


def test_token_groups_cover_client_methods():
    """客户端全部契约方法都被分组覆盖（防新增契约方法漏计量分组）。"""
    from ai.token_meter import token_group_of
    client_methods = [m for m in dir(AIClient)
                      if m.endswith("_decide") or m in (
                          "dialogue", "polish_decree", "draft_decree", "parse_decree",
                          "council_review", "monthly_report", "event_narrative",
                          "advice", "final_eval")]
    for m in client_methods:
        assert token_group_of(m) in (
            "召对·AI", "拟旨", "会签", "推演", "月报叙事"), f"方法 {m} 未入任何分组"


def test_hud_no_hitrate_inline():
    """回归（Tk 废弃后迁移至 Web）：顶栏不内嵌「召对省 N 次(Y%)」（命中率在 Token 明细表）。"""
    _fe = os.path.join(_GAME_ROOT, "..", "game", "frontend",
                       "src", "renderer", "hud", "TopBar.tsx")
    if not os.path.exists(_fe):
        return  # 前端工程不在本机（可选目录）→ 跳过
    with open(_fe, encoding="utf-8") as f:
        src = f.read()
    assert "召对省" not in src, "HUD 顶栏不应再显示召对命中率"
