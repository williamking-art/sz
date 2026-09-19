# -*- coding: utf-8 -*-
"""前端面板**类型契约**测试（取代散落的"源码文本断言"）。

2026-09-19 测试项审查结论：
- 原 `test_dock_has_diplomacy`（`'"diplomacy"' in Dock.tsx`）与
  `test_right_strip_has_minsheng`（`'"pop"' in RightStrip.tsx`）属**脆弱文本断言**：
  改文案/重构即失败，而真实退化（面板失联、点不开）未必被它捕获；
- 本文件以**类型契约 + 三处一致性**替代：`gameStore.PanelKind`（类型真源）→ `Dock.COMMANDS`
  （入口）→ `OverlayStack.PanelBody`（实现分支），任一环节缺键即失败。
- 前端工程不在本机时（可选目录）整个模块跳过，不产生假绿。

断言：
  ① 每个 PanelKind 成员都在 OverlayStack 有实现分支（或走 PlaceholderPanel 兜底）；
  ② Dock 的每个命令键 ∈ PanelKind（否则 `pushOverlay({kind})` 会编译失败/运行期空面板）；
  ③ 关键面板必须存在（含本轮新增的 `situation`，以及 `prefecture`/`memory` 等既有入口）。
"""
import os
import re
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
_FE = os.path.join(_GAME_ROOT, "frontend", "src", "renderer")
if not os.path.isdir(_FE):
    pytest.skip("前端工程不在本机（可选目录）", allow_module_level=True)

STORE = os.path.join(_FE, "store", "gameStore.tsx")
DOCK = os.path.join(_FE, "hud", "Dock.tsx")
STACK = os.path.join(_FE, "panels", "OverlayStack.tsx")

# 必须有入口的关键面板（新增面板时在此登记，即"入口存在性"的唯一断言处）
REQUIRED_PANELS = {
    "situation",   # 局势（含六类心气 + 集团⊆POP）
    "prefecture",  # 州县（含识字率/本路局势联动）
    "memory", "court", "ministers", "decree", "diplomacy", "military",
    "accounting", "pop", "land", "gazette", "pending",
}


def _read(p: str) -> str:
    with open(p, encoding="utf-8") as f:
        return f.read()


def _panel_kinds() -> set:
    """从 `export type PanelKind = "a" | "b" | ...` 提取成员。"""
    src = _read(STORE)
    m = re.search(r"export type PanelKind\s*=(.*?);", src, re.S)
    assert m, "gameStore.tsx 未找到 PanelKind 联合类型（类型真源丢失）"
    return set(re.findall(r'"([a-z0-9_]+)"', m.group(1)))


def _dock_keys() -> set:
    """从 `COMMANDS` 数组提取 `key: "..."`。"""
    src = _read(DOCK)
    m = re.search(r"const COMMANDS[^=]*=\s*\[(.*?)\];", src, re.S)
    assert m, "Dock.tsx 未找到 COMMANDS 数组"
    return set(re.findall(r'key:\s*"([a-z0-9_]+)"', m.group(1)))


def _stack_cases() -> set:
    """从 `switch (kind)` 提取 `case "..."` 分支。"""
    src = _read(STACK)
    return set(re.findall(r'case\s+"([a-z0-9_]+)"\s*:', src))


def test_panel_kind_has_stack_branch():
    kinds, cases = _panel_kinds(), _stack_cases()
    missing = sorted(kinds - cases)
    assert not missing, f"PanelKind 成员在 OverlayStack 无实现分支：{missing}"


def test_dock_keys_are_valid_panel_kinds():
    kinds, keys = _panel_kinds(), _dock_keys()
    bad = sorted(keys - kinds)
    assert not bad, f"Dock 命令键不在 PanelKind 中（会得到空面板）：{bad}"


def test_required_panels_have_entry_and_implementation():
    kinds, keys, cases = _panel_kinds(), _dock_keys(), _stack_cases()
    for name in sorted(REQUIRED_PANELS):
        assert name in kinds, f"关键面板 {name} 不在 PanelKind（类型真源）"
        assert name in cases, f"关键面板 {name} 无 OverlayStack 分支"
    # 关键入口至少要能从 Dock 或 RightStrip 打开（本文件只校验 Dock 可及的那批）
    dock_backed = REQUIRED_PANELS & keys
    assert dock_backed, "至少要有若干关键面板可直接从 Dock 打开"
    assert "situation" in keys, "局势面板必须可从 Dock 打开（本轮新增入口）"


def test_prefecture_panel_accepts_picked_prop():
    """州县面板必须支持 `props.picked`（局势面板「跳州路」联动依赖它）。"""
    src = _read(os.path.join(_FE, "panels", "PrefecturePanel.tsx"))
    assert "picked" in src, "PrefecturePanel 应支持 picked 参数（跳转到指定路）"
    sit = _read(os.path.join(_FE, "panels", "SituationPanel.tsx"))
    assert 'kind: "prefecture"' in sit and "picked" in sit, \
        "局势面板应能把 region_hint 跳到州县面板（双向联动）"
