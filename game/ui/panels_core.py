# -*- coding: utf-8 -*-
"""宋祚 · GUI core 面板 Mixin。

游戏主界面骨架：dock / 右侧竖排 / 浮层栈 / 返回主菜单。共享常量与工具见 ui.gui_common。
"""
import os
import sys
import random
import tkinter as tk
import ui.theme as theme
from content.data import (PERSONAL_ACTIONS, FACTION_NAMES, YAMEN_LIST, YAMEN_INFO,
    PREFECTURE_LIST, FIXED_PROCEDURES)
from ai.client import AIClient, _org_by_affiliation
import ai.client as ai_decree
from core.commands import AIRuntimeError as _AIRuntimeError
from ui.gui_common import (PAPER, PAPER2, CARD, INK, DIM, RED, RED_D, GOLD, GREEN,
    BORDER, SEAL_BG, KAI, SANS, DECREE_CATEGORIES,
    _bar, _format_effects, _judge_effects)
from ui.theme import GOLD_LIGHT
from ui.gui_common import humanize_coin, humanize_land, humanize_households


class PanelsCoreMixin:
    def _build_game_screen(self):
        self._clear_all()
        c = self.container

        # ============================================================
        # 三层结构
        #   L0 舆图层  MapCanvas 常驻底层，全生命周期不销毁
        #   L1 常驻HUD 顶部状态条 / 左侧局势卡 / 底部dock / 回合推演
        #   L2 浮层栈 不透明宣纸卡片，直接在舆图上展开，关闭回纯舆图
        # ============================================================
        # —— L0 舆图层 ——
        from ui.map import MapCanvas
        self.map_layer = tk.Frame(c, bg=PAPER)
        self.map_layer.place(x=0, y=0, relwidth=1, relheight=1)
        self._map_cv = MapCanvas(self.map_layer, self.state, on_select=self._show_region_detail)
        self._map_cv.place(x=0, y=0, relwidth=1, relheight=1)
        # 主动触发一次 resize，避免依赖 MapCanvas.__init__ 内置的 80ms 延迟，
        # 防止容器尚未布局完成时读取到 winfo_width/height==1 导致 fit=0。
        self._map_cv.after(80, self._map_cv._resize_redraw)

        # —— L1 常驻 HUD ——
        self._build_hud(c)

        # —— L2 浮层宿主（默认隐藏）——
        self.overlay_host = tk.Frame(c, bg="")
        self.overlay_host.place_forget()
        self._overlay_stack = []          # 浮层 Frame 列表（L2）
        self._overlay_titles = []         # 与栈对应的标题文本

        # 浮层宿主同时作为面板内容的默认挂载点（self.main）
        self.main = self.overlay_host
        self._panel_shell_root = None

        # 绑定 Esc：有浮层时关闭最上层浮层；无浮层（纯舆图）时调出设置页面
        def _on_esc(_e=None):
            if getattr(self, "_overlay_stack", None):
                self._close_overlay()
            else:
                try:
                    self._open_overlay(self._panel_settings, "设 置")
                except Exception:
                    pass
        self.root.bind("<Escape>", _on_esc)

        self._refresh_status()
        if not self._inited:
            self._log(f"▶ {self.state.era_name}{self.state.year}年{self.state.month}月，新朝开局。"
                      f"可召对大臣、自拟诏令、总揽六部、巡抚州县。")
            self._inited = True
        for m in self._pending_logs:
            self._log(m)
        self._pending_logs = []

        # 进入游戏即落在纯舆图（L0）之上，仅显示常驻 HUD
        self._current_panel = "疆域主页"
        self._refresh_hud()

    def _build_hud(self, c):
        s = self.state
        # 顶部状态条：朱红徽章 + 年号季节 + 三枚数值胶囊
        top_bar = tk.Frame(c, bg=CARD, relief="ridge", bd=1,
                           highlightbackground=GOLD, highlightthickness=1)
        top_bar.place(x=234, y=12, relwidth=0.66, height=50, anchor="nw")
        self._hud_top = top_bar

        badge_cv = tk.Canvas(top_bar, width=46, height=46, bg=CARD, highlightthickness=0)
        badge_cv.pack(side="left", padx=(10, 6), pady=2)
        badge_cv.create_oval(4, 4, 42, 42, fill=RED, outline=GOLD, width=2)
        badge_cv.create_text(23, 23, text="宋", fill="#f3e6c4", font=self._font(KAI, 18, "bold"))
        self._hud_time = tk.Label(top_bar, fg=INK, bg=CARD, font=self._font(KAI, 14, "bold"))
        self._hud_time.pack(side="left", padx=6, pady=10)
        pill_frame = tk.Frame(top_bar, bg=CARD)
        pill_frame.pack(side="right", padx=10, pady=8)
        self._hud_pills = {}
        for icon, lab in [("◆", "威望"), ("♥", "民心"), ("◈", "国库"), ("⛃", "内帑")]:
            pill = tk.Frame(pill_frame, bg=CARD, relief="ridge", bd=1, highlightbackground=BORDER)
            pill.pack(side="left", padx=4)
            lab_w = tk.Label(pill, fg=INK, bg=CARD, font=self._font(SANS, 10, "bold"))
            lab_w.pack(padx=8, pady=3)
            self._hud_pills[lab] = (icon, lab_w)
            # T14：国库/内帑 pill 挂悬浮收支栏（鼠标进入显示、离开隐藏）
            # 判定区适度放大：pill 加大内边距（易触发），直接 bind 到 pill
            if lab in ("国库", "内帑"):
                lab_w.configure(padx=12, pady=6)
                if lab == "国库":
                    self._hud_tooltip(pill, "国 库 收 支", self._treasury_tooltip_lines)
                else:
                    self._hud_tooltip(pill, "内 帑 收 支", self._imperial_tooltip_lines)
        # token 用量（工程化可见性）
        token_lab = tk.Label(pill_frame, fg=DIM, bg=CARD, font=self._font(SANS, 9, "bold"))
        token_lab.pack(side="left", padx=(6, 0), pady=3)
        self._hud_token = token_lab

        # 左侧常驻在办栏（原左侧卡位置，悬浮于舆图之上）
        # 顶部状态条位于 y=12、height=50（含边框约 52，底边≈64），卡片 y 留足间隙避开
        left_card = tk.Frame(c, bg=CARD, relief="ridge", bd=1,
                             highlightbackground=GOLD, highlightthickness=1)
        left_card.place(x=12, y=88, width=220, relheight=0.5, anchor="nw")
        left_card.pack_propagate(False)
        self._hud_left = left_card
        self._card_title(left_card, "在 办")
        todo_content = tk.Frame(left_card, bg=CARD)
        todo_content.pack(fill="both", expand=True, padx=(4, 0), pady=(0, 4))
        self._hud_todo = todo_content

        # 右侧竖排按钮栏（州县/军政/科技/工程）—— 悬浮于舆图之上
        self._build_right_strip(c)

        # 底部命令 dock（朝堂/群臣/朝报/个人行止/拟旨 + 回合推演）
        self._build_dock(c)

    def _build_right_strip(self, c):
        """右侧竖排悬浮按钮栏：州县/仓廪/会计/军政/科技/工程。
        T-028：接入 nav_* 图标，统一圆钮视觉，图标下文字用墨色。"""
        strip = tk.Frame(c, bg=PAPER)
        strip.place(relx=1.0, y=70, x=-10, width=86, relheight=0.74, anchor="ne")
        self._right_strip = strip
        items = [
            ("州县", "province", self._panel_prefectures),
            ("仓廪", "overview", self._panel_granary),
            ("会计", "personnel", self._panel_accounting),
            ("民生", "overview", self._panel_pop),
            ("群臣", "ministers", self._panel_yamen),
            ("军政", "war", self._panel_military_affairs),
            ("科技", "tech", self._panel_tech),
            ("工程", "works", self._panel_engineering),
        ]
        for label, icon_key, fn in items:
            self._round_icon_btn(
                strip, label,
                lambda f=fn, t=label: self._open_overlay(f, t),
                icon=icon_key, icon_family="nav", text_color=INK,
                pack_side="top", pack_pady=8,
            )

    def _build_dock(self, c):
        """底部悬浮按键栏：5 功能圆钮 + 回合推演朱红大印。"""
        bottom_bar = tk.Frame(c, bg=PAPER)
        bottom_bar.place(relx=0.0, rely=1.0, x=12, y=-14, anchor="sw")
        self._hud_dock = bottom_bar
        dock_items = [
            ("朝堂", "affairs", self._panel_overview),
            ("中枢", "ministers", self._panel_central_org),
            ("外交", "war", self._panel_diplomacy),
            ("朝报", "gazette", self._panel_daily_log),
            ("个人行止", "memorial", self._panel_personal),
            ("拟旨", "military", self._panel_decree_entry),
            ("国策", "tech", self._panel_focus),
        ]
        for label, icon_key, fn in dock_items:
            self._round_icon_btn(bottom_bar, label,
                                 lambda f=fn, t=label: self._open_overlay(f, t),
                                 icon=icon_key, text_color=INK)
        # 图鉴：大宋典制 wiki（只读，不依赖 AI）
        self._round_icon_btn(bottom_bar, "图鉴",
                             lambda: self._open_overlay(self._panel_codex, "图 鉴"),
                             icon="menu", text_color=INK)
        # 设置：聚合 存档/加载/主菜单/设置 入口（作为浮层打开，由 _panel_settings 内部导航）
        self._round_icon_btn(bottom_bar, "设置",
                             lambda: self._open_overlay(self._panel_settings, "设 置"),
                             icon="menu", text_color=INK)
        # 右下角回合推演
        endturn = tk.Frame(c, bg=PAPER)
        endturn.place(relx=1.0, rely=1.0, x=-14, y=-14, anchor="se")
        self._endturn_btn(endturn)

    def _hud_tooltip(self, widget, title, lines_fn):
        """宋式悬浮框：鼠标进入显示、离开隐藏；overrideredirect 不抢焦点、不挡操作。

        lines_fn: 可调用 → [(文本, fg|None, bold|None), ...]（每次进入动态生成）。
        """
        tl = {"w": None}

        def _show(_e=None):
            if tl["w"] is not None:
                try:
                    if tl["w"].winfo_exists():
                        return
                except Exception:
                    tl["w"] = None
            try:
                w = tk.Toplevel(self.root)
                w.overrideredirect(True)
                w.configure(bg="#140e0a")
                panel = tk.Frame(w, bg=PAPER, relief="ridge", bd=1,
                                 highlightbackground=GOLD, highlightthickness=2)
                panel.pack(padx=3, pady=3)
                self._title(panel, title, fg=RED, bg=PAPER,
                            font=self._font(KAI, 13, "bold"), anchor="center").pack(
                    padx=10, pady=(6, 2))
                for text, fg, bold in lines_fn() or []:
                    self._label(panel, text, fg=fg or INK, bg=PAPER,
                                font=self._font(SANS, 9, "bold" if bold else ""),
                                anchor="w").pack(anchor="w", padx=12, pady=1)
                w.update_idletasks()
                x = widget.winfo_rootx()
                y = widget.winfo_rooty() + widget.winfo_height() + 4
                w.geometry(f"+{x}+{y}")
                w.lift()
                tl["w"] = w
            except Exception:
                pass

        def _hide(_e=None):
            if tl["w"] is not None:
                try:
                    tl["w"].destroy()
                except Exception:
                    pass
                tl["w"] = None

        widget.bind("<Enter>", _show)
        widget.bind("<Leave>", _hide)

    def _treasury_tooltip_lines(self):
        """国库悬浮栏内容：常项（税入分项 + 财政总结）+ 一次性 + 累计（flow_summary 纯派生）。"""
        from core.flow_summary import build_flow_summary
        t = build_flow_summary(self.state)["treasury"]
        lines = [("常项收入", RED_D, True)]
        for lab, v in t["regular_in"]:
            lines.append((f"　{lab}：+{v:,} 贯", None, False))
        if not t["regular_in"]:
            lines.append(("　（本月无税入分项）", DIM, False))
        lines.append((f"财政：入 {t['month_in']:,} 贯 / 支 {t['month_out']:,} 贯", INK, True))
        lines.append(("一次性收支", RED_D, True))
        shown = 0
        for lab, v, fund in t["one_off"]:
            if fund == "imperial":
                continue
            lines.append((f"　{lab}：{'+' if v >= 0 else ''}{v:,} 贯", None, False))
            shown += 1
        if not shown:
            lines.append(("　（本月无大项）", DIM, False))
        lines.append((f"累计入 {t['total_in']:,} / 出 {t['total_out']:,} 贯", DIM, False))
        return lines

    def _imperial_tooltip_lines(self):
        """内帑悬浮栏内容：常项（酒课+抽成）+ 一次性/用度 + 余额。"""
        from core.flow_summary import build_flow_summary
        im = build_flow_summary(self.state)["imperial"]
        lines = [("常项收入", RED_D, True)]
        for lab, v in im["regular_in"]:
            lines.append((f"　{lab}：+{v:,} 贯", None, False))
        lines.append(("一次性/用度", RED_D, True))
        shown = 0
        for lab, v, _fund in im["one_off"]:
            lines.append((f"　{lab}：{'+' if v >= 0 else ''}{v:,} 贯", None, False))
            shown += 1
        if not shown:
            lines.append(("　（本月无内帑大项）", DIM, False))
        lines.append((f"内帑现 {im['balance']:,} 贯", RED_D, True))
        return lines

    def _refresh_hud(self):
        s = self.state
        if getattr(self, "_hud_time", None):
            # 古意纪年：年号·年份·季节·月份·朔日（每月初一称朔日）
            self._hud_time.configure(
                text=f"{s.era_name}{s.year}年·{self._season_name(s.month)}·{s.month}月朔日")
        # 顶栏 token 用量（工程化可见性；命中率统计移入「设置 → Token 用量」明细表）
        if getattr(self, "_hud_token", None):
            u = self.ai_client.token_usage if self.ai_client else {}
            self._hud_token.configure(
                text=f"词元 ▸ {int(u.get('prompt', 0))+int(u.get('completion', 0)):,}")
        if getattr(self, "_hud_pills", None):
            self._hud_pills["威望"][1].configure(text=f"◆威望 {int(s.prestige)}")
            self._hud_pills["民心"][1].configure(text=f"♥民心 {int(s.population_satisfaction)}")
            self._hud_pills["国库"][1].configure(text=f"◈国库 {humanize_coin(s.treasury)}")
            self._hud_pills["内帑"][1].configure(text=f"⛃内帑 {humanize_coin(s.imperial_treasury)}")
        if getattr(self, "_hud_left", None):
            self._refresh_left_card()
        self._refresh_status()

    def _refresh_left_card(self):
        content = getattr(self, "_hud_todo", None)
        if content is None:
            return
        for w in list(content.winfo_children()):
            w.destroy()

        def _mood_bar_color(v):
            # 档位取色骨架（保留原四档阈值 65/55/45）
            return theme.status_color(
                v,
                [(65, theme.DX_GOOD), (55, theme.DX_NORMAL), (45, theme.DX_WARN)],
                theme.DX_URGENT,
            )

        s = self.state
        issues = list(getattr(s, "longterm_public", [])) + list(getattr(s, "longterm_secret", []))
        labels = [t.get("task_name", t.get("title", "事务")) for t in issues] if issues else ["暂无在办大事", "江山初定，百废待兴"]
        for it in labels[:7]:
            row = tk.Frame(content, bg=CARD, cursor="hand2")
            row.pack(fill="x", padx=6, pady=4)
            row.grid_columnconfigure(0, weight=1)
            row.grid_columnconfigure(1, weight=0)
            txt = it[:12] if isinstance(it, str) else str(it)
            lab = self._label(row, txt, fg=INK, bg=CARD, font=self._font(SANS, 9), anchor="w")
            lab.grid(row=0, column=0, sticky="w")
            prog = tk.Frame(row, bg="#e0d3b3", width=60, height=8)
            prog.grid(row=0, column=1, sticky="e", padx=(6, 0))
            val = 30 + (hash(txt) % 60)
            tk.Frame(prog, bg=_mood_bar_color(val), width=int(0.6 * val), height=8).place(x=0, y=0)
            # 同右侧竖排按钮：Tk 事件不冒泡，点击命中内部 Label 时父 Frame 绑定不触发，
            # 故 row 与 lab 都绑定点击，保证点按文字区域也有效（T-027）。
            row.bind("<Button-1>", lambda e: self._open_overlay(self._panel_todo, "在办事务"))
            lab.bind("<Button-1>", lambda e: self._open_overlay(self._panel_todo, "在办事务"))

    def _update_overlay_geometry(self):
        """根据当前窗口尺寸更新浮层宿主的位置/大小，底部留出 dock 区域。

        返回 (width, height)。
        """
        if not getattr(self, "overlay_host", None) or not self.overlay_host.winfo_exists():
            return 0, 0
        margin_x = 14
        margin_top = 14
        win_w = max(self.root.winfo_width(), 1040)
        win_h = max(self.root.winfo_height(), 680)
        margin_bottom = int(win_h * 0.30)
        width = win_w - margin_x * 2
        height = win_h - margin_top - margin_bottom
        self.overlay_host.place(x=margin_x, y=margin_top, width=width, height=height)
        return width, height

    def _open_overlay(self, fn, title):
        """压栈创建一张不透明宣纸浮层卡片，并填充内容。
        背后铺半透明暗化遮罩（Canvas stipple 风格），明确模态感。
        T-028：卡片升级为宋版书页风格——宣纸纹理底、描金双线边框、四角云纹角标、
        朱红标题条 + 印章式「闭」钮。"""
        # 兜底：overlay_host 是 _build_game_screen 创建并挂在 self.container 下的浮层宿主。
        # 一旦 _clear_all 销毁 self.container（返回主菜单 → 设置面板等路径），
        # 旧 overlay_host 已成死引用，直接 place() 会抛 "bad window path name"。
        # 因此入口处检测失效就重建。
        if not getattr(self, "overlay_host", None) or not self.overlay_host.winfo_exists():
            host = getattr(self, "container", None) or self.root
            self.overlay_host = tk.Frame(host, bg="")
            self.overlay_host.place_forget()
            self._overlay_stack = []
            self._overlay_titles = []
            self._overlay_mask = None
            self._active_overlay = None
            self.main = self.overlay_host
            self._panel_shell_root = None
        else:
            # Dock/快捷入口需要「切换」而非堆叠：直接销毁已有浮层并清空栈。
            for card in self._overlay_stack:
                try:
                    if card.winfo_exists():
                        card.destroy()
                except tk.TclError:
                    pass
            self._overlay_stack.clear()
            self._overlay_titles.clear()
            self._overlay_mask = None
            self._active_overlay = None
            self._panel_shell_root = None
        # 浮层直接浮于底层舆图之上，不做全屏遮罩（避免黑底盖住舆图，符合"浮于舆图展开"观感）。
        # overlay_host 只覆盖卡片区域，底部 dock 区域保持可点。
        width, height = self._update_overlay_geometry()

        card = tk.Frame(self.overlay_host, bg=PAPER, highlightthickness=0)
        card.place(x=0, y=0, relwidth=1, relheight=1)
        self._overlay_mask = None
        self._overlay_stack.append(card)
        self._overlay_titles.append(title)
        self._active_overlay = card

        # ---- 宋版书页装饰层 ----
        pad = 16
        bar_h = 44
        bg_cv = tk.Canvas(card, bg=PAPER, highlightthickness=0)
        bg_cv.place(x=0, y=0, relwidth=1, relheight=1)
        # 宣纸纹理底图（平整无褶皱）
        skin = theme.panel_skin_image(width, height, seed=7 + len(self._overlay_stack))
        bg_cv.create_image(0, 0, image=skin, anchor="nw")
        bg_cv._skin_img = skin  # 防 GC
        # 描金双线边框
        theme.gold_frame(bg_cv, 6, 6, width - 6, height - 6, radius=18, tag="decor")
        # 四角云纹角标
        theme.cloud_corner(bg_cv, 22, 22, 28, quadrant="tl", tag="decor")
        theme.cloud_corner(bg_cv, width - 22, 22, 28, quadrant="tr", tag="decor")
        theme.cloud_corner(bg_cv, 22, height - 22, 28, quadrant="bl", tag="decor")
        theme.cloud_corner(bg_cv, width - 22, height - 22, 28, quadrant="br", tag="decor")

        # 标题条（朱红底 + 描金边）
        bar = tk.Frame(card, bg=RED, highlightthickness=0)
        bar.place(x=pad, y=pad, width=width - pad * 2, height=bar_h)
        # 标题文字
        title_fg = "#f3e6c4"
        title_lbl = tk.Label(bar, text=f"〔{title}〕", bg=RED, fg=title_fg,
                             font=self._font(KAI, 16, "bold"))
        title_lbl.pack(side="left", padx=(12, 0))
        # 印章式「闭」钮
        close = tk.Label(bar, text="闭", bg=RED, fg=title_fg,
                         font=self._font(KAI, 14, "bold"), cursor="hand2")
        close.pack(side="right", padx=(0, 10))
        close.bind("<Button-1>", lambda e: self._close_overlay())
        close.bind("<Enter>", lambda e: close.config(fg=GOLD_LIGHT))
        close.bind("<Leave>", lambda e: close.config(fg=title_fg))

        # 内容区
        inner = tk.Frame(card, bg=PAPER, highlightthickness=0)
        inner.place(x=pad, y=pad + bar_h + 8,
                    width=width - pad * 2,
                    height=height - pad * 2 - bar_h - 8)
        card._foot = None  # 底部按钮由 _back_to_main 自行决定，不再默认塞「关 闭」
        card._content_root = inner  # 每张卡自带内容根，关闭恢复时不再依赖索引

        self._panel_shell_root = inner  # 内容挂在当前浮层 inner
        self.main = inner
        self._current_panel = title
        fn()

    def _close_overlay(self):
        """销毁栈顶浮层；栈空则回到纯舆图。

        浮层直接浮于舆图之上，无全屏遮罩（见 _open_overlay）。
        """
        if not self._overlay_stack:
            return
        card = self._overlay_stack.pop()
        title = self._overlay_titles.pop()
        try:
            if card.winfo_exists():
                card.destroy()
        except tk.TclError:
            pass
        self._overlay_mask = None
        self._active_overlay = self._overlay_stack[-1] if self._overlay_stack else None
        if self._overlay_stack:
            below = self._overlay_stack[-1]
            restored = getattr(below, "_content_root", None)
            if restored is None or not restored.winfo_exists():
                restored = below.winfo_children()[1] if below.winfo_children() else below
            self.main = self._panel_shell_root = restored
        else:
            self.overlay_host.place_forget()
            self.main = self.overlay_host
            self._panel_shell_root = None
            self._current_panel = "疆域主页"

    def _ui_back_to_menu(self):
        """游戏中返回主菜单（_build_main_menu 内部会 _clear_all 重建界面，避免残留）。
        未存档直接退出会丢弃本局进度，故先征求确认。"""
        # 是=先存档 / 否=不保存直接回 / 取消=继续游戏
        ans = self.messagebox.askyesnocancel(
            "返回主菜单",
            "返回主菜单将结束本局（未保存的进度会丢失）。\n\n"
            "【是】先跳到「存档·读档」保存进度\n【否】不保存，直接回主菜单\n【取消】继续游戏")
        if ans is None:      # 取消 → 继续游戏
            return
        if ans:              # 是 → 先去存档
            self._open_overlay(self._panel_save_load, "存档 · 读档")
            return
        # 否 → 直接回主菜单
        self._pending_logs = []
        self.state = None
        self._build_main_menu()

    def _switch_panel(self, fn, name):
        """统一转调浮层栈打开面板。"""
        self._open_overlay(fn, name)

    def _clear_main(self):
        for w in list(self.main.winfo_children()):
            w.destroy()

    def _clear_all(self):
        # 销毁全部子容器并重建（menu 用 pack、game 用 grid，互不干扰）
        for w in list(self.root.winfo_children()):
            w.destroy()
        self.container = tk.Frame(self.root, bg=PAPER)
        self.container.pack(fill="both", expand=True)
        # 统一清理挂在 self.container 子树下、现已销毁的 widget 引用，
        # 从根上消除"bad window path name"死引用（T-020/T-021/T-022 同源问题）。
        # 各 _build_* 重建路径会重新赋值，置空后 getattr 判空即可安全跳过。
        for attr in ("overlay_host", "map_layer", "_map_cv", "_hud_left",
                     "_hud_dock", "_right_strip", "_hud_time", "_menu_canvas",
                     "_menu_bg_tk", "_hud_top", "_hud_pills", "_hud_token",
                     "_hud_todo"):
            setattr(self, attr, None)
        self.main = None
        self._panel_shell_root = None
        self._active_overlay = None
        self._overlay_stack = []
        self._overlay_titles = []
        self._overlay_mask = None

    def _refresh_head(self):
        s = self.state
        solar = getattr(s, "solar_term", "")
        txt = f"{s.era_name} {s.year}年 · {s.month}月（{solar}）"
        if getattr(self, "head_info", None):
            self.head_info.configure(text=txt)
        self._refresh_status()

    def _refresh_status(self):
        import ui.theme as theme
        s = self.state
        cv = getattr(self, "_status_canvas", None)
        if cv is None:
            return
        cv.delete("all")
        W = cv.winfo_width() or 900
        H = 44

        def quad(v, lo, hi):
            if v >= hi:
                return theme.DX_GOOD
            elif v >= (lo + hi) // 2:
                return theme.DX_NORMAL
            elif v >= lo:
                return theme.DX_WARN
            return theme.DX_URGENT

        items = [
            ("国库", s.treasury / 10000.0, 1000.0,
             quad(s.treasury / 10000.0, 250, 500)),
            ("内帑", s.imperial_treasury / 10000.0, 1000.0,
             quad(s.imperial_treasury / 10000.0, 250, 500)),
            ("民心", s.population_satisfaction, 100.0,
             quad(s.population_satisfaction, 45, 65)),
            ("皇威", s.prestige, 100.0, quad(s.prestige, 45, 65)),
            ("军备", sum(u.troops for u in s.army_units), 750000.0,
             quad(sum(u.troops for u in s.army_units), 60000, 300000)),
        ]
        n = len(items)
        cell = W / n
        for i, (lab, val, mx, col) in enumerate(items):
            x0 = i * cell + 16
            y0 = 8
            bw = cell - 32
            cv.create_text(x0, y0, text=lab, fill=INK, font=self._font(KAI, 11, "bold"),
                           anchor="w")
            bar_y = y0 + 6
            cv.create_rectangle(x0, bar_y, x0 + bw, bar_y + 16,
                                fill="#e3d4ad", outline=BORDER, width=1)
            frac = max(0.0, min(1.0, val / mx))
            cv.create_rectangle(x0, bar_y, x0 + bw * frac, bar_y + 16,
                                fill=col, outline=theme.shade(col, 0.7), width=1)
            disp = f"{val:.0f}" if mx >= 1000 else f"{val:.0f}"
            cv.create_text(x0 + bw, bar_y + 8, text=disp, fill=INK,
                           font=self._font(SANS, 9), anchor="e")

        # 铜钱徽章：泉货档位（定性词 + 色标，永不显示 money_supply 精确值）
        # 文案统一走后端 desensitize_shortage，杜绝 4 套口径漂移；此处仅据 shortage 映射色标。
        try:
            from content.data import desensitize_shortage
            shortage = s.coin.get("shortage", 0.3)
            badge = desensitize_shortage(shortage)
            if shortage <= 0.1:
                bcol = theme.DX_GOOD
            elif shortage <= 0.3:
                bcol = theme.DX_NORMAL
            elif shortage <= 0.6:
                bcol = theme.DX_WARN
            elif shortage <= 0.9:
                bcol = "#d47706"
            else:
                bcol = theme.DX_URGENT
            bx0, by0 = W - 120, 8
            # 铜钱（圆形方孔）
            cx, cy, r = bx0 + 12, by0 + 14, 10
            cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#d4a017",
                           outline="#8a6d0b", width=2)
            cv.create_rectangle(cx - 3, cy - 3, cx + 3, cy + 3, fill="#6b4e0a",
                                outline="")
            cv.create_text(bx0 + 28, by0, text=badge, fill=bcol,
                           font=self._font(KAI, 11, "bold"), anchor="w")
            cv.create_text(bx0 + 28, by0 + 16, text="据奏报·钱荒",
                           fill=DIM, font=self._font(SANS, 8), anchor="w")
        except Exception:
            pass

    def _panel_shell(self, title, with_back=True, scroll=True, back_cmd=None):
        """返回浮层内容 Frame（仿古宣纸卡片面板）。
        scroll=True  用滚动画布（长列表）；scroll=False  直接铺满（地图主页）。
        主菜单调用时 self.main 可能未建立，回退到 self.container。
        全局单例：同一浮层只保留一个面板根容器，防止多次打开造成叠加。
        返回按钮统一固定在 panel_root 底部，避免被 Canvas 窗口遮挡；滚动条按需显示。
        """
        # 鲁棒性兜底：浮层栈可能在 _clear_all/重建后状态丢失，逐字段重建
        if not hasattr(self, "_overlay_stack") or self._overlay_stack is None:
            self._overlay_stack = []
        if not hasattr(self, "_overlay_titles") or self._overlay_titles is None:
            self._overlay_titles = []
        # 清理栈内已 destroy 的死 Tk 引用
        self._overlay_stack = [c for c in self._overlay_stack
                               if c is not None and c.winfo_exists()]
        # 标题栈与浮层栈保持同长度
        while len(self._overlay_titles) > len(self._overlay_stack):
            self._overlay_titles.pop()
        while len(self._overlay_titles) < len(self._overlay_stack):
            self._overlay_titles.append("")

        # self.main 可能未建立（_clear_all 置空后为 None），回退到 container
        host = self.main or self.container

        # 若直接调用 _panel_shell（非经由 _open_overlay），
        # 则临时挂到 overlay 宿主上建立一层浮层。
        if not self._overlay_stack:
            self._open_overlay(lambda: None, title)

        panel_root = getattr(self, "_panel_shell_root", None)
        if panel_root is None or not panel_root.winfo_exists():
            panel_root = host
        inner = panel_root

        self._title(inner, title, fg=RED, bg=PAPER, font=self._font(KAI, 18, "bold"),
                    anchor="center").pack(pady=(8, 6))
        if not scroll:
            # 浮层根 foot（_open_overlay 已加「关 闭」），若提供 back_cmd 则补一个「返 回」
            if with_back and back_cmd:
                self._back_to_main(inner, back_cmd=back_cmd)
            return inner

        # 滚动画布：统一包裹，绑定鼠标滚轮，inner 宽度与可视区同步，滚动条按需显示
        wrap = tk.Frame(panel_root, bg=PAPER)
        wrap.pack(fill="both", expand=True, padx=6, pady=4)
        canvas = tk.Canvas(wrap, bg=PAPER, highlightthickness=0)
        sb = tk.Scrollbar(wrap, command=canvas.yview, bg=PAPER2, troughcolor=PAPER,
                          highlightbackground=PAPER, activebackground=GOLD)
        inner = tk.Frame(canvas, bg=PAPER)

        def _on_configure(event=None):
            canvas_width = canvas.winfo_width()
            if canvas_width > 1:
                canvas.itemconfig(inner_win, width=canvas_width)
            canvas.configure(scrollregion=canvas.bbox("all"))

            # 按需显示/隐藏垂直滚动条
            req_h = inner.winfo_reqheight()
            view_h = canvas.winfo_height()
            if view_h > 1 and req_h > view_h:
                if not getattr(sb, "_packed", False):
                    sb.pack(side="right", fill="y")
                    sb._packed = True
            else:
                if getattr(sb, "_packed", False):
                    sb.pack_forget()
                    sb._packed = False

        inner.bind("<Configure>", lambda e: _on_configure())
        canvas.bind("<Configure>", lambda e: _on_configure())

        def _on_mousewheel(event):
            if inner.winfo_reqheight() <= canvas.winfo_height():
                return
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        for w in (canvas, inner):
            w.bind("<MouseWheel>", _on_mousewheel)
        canvas.bind("<Enter>", lambda e: canvas.focus_set())
        # 全局滑轮：根据鼠标位置决定是否触发当前栈顶 card 的滚动
        # 这样浮层任意位置（标题条、foot、内边距空白）滑轮都能滚动
        app = self

        def _global_wheel(event):
            try:
                card = getattr(app, "_active_overlay", None)
                if card is None or not card.winfo_exists():
                    return None
                # 鼠标位置（屏幕坐标）转 card 坐标
                x, y = event.x_root, event.y_root
                cx = card.winfo_rootx()
                cy = card.winfo_rooty()
                cw = card.winfo_width()
                ch = card.winfo_height()
                if not (cx <= x <= cx + cw and cy <= y <= cy + ch):
                    return None
                # 在 card 内：找 card 内部所有 Canvas 滚轮
                # 简单实现：遍历 card 子树找首个带 _scrollable 标记的 canvas
                target = getattr(card, "_scroll_canvas", None)
                if target is None or not target.winfo_exists():
                    return None
                inner_f = getattr(card, "_scroll_inner", None)
                if inner_f is not None and inner_f.winfo_exists():
                    if inner_f.winfo_reqheight() <= target.winfo_height():
                        return None
                target.yview_scroll(int(-1 * (event.delta / 120)), "units")
                return "break"
            except Exception:
                return None

        # 默认替换同名 handler，避免多次打开浮层后 handler 堆积
        self.root.bind_all("<MouseWheel>", _global_wheel)
        self._wheel_handler = _global_wheel
        # 在当前浮层 card 上记录 canvas/inner 引用，供 _global_wheel 使用
        active_card = getattr(self, "_active_overlay", None)
        if active_card is not None:
            active_card._scroll_canvas = canvas
            active_card._scroll_inner = inner

        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb._packed = False
        inner_win = canvas.create_window((0, 0), window=inner, anchor="nw", width=canvas.winfo_width())

        # 仅在提供 back_cmd 时追加「返 回」按钮，避免与 _open_overlay 的「关 闭」重复
        if with_back and back_cmd:
            self._back_to_main(inner, back_cmd=back_cmd)
        return inner

    def _section(self, parent, title):
        self._title(parent, title, fg=RED_D, bg=PAPER, font=self._font(KAI, 14, "bold"),
                    anchor="w").pack(fill="x", padx=8, pady=(10, 4))

    def _back_to_main(self, parent, back_cmd=None):
        """添加「返 回」按钮（仅在提供 back_cmd 时调用）。
        在 parent 底部建一个独立 foot 容器，按钮放里面，不会被滚动 inner 吞掉。
        这样避免与「闭」印重复，也省去重复底部按钮。"""
        if not back_cmd:
            return
        foot = tk.Frame(parent, bg=PAPER)
        foot.pack(side="bottom", fill="x", padx=10, pady=(0, 6))
        self._btn(foot, "返 回", back_cmd, width=12, ghost=True).pack(side="right", padx=(0, 8))

    def _panel_overview(self):
        inner = self._panel_shell("朝 堂 一 览")
        s = self.state

        # 皇帝立绘（按年号时节切换冬夏常服/年龄段）
        top = tk.Frame(inner, bg=PAPER)
        top.pack(fill="x", padx=10, pady=6)
        from ui import assets as res
        ph = res.emperor_portrait(s, size=(200, 270))
        if ph:
            pf = tk.Frame(top, bg=PAPER, relief="ridge", bd=1,
                          highlightbackground=GOLD, highlightthickness=1)
            pf.pack(side="left", padx=(0, 12))
            tk.Label(pf, image=ph, bg=PAPER).pack(padx=4, pady=4)
            # 玉玺角标
            seal = res.seal_image(size=(34, 34))
            if seal:
                sf = tk.Label(pf, image=seal, bg=PAPER,
                              relief="solid", bd=1, highlightbackground=GOLD)
                sf.place(relx=1.0, rely=1.0, x=-4, y=-4, anchor="se")
        info = self._card(top)
        info.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        self._card_title(info, "御 容 · 奉天承运")
        age_txt = "青年" if s.year <= 1115 else ("壮年" if s.year <= 1125 else "暮年")
        season_txt = "冬常服" if s.month in (11, 12, 1, 2, 3) else "夏常服"
        self._label(info,
                    f"{s.era_name}{s.year}年{s.month}月\n"
                    f"御体：{int(s.emperor_health)}    皇威：{int(s.prestige)}\n"
                    f"天潢：{age_txt}天子 · 御着{season_txt}",
                    fg=INK, bg=CARD, font=self._font(SANS, 11), anchor="w",
                    justify="left").pack(padx=14, pady=8, fill="both", expand=True)

        # 中枢六部
        self._section(inner, "【中枢六部】")
        yamen_card = self._card(inner)
        yamen_card.pack(fill="x", padx=10, pady=4)
        self._card_title(yamen_card, "衙门均效")
        eff_y = sum(y["efficiency"] for y in s.yamen.values()) / len(s.yamen)
        self._meter(yamen_card, eff_y, 100, label="六部理政之效")

        # 外患
        self._section(inner, "【外患态度】")
        ext_card = self._card(inner)
        ext_card.pack(fill="x", padx=10, pady=4)
        self._card_title(ext_card, "四邻观衅")
        for k in ("辽", "西夏", "大理"):
            a = self._ext_att(k)
            self._meter(ext_card, a, 100, label=f"{k}")

        # 派系
        self._section(inner, "【派系】")
        fac_card = self._card(inner)
        fac_card.pack(fill="x", padx=10, pady=4)
        self._card_title(fac_card, "朝堂党争")
        for name in FACTION_NAMES:
            f = s.factions[name]
            self._meter(fac_card, f["influence"], 100, label=f"{name}·{f['leader']}")

        # 田亩 / 金融 / 科举 / 科技 / 外交 概览（四列卡片）
        self._section(inner, "【国力概览】")
        grid = tk.Frame(inner, bg=PAPER)
        grid.pack(fill="x", padx=10, pady=4)
        cells = [
            ("田亩户籍", f"垦田 {humanize_land(s.land['cultivated'])}\n隐漏 {int(s.land['hidden_rate']*100)}%\n在籍 {humanize_households(s.land['households'])}"),
            ("金融货币", f"交子 {humanize_coin(s.jiaozi['issued'])}\n信用 {int(s.jiaozi['trust'])}\n市舶{'开' if s.maritime['open'] else '未'}"),
            ("科举学校", f"{'开科' if s.exam['open'] else '停科'}\n人才 {int(s.exam['talent_pool'])}\n州县学 {s.exam['schools']}"),
            ("科技工技", f"技 {int(s.tech['level'])}\n火药 {s.tech['gunpowder']}\n水利 {s.tech['hydraulics']}"),
            ("外交", f"海盟{'成' if getattr(s,'alliance_jin_liao',False) else '未'}\n辽 {self._ext_att('辽')}\n西夏 {self._ext_att('西夏')}"),
            ("龙体·皇威", f"龙体 {int(s.emperor_health)}\n皇威 {int(s.prestige)}\n诏令 {s.decree_bandwidth-len(s.pending_decrees)}/{s.decree_bandwidth}"),
        ]
        for i, (t, body) in enumerate(cells):
            col = i % 3
            row = i // 3
            c = self._card(grid)
            c.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            self._card_title(c, t)
            self._label(c, body, fg=INK, bg=CARD, font=self._font(SANS, 10),
                        anchor="center", justify="center").pack(padx=10, pady=(2, 10))
        for col in range(3):
            grid.grid_columnconfigure(col, weight=1)

        # 开局邸报（首次开局展示，含待办三事）
        self._render_gazette(inner)

        # 帝国修正（legacies）：当前生效的历史包袱与消除进度
        self._render_legacies(inner)

        if s.active_events:
            self._section(inner, "【当前事件】")
            ev_card = self._card(inner)
            ev_card.pack(fill="x", padx=10, pady=4)
            self._card_title(ev_card, "边报急务")
            for e in s.active_events:
                self._label(ev_card, f"  ● {e['message']}", fg=RED_D, bg=CARD,
                            font=self._font(SANS, 11)).pack(anchor="w", padx=14, pady=3)
            self._label(ev_card, "", bg=CARD).pack(pady=2)

    def _render_gazette(self, inner):
        """开局邸报展示（仿《明末：捞金模拟器》opening_gazette）。

        首次开局全屏展示后，在朝堂一览顶部以「邸报」卡片呈现正文与待办三事。
        """
        gz = getattr(self.state, "opening_gazette", None)
        if not gz:
            return
        self._section(inner, "【开局邸报】")
        card = self._card(inner)
        card.pack(fill="x", padx=10, pady=4)
        self._card_title(card, f"{gz.get('header', '大宋邸报')} · {gz.get('era', '')}")
        body = gz.get("body", "")
        if body:
            self._label(card, body, fg=INK, bg=CARD, font=self._font(KAI, 11),
                        anchor="w", justify="left", wraplength=560).pack(anchor="w", padx=14, pady=4)
        tasks = gz.get("tasks", [])
        if tasks:
            self._label(card, "待办三事：", fg=RED_D, bg=CARD,
                        font=self._font(KAI, 11, "bold")).pack(anchor="w", padx=14, pady=(6, 2))
            for t in tasks:
                mark = "●" if t.get("urgent") else "○"
                self._label(card, f"  {mark} {t.get('title', '')}：{t.get('desc', '')}",
                            fg=INK, bg=CARD, font=self._font(SANS, 10),
                            anchor="w", justify="left", wraplength=560).pack(anchor="w", padx=14, pady=2)
        hint = gz.get("hint", "")
        if hint:
            self._label(card, hint, fg=GOLD, bg=CARD, font=self._font(KAI, 10),
                        anchor="w").pack(anchor="w", padx=14, pady=(6, 4))

    def _render_legacies(self, inner):
        """帝国修正（legacies）展示：当前生效的历史包袱与消除进度。"""
        try:
            from core.legacy_mechanic import active_legacies, cleared_legacies
        except Exception:
            return
        active = active_legacies(self.state)
        cleared = cleared_legacies(self.state)
        if not active and not cleared:
            return
        self._section(inner, "【帝国修正】")
        card = self._card(inner)
        card.pack(fill="x", padx=10, pady=4)
        self._card_title(card, "历史包袱 · 破局目标")
        if active:
            for e in active:
                name = e.get("name", "")
                desc = e.get("desc", "")
                prog = e.get("progress", 0)
                self._label(card, f"  ● {name}：{desc}", fg=RED_D, bg=CARD,
                            font=self._font(SANS, 10), anchor="w", justify="left",
                            wraplength=560).pack(anchor="w", padx=14, pady=2)
                self._meter(card, prog, 100, label="消除进度")
        if cleared:
            names = "、".join(e.get("name", "") for e in cleared)
            self._label(card, f"  ✓ 已消除：{names}", fg=GREEN, bg=CARD,
                        font=self._font(SANS, 10), anchor="w").pack(anchor="w", padx=14, pady=2)

    def _panel_focus(self):
        """国策树面板：五大分支（政务/军事/科学/内卫/税务），节点卡片 + 解锁。"""
        inner = self._panel_shell("国 策 树")
        s = self.state
        try:
            from core.focus_mechanic import FOCUS_TREE, can_unlock, unlock_focus
        except Exception:
            self._label(inner, "国策树未初始化。", fg=INK, bg=PAPER,
                        font=self._font(SANS, 11)).pack(padx=14, pady=8)
            return
        tree = getattr(s, "focus_tree", {}) or {}
        if not tree:
            self._label(inner, "国策树尚未建立，请先开始新游戏。", fg=INK, bg=PAPER,
                        font=self._font(SANS, 11)).pack(padx=14, pady=8)
            return
        # 顶部说明
        self._label(inner, "五大分支国策，择一而专，互斥相制。解锁节点以固国本。",
                    fg=DIM, bg=PAPER, font=self._font(KAI, 11)).pack(anchor="w", padx=14, pady=(6, 2))
        for branch, bspec in FOCUS_TREE.items():
            cur = tree.get(branch, {})
            self._section(inner, f"【{bspec['name']}】{bspec.get('desc', '')}")
            card = self._card(inner)
            card.pack(fill="x", padx=10, pady=4)
            self._card_title(card, f"{bspec['name']} · 已解锁 {sum(1 for n in cur.get('nodes', {}).values() if n.get('unlocked'))}/{len(bspec['nodes'])}")
            for nk, nd in bspec["nodes"].items():
                node = cur.get("nodes", {}).get(nk, {})
                unlocked = node.get("unlocked", False)
                lvl = node.get("power_level", 0)
                row = tk.Frame(card, bg=CARD)
                row.pack(fill="x", padx=10, pady=3)
                mark = "✓" if unlocked else "○"
                fg = GREEN if unlocked else INK
                self._label(row, f"{mark} {nd['name']}（权{nd['power_level']}）",
                            fg=fg, bg=CARD, font=self._font(KAI, 11, "bold"),
                            anchor="w").pack(side="left", padx=(0, 8))
                self._label(row, nd.get("desc", ""), fg=DIM, bg=CARD,
                            font=self._font(SANS, 9), anchor="w").pack(side="left", fill="x", expand=True)
                if not unlocked:
                    ok, reason = can_unlock(s, branch, nk)
                    if ok:
                        self._btn(row, "解锁", lambda b=branch, k=nk: self._do_focus_unlock(b, k),
                                  width=6, ghost=True).pack(side="right", padx=(6, 0))
                    else:
                        self._label(row, reason, fg=DIM, bg=CARD,
                                    font=self._font(SANS, 8), anchor="e").pack(side="right", padx=(6, 0))
                else:
                    self._label(row, f"解锁：{nd.get('unlock', '')}", fg=GREEN, bg=CARD,
                                font=self._font(SANS, 8), anchor="e").pack(side="right", padx=(6, 0))

    def _do_focus_unlock(self, branch, node_key):
        """国策解锁交互：调用 unlock_focus 并刷新面板。"""
        try:
            from core.focus_mechanic import unlock_focus
            res = unlock_focus(self.state, branch, node_key)
            msg = res.get("message", "")
            if res.get("ok"):
                self.messagebox.showinfo("国策解锁", msg)
            else:
                self.messagebox.showwarning("国策解锁", msg)
        except Exception as e:
            self.messagebox.showerror("国策解锁", f"解锁失败：{e}")
        self._open_overlay(self._panel_focus, "国 策 树")

    def _season_name(self, month):
        if month in (12, 1, 2):
            return "冬"
        if month in (3, 4, 5):
            return "春"
        if month in (6, 7, 8):
            return "夏"
        return "秋"

