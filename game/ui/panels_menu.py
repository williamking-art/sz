# -*- coding: utf-8 -*-
"""宋祚 · GUI menu 面板 Mixin。

主菜单 / 开局引子 / 结局界面。共享常量与工具见 ui.gui_common。
"""
import os
import sys
import random
import tkinter as tk
import ui.theme as theme
from ai.client import AIClient, _org_by_affiliation
from ui.gui_common import (PAPER, PAPER2, CARD, INK, DIM, RED, RED_D, GOLD, GREEN,
    BORDER, SEAL_BG, KAI, SANS, DECREE_CATEGORIES,
    _bar, _format_effects, _judge_effects)


class PanelsMenuMixin:
    def _build_main_menu(self):
        from PIL import Image, ImageDraw, ImageTk
        self._clear_all()
        self._inited = False
        self._menu_bg_index = random.randint(0, 3)
        f = self.container

        cv = tk.Canvas(f, bg="#0f0b08", highlightthickness=0)
        cv.place(x=0, y=0, relwidth=1, relheight=1)
        self._menu_canvas = cv
        self._menu_bg_tk = None

        # 左侧渐变遮罩（让文字可读）
        self._menu_mask_tk = None

        # 竖排标题容器
        title_cv = tk.Canvas(cv, bg="#0f0b08", highlightthickness=0)
        title_cv.place(x=48, y=36, width=120, height=420)
        self._menu_title_cv = title_cv

        def draw_title(ev=None):
            title_cv.delete("all")
            chars = ["宋", "祚"]
            # 描金双层：底层金色偏移 + 上层米白，模拟描金立体
            for i, ch in enumerate(chars):
                y = 20 + i * 92
                title_cv.create_text(62, y + 2, text=ch, fill=GOLD,
                                     font=self._font(KAI, 72, "bold"), anchor="n")
                title_cv.create_text(60, y, text=ch, fill="#f3e6c4",
                                     font=self._font(KAI, 72, "bold"), anchor="n")
            title_cv.create_text(92, 18, text="·", fill=RED, font=self._font(KAI, 20, "bold"), anchor="n")
            title_cv.create_text(60, 205, text="北 宋 治 国 模 拟", fill="#d9c59a",
                                 font=self._font(SANS, 11), anchor="n")
        title_cv.bind("<Configure>", draw_title)
        draw_title()

        # 左侧按钮列
        btn_frame = tk.Frame(cv, bg="#0f0b08")
        btn_frame.place(x=44, y=280)
        menu_items = [
            ("继续游戏", self._panel_save_load),
            ("开始新游戏", lambda: self._new_game("史实")),
            ("轻松开局", lambda: self._new_game("轻松")),
            ("读取存档", self._panel_save_load),
            ("游戏设置", lambda: self._panel_ai_config(self._build_main_menu)),
            ("退出游戏", self.root.quit),
        ]
        start_btn = None
        for i, (txt, cmd) in enumerate(menu_items):
            b = self._song_button(btn_frame, txt, cmd, width=168, height=42,
                                  font=self._font(KAI, 14))
            b.pack(pady=8)
            if txt == "开始新游戏":
                start_btn = b
        if start_btn:
            start_btn.focus_set()
            start_btn.bind("<Return>", lambda e: start_btn.children["!canvas"].event_generate("<Button-1>"))

        # 底部小字（根据 AI 配置状态动态提示）
        if self.ai_client and getattr(self.ai_client, "available", False):
            note_txt = "AI 叙事已启用（在线模型）。"
        else:
            note_txt = "⚠ 尚未配置 AI 模型，开始游戏前请先到「游戏设置 → AI 配置」完成配置。"
        note = tk.Label(cv, text=note_txt, fg="#cdbd97", bg="#0f0b08",
                       font=self._font(SANS, 9), padx=8, pady=3,
                       relief="ridge", bd=1, highlightbackground=GOLD,
                       highlightthickness=1)
        note.place(x=44, rely=1.0, y=-30)

        # 版本印章（朱文方印风格）
        seal_lbl = tk.Label(cv, text="宋祚 · SongZuo", fg="#f3e6c4", bg=RED,
                            font=self._font(SANS, 8), padx=8, pady=3,
                            relief="ridge", bd=1, highlightbackground=GOLD,
                            highlightthickness=1)
        seal_lbl.place(relx=1.0, rely=1.0, x=-12, y=-12, anchor="se")

        def draw_bg(ev=None):
            try:
                w = max(2, cv.winfo_width())
                h = max(2, cv.winfo_height())
            except tk.TclError:
                return
            # 容错：canvas 重建后首次 <Configure> 触发时，旧 tag 可能尚未建立
            # （如 _clear_all 重建主菜单）。此时 delete/lower/tag_raise 会抛
            # "tagOrId ... doesn't match any items" TclError，用 find_withtag 守卫。
            if cv.find_withtag("bg_img"):
                cv.delete("bg_img")
            img = self._load_menu_bg(w, h)
            if img:
                self._menu_bg_tk = img
                cv.create_image(0, 0, anchor="nw", image=img, tags="bg_img")
                if cv.find_withtag("bg_img"):
                    try:
                        cv.lower("bg_img")
                    except tk.TclError:
                        pass
            # 左侧遮罩
            mask = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            dr = ImageDraw.Draw(mask)
            dr.rectangle([0, 0, 280, h], fill=(15, 11, 8, 160))
            dr.polygon([(280, 0), (340, 0), (280, h), (220, h)], fill=(15, 11, 8, 160))
            self._menu_mask_tk = ImageTk.PhotoImage(mask)
            cv.create_image(0, 0, anchor="nw", image=self._menu_mask_tk, tags="mask")
            if cv.find_withtag("mask"):
                try:
                    cv.lower("mask")
                except tk.TclError:
                    pass
            if cv.find_withtag("bg_img") and cv.find_withtag("mask"):
                try:
                    cv.tag_raise("mask", "bg_img")
                except tk.TclError:
                    pass

        cv.bind("<Configure>", draw_bg)
        # 延迟触发一次，确保尺寸有效
        self.root.after(50, draw_bg)

    def _load_menu_bg(self, w, h):
        """加载并缩放主菜单背景图（PIL 等比 cover）。"""
        try:
            from PIL import Image, ImageTk
            idx = self._menu_bg_index
            path = self._resource(f"assets/ui/menu_bg_{idx+1}.png")
            if not os.path.exists(path):
                return None
            img = Image.open(path).convert("RGBA")
            iw, ih = img.size
            scale = max(w / iw, h / ih)
            nw, nh = int(iw * scale), int(ih * scale)
            img = img.resize((nw, nh), Image.LANCZOS)
            # 居中裁剪
            left = (nw - w) // 2
            top = (nh - h) // 2
            img = img.crop((left, top, left + w, top + h))
            return ImageTk.PhotoImage(img)
        except Exception:
            return None

    def _new_game(self, difficulty):
        # —— AI 模型软检测：首次才联网自检(被缓存)，失败不拦截，仅提示 ——
        # 避免每次开局同步联网最长 15s 阻塞主线程导致界面卡死。
        # 取消离线兜底：AI 不可用时各叙事面板返回 _error 标记，由对应面板提示配置。
        if self.ai_client is not None:
            good, msg = self.ai_client.probe(timeout=8)
            if not good:
                self.messagebox.showinfo(
                    "AI 模型暂不可用",
                    f"AI 叙事模型自检未通过，叙事功能（召对/拟诏/月报等）将提示配置 AI：\n{msg}")
        # —— 原有逻辑（经 backend，可本地/远程）——
        self.state = self.backend.new_game(difficulty, self.ai_client)
        self._pending_logs = []
        self._inited = False
        self._show_intro()

    def _show_intro(self):
        self._clear_all()
        f = self.container
        ban = tk.Frame(f, bg=RED)
        ban.pack(fill="x")
        self._title(ban, "建中靖国元年 · 春正月", fg="#f3e6c4", bg=RED,
                    font=self._font(KAI, 22, "bold"), anchor="center").pack(pady=14)

        # —— 引子 ——
        st_w = self._scrolled(f, bg=CARD, font=self._font(KAI, 13), padx=24, pady=14)
        st_w._text.insert("1.0",
            ("元符三年，向太后垂帘，立端王赵佶为帝。\n\n"
             "新帝登基，年号建中靖国，意在新旧两党之间调停中正，以靖国家。"
             "朝堂之上，新党蔡京卷土重来之势渐显，旧党元祐诸臣仍据要津。"
             "宦官童贯深得帝心，西军种师道枕戈待旦……\n\n"
             "而你，就是这位年仅十九岁的新天子——赵佶。\n\n"
             "你的每一个决定，都将影响大宋国祚的命运。\n是重蹈史实，还是中兴大宋？"))
        st_w._text.configure(state="disabled")
        st_w.pack(fill="both", expand=True, padx=40, pady=(10, 6))

        # —— 开局邸报（史翰青 A14 文案落地，进奏院状报）——
        from content.codex_text import GAZETTE_OPENING, GAZETTE_HEADER
        gaz = self._scrolled(f, bg=CARD, font=self._font(KAI, 12), padx=24, pady=12, height=17)
        t = gaz._text
        t.tag_configure("h", foreground=RED_D, font=self._font(KAI, 13, "bold"), spacing1=8)
        t.tag_configure("b", foreground=INK, font=self._font(KAI, 12))
        t.insert("end", GAZETTE_HEADER + "\n", "h")
        for head, body, _note in GAZETTE_OPENING:
            t.insert("end", f"【{head}】", "h")
            t.insert("end", body + "\n\n", "b")
        t.configure(state="disabled")
        gaz.pack(fill="both", expand=True, padx=40, pady=(0, 6))

        # —— 开局入口：登基治国（不设可行动项引导，玩家自行探索）——
        bar = tk.Frame(f, bg=PAPER)
        bar.pack(pady=(4, 14))
        self._seal_btn(bar, "登 基 治 国", self._build_game_screen, big=True).pack(side="left", padx=8)

    def _ui_game_over(self):
        s = self.state
        if not getattr(s, "game_over", False):
            s.game_over = True
            s.game_result = "陛下主动退位，江山交予后人。"
        try:
            eval_result, ai_eval = self.backend.conclude(s, self.ai_client)
        except _AIRuntimeError as e:
            self.messagebox.showerror("AI 叙事中断", str(e))
            return
        self._panel_game_over(eval_result, ai_eval)

    def _panel_game_over(self, eval_result, ai_eval):
        tl, body = self._overlay("大 宋 国 祚 · 终", width=760, height=640)
        self._title(body, "大 宋 国 祚 · 终", fg=RED, bg=PAPER, font=self._font(KAI, 22, "bold"),
                    anchor="center").pack(pady=(8, 4))
        self._label(body, self.state.game_result, fg=INK, bg=PAPER, font=self._font(KAI, 13),
                    anchor="center", justify="center").pack(pady=4)

        card = self._card(body)
        card.pack(fill="both", expand=True, padx=12, pady=8)
        lines = ["【七维评价】"]
        for k, v in eval_result["scores"].items():
            lines.append(f"  {k:10s}: {_bar(int(v),20)} {v:.0f}")
        lines.append(f"  加权总分: {eval_result['total']:.1f}  —  {eval_result['outcome']}")
        lines.append("")
        lines.append(eval_result["description"])
        if ai_eval:
            lines.append("")
            lines.append("【史官评曰】")
            lines.append(ai_eval)
        txt = self._scrolled(card, bg=CARD, font=self._font(SANS, 11), padx=16, pady=14)
        txt._text.insert("1.0", "\n".join(lines))
        txt._text.configure(state="disabled")
        txt.pack(fill="both", expand=True, padx=12, pady=12)
        self._seal_btn(body, "回 主 菜 单", self._build_main_menu, big=True).pack(pady=(0, 10))

