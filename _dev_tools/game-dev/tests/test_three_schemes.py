# -*- coding: utf-8 -*-
"""三方案落地测试：叙事数字校验 / 来源闭集 / 人物校验表 / 工具注册护栏。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState  # noqa: E402
from ai.narrative_guard import (  # noqa: E402
    _validate_narrative_numbers, _build_numeric_ranges, _build_source_closure,
    build_character_statuses, build_character_blacklist, _validate_characters,
)


def _new_state():
    return GameState("史实")


def test_numeric_validation_in_range():
    """数字+单位校验：区间内数字保留；区间外改写定性词。"""
    s = _new_state()
    ranges = {"贯": (0, 100), "石": (0, 1000)}
    text, flag = _validate_narrative_numbers("府库得五十贯，赈济三百石。", ranges)
    assert flag is False
    assert "五十贯" in text and "三百石" in text
    # 区间外 → 定性词改写
    text2, flag2 = _validate_narrative_numbers("府库得100000000贯。", ranges)
    assert flag2 is True
    assert "100000000贯" not in text2
    assert any(q in text2 for q in ("寥寥", "可观", "充盈"))


def test_numeric_ranges_hard_anchor():
    """硬锚：石区间上限 = 太仓存量（调粮/赈济≤仓廪）。"""
    s = _new_state()
    ranges = _build_numeric_ranges(s)
    assert ranges["石"][1] == max(1, int(getattr(s, "granary", 0)))
    assert ranges["贯"][1] >= int(getattr(s, "treasury", 0))


def test_source_closure():
    """来源闭集：含诏书/事件/记忆图谱/日志，且带硬约束文本。"""
    s = _new_state()
    closure = _build_source_closure(s)
    assert "本期取材" in closure and "禁止引用闭集外" in closure


def test_character_statuses_and_blacklist():
    """人物校验表 + 黑名单：已故/已黜入黑名单，在朝具名人物列出。"""
    s = _new_state()
    statuses = build_character_statuses(s)
    assert "蔡京" in statuses
    assert statuses["蔡京"]["status"] == "active"
    bl = build_character_blacklist(statuses)
    assert "在朝具名人物" in bl
    # 具名已故人物 → 校验标记
    bad, names = _validate_characters("已故韩忠彦曾言……", statuses)
    if statuses.get("韩忠彦", {}).get("status") != "active":
        assert bad is True


def test_tool_registry_guardrails():
    """工具注册（对齐：名称放开/效果放宽/软约束 cost/合理性）；执行走 free_effect 拒绝式。"""
    from core.tool_registry import register_tool, deactivate_tool, execute_tool
    s = _new_state()
    # 名称放开（仅防重名）——任意名可注册
    r = register_tool(s, {"name": "天降祥瑞", "effect_template": {"prestige": "中"}}, created_by="蔡京")
    assert r["ok"] is True, "名称放开（仅防重名）"
    # 效果字段自由设计（magic 也接受——合理性软校验）
    r2 = register_tool(s, {"name": "保甲", "effect_template": {"magic": "大"}}, created_by="蔡京")
    assert r2["ok"] is True, "效果字段自由设计（白名单放宽）"
    # 重名拒绝
    r2b = register_tool(s, {"name": "保甲", "effect_template": {"prestige": "中"}}, created_by="蔡京")
    assert r2b["ok"] is False and "已注册" in r2b["msg"]
    # cost 超存量（含软约束倍率）→ 拒绝
    r3 = register_tool(s, {"name": "市易", "effect_template": {"treasury": "小"},
                           "cost": {"treasury": 999999999}}, created_by="蔡京")
    assert r3["ok"] is False and "成本" in r3["msg"]
    # 合法注册 + 执行（free_effect 拒绝式落地；第 3 个工具 cost ×1.2 软约束倍率）
    r4 = register_tool(s, {"name": "义仓", "effect_template": {"population_satisfaction": "小"},
                           "cost": {"treasury": 100000}}, created_by="蔡京")
    assert r4["ok"] is True
    t0 = s.treasury
    log = execute_tool(s, r4["tool_id"], {})
    assert s.treasury == t0 - 120000  # cost 100000 × 1.2（第 3 个软约束倍率）
    assert s.tool_registry[r4["tool_id"]]["usage"] == 1
    # 注销（active=False 不物理删）
    assert deactivate_tool(s, r4["tool_id"])["ok"] is True
    assert r4["tool_id"] in s.tool_registry and s.tool_registry[r4["tool_id"]]["active"] is False
    # 去硬上限：注册多个不硬拒（软约束成本递增）
    s2 = _new_state()
    for i in range(20):
        reg = register_tool(s2, {"name": f"新制{i}", "effect_template": {"prestige": "微"}}, created_by="x")
        assert reg["ok"] is True, f"第 {i+1} 个工具应允许（去硬上限）：{reg}"


def test_tool_registry_roundtrip():
    """工具注册表存档往返。"""
    from core.tool_registry import register_tool
    from core.save_load import save_game, load_game, _slot_path
    s = _new_state()
    register_tool(s, {"name": "常平", "effect_template": {"prestige": "小"}}, created_by="蔡京")
    assert save_game(s, slot=9)
    s2 = load_game(9)
    assert s2 is not None
    assert len(s2.tool_registry) == 1
    if os.path.exists(_slot_path(9)):
        os.remove(_slot_path(9))
