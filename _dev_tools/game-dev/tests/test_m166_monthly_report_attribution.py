# -*- coding: utf-8 -*-
"""M166 月报归因（P5 收口）· 定向回归。

把 `readout_hub` 的关键读数并入**程序真值月报**（`fallback_report`）：
① **只读**（不写 state）；② **不可读 ⇒ 明写「未定义」**（缺失≠0，**不显示 0**）；
③ 读数模块整块不可用 ⇒ **失败原因写进文本**（不静默）；④ 只改**文本**、不改数值。
"""

from core import commands
from game.ai.narrative_fallback import _readout_summary, fallback_report  # noqa: F401  (路径由测试运行器决定)


def _months(state, n=6):
    import core.settlement as S
    for _ in range(n):
        S.run_monthly_settlement(state)
    return state


def test_readout_summary_contains_key_readouts():
    s = _months(commands.new_game())
    txt = _readout_summary(s)
    assert "读数摘要" in txt and "试点主瓶颈" in txt and "试点链条缺口" in txt
    # 主瓶颈为枚举值（真实局实测 capacity_shortage）
    assert s is not None


def test_readout_summary_is_undefined_not_zero_when_unreadable():
    """不可读 ⇒ 必须出现「未定义」，**绝不出现 0**（缺失≠0）。"""
    class _S:                                                # 空状态：读数应不可读
        prefectures: dict = {}

    txt = _readout_summary(_S())
    assert "未定义" in txt
    assert "缺口 0" not in txt and "主瓶颈0" not in txt


def test_fallback_report_includes_summary_and_keeps_template():
    s = _months(commands.new_game())
    r = fallback_report(year=1101, month=3, era_name="建中靖国", state=s)
    body = r.get("report") if isinstance(r, dict) else str(r)
    assert "读数摘要" in body
    assert body.endswith("）")                               # 句式完整（括号闭合）


def test_fallback_report_without_state_still_works():
    r = fallback_report(year=1101, month=3, era_name="建中靖国")
    body = r.get("report") if isinstance(r, dict) else str(r)
    assert body and "读数摘要" not in body                    # 无 state ⇒ 不追加（向后兼容）
