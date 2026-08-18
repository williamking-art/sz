# -*- coding: utf-8 -*-
"""宋祚 · GUI 版入口

双击 / exe 启动后运行的窗口程序。仅负责创建 tkinter 主窗口并加载 GUI 应用。
"""
import os
import sys
import traceback

import tkinter as tk
from ui.gui import SongZuoApp


def _log_path():
    """exe / 源码 同目录下的运行日志路径，便于排查启动异常。

    单文件(frozen)模式下 sys.argv[0] 指向临时解包目录，故改用 sys.executable
    所在目录，保证日志落在 EXE 同级目录。
    """
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "songzuo_runtime.log")


def main():
    log = _log_path()
    try:
        root = tk.Tk()

        # 捕获 tkinter 回调（mainloop 运行期）里的未处理异常，写入日志
        def _report_cb_exc(exc_type, exc_value, exc_tb):
            try:
                with open(log, "a", encoding="utf-8") as f:
                    f.write("\n[CRASH] callback exception " + "-" * 30 + "\n")
                    f.write("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
            except Exception:
                pass
            # 仍弹窗提示用户
            try:
                import tkinter.messagebox as mb
                mb.showerror("宋祚 · 运行错误",
                             f"运行中出现异常：\n{exc_value}\n\n详情见 songzuo_runtime.log")
            except Exception:
                pass

        root.report_callback_exception = _report_cb_exc

        SongZuoApp(root)
        # 标记：GUI 初始化成功
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"[OK] init passed, title={root.title()!r}, geometry={root.geometry()}\n")
        root.mainloop()
    except Exception:
        with open(log, "a", encoding="utf-8") as f:
            f.write("\n[CRASH] " + "-" * 40 + "\n")
            f.write(traceback.format_exc())
            f.write("\n")
        # 若有 GUI，再尝试弹错误提示（不影响日志）
        try:
            import tkinter.messagebox as mb
            mb.showerror("宋祚 · 启动失败",
                         "初始化失败，详情见 songzuo_runtime.log")
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
