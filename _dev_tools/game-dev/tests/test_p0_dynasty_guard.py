# -*- coding: utf-8 -*-
"""P0 朝代字面量守卫：core/content 里的宋/路/1101 等只降不升（存量基线棘轮）。"""
from __future__ import annotations

import ast
import json
import os
from collections import Counter
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
BASELINE = Path(__file__).with_name("testdata") / "dynasty_literals_baseline.json"
PATTERNS = ("宋", "路", "州府", "治所", "交子", "榷场", "市舶", "岁币", "1101", "song_", "SONG_")
SKIP_DIRS = {"__pycache__", "node_modules", ".git"}


def _count_file(path: Path) -> Counter:
    c = Counter()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return c
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for pat in PATTERNS:
                if pat in node.value:
                    c[pat] += 1
        elif isinstance(node, ast.Name):
            for pat in PATTERNS:
                if pat in node.id:
                    c[pat] += 1
        elif isinstance(node, ast.Attribute):
            for pat in PATTERNS:
                if pat in node.attr:
                    c[pat] += 1
    return c


def _scan() -> dict:
    out = {}
    for base in ("game/core", "game/content"):
        root = REPO / base
        for path in sorted(root.rglob("*.py")):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            c = _count_file(path)
            if c:
                out[str(path.relative_to(REPO)).replace("\\", "/")] = dict(c)
    return out


def test_dynasty_literals_ratchet():
    cur = _scan()
    if os.environ.get("DYNASTY_GUARD_WRITE") == "1":
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(cur, ensure_ascii=False, indent=1, sort_keys=True),
                            encoding="utf-8")
        pytest.skip("已写入朝代字面量基线")

    assert BASELINE.is_file(), "缺基线；用 DYNASTY_GUARD_WRITE=1 生成"
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    bad = []
    for f, counts in cur.items():
        old = base.get(f, {})
        for pat, n in counts.items():
            if n > int(old.get(pat, 0)):
                bad.append("%s: %s %s→%s" % (f, pat, old.get(pat, 0), n))
    assert not bad, "新增朝代字面量（应改用中性 ID/适配层）：\n" + "\n".join(bad[:20])
