#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""仓库完整性门禁（2026-10-18 全审）。

检查：
1. 不存在「tracked 文件被删除」（git status 的 ` D`）；
2. `_dev_tools/game-dev/tests/` 下没有未跟踪的 test_*.py
   （默认仅告警；`--strict` 时判失败 —— 发版/CI 用 strict）；
3. 关键生产文件已被 git 跟踪（如 spatial_warehouse_bridge.py）；
4. 测试用例跟踪数下限（防扫描/入库失效）。

用法：python _dev_tools/check_repo_integrity.py [--strict]
退出码：0=通过；1=有硬问题（或 strict 下的未跟踪测试）。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(*args: str) -> str:
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="ignore")
    return p.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="未跟踪测试也判失败（发版/CI）")
    args = ap.parse_args()
    problems, warnings = [], []

    status = _git("status", "--porcelain=v1", "-uall")
    deleted = [ln[3:] for ln in status.splitlines() if ln.startswith(" D")]
    if deleted:
        problems.append(f"tracked 文件被删除 {len(deleted)} 个，例：{deleted[:3]}")

    untracked = _git("ls-files", "--others", "--exclude-standard",
                     "_dev_tools/game-dev/tests").splitlines()
    untracked_tests = [p for p in untracked
                       if os.path.basename(p).startswith("test_") and p.endswith(".py")]
    if untracked_tests:
        msg = f"测试目录有未跟踪用例 {len(untracked_tests)} 个：{untracked_tests[:3]}"
        (problems if args.strict else warnings).append(msg)

    tracked = set(_git("ls-files").splitlines())
    for key in (
        "game/core/foundation/ledger/spatial_warehouse_bridge.py",
        "game/core/settlement_pipeline.py",
        "game/core/domains/economy/market.py",
        "_dev_tools/game-dev/tests/test_audit_core_p0_fixes.py",
        "AGENTS.md",
    ):
        if key not in tracked:
            problems.append(f"关键文件未被 git 跟踪：{key}")

    if len([p for p in tracked if p.startswith("_dev_tools/game-dev/tests/test_")]) < 300:
        problems.append("测试用例跟踪数 <300（疑似扫描/入库失效）")

    print(f"repo-integrity: tracked={len(tracked)} "
          f"untracked_tests={len(untracked_tests)} deleted={len(deleted)} "
          f"strict={args.strict}")
    for w in warnings:
        print(f"  WARN {w}")
    for p in problems:
        print(f"  FAIL {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())