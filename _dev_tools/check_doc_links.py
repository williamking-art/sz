#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查仓库内 Markdown 相对链接是否断链（2026-10-18 全审门禁）。

用法：
    python _dev_tools/check_doc_links.py [--root <repo>]
退出码：0=无断链；1=存在断链。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.parse

SKIP_PREFIX = ("http://", "https://", "mailto:", "tel:", "file:", "data:", "#")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
SKIP_DIRS = {".git", "node_modules", "__pycache__", "dist", "build", ".venv",
             ".audit-venv", "target", ".pytest_cache", ".ruff_cache",
             # 生成/临时/归档副本：不是仓库文档，断链不计
             "_scratch", "scratch", "tmp", "_ming_probe", ".qoder",
             # `.cloudbase` 是**历史残留目录**（CloudBase 已于 2026-10-22 停用，云侧迁阿里云；
             # 见 mcp-songzuo/README.md 与 docs/开发服务器与回归测试说明.md §8.8），
             # 保留跳过以便本机旧目录仍在时不被当作文档目录扫描。
             ".cloudbase", ".codebuddy", ".mnemon", ".agents", "songzuo",
             # 纸娃娃实验目录（用户裁定冻结，不在文档门禁范围）
             "paperdoll_experiment",
             # 历史归档（AGENTS §1：archive 为**只读留档，勿改勿删**）
             # —— 2026-10-21 归档时相对链接未重写，实测 15 处断链全部落在
             #    `archive/2026-10-21-historical/`（指向已迁走的 specs/docs/analysis）。
             #    按"历史档不追改"的既有规矩跳过；现行文档断链仍会被本脚本拦下。
             "archive",
             # vendored 第三方仓库的**本机副本**：deepseek-ai/deepseek-harness 及其市场件。
             # 两者 `git ls-files` 均为 **0**（不在本仓库内），本机解包后会被 os.walk
             # 从仓库根扫到；其内部相对链接断不断不归我们管。实测（2026-10-23）37 处
             # 断链**全部**落在这两处，使门禁在本机恒失败（EXIT=1）——而干净克隆/CI
             # 没有这两个目录、本来会通过 ⇒ 属"本机噪声淹没真信号"，与 .cloudbase 同理。
             # 我们自己的文档实测 0 断链（2186 个 md）。
             "deepseek-harness-master", "dsh-market"}


def iter_markdown(root: str):
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            if fn.lower().endswith(".md"):
                yield os.path.join(dp, fn)


def check(root: str) -> list[tuple[str, str, str]]:
    broken = []
    for path in iter_markdown(root):
        try:
            text = open(path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for raw in LINK_RE.findall(text):
            target = raw.strip().strip("<>").split()[0] if raw.strip() else ""
            if not target or target.startswith(SKIP_PREFIX):
                continue
            if "{{" in target or "$" in target:
                continue
            target = urllib.parse.unquote(target.split("#", 1)[0])
            if not target:
                continue
            if target.startswith("/"):
                resolved = os.path.join(root, target.lstrip("/\\"))
            else:
                resolved = os.path.normpath(os.path.join(os.path.dirname(path), target))
            if not os.path.exists(resolved):
                broken.append((os.path.relpath(path, root), raw, resolved))
    return broken


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    broken = check(root)
    total = sum(1 for _ in iter_markdown(root))
    print(f"doc-links: {total} md, broken={len(broken)}")
    for src, raw, resolved in broken[:50]:
        print(f"  BROKEN {src}: {raw} -> {os.path.relpath(resolved, root)}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())