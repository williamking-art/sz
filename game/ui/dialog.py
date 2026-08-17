# -*- coding: utf-8 -*-
"""宋祚 · 游戏内自制弹窗（替代原生 tkinter.messagebox）。

统一宋式视觉：宣纸底 / 朱红印章 / 楷体标题 / 描金圆角按钮，
模态阻塞行为与原 messagebox 一致（grab_set + wait_window）。

设计约束（分层纪律）：
- 仅消费 ui.gui_common / ui.theme 的主题常量与绘制工具，
  不反向 import core / ai / content / backend，也不依赖 panels_* 的实例方法。
- 提供 show_info / show_warning / show_error / ask_yesno / ask_yesnocancel，
  首参统一为 parent（Tk 容器），返回语义与原 messagebox 对齐。
"""
import tkinter as tk
from tkinter import font as tkfont

from ui.gui_common import (
    PAPER, CARD, INK, DIM, RED, RED_D, GOLD, BORDER, SEAL_BG, KAI, SANS,
)
from ui.theme import GOLD_LIGHT, round_rect

# 四类弹窗的印章色块（左侧竖条 / 图标底）
_COLORS = {
    "info":    "#3f6f8f",   # 青蓝（告）
    "warning": "#b5802a",   # 赭黄（警）
    "error":   "#8a2b22",   # 深朱（误）
    "ask":     "#4a3a22",   # 墨褐（问）
}
_LABELS = {
    "info": "告", "warning": "警", "error": "误", "ask": "问",
}
_TITLE_FG = {
    "info": "#3f6f8f", "warning": "#b5802a", "error": RED, "ask": INK,
}


def _font(family, size, *weight):
    if weight:
        return (family, size, weight[0])
    return (family, size)


