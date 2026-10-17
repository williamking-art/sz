# -*- coding: utf-8 -*-
"""backend/client.py action 分派表 ↔ core.commands 实现符号契约（2026-10-17 全审 A-3）。

背景：`LocalBackend.action` 的分派表直接调用 `core.commands.<name>`，但
`core/commands.py` 只从 `commands_decree` 重导出了一部分符号 ⇒ 9 个前端按钮
经 `/api/action` 必然 AttributeError -> 500。本用例锁死「分派表引用的每个
`cmd.*` 都必须是可调用的 core.commands 属性」，防止再次漂移。
"""
import re
from pathlib import Path

import core.commands as cmd


def _dispatcher_block() -> str:
    commands_py = Path(cmd.__file__).resolve()
    client_py = commands_py.parents[1] / "backend" / "client.py"
    src = client_py.read_text(encoding="utf-8")
    start = src.index("handlers = {")
    end = src.index("handlers.get", start)
    return src[start:end]


def test_action_dispatcher_symbols_are_reexported():
    block = _dispatcher_block()
    names = sorted(set(re.findall(r"\bcmd\.([A-Za-z_]\w*)", block)))
    assert names, "分派表解析失败（可能已重构，需同步本用例）"
    missing = [n for n in names if not callable(getattr(cmd, n, None))]
    assert not missing, f"分派表引用未导出/不可调用符号: {missing}"


def test_critical_action_keys_present():
    block = _dispatcher_block()
    for action in (
        "issue_free_decree", "issue_kouyu", "merge_drafts",
        "issue_edict_from_review", "reject_edict_draft",
        "propose_inner_transfer", "confirm_inner_transfer",
        "cancel_inner_transfer", "bestow_imperial_favor",
    ):
        assert f'"{action}"' in block, f"分派表缺少动作 {action}"