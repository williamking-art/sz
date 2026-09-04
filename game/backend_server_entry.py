# -*- coding: utf-8 -*-
"""Songzuo backend.server PyInstaller entry point."""
import sys
import os

# PyInstaller 冻结环境下：资源根 = exe 同级目录
if getattr(sys, "frozen", False):
    root = os.path.dirname(os.path.abspath(sys.executable))
    os.chdir(root)
    # 打包后的模块都在 exe 内部，直接 import 即可
    sys.path.insert(0, root)

from backend.server import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main() or 0)