def _round_button(parent, text, command, kind="ok"):
    """宋式描金圆角按钮（不依赖 panels 实例方法，独立可复用）。"""
    w, h = 132, 38
    cv = tk.Canvas(parent, width=w, height=h, bg=CARD, highlightthickness=0)
    state = {"hover": False}

    def draw():
        cv.delete("all")
        r = 9
        if kind == "cancel" and not state["hover"]:
            bg, outline, fg = PAPER, BORDER, INK
        else:
            bg, outline, fg = (RED_D if state["hover"] else RED), GOLD_LIGHT, "#f3e6c4"
        round_rect(cv, 2, 2, w - 2, h - 2, r, fill=bg, outline=outline, width=2)
        round_rect(cv, 6, 6, w - 6, h - 6, max(1, r - 3),
                   outline=GOLD_LIGHT if state["hover"] else BORDER, width=1)
        cv.create_text(w // 2, h // 2, text=text, fill=fg, font=_font(KAI, 14, "bold"))

    def fire():
        draw()
        command()

    draw()
    cv.bind("<Enter>", lambda e: (state.update(hover=True), draw()))
    cv.bind("<Leave>", lambda e: (state.update(hover=False), draw()))
    cv.bind("<Button-1>", lambda e: fire())
    return cv


def _build_dialog(parent, kind, title, message, buttons):
    """通用弹窗构造。buttons: list of (text, kind, return_value)。

    返回 (toplevel, result_holder dict)。
    """
    root = parent
    while root is not None and not isinstance(root, tk.Tk):
        try:
            root = root.nametowidget(root.winfo_parent())
        except Exception:
            root = getattr(parent, "master", None)
            if root is None:
                break

    win = tk.Toplevel(parent)
    win.overrideredirect(True)
    win.configure(bg=PAPER)
    win.attributes("-topmost", True)

    result = {"value": None}

    # 内容测量（按文字宽度估算）
    lines = []
    for paragraph in message.split("\n"):
        lines.append(paragraph)
    msg_font = _font(SANS, 12)
    approx_w = max([tkfont.Font(name=msg_font[0], size=msg_font[1]).measure(ln)
                    for ln in lines] + [120])
    body_w = max(300, min(520, approx_w + 60))
    win_w = body_w + 40
    win_h = 150 + 22 * max(1, len(lines))

    # 外壳（描金双线圆角）
    outer = tk.Canvas(win, width=win_w, height=win_h, bg=SEAL_BG,
                      highlightthickness=0)
    outer.pack(padx=0, pady=0)
    round_rect(outer, 1, 1, win_w - 1, win_h - 1, 14, fill=PAPER, outline=GOLD, width=2)
    round_rect(outer, 6, 6, win_w - 6, win_h - 6, 11, outline=BORDER, width=1)

    # 标题区（左侧印章色块 + 楷体标题）
    accent = _COLORS[kind]
    outer.create_rectangle(20, 22, 56, 58, fill=accent, outline=accent)
    outer.create_text(38, 40, text=_LABELS[kind], fill="#f3e6c4",
                      font=_font(KAI, 18, "bold"))
    outer.create_text(70, 40, text=title, fill=_TITLE_FG[kind],
                      font=_font(KAI, 17, "bold"), anchor="w")

    # 正文
    outer.create_text(38, 88, text=message, fill=INK, font=msg_font,
                      anchor="nw", width=body_w)

    # 按钮区
    btn_frame = tk.Frame(win, bg=PAPER)
    btn_frame.place(x=0, y=win_h - 52, width=win_w, height=44)

    def close(v):
        result["value"] = v
        win.grab_release()
        win.destroy()

    for text, bkind, rv in buttons:
        b = _round_button(btn_frame, text, lambda rv=rv: close(rv), kind=bkind)
        b.pack(side="right", padx=10)

    # 居中于父窗口
    win.update_idletasks()
    if root is not None:
        px, py = root.winfo_rootx(), root.winfo_rooty()
        pw, ph = root.winfo_width(), root.winfo_height()
        x = px + (pw - win_w) // 2
        y = py + (ph - win_h) // 2
    else:
        x = (win.winfo_screenwidth() - win_w) // 2
        y = (win.winfo_screenheight() - win_h) // 2
    win.geometry(f"{win_w}x{win_h}+{x}+{y}")

    win.grab_set()
    win.focus_set()
    return win, result


def show_info(parent, title, message):
    win, res = _build_dialog(parent, "info", title, message,
                            [("确定", "ok", None)])
    win.wait_window(win)
    return None


def show_warning(parent, title, message):
    win, res = _build_dialog(parent, "warning", title, message,
                            [("确定", "ok", None)])
    win.wait_window(win)
    return None


def show_error(parent, title, message):
    win, res = _build_dialog(parent, "error", title, message,
                            [("确定", "ok", None)])
    win.wait_window(win)
    return None


def ask_yesno(parent, title, message):
    """返回 True（是）/ False（否）。与原 messagebox.askyesno 对齐。"""
    win, res = _build_dialog(parent, "ask", title, message,
                            [("是", "ok", True), ("否", "cancel", False)])
    win.wait_window(win)
    return res["value"]


def ask_yesnocancel(parent, title, message):
    """返回 True（是）/ False（否）/ None（取消）。对齐 askyesnocancel。"""
    win, res = _build_dialog(parent, "ask", title, message,
                            [("是", "ok", True), ("否", "cancel", False),
                             ("取消", "cancel", None)])
    win.wait_window(win)
    return res["value"]


class MsgProxy:
    """实例级适配器：让 panels 内可写成 self.messagebox.showinfo(...) 而无需传 parent。

    自动以宿主实例的 self.root（Tk 主窗口）作为弹窗父级，
    从而复用 dialog 模块且零侵入调用点（仅把 messagebox 前缀改为 self.messagebox）。
    """

    def __init__(self, host):
        self._host = host

    @property
    def _parent(self):
        return getattr(self._host, "root", None) or self._host

    def showinfo(self, title, message):
        return show_info(self._parent, title, message)

    def showwarning(self, title, message):
        return show_warning(self._parent, title, message)

    def showerror(self, title, message):
        return show_error(self._parent, title, message)

    def askyesno(self, title, message):
        return ask_yesno(self._parent, title, message)

    def askyesnocancel(self, title, message):
        return ask_yesnocancel(self._parent, title, message)
