# -*- coding: utf-8 -*-
"""目录索引一致性：`core/game_state.py`、`core/commands.py` 的**纯符号目录**所列名字必须真实存在。

背景（2026-09-27 审查）：这两个目录原先带自动生成的行号，实测 `game_state.py` 46/46、
`commands.py` 38/38 **行号全错**（偏移 +44~+335），反而误导；已改为**只列符号名**。
本测试守住"名字不漂移"这唯一的剩余风险（行号已不再出现）。
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

MODULES = ("core/game_state.py", "core/commands.py")
NAME_RE = re.compile(r"^#\s+(?:def|class|\.def)\s+(\S+)")


def _listed_and_existing(rel):
    path = os.path.join(_GAME_ROOT, rel)
    src = open(path, encoding="utf-8").read()
    listed, in_block = [], False
    for line in src.splitlines():
        if line.startswith("# ══ 目录（"):
            in_block = True
            continue
        if line.startswith("# ══ 目录结束"):
            in_block = False
            continue
        if in_block:
            m = NAME_RE.match(line)
            if m:
                listed.append(m.group(1))
    tree = ast.parse(src)
    top = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    methods = set()
    for n in tree.body:
        if isinstance(n, ast.ClassDef):
            methods |= {f.name for f in n.body
                        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return listed, top | methods


@pytest.mark.parametrize("rel", MODULES)
def test_doc_index_names_exist(rel):
    listed, existing = _listed_and_existing(rel)
    assert listed, f"{rel} 的目录块为空或未匹配（格式变更？）"
    missing = [n for n in listed if n not in existing]
    assert not missing, f"{rel} 目录列出了不存在的符号：{missing}"
