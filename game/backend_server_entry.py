# -*- coding: utf-8 -*-
"""Songzuo backend.server PyInstaller entry point.

⚠️ 2026-09-27 修（用户实测崩溃）：PyInstaller 以 `console=False`（无控制台）打包时，
**`sys.stdout` / `sys.stderr` / `sys.stdin` 可能是 None**；而 uvicorn 的默认日志 formatter
会调 `sys.stdout.isatty()` → `AttributeError: 'NoneType' object has no attribute 'isatty'`，
表现为「Failed to execute script 'backend_server_entry'」弹窗直接崩掉。

  为什么 Electron 启动时没崩：主进程用管道 spawn（stdout/stderr 是管道对象而非 None）；
  但**用户双击这个 exe**（无控制台、无管道）时必崩 —— 所以必须在入口处兜底。

兜底策略：三者任一为 None 时指向 `os.devnull`：进程照常起服务（只是没有控制台输出），
而不是崩给用户看。
"""
import os
import sys

# --- 无控制台（PyInstaller console=False / pythonw / 双击）时的 stdio 兜底 ---
# 必须在 import uvicorn / 配置 logging **之前**执行。
for _name in ("stdin", "stdout", "stderr"):
    if getattr(sys, _name, None) is None:
        try:
            setattr(sys, _name, open(os.devnull, "r" if _name == "stdin" else "w",
                                     encoding="utf-8"))
        except OSError:
            pass

# PyInstaller 冻结环境下：资源根 = exe 同级目录
if getattr(sys, "frozen", False):
    root = os.path.dirname(os.path.abspath(sys.executable))
    os.chdir(root)
    # 打包后的模块都在 exe 内部，直接 import 即可
    sys.path.insert(0, root)

from backend.server import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main() or 0)
