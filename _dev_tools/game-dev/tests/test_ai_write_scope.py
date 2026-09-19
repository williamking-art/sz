# -*- coding: utf-8 -*-
"""审查报告 §6「AI 不得直接写 JIAOZI_INFO/BANK_INFO/TECH_INFO 或 POP」的哨兵测试。

口径（现状核实）：
  · AI **没有**通用写状态工具 —— `_TOOL_NAMES` 是冻结白名单，`update_state` 仅
    在 STATE_TOOL_SCHEMAS 里作为"未来接线的 schema"预留，**不在白名单内**；
  · AI 唯一能改状态的工具是 `relief_grant`，其 `changes` 路径**硬编码**为
    treasury / prefectures.<路>.pops.农|工匠.wealth / prefectures.<路>.refugees，
    数值经 `_safe_int` 夹取、地域经 `_resolve_region` 校验、守恒由 applier 保证；
  · 程序结算（"settlement"/"situations"）可写 POP，这是**设计如此**（POP 是权威源）。

本文件把这些纪律**钉死**，防止将来"误加一个通用写状态工具"绕过全部约束。
"""
import ast
import os
import re
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

_AI_DIR = os.path.join(_GAME_ROOT, "ai")

# 允许出现的危险/通用写状态工具名（任何一条出现在白名单里都要报警）
_FORBIDDEN_TOOL_NAMES = {
    "update_state", "set_state", "write_state", "apply_changes",
    "set_field", "patch_state", "edit_state",
}


def test_update_state_is_not_an_ai_tool():
    """`update_state` 只能是"预留 schema"，不得进入 AI 可调工具白名单。"""
    from ai.client_utils import _TOOL_NAMES
    assert isinstance(_TOOL_NAMES, frozenset), "工具白名单必须是 frozenset（不可变）"
    assert "update_state" not in _TOOL_NAMES, \
        "update_state 一旦可调，AI 就能按 VALID_PATHS 直写 POP/国库，§6 立刻失守"
    assert not (_FORBIDDEN_TOOL_NAMES & set(_TOOL_NAMES)), \
        f"白名单出现通用写状态工具：{_FORBIDDEN_TOOL_NAMES & set(_TOOL_NAMES)}"


def test_ai_applier_entry_is_single_and_in_client_utils():
    """AI 侧调用 `applier_pipeline` 的地方**有且仅有一处**（relief_grant）。"""
    calls = []
    for root, _dirs, files in os.walk(_AI_DIR):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = os.path.join(root, fn)
            with open(p, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "applier_pipeline":
                    calls.append((os.path.relpath(p, _GAME_ROOT), node.lineno))
    assert len(calls) == 1, f"AI 侧 applier_pipeline 调用点应为 1 处，得到 {calls}"
    assert calls[0][0].replace("\\", "/").endswith("ai/client_utils.py"), calls


def test_relief_grant_paths_are_hardcoded_and_whitelisted():
    """AI 写路径必须硬编码且落在赈济白名单内（AI 不能自带 path）。

    注：路径含 f-string（如 f"prefectures.{region}.pops.农.wealth"），不是 AST 常量，
    故用**源码文本**提取字面量路径进行断言。
    """
    p = os.path.join(_AI_DIR, "client_utils.py")
    with open(p, "r", encoding="utf-8") as f:
        src = f.read()

    # 截出 applier_pipeline(...) 那一段（到闭合括号）
    start = src.index("applier_pipeline(state, [")
    seg = src[start:start + 1500]

    paths = re.findall(r'"(treasury|prefectures\.[^"]*|jiaozi[^"]*|bank[^"]*|tech[^"]*)"', seg)
    paths += re.findall(r'f"(prefectures\.[^"]*)"', seg)
    assert paths, "赈济调用里应出现显式 path 字面量"
    for v in paths:
        assert v.startswith(("treasury", "prefectures.")), f"赈济路径越界：{v}"
        assert not v.startswith(("jiaozi", "bank", "standard", "tech",
                                 "maritime", "coin")), f"AI 不得触达金融/科技账本：{v}"
    assert any("pops.农.wealth" in v for v in paths), paths
    assert "treasury" in paths, paths


def test_dispatch_has_whitelist_guard_in_source():
    """`_tool_dispatch` 必须以**服务端白名单**为第一道闸门（未登记工具拒绝式处理）。"""
    p = os.path.join(_AI_DIR, "client_utils.py")
    with open(p, "r", encoding="utf-8") as f:
        src = f.read()
    assert "if name not in _TOOL_NAMES:" in src, "工具分发缺少白名单闸门"
    assert "未授权工具被拒" in src, "未知工具必须给出明确拒绝文本"


def test_program_settlement_may_write_pop_but_ai_may_not():
    """POP 路径对**程序结算**放行是设计（POP 是权威源）；对 AI 的拦截靠工具白名单。"""
    from engine.state_applier import VALID_PATHS
    assert any(p.startswith("prefectures.") and "pops" in p for p in VALID_PATHS), \
        "程序需要能写 POP（否则结算无权威源）"
    from ai.client_utils import _TOOL_NAMES
    assert not (_FORBIDDEN_TOOL_NAMES & set(_TOOL_NAMES))
