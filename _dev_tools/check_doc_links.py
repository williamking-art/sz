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
             ".cloudbase", ".codebuddy", ".mnemon", ".agents", "songzuo",
             # 纸娃娃实验目录（用户裁定冻结，不在文档门禁范围）
             "paperdoll_experiment"}


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