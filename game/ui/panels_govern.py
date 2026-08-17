# -*- coding: utf-8 -*-
"""宋祚 · GUI govern 面板 Mixin。

朝堂 / 群臣 / 召见奏对 / 拟旨 / 舆图 / 在办事务等治理面板。共享常量与工具见 ui.gui_common。
"""
import os
import sys
import random
import tkinter as tk
import ui.theme as theme
from content.data import (PERSONAL_ACTIONS, FACTION_NAMES, YAMEN_LIST, YAMEN_INFO,
    PREFECTURE_LIST, FIXED_PROCEDURES)
from ai.client import AIClient, _org_by_affiliation
import ai.decree as ai_decree
from core.commands import AIRuntimeError as _AIRuntimeError
from ui.gui_common import (PAPER, PAPER2, CARD, INK, DIM, RED, RED_D, GOLD, GREEN,
    BORDER, SEAL_BG, KAI, SANS, DECREE_CATEGORIES, LOCAL_ACTS,
    _bar, _format_effects, _judge_effects)


class PanelsGovernMixin:
    # 衙门 faction 简称 → 派系名（原 gui.py 类属性，拆分时保留）
    _FACTION_ALIAS = {"宦官": "宦官集团", "西军": "西军集团", "枢密": "清流言官"}

    def _chancellor_factions(self):
        """宰执派系（跟人，不跟派系）：占据宰相岗位（尚书左/右仆射）者所属派系。

        从运行态 central_orgs["尚书省"]["holders"] 动态判定：谁任宰相，其所属派系即宰执派系。
        若该派系 leader 恰是宰相本人，则该派系单列「宰执」；宰相换人后 UI 自动跟随，
        不依赖硬编码派系名。
        """
        holders = ((self.state.central_orgs or {}).get("尚书省") or {}).get("holders") or {}
        names = {holders.get(p) for p in ("尚书左仆射", "尚书右仆射")} - {None, ""}
        if not names:
            return set()
        return {fn for fn, f in (self.state.factions or {}).items()
                if f.get("leader") in names}

    def _panel_audience(self):
        """召对奏事（统一对话入口）：先选类别（部官/守臣/使节/领袖），再选人物入对。"""
        from ui import assets as res

        # 构建四类可召见人物
        # 部官：六部主官（按衙门取对应派系领袖）
        # 衙门 faction 字段为简称，需映射到派系名（如 宦官→宦官集团、西军→西军集团）
        _faction_alias = {"宦官": "宦官集团", "西军": "西军集团", "枢密": "清流言官"}
        bu_guan = []
        for yamen in YAMEN_LIST:
            fac_short = self.state.yamen[yamen]["faction"]
            fac_name = _faction_alias.get(fac_short, fac_short)
            leader = ""
            if fac_name in self.state.factions:
                leader = self.state.factions[fac_name]["leader"]
            kind = "military" if fac_name in ("西军集团", "宦官集团") else "civil"
            title = leader if leader else f"{yamen}堂官"
            bu_guan.append((title, f"尚书·{yamen}", kind, leader))
        # 守臣：诸路安抚 / 知事（以路名为守臣标识）
        shou_chen = []
        for name in PREFECTURE_LIST:
            shou_chen.append((f"知{name}事", name, "civil", ""))
        # 使节：外部势力来使
        shi_jie = []
        for name in self.state.external_regimes:
            info = self.state.external_regimes[name]
            shi_jie.append((f"{info.get('name', name)}使", f"{info.get('name', name)}国来使　势{info.get('power', 0)}　态{info.get('attitude', 0)}",
                            "foreign", ""))
        # 领袖：各派系领袖（与部官去重，仍单列便于专召）
        ling_xiu = []
        for fn in FACTION_NAMES:
            leader = self.state.factions[fn]["leader"]
            ling_xiu.append((leader, f"{fn}领袖", "military" if fn in ("阉党", "西军") else "civil", leader))

        CATS = [
            ("部官", bu_guan),
            ("守臣", shou_chen),
            ("使节", shi_jie),
            ("领袖", ling_xiu),
        ]

        tl, body = self._overlay("召对奏事", width=760, height=520)
        c = tk.Frame(body, bg=PAPER)
        c.pack(fill="both", expand=True)
        bg = res.audience_bg(size=(740, 500))
        if bg:
            bg_lbl = tk.Label(c, image=bg, bg=PAPER)
            bg_lbl.place(x=0, y=0, relwidth=1, relheight=1)
            tl._aud_bg = bg_lbl

        content = tk.Frame(c, bg=PAPER)
        content.pack(fill="both", expand=True, padx=24, pady=(0, 14))

        self._label(content, "召对奏事 · 垂询臣工", fg=RED_D, bg=PAPER,
                    font=self._font(KAI, 15, "bold")).pack(anchor="w", pady=(6, 2))
        self._label(content, "先择其类，再点人物入对；陛下亲问，而后朱批颁诏。",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 10)).pack(anchor="w", pady=(0, 8))

        # 左侧：类别标签 + 人物列表
        left = tk.Frame(content, bg=PAPER)
        left.pack(side="left", fill="y", padx=(0, 16))
        tab_frame = tk.Frame(left, bg=PAPER)
        tab_frame.pack(fill="x", pady=(0, 6))
        list_card = self._card(left)
        list_card.pack(fill="both", expand=True)
        lb = tk.Listbox(list_card, bg=CARD, fg=INK, selectbackground=RED,
                        selectforeground="#f3e6c4", font=self._font(SANS, 12),
                        relief="flat", height=9, bd=0, highlightthickness=0)
        lb.pack(fill="both", expand=True, padx=10, pady=10)

        # 右侧：预览
        right = tk.Frame(content, bg=PAPER)
        right.pack(side="left", fill="both", expand=True)
        pf = tk.Frame(right, bg=CARD, relief="ridge", bd=1,
                      highlightbackground=GOLD, highlightthickness=1)
        pf.pack(pady=(8, 8))
        pic_lbl = tk.Label(pf, image=None, bg=CARD, width=170, height=230)
        pic_lbl.pack(padx=5, pady=5)
        name_lbl = self._label(pf, "请选择对象", fg=INK, bg=CARD,
                               font=self._font(KAI, 13, "bold"), anchor="center")
        name_lbl.pack(fill="x", pady=(0, 4))
        role_lbl = self._label(right, "", fg=DIM, bg=PAPER, font=self._font(SANS, 11), anchor="w")
        role_lbl.pack(fill="x", pady=(2, 2))
        fac_lbl = self._label(right, "", fg=DIM, bg=PAPER, font=self._font(SANS, 11), anchor="w")
        fac_lbl.pack(fill="x", pady=(2, 2))
        hint_lbl = self._label(right, "", fg=INK, bg=PAPER, font=self._font(SANS, 10),
                               anchor="w", justify="left")
        hint_lbl.pack(fill="x", pady=(2, 2))

        current = {"cat": 0, "rows": []}

        def fill_list(cat_idx):
            current["cat"] = cat_idx
            lb.delete(0, "end")
            current["rows"] = CATS[cat_idx][1]
            for pers, role, kind, leader in current["rows"]:
                lb.insert("end", f"○ {pers}　{role}")
            if current["rows"]:
                lb.selection_set(0)
                update_preview()

        def update_preview(event=None):
            sel = lb.curselection()
            if not sel:
                return
            pers, role, kind, leader = current["rows"][sel[0]]
            name_lbl.config(text=pers)
            role_lbl.config(text=role)
            # 派系信息（仅部官/领袖有）
            fac_text = ""
            if leader:
                faction = next((n for n, fc in self.state.factions.items()
                                if fc["leader"] == leader), "")
                if faction:
                    f = self.state.factions[faction]
                    fac_text = f"派系：{faction}　影响力 {f['influence']}　支持 {f['satisfaction']}　凝聚 {f['cohesion']}"
            fac_lbl.config(text=fac_text)
            hint_lbl.config(text="双击或点“入对”，与臣工当面问对。")
            p = res.minister_portrait(kind, size=(170, 230))
            if p:
                pic_lbl.config(image=p)
                tl._preview_por = p

        # 类别标签按钮
        tab_btns = []
        for i, (name, _g) in enumerate(CATS):
            b = self._btn(tab_frame, name, lambda idx=i: (fill_list(idx), _hl(idx)),
                          width=8, ghost=False)
            b.pack(side="left", padx=3)
            tab_btns.append(b)

        def _hl(active):
            for i, b in enumerate(tab_btns):
                try:
                    b.config(relief="sunken" if i == active else "raised")
                except Exception:
                    pass

        lb.bind("<<ListboxSelect>>", update_preview)
        fill_list(0)
        _hl(0)

        def do_audience():
            sel = lb.curselection()
            if not sel:
                self.self.messagebox.showinfo("提示", "请先选择一位臣工。")
                return
            pers, role, kind, leader = current["rows"][sel[0]]
            tl.destroy()
            self._panel_dialogue(pers, role=role, kind=kind)

        bar = tk.Frame(c, bg=PAPER)
        bar.pack(pady=(0, 16))
        self._seal_btn(bar, "入 对", do_audience, big=True).pack(side="left", padx=8)
        self._btn(bar, "返 回", tl.destroy, width=12, ghost=True).pack(side="left", padx=8)
        lb.bind("<Double-Button-1>", lambda e: do_audience())

    def _panel_dialogue(self, minister, role="", kind=None):
        """与单个臣工奏对弹层：左侧立绘，右侧奏对记录 + 朱批输入 + 拟旨/返回。

        minister: 人物名（可为部官/守臣/使节/领袖）。
        role:     身份说明（如“尚书·户部”）。kind=None 时按派系自动判文武/外藩。
        """
        self._current_minister = minister
        from ui import assets as res

        # 宿主兼容：若已在 _open_overlay 卡片栈内（如群臣面板召见），直接渲染到当前卡片，
        # 避免再叠加一个 Toplevel 导致返回黑屏；否则仍用独立 _overlay 弹层。
        in_card = bool(self._overlay_stack)
        if in_card:
            body = self._panel_shell_root
            tl = None
        else:
            tl, body = self._overlay(f"召对 · {minister}", width=920, height=620)
        # 图片引用统一存 self，防止两套宿主下被 GC 回收（黑屏/白块）
        self._dialogue_bg = None
        self._dialogue_por = None
        self._dialogue_tl = tl

        c = tk.Frame(body, bg=PAPER)
        c.pack(fill="both", expand=True)
        bg = res.audience_bg(size=(900, 600))
        if bg:
            bg_lbl = tk.Label(c, image=bg, bg=PAPER)
            bg_lbl.place(x=0, y=0, relwidth=1, relheight=1)
            self._dialogue_bg = bg_lbl

        main = tk.Frame(c, bg=PAPER)
        main.pack(fill="both", expand=True, padx=18, pady=(0, 14))

        # 左侧：大臣立绘 + 名讳牌 + 派系属性
        left = tk.Frame(main, bg=PAPER, width=210)
        left.pack(side="left", fill="y", padx=(0, 14))

        faction = next((n for n, fc in self.state.factions.items()
                        if fc["leader"] == minister), "")
        if kind is None:
            kind = "military" if faction in ("阉党", "西军") else "civil"
        por = res.minister_portrait(kind, size=(190, 260))
        pf = tk.Frame(left, bg=CARD, relief="ridge", bd=1,
                      highlightbackground=GOLD, highlightthickness=1)
        pf.pack(pady=(6, 10))
        pic = tk.Label(pf, image=por if por else None, bg=CARD,
                       width=190, height=260)
        pic.pack(padx=5, pady=5)
        self._dialogue_por = por

        plaque = tk.Frame(left, bg=RED, relief="ridge", bd=1,
                          highlightbackground=GOLD, highlightthickness=1)
        plaque.pack(fill="x", pady=(0, 10))
        self._label(plaque, minister, fg="#f3e6c4", bg=RED,
                    font=self._font(KAI, 14, "bold"), anchor="center").pack(pady=4)

        if role:
            self._label(left, role, fg=DIM, bg=PAPER, font=self._font(SANS, 10)).pack(
                anchor="w", pady=(0, 6))
        if faction:
            f = self.state.factions[faction]
            self._label(left, f"派系：{faction}", fg=INK, bg=PAPER,
                        font=self._font(SANS, 10)).pack(anchor="w", pady=1)
            self._label(left, f"影响力 {f['influence']}　支持 {f['satisfaction']}",
                        fg=DIM, bg=PAPER, font=self._font(SANS, 9)).pack(anchor="w", pady=1)
            self._label(left, f"凝聚力 {f['cohesion']}",
                        fg=DIM, bg=PAPER, font=self._font(SANS, 9)).pack(anchor="w", pady=1)

        # 右侧：奏对记录 + 输入
        right = tk.Frame(main, bg=PAPER)
        right.pack(side="left", fill="both", expand=True)

        hist_frame = self._scrolled(right, bg=CARD, font=self._font(KAI, 12), padx=14, pady=12,
                                    scrollbar=False)
        hist_frame.pack(fill="both", expand=True, pady=(0, 8))
        hist = hist_frame._text
        hist.tag_configure("minister", foreground=RED_D, spacing1=6, spacing3=4,
                           lmargin1=8, lmargin2=8, font=self._font(KAI, 12, "bold"))
        hist.tag_configure("emperor", foreground=theme.DX_GOOD, spacing1=6,
                           spacing3=4, justify="right", font=self._font(KAI, 12))

        def refresh():
            entries = [(sp, tx) for sp, tx in self.state.dialogue_history
                       if sp == "朕" or sp == minister]
            hist.configure(state="normal")
            hist.delete("1.0", "end")
            if not entries:
                hist.insert("end", "（陛下尚未垂询，请下旨问对。）\n", "minister")
            for sp, tx in entries:
                if sp == "朕":
                    hist.insert("end", f"朕：{tx}\n\n", "emperor")
                else:
                    hist.insert("end", f"{sp}：{tx}\n\n", "minister")
            hist.configure(state="disabled")
            hist.see("end")

        refresh()

        # 朱批输入框
        input_card = self._card(right)
        input_card.pack(fill="x", pady=(0, 8))
        placeholder = "以朕之口吻垂询…（Enter 发送，Shift+Enter 换行）"
        txt = tk.Text(input_card, bg="#fffdf8", fg=DIM, relief="flat", wrap="word",
                      font=self._font(SANS, 11), height=3, padx=10, pady=8,
                      insertbackground=INK, highlightthickness=0, bd=0)
        txt.pack(fill="x", padx=12, pady=8)
        txt.insert("1.0", placeholder)

        def clear_placeholder(event=None):
            if txt.get("1.0", "end-1c") == placeholder:
                txt.delete("1.0", "end")
                txt.config(fg=INK)

        def restore_placeholder(event=None):
            if not txt.get("1.0", "end-1c").strip():
                txt.delete("1.0", "end")
                txt.insert("1.0", placeholder)
                txt.config(fg=DIM)

        txt.bind("<FocusIn>", clear_placeholder)
        txt.bind("<FocusOut>", restore_placeholder)

        def send():
            text = txt.get("1.0", "end-1c").strip()
            if not text or text == placeholder:
                return
            try:
                _, self.state = self.backend.action(
                    self.state, "audience_dialogue",
                    {"minister": minister, "text": text}, self.ai_client)
            except _AIRuntimeError as e:
                # AI 运行时故障：停下并提醒，不写对话、不刷新状态
                self.self.messagebox.showerror("AI 叙事中断", str(e))
                return
            txt.delete("1.0", "end")
            restore_placeholder()
            refresh()

        def on_return(event):
            # Shift+Enter 换行；单独 Enter 发送
            if event.state & 0x1:
                return
            send()
            return "break"

        txt.bind("<Return>", on_return)

        bar = tk.Frame(right, bg=PAPER)
        bar.pack(fill="x")
        self._seal_btn(bar, "发 送", send, big=True).pack(side="left", padx=6)
        def _close_dialogue():
            if in_card:
                self._close_overlay()
            else:
                self._dialogue_tl.destroy()

        self._btn(bar, "据此拟旨",
                  lambda: (_close_dialogue(), self._panel_decree_entry(minister)),
                  width=12, gold=True).pack(side="left", padx=6)
        self._btn(bar, "返 回", _close_dialogue, width=12, ghost=True).pack(side="left", padx=6)

    def _panel_decree_entry(self, minister=None):
        from content.data import ORG_AFFILIATION

        inner = self._panel_shell("拟 旨 颁 布", with_back=False)
        advice = ""
        if minister:
            for sp, tx in reversed(self.state.dialogue_history):
                if sp == minister:
                    advice = tx
                    break

        # 顶部 tab：圣旨回书 / 上月诏令 / 本月待签 / 奏报摘要
        tab_var = tk.StringVar(value="圣旨回书")
        tab_meta = ["圣旨回书", "本月待签", "上月诏令", "奏报摘要"]
        tab_bar = tk.Frame(inner, bg=PAPER2 if 'PAPER2' in globals() else "#efe6d2")
        tab_bar.pack(fill="x", padx=10, pady=(2, 6))
        tab_bodies = {}

        def _select_tab(name):
            tab_var.set(name)
            for n, b in tab_btns.items():
                b.config(relief="sunken" if n == name else "raised",
                         bg=(RED if n == name else PAPER2 if 'PAPER2' in globals() else "#efe6d2"))
            for n, body in tab_bodies.items():
                body.pack_forget() if n != name else body.pack(fill="both", expand=True, padx=10, pady=4)

        tab_btns = {}
        for n in tab_meta:
            b = tk.Button(tab_bar, text=n, font=self._font(KAI, 12, "bold"),
                          bg=(RED if n == tab_var.get() else PAPER2 if 'PAPER2' in globals() else "#efe6d2"),
                          fg=("#f3e6c4" if n == tab_var.get() else INK),
                          relief=("sunken" if n == tab_var.get() else "raised"),
                          cursor="hand2", command=lambda x=n: _select_tab(x))
            b.pack(side="left", padx=2, ipadx=10, ipady=4)
            tab_btns[n] = b

        # 主体：左右分栏
        main = tk.Frame(inner, bg=PAPER)
        main.pack(fill="both", expand=True, padx=10, pady=4)

        # 左栏：本月御旨/待签草稿列表
        left = tk.Frame(main, bg=PAPER, width=300)
        left.pack(side="left", fill="y", padx=(0, 10))
        self._title(left, "本月待签诏草", fg=RED_D, bg=PAPER, font=self._font(KAI, 13, "bold"),
                    anchor="w").pack(fill="x", pady=(2, 4))
        list_card = self._card(left)
        list_card.pack(fill="both", expand=True)
        lb = tk.Listbox(list_card, bg=CARD, fg=INK, selectbackground=RED, selectforeground="#f3e6c4",
                        font=self._font(SANS, 11), relief="flat", height=14, bd=0, highlightthickness=0)
        lb.pack(fill="both", expand=True, padx=10, pady=8)

        def _refresh_list():
            lb.delete(0, "end")
            if not self.state.edict_drafts:
                lb.insert("end", "（暂无可会签诏草）")
                return
            for i, d in enumerate(self.state.edict_drafts):
                org = d.get("org_hint", "政府")
                lb.insert("end", f"{i+1}. 〔{org}〕{d.get('title','')}")

        _refresh_list()

        list_bar = tk.Frame(left, bg=PAPER)
        list_bar.pack(fill="x", pady=4)
        self._btn(list_bar, "批改",
                  lambda: _open_draft_editor(lb.curselection()[0] if lb.curselection() else None),
                  width=10).pack(side="left", padx=3)
        self._btn(list_bar, "弃删",
                  lambda: _discard(lb.curselection()[0] if lb.curselection() else None),
                  width=10, ghost=True).pack(side="left", padx=3)
        self._btn(list_bar, "据此廷议",
                  lambda: _open_council(lb.curselection()[0] if lb.curselection() else None),
                  width=10, gold=True).pack(side="left", padx=3)

        # 右栏：起草御旨
        right = tk.Frame(main, bg=PAPER)
        right.pack(side="left", fill="both", expand=True)
        body_sheet = tk.Frame(right, bg=PAPER)
        tab_bodies["圣旨回书"] = body_sheet

        # 响应式 wraplength 管理：收集所有需随窗口宽度换行的 Label
        _resp_labels = []  # (widget, margin_ratio)

        if advice:
            self._label(body_sheet, f"据 {minister} 奏对意见草诏：", fg=RED_D, bg=PAPER,
                        font=self._font(KAI, 12), anchor="w").pack(padx=4, pady=2)
            ad_card = self._card(body_sheet)
            ad_card.pack(fill="x", padx=2, pady=2)
            ad_lbl = self._label(ad_card, advice, fg=INK, bg=CARD, font=self._font(SANS, 11),
                                 wraplength=520, justify="left")
            ad_lbl.pack(anchor="w", padx=12, pady=8)
            _resp_labels.append((ad_lbl, 48))

        self._label(body_sheet, "陛下诏意（例如：减免两浙路田赋，以安民心）：", fg=INK, bg=PAPER,
                    font=self._font(SANS, 11), anchor="w").pack(padx=4, pady=(6, 0))
        intent_card = self._card(body_sheet)
        intent_card.pack(fill="both", expand=True, padx=2, pady=2)
        intent = tk.Text(intent_card, bg="#fffdf8", fg=INK, insertbackground=INK, relief="flat",
                         wrap="word", font=self._font(SANS, 11), height=4, padx=10, pady=8,
                         highlightthickness=0, bd=0)
        intent.pack(fill="both", expand=True, padx=12, pady=8)
        if advice:
            intent.insert("1.0", advice)

        org_row = tk.Frame(body_sheet, bg=PAPER)
        org_row.pack(fill="x", padx=4, pady=2)
        self._label(org_row, "机构归属：", fg=INK, bg=PAPER, font=self._font(SANS, 11)).pack(side="left")
        org_var = tk.StringVar(value="政府")
        for o in ("内廷", "政府", "地方"):
            tk.Radiobutton(org_row, text=o, variable=org_var, value=o, bg=PAPER,
                           fg=(RED if o == "内廷" else INK), activebackground=PAPER,
                           font=self._font(KAI, 11, "bold"), cursor="hand2",
                           selectcolor=PAPER2 if 'PAPER2' in globals() else "#efe6d2",
                           relief="flat").pack(side="left", padx=10)
        self._label(org_row, "（润色后 AI 亦会据诏意判定，可手改）", fg=DIM, bg=PAPER,
                    font=self._font(SANS, 9)).pack(side="left", padx=4)

        # 预览卡（圣旨润色后展示）
        preview_card = self._card(body_sheet)
        preview_card.pack(fill="both", expand=True, padx=2, pady=4)
        pv_title = self._title(preview_card, "（诏书预览）", fg=RED, bg=CARD,
                               font=self._font(KAI, 15, "bold"), anchor="center")
        pv_title.pack(pady=(6, 2))
        pv_body = self._label(preview_card, "点按下方「圣旨润色」，知制诰将润色为正式诏书。",
                              fg=INK, bg=CARD, font=self._font(KAI, 12), wraplength=560, justify="left")
        pv_body.pack(anchor="w", padx=14, pady=4)
        _resp_labels.append((pv_body, 48))
        pv_eff = self._label(preview_card, "", fg=RED_D, bg=CARD, font=self._font(SANS, 11), anchor="w")
        pv_eff.pack(anchor="w", padx=14, pady=(2, 8))

        current_draft = {}

        def _render_preview(d):
            nonlocal current_draft
            current_draft = d
            pv_title.config(text=f"〔{d.get('org_hint','政府')}〕{d.get('title','')}")
            pv_body.config(text=d.get("body", ""))
            pv_eff.config(text=f"〔推演效果〕{_format_effects(d.get('effects', []))}")

        def _polish():
            text = intent.get("1.0", "end-1c").strip()
            if not text:
                self.self.messagebox.showinfo("提示", "请先写明诏意。")
                return
            try:
                d = self.ai_client.polish_decree(text, self.state.get_state_summary())
            except _AIRuntimeError as e:
                # AI 运行时故障：停下并提醒，不渲染预览
                self.self.messagebox.showerror("AI 叙事中断", str(e))
                return
            d["org_hint"] = org_var.get()
            if advice:
                d["source_minister"] = minister
            _render_preview(d)

        # 其他 tab 体
        tab_bodies["本月待签"] = tk.Frame(right, bg=PAPER)
        tab_bodies["上月诏令"] = tk.Frame(right, bg=PAPER)
        tab_bodies["奏报摘要"] = tk.Frame(right, bg=PAPER)

        def _render_other_tabs():
            # 本月待签
            f = tab_bodies["本月待签"]
            for w in list(f.children.values()):
                w.destroy()
            self._title(f, "本月待签诏草", fg=RED_D, bg=PAPER, font=self._font(KAI, 13, "bold"),
                        anchor="w").pack(fill="x", pady=4)
            if not self.state.edict_drafts:
                self._label(f, "（暂无可会签诏草）", fg=DIM, bg=PAPER, font=self._font(SANS, 11)).pack(padx=6, pady=6)
            for i, d in enumerate(self.state.edict_drafts):
                c = self._card(f)
                c.pack(fill="x", padx=4, pady=4)
                self._label(c, f"〔{d.get('org_hint','政府')}〕{d.get('title','')}",
                            fg=RED, bg=CARD, font=self._font(KAI, 13, "bold")).pack(anchor="w", padx=12, pady=(6, 2))
                body_lbl = self._label(c, d.get("body", ""), fg=INK, bg=CARD, font=self._font(KAI, 11),
                                        wraplength=560, justify="left")
                body_lbl.pack(anchor="w", padx=12, pady=2)
                _resp_labels.append((body_lbl, 48))
                self._label(c, f"〔推演效果〕{_format_effects(d.get('effects', []))}",
                            fg=RED_D, bg=CARD, font=self._font(SANS, 11)).pack(anchor="w", padx=12, pady=(2, 6))
                bb = tk.Frame(c, bg=CARD)
                bb.pack(fill="x", padx=12, pady=(0, 6))
                self._btn(bb, "去廷议", lambda i=i: _open_council(i), width=10, gold=True).pack(side="left", padx=3)
                self._btn(bb, "弃删", lambda i=i: _discard(i), width=10, ghost=True).pack(side="left", padx=3)
            # 上月诏令
            f2 = tab_bodies["上月诏令"]
            for w in list(f2.children.values()):
                w.destroy()
            self._title(f2, "上月已颁诏令", fg=RED_D, bg=PAPER, font=self._font(KAI, 13, "bold"),
                        anchor="w").pack(fill="x", pady=4)
            issued = self.state.pending_decrees + self.state.active_decrees
            if not issued:
                self._label(f2, "（暂无已颁诏令）", fg=DIM, bg=PAPER, font=self._font(SANS, 11)).pack(padx=6, pady=6)
            for i, d in enumerate(issued):
                c = self._card(f2)
                c.pack(fill="x", padx=4, pady=4)
                self._label(c, f"《{d.get('title','')}》〔{d.get('category','诏令')}〕",
                            fg=RED, bg=CARD, font=self._font(KAI, 13, "bold")).pack(anchor="w", padx=12, pady=(6, 2))
                desc_lbl = self._label(c, d.get("desc", ""), fg=INK, bg=CARD, font=self._font(KAI, 11),
                                        wraplength=560, justify="left")
                desc_lbl.pack(anchor="w", padx=12, pady=2)
                _resp_labels.append((desc_lbl, 48))
            # 奏报摘要
            f3 = tab_bodies["奏报摘要"]
            for w in list(f3.children.values()):
                w.destroy()
            self._title(f3, "奏报摘要", fg=RED_D, bg=PAPER, font=self._font(KAI, 13, "bold"),
                        anchor="w").pack(fill="x", pady=4)
            report = ""
            if self.ai_client and getattr(self.ai_client, "available", False):
                try:
                    report = self.ai_client.monthly_report(
                        self.state.year, self.state.month, self.state.era_name, self.state.posture)
                    if isinstance(report, dict):
                        report = report.get("report", "")
                    elif isinstance(report, str):
                        report = report.strip()
                        if report.startswith("{") or report.startswith("["):
                            try:
                                import json
                                data = json.loads(report)
                                if isinstance(data, dict):
                                    report = data.get("report", "")
                            except Exception:
                                pass
                except Exception:
                    report = ""
            report_lbl = self._label(f3, report or "（当前档期无奏报摘要，或 AI 不可用）", fg=INK, bg=PAPER,
                                       font=self._font(KAI, 11), wraplength=560, justify="left")
            report_lbl.pack(padx=6, pady=6)
            _resp_labels.append((report_lbl, 36))

        # 响应式：窗口/容器尺寸变化时动态更新所有 wraplength
        def _refresh_wraplength(event=None):
            w = right.winfo_width()
            if w > 60:
                for lbl, margin in _resp_labels:
                    try:
                        lbl.config(wraplength=max(120, w - margin))
                    except Exception:
                        pass

        right.bind("<Configure>", _refresh_wraplength)
        # 初始触发一次
        right.after(50, _refresh_wraplength)

        # 草稿操作
        def _open_draft_editor(idx):
            if idx is None:
                self.self.messagebox.showinfo("提示", "请先在左侧选择一道诏草。")
                return
            if idx >= len(self.state.edict_drafts):
                return
            d = self.state.edict_drafts[idx]
            tl, body = self._overlay(f"批改诏草 · {d.get('title','')}", width=720, height=560)
            self._label(body, "诏意正文（可直接修改）：", fg=INK, bg=PAPER, font=self._font(SANS, 11)).pack(padx=14, pady=4)
            txt = tk.Text(body, bg="#fffdf8", fg=INK, relief="flat", wrap="word",
                          font=self._font(SANS, 11), height=8, padx=10, pady=8, highlightthickness=0, bd=0)
            txt.pack(fill="x", padx=14, pady=4)
            txt.insert("1.0", d.get("body", ""))
            bb = tk.Frame(body, bg=PAPER)
            bb.pack(pady=10)

            def _save():
                d["body"] = txt.get("1.0", "end-1c").strip()
                nd = self.ai_client.polish_decree(d["body"], self.state.get_state_summary())
                for k in ("title", "effects", "org_hint"):
                    d[k] = nd.get(k, d.get(k))
                self.state.store_council_review(d["id"], {})
                _refresh_list(); _render_other_tabs()
                tl.destroy()
                self.self.messagebox.showinfo("已存", "诏草已批改，重入待签。")

            self._seal_btn(bb, "保 存 修 改", _save, big=True).pack(side="left", padx=8)
            self._btn(bb, "关 闭", tl.destroy, width=12, ghost=True).pack(side="left", padx=8)

        def _discard(idx):
            if idx is None:
                self.self.messagebox.showinfo("提示", "请先在左侧选择一道诏草。")
                return
            if idx >= len(self.state.edict_drafts):
                return
            d = self.state.edict_drafts[idx]
            self.state.remove_edict_draft(d["id"])
            _refresh_list(); _render_other_tabs()
            self.messagebox.showinfo("已弃", f"已弃删诏草「{d.get('title','')}」。")

        def _open_council(idx):
            # 若未选，则把当前润色草稿先入待签
            if idx is None:
                if not current_draft:
                    self.self.messagebox.showinfo("提示", "请先在右侧润色出诏草，或左侧选一道待签诏草。")
                    return
                did = self.state.add_edict_draft(dict(current_draft))
                idx = len(self.state.edict_drafts) - 1
                _refresh_list()
            d = self.state.edict_drafts[idx]
            _council_overlay(d)

        def _council_overlay(d):
            did = d["id"]
            review = self.state.council_reviews.get(did)
            if not review:
                try:
                    review = self.ai_client.council_review(d, self.state.get_state_summary(), state=self.state)
                except Exception:
                    review = {"memo": "（会签不可用）", "objections": "（门下省未见条目）",
                              "executions": "（六部俟旨）", "verdict": "可准", "revised_effects": []}
                self.state.store_council_review(did, review)
            tl, body = self._overlay("御前廷议", width=780, height=640)
            self._title(body, f"〔廷议〕{d.get('title','')}", fg=RED, font=self._font(KAI, 16, "bold")).pack(pady=6)

            # 依职权相关大臣回话（廷议：相关大臣先回话，皇帝可钦点他人入对）
            try:
                org_hint = d.get("org_hint", "政府")
                org_key = _org_by_affiliation(self.state, org_hint)
                rel = self.state.org_ministers(org_key) if org_key else []
            except Exception:
                org_key, rel = "", []
            if rel:
                self._label(body, f"依职权相关大臣：{'、'.join(rel)}（已据所司回话）",
                            fg=RED_D, bg=PAPER, font=self._font(KAI, 12, "bold"), anchor="w").pack(fill="x", padx=16, pady=(2, 2))

            # 钦点入对：可召其他朝臣廷前对质
            summon_row = tk.Frame(body, bg=PAPER)
            summon_row.pack(fill="x", padx=16, pady=2)
            self._label(summon_row, "钦点入对：", fg=INK, bg=PAPER, font=self._font(SANS, 11)).pack(side="left")
            summon_var = tk.StringVar(value="（请选）")
            try:
                all_names = [n for n in self.state.loyalty
                             if n not in rel and self.state.minister_status(n) == "active"]
            except Exception:
                all_names = []
            summon_menu = tk.OptionMenu(summon_row, summon_var, "（请选）", *all_names)
            summon_menu.config(bg=CARD, fg=INK, relief="flat", font=self._font(SANS, 11),
                               highlightthickness=0, activebackground=PAPER2)
            summon_menu["menu"].config(bg=CARD, fg=INK, font=self._font(SANS, 10))
            summon_menu.pack(side="left", padx=6)

            def _summon():
                who = summon_var.get()
                if not who or who == "（请选）":
                    self.self.messagebox.showinfo("提示", "请先钦点一位大臣入对。")
                    return
                tl.destroy()
                self._open_overlay(lambda: self._panel_dialogue(who, role=f"廷前入对·{d.get('title','')}"),
                                   f"廷议召对 · {who}")

            self._btn(summon_row, "召 入 对 质", _summon, width=12, gold=True).pack(side="left", padx=8)

            sc = self._scrolled(body, bg=CARD, font=self._font(KAI, 12), height=18)
            sc.pack(fill="both", expand=True, padx=14, pady=6)
            t = sc._text
            t.tag_configure("h", foreground=RED_D, font=self._font(KAI, 12, "bold"))
            t.tag_configure("b", foreground=INK, font=self._font(KAI, 12))
            t.insert("end", "【中书省拟稿】\n", "h")
            t.insert("end", review.get("memo", "") + "\n\n", "b")
            t.insert("end", "【门下省封驳】\n", "h")
            t.insert("end", review.get("objections", "") + "\n\n", "b")
            t.insert("end", "【尚书省及六部执行】\n", "h")
            t.insert("end", review.get("executions", "") + "\n\n", "b")
            t.insert("end", f"【会签结论】{review.get('verdict','可准')}\n", "h")
            rev = review.get("revised_effects", [])
            if rev:
                t.insert("end", f"〔拟改效果〕{_format_effects(rev)}\n", "b")
            bb = tk.Frame(body, bg=PAPER)
            bb.pack(pady=8)

            def _approve():
                msg, self.state = self.backend.action(
                    self.state, "issue_edict_from_review", {"draft_id": did, "decision": "approve"})
                self._pending_logs.append(msg)
                _refresh_list(); _render_other_tabs(); tl.destroy()
                self.self.messagebox.showinfo("已准奏", msg)

            def _reject():
                msg, self.state = self.backend.action(
                    self.state, "reject_edict_draft", {"draft_id": did})
                self._pending_logs.append(msg)
                _refresh_list(); _render_other_tabs(); tl.destroy()
                self.self.messagebox.showinfo("已打回", msg)

            def _force():
                msg, self.state = self.backend.action(
                    self.state, "issue_edict_from_review", {"draft_id": did, "decision": "force"})
                self._pending_logs.append(msg)
                _refresh_list(); _render_other_tabs(); tl.destroy()
                self.self.messagebox.showinfo("御笔直发", msg)

            self._seal_btn(bb, "准 奏", _approve, big=True).pack(side="left", padx=6)
            self._btn(bb, "打 回", _reject, width=12).pack(side="left", padx=6)
            self._btn(bb, "御笔强推（中旨）", _force, width=16, gold=True).pack(side="left", padx=6)

        # 底部按钮栏：圣旨润色 / 去廷议 / 御笔直发 / 汇成诏书
        bottom = tk.Frame(inner, bg=PAPER)
        bottom.pack(side="bottom", fill="x", padx=10, pady=8)
        self._seal_btn(bottom, "圣 旨 润 色", _polish, big=True).pack(side="left", padx=6)
        self._btn(bottom, "去 廷 议", lambda: _open_council(None), width=12, gold=True).pack(side="left", padx=6)
        self._btn(bottom, "御 笔 直 发（明诏）",
                  lambda: self._direct_issue(current_draft, org_var.get(), is_secret=False), width=14).pack(side="left", padx=6)
        self._btn(bottom, "密 旨 直 发",
                  lambda: self._direct_issue(current_draft, org_var.get(), is_secret=True), width=12,
                  ghost=True).pack(side="left", padx=6)
        self._btn(bottom, "汇 成 诏 书",
                  lambda: self._merge_selected(lb), width=12).pack(side="left", padx=6)
        self._btn(bottom, "关 闭",
                  lambda: self._close_overlay(),
                  width=12, ghost=True).pack(side="right", padx=6)

        _select_tab("圣旨回书")
        _render_other_tabs()

    def _direct_issue(self, draft, org_hint, is_secret=False):
        if not draft:
            self.messagebox.showinfo("提示", "请先在右侧润色出诏草。")
            return
        text = draft.get("body") or draft.get("text") or draft.get("intent") or ""
        if not text.strip():
            self.messagebox.showinfo("提示", "诏意正文为空。")
            return
        summary = self.state.get_state_summary()
        res = ai_decree.parse_decree(text, summary, is_secret=is_secret)
        if res.get("_error"):
            self.messagebox.showerror("拟旨失败", res.get("narrative", "AI 不可用。"))
            return
        minister = draft.get("source_minister") or self._current_minister or "陛下"
        msg, self.state = self.backend.action(
            self.state, "issue_free_decree",
            {"parse_result": res, "minister": minister, "is_secret": is_secret})
        self._pending_logs.append(f"〔拟旨〕{msg}")
        self._log(f"〔拟旨〕{msg}")
        self._refresh_hud()
        self.messagebox.showinfo("御笔直发", f"{msg}\n\n推演按语：{res.get('narrative','')}")
        # 回到纯舆图（关闭本浮层）
        self._close_overlay()

    def _merge_selected(self, lb):
        sel = list(lb.curselection())
        if not sel:
            self.messagebox.showinfo("提示", "请在左侧选择若干道诏草（Ctrl/Shift 多选）以汇成一道。")
            return
        ids = [self.state.edict_drafts[i]["id"] for i in sel if i < len(self.state.edict_drafts)]
        msg, self.state = self.backend.action(self.state, "merge_drafts", {"draft_ids": ids})
        self._pending_logs.append(msg)
        self._switch_panel(self._panel_decree_entry, "拟旨颁布")
        self.messagebox.showinfo("汇成", msg)

    def _panel_secret_decree(self):
        inner = self._panel_shell("批答密旨")
        self._label(inner, "密旨（仅对单一派系/将领生效，成功率受忠诚度影响）", fg=RED_D, bg=PAPER,
                    font=self._font(KAI, 12), anchor="w", justify="left").pack(padx=12, pady=6)
        card = self._card(inner)
        card.pack(fill="x", padx=10, pady=4)
        lb = tk.Listbox(card, bg=CARD, fg=INK, selectbackground=RED, selectforeground="#f3e6c4",
                        font=self._font(SANS, 11), relief="flat", height=6, bd=0, highlightthickness=0)
        lb.pack(fill="x", padx=14, pady=10)
        for i, name in enumerate(FACTION_NAMES, 1):
            lb.insert("end", f"[{i}] {name}")
        self._label(card, "密旨内容（简述）", fg=INK, bg=CARD, font=self._font(SANS, 11),
                    anchor="w").pack(anchor="w", padx=14, pady=(4, 0))
        desc = tk.Entry(card, bg="#fff", fg=INK, insertbackground=INK, relief="flat",
                        font=self._font(SANS, 11), bd=1, highlightthickness=0)
        desc.pack(fill="x", padx=14, pady=(2, 10))

        def do():
            sel = lb.curselection()
            if not sel:
                self.self.messagebox.showinfo("提示", "请选择目标派系。")
                return
            target = FACTION_NAMES[sel[0]]
            msg, self.state = self.backend.action(
                self.state, "issue_secret_decree",
                {"target": target, "content": desc.get().strip()})
            self._pending_logs.append(f"密旨→{target}：{msg}")
            self._switch_panel(self._panel_overview, "朝堂一览")

        desc.bind("<Return>", lambda e: do())
        desc.bind("<KP_Enter>", lambda e: do())

        bar = tk.Frame(inner, bg=PAPER)
        bar.pack(pady=10)
        self._seal_btn(bar, "下 达", do, big=True).pack(side="left", padx=8)

    def _panel_yamen(self):
        """群臣：大臣列表（宰执 + 派系领袖 + 六部尚书），可召见奏对。施政一律走拟旨。"""
        inner = self._panel_shell("群 臣")
        self._label(inner, "朝堂臣工，各有职司；召见入对，垂询天下。凡施政诏令，皆由圣旨推演。",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 11), anchor="w").pack(padx=12, pady=(2, 10))
        s = self.state
        chancellors = self._chancellor_factions()

        # 宰执（单列，朱红描金以示尊崇；跟人——占宰相岗位者所属派系）
        self._card_title2(inner, "宰 执")
        fc = self._card(inner)
        fc.pack(fill="x", padx=10, pady=4)
        for fn in chancellors:
            if fn not in s.factions:
                continue
            f = s.factions[fn]
            row = tk.Frame(fc, bg=CARD, highlightbackground=GOLD, highlightthickness=1)
            row.pack(fill="x", padx=12, pady=4)
            self._title(row, f["leader"], fg=RED_D, bg=CARD, font=self._font(KAI, 14, "bold"), anchor="w").pack(side="left")
            self._label(row, f"{fn}·宰执　影响{f['influence']}　心向{f['satisfaction']}",
                        fg=DIM, bg=CARD, font=self._font(SANS, 10), anchor="e").pack(side="right")
            self._btn(row, "召见奏对", lambda m=f["leader"], fn=fn: self._open_overlay(
                lambda: self._panel_dialogue(m, role=f"{fn}·宰执"), f"召对 · {m}"),
                width=10, ghost=False).pack(side="right", padx=6)

        # 其余派系领袖
        self._card_title2(inner, "派 系 领 袖")
        fc2 = self._card(inner)
        fc2.pack(fill="x", padx=10, pady=4)
        for fn in FACTION_NAMES:
            if fn in chancellors:
                continue
            f = s.factions[fn]
            row = tk.Frame(fc2, bg=CARD)
            row.pack(fill="x", padx=12, pady=4)
            self._title(row, f["leader"], fg=RED, bg=CARD, font=self._font(KAI, 13, "bold"), anchor="w").pack(side="left")
            self._label(row, f"{fn}·影响{f['influence']}　心向{f['satisfaction']}",
                        fg=DIM, bg=CARD, font=self._font(SANS, 10), anchor="e").pack(side="right")
            self._btn(row, "召见奏对", lambda m=f["leader"], fn=fn: self._open_overlay(
                lambda: self._panel_dialogue(m, role=f"{fn}·领袖"), f"召对 · {m}"),
                width=10, ghost=False).pack(side="right", padx=6)

        # 六部尚书
        self._card_title2(inner, "中 枢 六 部 尚 书")
        yc = self._card(inner)
        yc.pack(fill="x", padx=10, pady=4)
        for name in YAMEN_LIST:
            y = s.yamen[name]
            fac_name = self._FACTION_ALIAS.get(y["faction"], y["faction"])
            leader = s.factions[fac_name]["leader"] if fac_name in s.factions else ""
            row = tk.Frame(yc, bg=CARD)
            row.pack(fill="x", padx=12, pady=4)
            self._title(row, name, fg=RED, bg=CARD, font=self._font(KAI, 13, "bold"), anchor="w").pack(side="left")
            self._label(row, f"尚书 {leader}　效{y['efficiency']}%", fg=DIM, bg=CARD,
                        font=self._font(SANS, 10), anchor="e").pack(side="right")
            self._btn(row, "召见奏对", lambda m=leader or f"{name}堂官", nm=name: self._open_overlay(
                lambda: self._panel_dialogue(m, role=f"尚书·{nm}"), f"召对 · {m}"),
                width=10, ghost=False).pack(side="right", padx=6)

    def _panel_map(self):
        """地图为全屏常驻底图，本函数仅刷新 HUD。"""
        self._refresh_hud()
        if getattr(self, "_map_cv", None):
            self._map_cv.refresh()

    def _show_region_detail(self, key, external=False):
        """点击舆图区域 → 浮层详情（复用既有浮层机制，不依赖右侧详情卡）。"""
        s = self.state
        if not external:
            name = s.prefectures.get(key, {}).get("name", key)
            self._open_overlay(lambda: self._panel_prefecture(key),
                               f"{name}·地方政令")
        else:
            ex = s.external_regimes.get(key, {})
            ename = ex.get("name", key)
            # 外交类施政统一走拟旨（圣旨推演）
            self._open_overlay(self._panel_decree_entry, f"{ename}·外交纵横")

    def _ext_att(self, key):
        """安全读取外部政权态度。"""
        ex = getattr(self.state, "external_regimes", {}).get(key, {})
        return int(ex.get("attitude", 50))

    def _panel_todo(self):
        inner = self._panel_shell("在 办 事 务")
        s = self.state
        tab_frame = tk.Frame(inner, bg=PAPER)
        tab_frame.pack(fill="x", padx=12, pady=6)
        body = tk.Frame(inner, bg=PAPER)
        body.pack(fill="both", expand=True, padx=12, pady=4)

        def _draw(tab):
            for w in body.winfo_children():
                w.destroy()
            for b, t in tabs:
                b.configure(bg=RED if t == tab else CARD, fg="#f3e6c4" if t == tab else RED_D)
            if tab == "公开事务":
                items = list(getattr(s, "longterm_public", []))
            else:
                items = list(getattr(s, "longterm_secret", []))
            if not items:
                self._label(body, "— 暂无在办" + tab + " —", fg=DIM, bg=PAPER,
                            font=self._font(SANS, 12)).pack(anchor="center", pady=30)
                return
            for t in items:
                card = tk.Frame(body, bg=PAPER)
                card.pack(fill="x", padx=8, pady=5, ipady=4)
                if tab == "密令":
                    card.configure(relief="ridge", bd=1, highlightbackground="#6b4e16",
                                   highlightthickness=1)
                self._label(card, t.get("task_name", t.get("title", "事务")),
                            fg=INK, bg=card["bg"], font=self._font(KAI, 13, "bold"),
                            anchor="w").pack(anchor="w", padx=10, pady=(4, 2))
                prog = int(t.get("progress", 0))
                bar = tk.Frame(card, bg="#e0d3b3", height=10)
                bar.pack(fill="x", padx=10, pady=(0, 4))
                tk.Frame(bar, bg=RED, width=max(2, int(bar.winfo_width() * prog / 100)) if bar.winfo_width() > 1 else 2,
                         height=10).place(x=0, y=0)
                self._label(card, f"承办：{t.get('minister','—')}   进度 {prog}%\n{t.get('last_log','')}",
                            fg=DIM, bg=card["bg"], font=self._font(SANS, 9), anchor="w",
                            justify="left").pack(anchor="w", padx=10, pady=(0, 4))

        tabs = []
        for label, key in [("公 开 事 务", "公开事务"), ("密 令", "密令")]:
            b = self._btn(tab_frame, label, lambda k=key: _draw(k), width=12, gold=(key == "公开事务"))
            b.pack(side="left", padx=4)
            tabs.append((b, key))
        _draw("公开事务")

    def _panel_daily_log(self):
        inner = self._panel_shell("朝 报")
        box = self._scrolled(inner, bg=CARD, font=self._font(SANS, 10), padx=12, pady=6)
        box._text.configure(state="normal")
        txt = self._log_text()
        box._text.delete("1.0", "end")
        box._text.insert("end", txt)
        box._text.configure(state="disabled")
        box.pack(fill="both", expand=True, padx=10, pady=(2, 8))

    def _log_text(self):
        s = self.state
        parts = [f"〔{s.era_name}{s.year}年{s.month}月〕"]
        for m in getattr(self, "_log_lines", []):
            parts.append(m)
        return "\n".join(parts)

