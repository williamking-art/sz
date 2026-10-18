# -*- coding: utf-8 -*-
"""质量放行门 · 仓储损耗接线（G-3 P2b）。

用户 2026-10-18：「粮的损耗不是有天道系统来裁决多寡吗」
⇒ 天道给 storage_loss 档位（无/轻/中/重），程序换算率；旧实现挂在 outflow（发仓档位）上是错的。

本门钉住：
1. 契约：storage_loss 缺省/非法 ⇒ 回落「中」（不伪造灾损）；合法档位原样保留；
2. 结算：档位真的影响损耗（重 > 中 > 轻 > 无=0）；
3. 默认零变更：无 AI 决策时损耗 == 旧口径 int(granary × SPARROW_RAT)；
4. 语义修正：outflow 档位不再影响损耗。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from content.data import SPARROW_RAT  # noqa: E402


def _new_state_with_ai(ai_granary):
    from core.commands import new_game

    s = new_game()
    s._granary_ai = {"granary": dict(ai_granary), "narrative": ""}
    return s


def _run_granary(state):
    from core.settlement_granary import _settle_granary

    log = []
    _settle_granary(state, log)
    return int(state.granary_stats.get("sparrow", 0)), log


def test_contract_defaults_storage_loss_to_mid():
    """契约层：缺 storage_loss ⇒ 中；非法值 ⇒ 中（拒绝式不伪造灾损）。"""
    from ai.contracts_settle import SettleContractMixin

    fn = SettleContractMixin.granary_decide
    assert "storage_loss" in (fn.__doc__ or ""), "契约文档未声明 storage_loss"
    import re
    code = Path(fn.__code__.co_filename).read_text(encoding="utf-8")
    assert "storage_loss" in code, "实现里没有 storage_loss 解析"
    assert re.search(r'"storage_loss"\]\s*=\s*sl if sl in', code), "缺少缺省回落逻辑"


def test_loss_scales_with_tier():
    """结算层：档位真的改变损耗量（重 > 中 > 轻 > 无=0）。"""
    seen = {}
    for tier in ("无", "轻", "中", "重"):
        s = _new_state_with_ai({"inflow": "小", "outflow": "小", "price_stabilize": "小",
                                "army_supply": "小", "storage_loss": tier})
        sparrow, _log = _run_granary(s)
        seen[tier] = sparrow
    assert seen["无"] == 0, f"「无」档应零损耗：{seen}"
    assert seen["轻"] <= seen["中"] <= seen["重"], f"档位未单调：{seen}"
    assert seen["重"] > seen["中"] > 0, f"「重」档必须显著高于「中」：{seen}"


def test_default_equals_legacy_rate():
    """默认零变更：无 AI 决策 ⇒ 损耗 == int(granary × SPARROW_RAT)（旧口径）。"""
    from core.commands import new_game

    s = new_game()
    s._granary_ai = {}                      # 无 AI 决策
    expected = int(s.granary * SPARROW_RAT)
    sparrow, _ = _run_granary(s)
    assert sparrow == expected, f"默认损耗 {sparrow} != 旧口径 {expected}"


def test_outflow_tier_no_longer_drives_loss():
    """语义修正：outflow（发仓档位）不再影响损耗（旧实现把它当损耗倍率）。"""
    a = _new_state_with_ai({"inflow": "小", "outflow": "无", "price_stabilize": "小",
                            "army_supply": "小", "storage_loss": "中"})
    b = _new_state_with_ai({"inflow": "小", "outflow": "大", "price_stabilize": "小",
                            "army_supply": "小", "storage_loss": "中"})
    sa, _ = _run_granary(a)
    sb, _ = _run_granary(b)
    assert sa == sb, f"outflow 档位仍在影响损耗：{sa} vs {sb}"