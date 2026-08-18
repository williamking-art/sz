# -*- coding: utf-8 -*-
"""宋祚 · GUI basic 面板 Mixin。

通用控件工厂 / 主题样式 / 资源加载 / 浮层底座。
共享常量与工具见 ui.gui_common。
"""
import os
import sys
import tkinter as tk
import ui.theme as theme
from ui.gui_common import (PAPER, PAPER2, CARD, INK, DIM, RED, RED_D, GOLD, GREEN,
    BORDER, SEAL_BG, KAI, SANS, DECREE_CATEGORIES,
    _bar, _format_effects, _judge_effects)
from ui.theme import GOLD_LIGHT, round_rect
from ui.dialog import MsgProxy

# 字号全局缩放：由「杂项设置」font_scale 档位(0/1/2)决定倍率，作用于所有 _font 工厂
_FONT_SCALE_TABLE = {0: 0.85, 1: 1.0, 2: 1.15}
_FONT_MIN_SIZE = 6
_FONT_MAX_SIZE = 96


class PanelsBasicMixin:
    @property
    def messagebox(self):
        """宋式游戏内弹窗适配器（替代原生 tkinter.messagebox）。

        调用处写法从 messagebox.showinfo(...) 改为 self.messagebox.showinfo(...)，
        父窗口自动取 self.root，无需改动分支逻辑。
        """
        if not hasattr(self, "_msgbox_proxy"):
            self._msgbox_proxy = MsgProxy(self)
        return self._msgbox_proxy

    def _font(self, family, size, *weight):
        """字号工厂：按 font_scale 档位全局缩放，统一字族来源。

        family: 'KAI' | 'SANS' | 任意字体名字符串
        size:   原始字号（int/float）
        weight: 可选第 3 参（如 "bold"），原样透传；无则不附加
        返回:   (实际字体名, 缩放后字号[, "bold"]) 三元组或二元组
        """
        scale = getattr(self, "_font_scale", 1.0)
        actual = getattr(self, "_kai_actual", "KaiTi")
        fam = actual if family == "KAI" else family  # KAI 用实例解析后的楷体名
        scaled = max(_FONT_MIN_SIZE, min(_FONT_MAX_SIZE, int(round(size * scale))))
        if weight:
            return (fam, scaled, weight[0])
        return (fam, scaled)

    def _load_font_scale(self):
        """读取「杂项设置」字号档位（0/1/2 → 倍率），存 self._font_scale。"""
        try:
            idx = int(self._misc_get("font_scale", 1))
        except Exception:
            idx = 1
        self._font_scale = _FONT_SCALE_TABLE.get(idx, 1.0)

    def _resource(self, name):
        if getattr(sys, "frozen", False):
            exe = os.path.join(os.path.dirname(sys.executable), name)
            if os.path.exists(exe):
                return exe
            # 打包时 resources 在 _MEIPASS（含 assets/ 子目录）
            if hasattr(sys, "_MEIPASS"):
                for cand in (os.path.join(sys._MEIPASS, name),
                             os.path.join(sys._MEIPASS, "assets", name)):
                    if os.path.exists(cand):
                        return cand
        proj = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", name)
        if os.path.exists(proj):
            return proj
        # 回退：assets/ 下（开发态图标等本体资源）
        ast = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", name)
        return ast

    def _scrollable_frame(self, parent, bg=None):
        """返回 (container, content) 的轻量滚动容器；content 用于放置实际子控件。"""
        if bg is None:
            bg = parent["bg"] if parent["bg"] else PAPER
        container = tk.Frame(parent, bg=bg)
        canvas = tk.Canvas(container, bg=bg, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=bg)
        content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw", width=0)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        # 鼠标滚轮
        def _on_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        container.bind("<Enter>", lambda e: container.bind_all("<MouseWheel>", _on_wheel))
        container.bind("<Leave>", lambda e: container.unbind_all("<MouseWheel>"))
        return container, content

    def _label(self, parent, text, fg=INK, bg=None, font=None, anchor="w", **kw):
        if font is None:
            font = self._font(SANS, 11, "bold")
        if bg is None:
            bg = parent["bg"] if parent["bg"] else PAPER
        return tk.Label(parent, text=text, fg=fg, bg=bg, font=font, anchor=anchor, **kw)

    def _title(self, parent, text, fg=RED, bg=None, font=None, **kw):
        if font is None:
            font = self._font(KAI, 18, "bold")
        return self._label(parent, text, fg=fg, bg=bg, font=font, **kw)

    def _seal_btn(self, parent, text, command, big=False):
        """仿 .ie-seal 印章按钮：朱红方印 + 楷体 + 微浮雕阴影。"""
        bg = RED if big else SEAL_BG
        w = 16 if big else 13
        h = 2 if big else 1
        b = tk.Button(
            parent, text=text, command=command, width=w, height=h,
            bg=bg, fg="#f3e6c4", activebackground=RED_D, activeforeground="#f3e6c4",
            relief="flat", font=self._font(KAI, 14 if big else 12, "bold"),
            cursor="hand2", highlightthickness=0, bd=0,
            disabledforeground="#e0c9a0",
        )
        b.bind("<Enter>", lambda e: b.configure(bg=RED_D))
        b.bind("<Leave>", lambda e: b.configure(bg=bg if not big else RED))
        return b

    def _btn(self, parent, text, command, width=14, gold=False, ghost=False):
        """次级按钮：描金实心 / 幽灵描边。"""
        if gold:
            bg, fg = GOLD, INK
            abg, afg = "#d9b25a", INK
        elif ghost:
            bg, fg = PAPER2, RED_D
            abg, afg = "#e7d6ad", RED_D
        else:
            bg, fg = CARD, RED_D
            abg, afg = "#f1e7cf", RED_D
        return tk.Button(
            parent, text=text, command=command, width=width,
            bg=bg, fg=fg, activebackground=abg, activeforeground=afg,
            relief="flat", font=self._font(SANS, 11, "bold"), cursor="hand2",
            highlightthickness=0, bd=1,
        )

    def _card(self, parent, padx=14, pady=12, **kw):
        """仿 .ie-card：米白宣纸 + 描边 + 圆角（tk 用 ridge 近似圆角感）。"""
        f = tk.Frame(parent, bg=CARD, relief="ridge", bd=1,
                     highlightbackground=BORDER, highlightthickness=1)
        return f

    def _meter(self, parent, value, maxv=100, width=160, height=12, label=None):
        """可视化圆角进度条（仿仪表面板），返回 canvas 供刷新。
        进度条随父容器宽度伸缩（响应式）。"""
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", padx=14, pady=3)
        cv = tk.Canvas(row, width=width, height=height, bg=CARD,
                       highlightthickness=0)
        cv.pack(side="left", fill="x", expand=True)
        txt = self._label(row, "", fg=INK, bg=CARD, font=self._font(SANS, 11))
        txt.pack(side="left", padx=8)
        if label is not None:
            self._label(row, label, fg=DIM, bg=CARD, font=self._font(SANS, 11)).pack(side="right", padx=8)
        ratio = max(0, min(100, value / maxv * 100)) if maxv else 0
        txt.configure(text=f"{int(value)} / {int(maxv)}  ({int(ratio)}%)")

        def _draw(ev=None):
            w = cv.winfo_width() or width
            cv.delete("all")
            theme.progress_bar(cv, 0, 0, w, height, value, maxv)

        cv.bind("<Configure>", _draw)
        _draw()
        return cv

    def _card_title(self, card, text):
        """卡片标题 + 下划金线（装饰）。"""
        self._title(card, text, fg=RED_D, bg=CARD, font=self._font(KAI, 13, "bold"),
                    anchor="center").pack(pady=(8, 2))
        cv = tk.Canvas(card, height=3, bg=CARD, highlightthickness=0)
        cv.pack(fill="x", padx=20, pady=(0, 4))
        cv.create_line(0, 1, 9999, 1, fill=GOLD, width=2)

    def _card_title2(self, parent, text):
        """面板内小节标题（左对齐红字，下划金线）。"""
        self._title(parent, text, fg=RED, bg=PAPER, font=self._font(KAI, 14, "bold"),
                    anchor="w").pack(anchor="w", padx=12, pady=(10, 4))
        cv = tk.Canvas(parent, height=3, bg=PAPER, highlightthickness=0)
        cv.pack(fill="x", padx=12, pady=(0, 2))
        cv.create_line(0, 1, 9999, 1, fill=GOLD, width=2)

    def _scrolled(self, parent, scrollbar=True, **kw):
        bg = kw.pop("bg", CARD)
        fg = kw.pop("fg", INK)
        wrap = kw.pop("wrap", "word")
        font = kw.pop("font", None)
        if font is None:
            font = self._font(SANS, 10)
        padx = kw.pop("padx", 12)
        pady = kw.pop("pady", 12)
        frame = tk.Frame(parent, bg=bg, **kw)
        txt = tk.Text(frame, bg=bg, fg=fg, relief="flat", wrap=wrap, font=font,
                      padx=padx, pady=pady, insertbackground=INK, selectbackground=GOLD,
                      selectforeground=INK, highlightthickness=0, bd=0)
        if scrollbar:
            sb = tk.Scrollbar(frame, command=txt.yview, bg=PAPER2, troughcolor=PAPER,
                              activebackground=GOLD)
            txt.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            txt.pack(side="left", fill="both", expand=True)
        else:
            txt.pack(fill="both", expand=True)
        frame._text = txt
        return frame

    def _overlay(self, title, width=820, height=620):
        """返回 (toplevel, body_frame)。半透明遮罩 + 居中宣纸卡片。
        同时只保留一个弹层，避免重复打开堆叠。"""
        if self._active_overlay is not None and self._active_overlay.winfo_exists():
            self._active_overlay.destroy()
            self._active_overlay = None

        tl = tk.Toplevel(self.root)
        tl.title(title)
        # 隐藏系统窗口栏，仅保留游戏内朱红标题栏与「✕ 关」按钮
        try:
            tl.overrideredirect(True)
        except Exception:
            pass
        pw, ph = self.root.winfo_width(), self.root.winfo_height()
        px, py = self.root.winfo_x(), self.root.winfo_y()
        x = px + max(0, (pw - width) // 2)
        y = py + max(0, (ph - height) // 5)
        tl.geometry(f"{width}x{height}+{x}+{y}")
        tl.configure(bg="#140e0a")
        tl.attributes("-alpha", 1.0)
        tl.transient(self.root)
        tl.grab_set()

        def _close_overlay():
            if self._active_overlay is tl:
                self._active_overlay = None
            tl.destroy()

        # 遮罩层
        mask = tk.Frame(tl, bg="#140e0a")
        mask.place(x=0, y=0, relwidth=1, relheight=1)
        mask.bind("<Button-1>", lambda e: None)  # 吞掉点击

        panel = tk.Frame(tl, bg=PAPER, relief="ridge", bd=2,
                         highlightbackground=GOLD, highlightthickness=2)
        panel.place(relx=0.5, rely=0.5, anchor="center",
                    width=min(width - 24, int(self.root.winfo_width() * 0.92)),
                    height=min(height - 24, int(self.root.winfo_height() * 0.9)))

        head = tk.Frame(panel, bg=RED)
        head.pack(fill="x")
        self._title(head, title, fg="#f3e6c4", bg=RED, font=self._font(KAI, 18, "bold")).pack(
            side="left", padx=18, pady=12)
        close = self._btn(head, "✕ 关", _close_overlay, width=8, ghost=True)
        close.pack(side="right", padx=14, pady=10)

        body = tk.Frame(panel, bg=PAPER)
        body.pack(fill="both", expand=True, padx=14, pady=12)

        self._active_overlay = tl
        tl.protocol("WM_DELETE_WINDOW", _close_overlay)

        tl.deiconify()
        tl.lift(self.root)
        tl.focus_force()
        tl.attributes("-topmost", True)
        tl.attributes("-topmost", False)
        return tl, body

    def _round_icon_btn(self, parent, text, command, icon=None,
                         icon_family="dock", text_color="#f3e6c4",
                         pack_side="left", pack_pady=0):
        """绘制圆形图标按钮（仿崇祯模拟器底部 dock）。

        接 Agnes 生成的透明 PNG 图标，含呼吸/悬浮发光/点击波纹/AI 加载环动效。
        icon: 图标键名（对应 assets/ui/{icon_family}_{icon}.png），缺省用单字。
        icon_family: "dock" / "nav" / "func" 之一，决定文件名前缀。
        text_color: 图标下方文字颜色（dock 默认米白，nav 可用墨色）。
        """
        size = 72
        pad = 10
        cv = tk.Canvas(parent, width=size, height=size, bg=PAPER,
                       highlightthickness=0)
        cv.pack(side=pack_side, padx=pad, pady=pack_pady)
        # 加载透明图标
        img = None
        if icon:
            try:
                path = self._resource(f"ui/{icon_family}_{icon}.png")
                if path and os.path.exists(path):
                    from PIL import Image, ImageTk
                    pil_img = Image.open(path).convert("RGBA")
                    icon_size = max(24, size - 28)
                    pil_img = pil_img.resize((icon_size, icon_size), Image.LANCZOS)
                    tk_img = ImageTk.PhotoImage(pil_img)
                    # 若带白底则抠底（theme.remove_white_bg 期望 tk.PhotoImage）
                    try:
                        theme.remove_white_bg(tk_img)
                    except Exception:
                        pass
                    img = tk_img
                    cv._icon_img = img  # 保持引用，防止被 GC 回收
            except Exception:
                img = None
        state = {"hover": False, "click": 0, "seq": 0, "loading": False, "alive": True}

        def draw():
            cv.delete("all")
            r = size / 2
            cx = cy = r
            pulse = 1 + 0.04 * state["hover"]  # hover 微放大
            rr = (r - 4) * pulse
            bg = RED if state["hover"] else CARD
            outline = GOLD if state["hover"] else BORDER
            ow = 3 if state["hover"] else 2
            cv.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, fill=bg,
                           outline=outline, width=ow)
            # 图标（透明 PNG）
            if img:
                try:
                    cv.create_image(cx, cy - 6, image=img)
                except Exception:
                    pass
            # 单字（图标缺失时回退）
            if not img:
                cv.create_text(cx, cy - 8, text=text[0], fill="#f3e6c4",
                               font=self._font(KAI, 18, "bold"))
            cv.create_text(cx, size - 10, text=text, fill=text_color,
                           font=self._font(SANS, 9, "bold"))
            # 呼吸光晕（静止时缓慢脉动）
            breath = (state["seq"] % 60) / 60.0
            glow = int(40 + 25 * (1 - abs(breath - 0.5) * 2))
            cv.create_oval(cx - rr + 2, cy - rr + 2, cx + rr - 2, cy + rr - 2,
                           outline="#caa24a", width=1, stipple="gray75")
            # 点击波纹
            if state["click"] > 0:
                cr = rr + (8 - state["click"]) * 3
                cv.create_oval(cx - cr, cy - cr, cx + cr, cy + cr,
                               outline=GOLD, width=2)
                state["click"] -= 1
            # AI 加载旋转环
            if state["loading"]:
                a0 = (state["seq"] * 12) % 360
                cv.create_arc(cx - rr + 4, cy - rr + 4, cx + rr - 4, cy + rr - 4,
                              start=a0, extent=90, style="arc",
                              outline=GOLD, width=2)

        def step(seq):
            state["seq"] = seq
            try:
                draw()
            except Exception:
                pass

        draw()
        self.register_anim(type("Anim", (), {"step": step, "alive": True})())
        cv.bind("<Enter>", lambda e: (state.update({"hover": True})))
        cv.bind("<Leave>", lambda e: (state.update({"hover": False})))
        cv.bind("<Button-1>", lambda e: (state.update({"click": 8}), command()))

        # 暴露加载态控制（AI 调用时设 loading）
        cv._set_loading = lambda v: state.update({"loading": bool(v)})

    def _endturn_btn(self, parent):
        """右下角大红色“回合推演”按钮。"""
        size = 96
        cv = tk.Canvas(parent, width=size, height=size, bg=PAPER, highlightthickness=0)
        cv.pack()

        def draw(active=False):
            cv.delete("all")
            bg = RED_D if active else RED
            cv.create_oval(4, 4, size-4, size-4, fill=bg, outline=GOLD, width=3)
            cv.create_text(size/2, size/2-2, text="回合", fill="#f3e6c4",
                           font=self._font(KAI, 14, "bold"))
            cv.create_text(size/2, size/2+16, text="推演", fill="#f3e6c4",
                           font=self._font(KAI, 14, "bold"))

        draw(False)
        cv.bind("<Enter>", lambda e: draw(True))
        cv.bind("<Leave>", lambda e: draw(False))
        cv.bind("<Button-1>", lambda e: self._ui_next_turn())

    def _song_button(self, parent, text, command, width=160, height=40,
                     font=None, focus=False):
        """宋式描金圆角长按钮（主菜单/结局等长条按钮）。

        常态：宣纸色底 + 描金双线边框 + 墨色字。
        悬浮：朱红底 + 高亮金边 + 米白字。
        """
        if font is None:
            font = self._font(KAI, 14)
        wrap = tk.Frame(parent, bg="#0f0b08", highlightthickness=0)
        cv = tk.Canvas(wrap, width=width, height=height, bg="#0f0b08",
                       highlightthickness=0)
        cv.pack()

        def draw(hover=False):
            cv.delete("all")
            r = 10
            bg = RED if hover else CARD
            outline = GOLD_LIGHT if hover else GOLD
            ow = 3 if hover else 2
            # 外框
            theme.round_rect(cv, 2, 2, width - 2, height - 2, r, fill=bg,
                       outline=outline, width=ow)
            # 内细金线
            theme.round_rect(cv, 6, 6, width - 6, height - 6, max(1, r - 3),
                       outline=GOLD_LIGHT if hover else BORDER, width=1)
            # 文字
            fg = "#f3e6c4" if hover else INK
            cv.create_text(width // 2, height // 2, text=text, fill=fg,
                           font=font)

        draw(False)
        cv.bind("<Enter>", lambda e: draw(True))
        cv.bind("<Leave>", lambda e: draw(False))
        cv.bind("<Button-1>", lambda e: (draw(True), command()))
        if focus:
            cv.bind("<Return>", lambda e: command())
            cv.focus_set()
        return wrap

