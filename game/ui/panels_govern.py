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
import ai.client as ai_decree
from core.commands import AIRuntimeError as _AIRuntimeError
from ui.gui_common import (PAPER, PAPER2, CARD, INK, DIM, RED, RED_D, GOLD, GREEN,
    BORDER, SEAL_BG, KAI, SANS, DECREE_CATEGORIES,
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

        # 对话口谕内帑调拨（商量确认式）：待准栏（已谕未准时显示 + 准/罢）
        pending_bar = tk.Frame(right, bg=PAPER)
        pending_bar.pack(fill="x", pady=(0, 4))

        def _refresh_pending():
            for w in pending_bar.winfo_children():
                w.destroy()
            p = getattr(self.state, "pending_inner_transfer", None)
            if not p:
                return
            amt = int(p["amount"])
            self._label(pending_bar, f"已谕：发内帑 {amt} 贯入国库，待准", fg="#8a671e",
                        bg=PAPER, font=self._font(KAI, 11)).pack(side="left", padx=4)
            def _confirm():
                from core.commands_decree import confirm_inner_transfer
                msg = confirm_inner_transfer(self.state)
                self.state.dialogue_history.append((minister, f"（朱批）{msg}"))
                refresh(); _refresh_pending()
            def _cancel():
                from core.commands_decree import cancel_inner_transfer
                msg = cancel_inner_transfer(self.state)
                self.state.dialogue_history.append((minister, f"（朱批）{msg}"))
                refresh(); _refresh_pending()
            self._seal_btn(pending_bar, "准", _confirm, big=False).pack(side="left", padx=4)
            self._btn(pending_bar, "罢", _cancel, width=6, ghost=True).pack(side="left", padx=4)
        _refresh_pending()

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

        dialogue_ctl = {"busy": False, "send_btn": None, "set_loading": None}

        def _set_dialogue_busy(v):
            dialogue_ctl["busy"] = bool(v)
            btn = dialogue_ctl["send_btn"]
            if btn is not None:
                try:
                    btn.config(state="disabled" if v else "normal")
                except Exception:
                    pass
            set_loading = dialogue_ctl["set_loading"]
            if set_loading is not None:
                try:
                    set_loading(v)
                except Exception:
                    pass

        def send():
            if dialogue_ctl["busy"]:
                return  # 推演中防重复点击
            text = txt.get("1.0", "end-1c").strip()
            if not text or text == placeholder:
                return
            # 对话口谕内帑调拨（商量确认式）：输入含「内帑」→ 提议待准（不即时划账，不走 AI 召对）
            if any(k in text for k in ("发内帑", "拨内帑", "内帑")):
                from core.commands_decree import propose_inner_transfer
                amt = _parse_inner_amount(text)
                if amt is None:
                    self.messagebox.showwarning(
                        "内帑调拨", "未识别金额，请注明如「发内帑 50 万入国库」")
                    return
                msg = propose_inner_transfer(self.state, amt)
                self.state.dialogue_history.append(("朕", text))
                self.state.dialogue_history.append((minister, f"（回奏）{msg}"))
                txt.delete("1.0", "end")
                restore_placeholder()
                refresh()
                _refresh_pending()
                return
            if not (self.ai_client and getattr(self.ai_client, "available", False)):
                self.messagebox.showerror(
                    "AI 叙事中断",
                    "AI 叙事不可用：召对需要 AI 接入。请在「游戏设置 → AI 配置」中完成配置后重试。")
                return
            # T6 异步召对：主线程先入史/快照，AI 后台推演（加载环），回奏主线程落地
            try:
                from core.commands import audience_dialogue_prepare, audience_dialogue_apply
                kwargs, note = audience_dialogue_prepare(self.state, minister, text)
            except Exception as e:
                self.messagebox.showerror("召对准备失败", str(e))
                return
            if note is not None:
                # 已薨/罢黜：prepare 已写入史册说明，直接刷新
                refresh()
                _refresh_pending()
                return
            _set_dialogue_busy(True)

            def _on_success(obj):
                _set_dialogue_busy(False)
                try:
                    reply = audience_dialogue_apply(self.state, minister, obj)
                except Exception as e:
                    self.messagebox.showerror("AI 叙事中断", str(e))
                    return
                if not reply:
                    self.messagebox.showerror(
                        "AI 叙事中断",
                        "AI 叙事不可用：召对需要 AI 接入。请在「游戏设置 → AI 配置」中完成配置后重试。")
                    return
                txt.delete("1.0", "end")
                restore_placeholder()
                refresh()
                _refresh_pending()

            def _on_error(exc):
                _set_dialogue_busy(False)
                if isinstance(exc, _AIRuntimeError):
                    self.messagebox.showerror("AI 叙事中断", str(exc))
                else:
                    self.messagebox.showerror("召对错误", str(exc))

            from core.async_ai import run_ai_call
            run_ai_call(self.ai_client, "dialogue", **kwargs,
                        on_success=_on_success, on_error=_on_error, ui=self.root)

        def on_return(event):
            # Shift+Enter 换行；单独 Enter 发送
            if event.state & 0x1:
                return
            send()
            return "break"

        txt.bind("<Return>", on_return)

        bar = tk.Frame(right, bg=PAPER)
        bar.pack(fill="x")
        dialogue_ctl["send_btn"] = self._seal_btn(bar, "发 送", send, big=True)
        dialogue_ctl["send_btn"].pack(side="left", padx=6)
        _ring, _set_loading = self._busy_ring(bar, size=44)
        _ring.pack(side="left", padx=(4, 0))
        dialogue_ctl["set_loading"] = _set_loading
        def _close_dialogue():
            if in_card:
                self._close_overlay()
            else:
                self._dialogue_tl.destroy()

        self._btn(bar, "据此拟旨",
                  lambda: (_close_dialogue(), self._panel_decree_entry(minister)),
                  width=12, gold=True).pack(side="left", padx=6)
        self._btn(bar, "返 回", _close_dialogue, width=12, ghost=True).pack(side="left", padx=6)

    def _close_and_switch(self, fn, title):
        """关闭当前浮层并转调目标面板（朝局简报跳转用）。"""
        try:
            self._close_overlay()
        except Exception:
            pass
        self._switch_panel(fn, title)

    def _render_briefing(self, parent):
        """朝局简报：程序规则可行动项（确定性推导，无 AI，不伪造），可点击跳转对应面板。

        挂载点：月报面板（奏报摘要）顶部。规则来自 core.briefing（只读 state）。
        """
        from core.briefing import build_briefing_actions
        actions = build_briefing_actions(self.state)
        card = self._card(parent)
        card.pack(fill="x", padx=2, pady=(2, 6))
        self._card_title(card, "朝 局 简 报 · 可 行 事 项")
        goto_map = {
            "decree": (self._panel_decree_entry, "拟旨颁布"),
            "audience": (self._panel_yamen, "群 臣"),
            "tech": (self._panel_tech, "科 技 树"),
            "army": (self._panel_military_affairs, "军政机务"),
            "todo": (self._panel_todo, "在 办 事 务"),
        }
        for a in actions:
            row = tk.Frame(card, bg=CARD)
            row.pack(fill="x", padx=12, pady=1)
            # 非纯颜色传意：急务用「●」符号 + 朱批色双编码
            if a.get("urgent"):
                mark, col = "● ", theme.DX_URGENT
            else:
                mark, col = "○ ", theme.DX_NORMAL
            self._label(row, mark + str(a.get("title", "")), fg=col, bg=CARD,
                        font=self._font(KAI, 11, "bold"), anchor="w").pack(side="left")
            self._label(row, str(a.get("desc", "")), fg=INK, bg=CARD,
                        font=self._font(SANS, 9), anchor="w").pack(side="left", padx=(6, 0))
            fn, title = goto_map.get(a.get("goto"), (self._panel_decree_entry, "拟旨颁布"))
            self._btn(row, "前 往",
                      lambda f=fn, t=title: self._close_and_switch(f, t),
                      width=6, ghost=True).pack(side="right", padx=4)

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

        polish_ctl = {"btn": None, "busy": False}

        def _polish():
            if polish_ctl["busy"]:
                return  # 推演中防重复点击
            text = intent.get("1.0", "end-1c").strip()
            if not text:
                self.messagebox.showinfo("提示", "请先写明诏意。")
                return
            if not (self.ai_client and getattr(self.ai_client, "available", False)):
                self.messagebox.showwarning(
                    "AI 未接入", "未接入 AI，请配置 OpenAI 兼容 API（base_url/api_key/model）：游戏设置 → AI 配置。")
                return
            # T6 异步化：后台润色，主线程落地渲染；任务中按钮禁用 + 预览显示推演中
            polish_ctl["busy"] = True
            btn = polish_ctl["btn"]
            if btn is not None:
                try:
                    btn.config(state="disabled")
                except Exception:
                    pass
            pv_body.config(text="推演中…（知制诰润色诏书）")
            summary = self.state.get_state_summary()   # 主线程快照

            def _on_success(d):
                polish_ctl["busy"] = False
                if btn is not None:
                    try:
                        btn.config(state="normal")
                    except Exception:
                        pass
                try:
                    pv_body.config(text="点按下方「圣旨润色」，知制诰将润色为正式诏书。")
                except Exception:
                    pass
                d["org_hint"] = org_var.get()
                if advice:
                    d["source_minister"] = minister
                _render_preview(d)

            def _on_error(e):
                polish_ctl["busy"] = False
                if btn is not None:
                    try:
                        btn.config(state="normal")
                    except Exception:
                        pass
                try:
                    pv_body.config(text="润色失败，可重试。")
                except Exception:
                    pass
                self.messagebox.showerror("AI 叙事中断", str(e))

            from core.async_ai import run_ai_call
            run_ai_call(self.ai_client, "polish_decree", text, summary,
                        on_success=_on_success, on_error=_on_error, ui=self.root)

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
            # 朝局简报（可行动项程序规则；确定性，无 AI，AI 缺失不降级伪造）
            try:
                self._render_briefing(f3)
            except Exception:
                pass
            report = ""
            if not (self.ai_client and getattr(self.ai_client, "available", False)):
                self.messagebox.showwarning(
                    "AI 未接入", "未接入 AI，请配置 OpenAI 兼容 API（base_url/api_key/model）：游戏设置 → AI 配置。奏报暂缺。")
                report_lbl = self._label(f3, "（当前档期无奏报摘要，或 AI 不可用）", fg=INK, bg=PAPER,
                                         font=self._font(KAI, 11), wraplength=560, justify="left")
                report_lbl.pack(padx=6, pady=6)
                _resp_labels.append((report_lbl, 36))
            else:
                # T6 异步：月折后台生成，完成后回填（不阻塞 tab 渲染；朝局 hash 缓存防重复烧 token）
                report_lbl = self._label(f3, "推演中…（起居注修月折）", fg=DIM, bg=PAPER,
                                         font=self._font(KAI, 11), wraplength=560, justify="left")
                report_lbl.pack(padx=6, pady=6)
                _resp_labels.append((report_lbl, 36))
                summary_args = (self.state.year, self.state.month,
                                self.state.era_name, self.state.posture)

                def _on_success(report):
                    text = report.get("report", "") if isinstance(report, dict) else str(report or "")
                    try:
                        report_lbl.config(text=text or "（当前档期无奏报摘要）")
                    except Exception:
                        pass

                def _on_error(e):
                    try:
                        report_lbl.config(text=f"（月折生成失败：{e}）")
                    except Exception:
                        pass

                from core.async_ai import run_ai_call
                run_ai_call(self.ai_client, "monthly_report", *summary_args,
                            on_success=_on_success, on_error=_on_error, ui=self.root)

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

            save_ctl = {"btn": None, "busy": False}

            def _save():
                if save_ctl["busy"]:
                    return  # 推演中防重复点击
                d["body"] = txt.get("1.0", "end-1c").strip()
                # T6 异步化：润色后台执行，保存按钮禁用，完成后主线程落地
                save_ctl["busy"] = True
                btn = save_ctl["btn"]
                if btn is not None:
                    try:
                        btn.config(state="disabled")
                    except Exception:
                        pass
                summary = self.state.get_state_summary()

                def _on_success(nd):
                    save_ctl["busy"] = False
                    if btn is not None:
                        try:
                            btn.config(state="normal")
                        except Exception:
                            pass
                    for k in ("title", "effects", "org_hint"):
                        d[k] = nd.get(k, d.get(k))
                    self.state.store_council_review(d["id"], {})
                    _refresh_list(); _render_other_tabs()
                    try:
                        tl.destroy()
                    except Exception:
                        pass
                    self.messagebox.showinfo("已存", "诏草已批改，重入待签。")

                def _on_error(e):
                    save_ctl["busy"] = False
                    if btn is not None:
                        try:
                            btn.config(state="normal")
                        except Exception:
                            pass
                    self.messagebox.showerror("AI 叙事中断", str(e))

                from core.async_ai import run_ai_call
                run_ai_call(self.ai_client, "polish_decree", d["body"], summary,
                            on_success=_on_success, on_error=_on_error, ui=self.root)

            save_ctl["btn"] = self._seal_btn(bb, "保 存 修 改", _save, big=True)
            save_ctl["btn"].pack(side="left", padx=8)
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

            def _render_review(rev):
                t.delete("1.0", "end")
                t.insert("end", "【中书省拟稿】\n", "h")
                t.insert("end", rev.get("memo", "") + "\n\n", "b")
                t.insert("end", "【门下省封驳】\n", "h")
                t.insert("end", rev.get("objections", "") + "\n\n", "b")
                t.insert("end", "【尚书省及六部执行】\n", "h")
                t.insert("end", rev.get("executions", "") + "\n\n", "b")
                t.insert("end", f"【会签结论】{rev.get('verdict','可准')}\n", "h")
                r2 = rev.get("revised_effects", [])
                if r2:
                    t.insert("end", f"〔拟改效果〕{_format_effects(r2)}\n", "b")

            if review:
                _render_review(review)
            elif not (self.ai_client and getattr(self.ai_client, "available", False)):
                # AI 未接入：规则意见代替（明确标注，不伪造 AI 文本）
                fb = {"memo": "（会签不可用）", "objections": "（门下省未见条目）",
                      "executions": "（六部俟旨）", "verdict": "可准", "revised_effects": []}
                self.state.store_council_review(did, fb)
                _render_review(fb)
            else:
                # T6 异步会签：先渲染"推演中"，完成后主线程回填
                _render_review({"memo": "（廷议推演中…）", "objections": "（门下省核议中…）",
                                "executions": "（六部承旨待办中…）", "verdict": "—", "revised_effects": []})
                summary = self.state.get_state_summary()

                def _on_success(rev):
                    self.state.store_council_review(did, rev)
                    try:
                        _render_review(rev)
                    except Exception:
                        pass

                def _on_error(e):
                    fb = {"memo": "（会签不可用）", "objections": "（门下省未见条目）",
                          "executions": "（六部俟旨）", "verdict": "可准", "revised_effects": []}
                    self.state.store_council_review(did, fb)
                    try:
                        _render_review(fb)
                    except Exception:
                        pass
                    self.messagebox.showerror("AI 叙事中断", str(e))

                from core.async_ai import run_ai_call
                run_ai_call(self.ai_client, "council_review", d, summary, state=self.state,
                            on_success=_on_success, on_error=_on_error, ui=self.root)
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
        polish_ctl["btn"] = self._seal_btn(bottom, "圣 旨 润 色", _polish, big=True)
        polish_ctl["btn"].pack(side="left", padx=6)
        self._btn(bottom, "去 廷 议", lambda: _open_council(None), width=12, gold=True).pack(side="left", padx=6)
        _direct_btns = []
        _d1 = self._btn(bottom, "御 笔 直 发（明诏）",
                        lambda: self._direct_issue(current_draft, org_var.get(), is_secret=False,
                                                   _busy_btns=_direct_btns), width=14)
        _d1.pack(side="left", padx=6)
        _direct_btns.append(_d1)
        _d2 = self._btn(bottom, "密 旨 直 发",
                        lambda: self._direct_issue(current_draft, org_var.get(), is_secret=True,
                                                   _busy_btns=_direct_btns), width=12,
                        ghost=True)
        _d2.pack(side="left", padx=6)
        _direct_btns.append(_d2)
        self._btn(bottom, "汇 成 诏 书",
                  lambda: self._merge_selected(lb), width=12).pack(side="left", padx=6)
        self._btn(bottom, "关 闭",
                  lambda: self._close_overlay(),
                  width=12, ghost=True).pack(side="right", padx=6)

        _select_tab("圣旨回书")
        _render_other_tabs()

    def _direct_issue(self, draft, org_hint, is_secret=False, _busy_btns=None):
        if getattr(self, "_direct_issue_busy", False):
            return  # 推演中防重复点击
        if not draft:
            self.messagebox.showinfo("提示", "请先在右侧润色出诏草。")
            return
        text = draft.get("body") or draft.get("text") or draft.get("intent") or ""
        if not text.strip():
            self.messagebox.showinfo("提示", "诏意正文为空。")
            return
        summary = self.state.get_state_summary()

        def _set_busy(v):
            self._direct_issue_busy = bool(v)
            for _b in (_busy_btns or []):
                if _b is not None:
                    try:
                        _b.config(state="disabled" if v else "normal")
                    except Exception:
                        pass

        def _land(res):
            _set_busy(False)
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

        if not (self.ai_client and getattr(self.ai_client, "available", False)):
            # 无 AI：同步程序兜底（_fallback_parse 含 _error 标记，不伪造）
            try:
                res = ai_decree.parse_decree(text, summary, is_secret=is_secret)
            except Exception as e:
                self.messagebox.showerror("AI 叙事中断", str(e))
                return
            _land(res)
            return
        # T6 异步化：拟旨解析后台执行，任务中按钮禁用
        _set_busy(True)

        def _on_success(res):
            try:
                _land(res)
            except Exception as e:
                _set_busy(False)
                self.messagebox.showerror("AI 叙事中断", str(e))

        def _on_error(e):
            _set_busy(False)
            self.messagebox.showerror("AI 叙事中断", str(e))

        from core.async_ai import run_ai_call
        run_ai_call(self.ai_client, "parse_decree", text, summary, is_secret=is_secret,
                    on_success=_on_success, on_error=_on_error, ui=self.root)

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

    # 中枢面板机构分组（只列中枢机构官员；运行态以 state.central_orgs 为权威）
    _CENTRAL_ORG_GROUPS = (
        ("宰 执（尚书省）", ("尚书省",)),
        ("三 省·中书门下", ("中书省", "门下省")),
        ("枢 密 院", ("枢密院",)),
        ("三 衙", ("殿前司", "侍卫亲军马军司", "侍卫亲军步军司")),
        ("中 枢 六 部", ("吏部", "户部", "礼部", "兵部", "刑部", "工部")),
    )

    def _faction_of(self, name):
        """大臣姓名 → 派系名（state.factions leader 反查；回退 MINISTERS 档案）。"""
        try:
            for fn, f in self.state.factions.items():
                if f.get("leader") == name:
                    return fn
        except Exception:
            pass
        try:
            from content.ministers.data import MINISTERS
            return MINISTERS.get(name, {}).get("faction", "")
        except Exception:
            return ""

    def _panel_central_org(self):
        """中枢面板：只列中枢机构官员（宰执/三省/枢密/三衙/六部 holders），
        显示官职 + 姓名 + 派系，可召对奏对。数据源 state.central_orgs + MINISTERS。"""
        inner = self._panel_shell("中 枢")
        self._label(inner, "中枢机要，百官之枢。凡在任者皆可召对奏事；施政诏令仍由圣旨推演。",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 11), anchor="w").pack(
            padx=12, pady=(2, 10))
        s = self.state
        orgs = getattr(s, "central_orgs", None) or {}
        shown = 0
        for gtitle, keys in self._CENTRAL_ORG_GROUPS:
            cards = []
            for key in keys:
                o = orgs.get(key)
                if not o or o.get("abolished"):
                    continue
                for title, holder in (o.get("holders") or {}).items():
                    if holder:
                        cards.append((
                            self._minister_card_data(holder, f"{key}·{title}"),
                            self._minister_kind(holder),
                            lambda m=holder, t=f"{title}", k=key: self._open_overlay(
                                lambda: self._panel_dialogue(m, role=f"{k}·{t}"),
                                f"召对 · {m}")))
            if not cards:
                continue
            self._card_title2(inner, gtitle)
            gc = self._card(inner)
            gc.pack(fill="x", padx=10, pady=4)
            self._minister_card_grid(gc, cards)
            shown += len(cards)
        if not shown:
            self._label(inner, "（中枢机要暂无在任者）", fg=DIM, bg=PAPER,
                        font=self._font(SANS, 11)).pack(padx=12, pady=10)

    def _minister_kind(self, name):
        """大臣立绘分类：military（西军等）/ civil（含宦官回退）；按派系档案 kind 判定。"""
        try:
            from content.ministers.data import FACTION_PROFILES
            for fn, f in self.state.factions.items():
                if f.get("leader") == name:
                    k = FACTION_PROFILES.get(fn, {}).get("kind", "civil")
                    return "military" if k == "military" else "civil"
        except Exception:
            pass
        return "civil"

    def _minister_card_data(self, name, role_label):
        """大臣卡片数据：名字/年龄/官职/个性/生平（脱敏——不含 loyalty/corruption）。

        数据源：MINISTERS（born/role/traits）+ persona.get_persona().style（性格一句话）
        + A14 简介（CODEX_MINISTER_BIO，其余由职司程序生成）。
        """
        from content.ministers.data import MINISTERS
        from content.codex_text import CODEX_MINISTER_BIO
        fig = MINISTERS.get(name, {}) or {}
        age = ""
        try:
            born = int(fig.get("born", 0) or 0)
            if born > 0:
                age = int(self.state.year) - born
        except Exception:
            age = ""
        style = ""
        try:
            from content.ministers.persona import get_persona
            style = str(get_persona(name).get("style", "") or "")
        except Exception:
            style = ""
        if not style:
            style = str(fig.get("traits", "") or "").replace("/", "，")
        bio = CODEX_MINISTER_BIO.get(name, "")
        if not bio:
            role = str(fig.get("role", "") or "")
            bio = f"{role}。" if role else "朝中大臣。"
        return {"name": name, "age": age, "role": role_label,
                "style": style, "bio": bio}

    def _minister_card(self, parent, data, kind, on_audience):
        """大臣立绘卡片：主体立绘 + 名字(年龄) / 官职 / 个性 / 生平 + 召见奏对。

        宋式：描金卡片 + 分类立绘（civil=文臣 / military=武将占位），下方依次信息行。
        """
        from ui import assets as res
        card = tk.Frame(parent, bg=CARD, relief="ridge", bd=1,
                        highlightbackground=GOLD, highlightthickness=1)
        por = res.minister_portrait(kind, size=(150, 200))
        pic = tk.Label(card, image=por if por else None, bg=CARD)
        pic.pack(pady=(10, 2))
        if por:
            card._por = por   # 防 GC 回收（黑屏）
        age_txt = f"（{data['age']} 岁）" if data.get("age") else ""
        self._title(card, f"{data['name']}{age_txt}", fg=RED_D, bg=CARD,
                    font=self._font(KAI, 13, "bold"), anchor="center").pack(pady=(2, 0))
        self._label(card, data.get("role", ""), fg=RED, bg=CARD,
                    font=self._font(SANS, 9, "bold"), anchor="center").pack(pady=(0, 2))
        if data.get("style"):
            self._label(card, f"性格：{data['style']}", fg=INK, bg=CARD,
                        font=self._font(SANS, 9), anchor="center",
                        wraplength=160).pack(pady=(0, 1))
        if data.get("bio"):
            self._label(card, data["bio"], fg=DIM, bg=CARD, font=self._font(SANS, 8),
                        anchor="w", wraplength=170, justify="left").pack(padx=8, pady=(0, 2))
        self._btn(card, "召见奏对", on_audience, width=10).pack(pady=(2, 8))
        return card

    def _minister_card_grid(self, parent, cards):
        """大臣卡片网格（3 列）：cards = [(data, kind, on_audience), ...]。"""
        for i, (data, kind, on_aud) in enumerate(cards):
            row, col = i // 3, i % 3
            self._minister_card(parent, data, kind, on_aud).grid(
                row=row, column=col, padx=6, pady=6, sticky="nsew")
        for c in range(3):
            parent.grid_columnconfigure(c, weight=1)

    # 外交势力区域分组（与 content/data.py EXTERNAL_REGIMES 注释分区对齐，单一映射源）
    _DIPLO_GROUPS = (
        ("北方与西北", ("辽", "西夏", "吐蕃", "喀尔喀蒙古", "漠南蒙古", "科尔沁",
                     "察哈尔", "海西", "建州", "东海")),
        ("东 方", ("高丽", "日本", "琉球")),
        ("西南与南方", ("大理", "安南", "占城", "真腊", "暹罗", "缅甸", "喜马拉雅山南诸国")),
        ("中亚南亚", ("注辇", "西辽", "高昌回鹘", "汪古部")),
        ("南 洋", ("吕宋", "柔佛", "苏门答剌", "婆罗", "爪哇", "美洛居", "渤泥")),
    )

    def _panel_diplomacy(self):
        """外交：势力列表（按区域分组）→ 省份/当前关系/国主对话（异步框架）。

        数据源：EXTERNAL_REGIMES（运行态 external_regimes）+ EXTERNAL_PROVINCES（省份权重）
        + state 关系（attitude/alliance_jin_liao/_sui_gong）。国主对话契约
        （diplomacy_dialogue）与条约（treaties）由谷承构落地后自动接入。
        """
        from content.data import EXTERNAL_PROVINCES
        from ui.format_units import humanize_coin
        inner = self._panel_shell("外 交")
        self._label(inner, "四夷八荒，邦交纵横。择一国主，面议和战盟约；凡条约之成，皆载史册。",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 11), anchor="w").pack(padx=12, pady=(2, 8))
        s = self.state
        regimes = getattr(s, "external_regimes", None) or {}

        main = tk.Frame(inner, bg=PAPER)
        main.pack(fill="both", expand=True, padx=10, pady=4)

        # —— 左：势力列表（按组）——
        left = tk.Frame(main, bg=PAPER, width=280)
        left.pack(side="left", fill="y", padx=(0, 10))
        self._label(left, "诸 国", fg=RED_D, bg=PAPER, font=self._font(KAI, 12, "bold"),
                    anchor="w").pack(fill="x", pady=(0, 2))
        lb = tk.Listbox(left, bg=CARD, fg=INK, selectbackground=RED,
                        selectforeground="#f3e6c4", font=self._font(SANS, 10),
                        relief="flat", bd=0, highlightthickness=0)
        lb.pack(fill="both", expand=True, padx=6, pady=6)
        rows = []
        for gtitle, keys in self._DIPLO_GROUPS:
            lb.insert("end", f"── {gtitle} ──")
            rows.append(None)
            for k in keys:
                r = regimes.get(k)
                if not r:
                    continue
                att = int(r.get("attitude", 50) or 50)
                lb.insert("end", f"  {k}　力 {r.get('power', 0)}　态 {att}")
                rows.append(k)

        # —— 右：详情（省份 + 关系 + 对话）——
        right = tk.Frame(main, bg=PAPER)
        right.pack(side="left", fill="both", expand=True)

        def _render_detail(idx):
            if idx >= len(rows) or rows[idx] is None:
                return
            key = rows[idx]
            r = regimes.get(key) or {}
            for w in right.winfo_children():
                w.destroy()
            # 头部：势力名 + 国力/态度/人口/月税
            head = tk.Frame(right, bg=PAPER)
            head.pack(fill="x")
            self._title(head, key, fg=RED, bg=PAPER, font=self._font(KAI, 16, "bold"),
                        anchor="w").pack(side="left")
            self._label(head,
                        f"力 {r.get('power', 0)}　态 {int(r.get('attitude', 50) or 50)}　"
                        f"口 {int(r.get('population', 0) or 0)} 万　"
                        f"月税 {humanize_coin(int(r.get('monthly_tax', 0) or 0))}",
                        fg=DIM, bg=PAPER, font=self._font(SANS, 10), anchor="e").pack(side="right")
            # 省份卡
            self._card_title2(right, "诸 省 分 野")
            pcard = self._card(right)
            pcard.pack(fill="x", padx=2, pady=4)
            provs = EXTERNAL_PROVINCES.get(key, [("本部", 1.0)])
            pop = int(r.get("population", 0) or 0)
            tax = int(r.get("monthly_tax", 0) or 0)
            for pname, weight in provs:
                row = tk.Frame(pcard, bg=CARD)
                row.pack(fill="x", padx=12, pady=2)
                self._label(row, f"　{pname}", fg=INK, bg=CARD,
                            font=self._font(KAI, 11, "bold"), anchor="w").pack(side="left")
                self._label(row,
                            f"{int(weight * 100)}%　口 {int(pop * weight)} 万　税 {humanize_coin(int(tax * weight))}",
                            fg=DIM, bg=CARD, font=self._font(SANS, 9), anchor="e").pack(side="right")
            # 当前关系卡
            self._card_title2(right, "当 前 关 系")
            rcard = self._card(right)
            rcard.pack(fill="x", padx=2, pady=4)
            _att = int(r.get("attitude", 50) or 50)
            _word = "友善" if _att >= 70 else ("一般" if _att >= 40 else ("敌视" if _att >= 20 else "仇敌"))
            rels = [f"态度：{_word}（{_att}）"]
            if key == "金" and getattr(s, "alliance_jin_liao", False):
                rels.append("盟约：已联金抗辽")
            if getattr(s, "_sui_gong", False):
                rels.append("岁币：已纳岁币")
            self._label(rcard, "　" + "　".join(rels), fg=INK, bg=CARD,
                        font=self._font(SANS, 10), anchor="w").pack(anchor="w", padx=12, pady=6)
            self._label(rcard, "　（条约记录/盟约/岁币/战争协议契约由谷承构落地后接入）",
                        fg=DIM, bg=CARD, font=self._font(SANS, 9), anchor="w").pack(
                anchor="w", padx=12, pady=(0, 6))
            # 国主对话区（异步框架：diplomacy_dialogue 契约待接入）
            self._card_title2(right, "国 主 会 面")
            dcard = self._card(right)
            dcard.pack(fill="both", expand=True, padx=2, pady=4)
            self._label(dcard, f"{key}国主（君主档案与外交对话契约待接入）",
                        fg=DIM, bg=CARD, font=self._font(SANS, 9), anchor="w").pack(
                anchor="w", padx=12, pady=2)
            log_txt = self._scrolled(dcard, bg="#fffdf8", font=self._font(SANS, 10), height=6)
            log_txt.pack(fill="both", expand=True, padx=10, pady=2)
            entry_row = tk.Frame(dcard, bg=CARD)
            entry_row.pack(fill="x", padx=10, pady=(2, 6))
            entry = tk.Entry(entry_row, bg="#fffdf8", fg=INK, relief="flat",
                             font=self._font(SANS, 10), insertbackground=INK,
                             highlightthickness=1, highlightbackground=BORDER)
            entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
            ctl = {"busy": False, "btn": None}
            ring, set_loading = self._busy_ring(entry_row, size=36)
            ring.pack(side="left", padx=(0, 4))
            ctl["set_loading"] = set_loading

            def _send_diplomacy():
                if ctl["busy"]:
                    return
                text = entry.get().strip()
                if not text:
                    self.messagebox.showinfo("提示", "请先写下要与国主商议之事。")
                    return
                ctl["busy"] = True
                btn = ctl["btn"]
                if btn is not None:
                    try:
                        btn.config(state="disabled")
                    except Exception:
                        pass
                if ctl["set_loading"]:
                    try:
                        ctl["set_loading"](True)
                    except Exception:
                        pass
                log_txt._text.configure(state="normal")
                log_txt._text.insert("end", f"朕：{text}\n\n")
                log_txt._text.see("end")
                log_txt._text.configure(state="disabled")

                def _on_success(reply):
                    ctl["busy"] = False
                    if btn is not None:
                        try:
                            btn.config(state="normal")
                        except Exception:
                            pass
                    if ctl["set_loading"]:
                        try:
                            ctl["set_loading"](False)
                        except Exception:
                            pass
                    reply_text = reply.get("reply", "") if isinstance(reply, dict) else str(reply or "")
                    log_txt._text.configure(state="normal")
                    log_txt._text.insert("end", f"{key}国主：{reply_text}\n\n")
                    log_txt._text.see("end")
                    log_txt._text.configure(state="disabled")

                def _on_error(exc):
                    ctl["busy"] = False
                    if btn is not None:
                        try:
                            btn.config(state="normal")
                        except Exception:
                            pass
                    if ctl["set_loading"]:
                        try:
                            ctl["set_loading"](False)
                        except Exception:
                            pass
                    if isinstance(exc, TypeError) and "diplomacy_dialogue" in str(exc):
                        self.messagebox.showinfo(
                            "待接入", "外交对话契约（diplomacy_dialogue）由谷承构落地后自动生效。")
                    else:
                        self.messagebox.showerror("AI 叙事中断", str(exc))

                from core.async_ai import run_ai_call
                run_ai_call(self.ai_client, "diplomacy_dialogue",
                            key, text, self.state.posture,
                            on_success=_on_success, on_error=_on_error, ui=self.root)

            ctl["btn"] = self._seal_btn(entry_row, "遣 使", _send_diplomacy, big=False)
            ctl["btn"].pack(side="right")

        def _on_select(event=None):
            sel = lb.curselection()
            if sel:
                _render_detail(sel[0])

        lb.bind("<<ListboxSelect>>", _on_select)
        # 默认选中「辽」
        for i, k in enumerate(rows):
            if k == "辽":
                lb.selection_set(i)
                lb.see(i)
                _render_detail(i)
                break

    def _panel_yamen(self):
        """群臣：大臣立绘卡片（宰执 + 派系领袖 + 六部尚书），可召见奏对。施政一律走拟旨。"""
        inner = self._panel_shell("群 臣")
        self._label(inner, "朝堂臣工，各有职司；召见入对，垂询天下。凡施政诏令，皆由圣旨推演。",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 11), anchor="w").pack(padx=12, pady=(2, 10))
        s = self.state
        chancellors = self._chancellor_factions()

        # 宰执（卡片网格，朱红描金以示尊崇；跟人——占宰相岗位者所属派系）
        self._card_title2(inner, "宰 执")
        cards = []
        for fn in chancellors:
            if fn not in s.factions:
                continue
            f = s.factions[fn]
            m = f["leader"]
            cards.append((
                self._minister_card_data(m, f"{fn}·宰执"),
                self._minister_kind(m),
                lambda mm=m, fn2=fn: self._open_overlay(
                    lambda: self._panel_dialogue(mm, role=f"{fn2}·宰执"), f"召对 · {mm}")))
        if cards:
            fc = self._card(inner)
            fc.pack(fill="x", padx=10, pady=4)
            self._minister_card_grid(fc, cards)

        # 其余派系领袖（卡片网格）
        self._card_title2(inner, "派 系 领 袖")
        cards = []
        for fn in FACTION_NAMES:
            if fn in chancellors:
                continue
            f = s.factions[fn]
            m = f["leader"]
            cards.append((
                self._minister_card_data(m, f"{fn}·领袖"),
                self._minister_kind(m),
                lambda mm=m, fn2=fn: self._open_overlay(
                    lambda: self._panel_dialogue(mm, role=f"{fn2}·领袖"), f"召对 · {mm}")))
        if cards:
            fc2 = self._card(inner)
            fc2.pack(fill="x", padx=10, pady=4)
            self._minister_card_grid(fc2, cards)

        # 六部尚书（卡片网格）
        self._card_title2(inner, "中 枢 六 部 尚 书")
        cards = []
        for name in YAMEN_LIST:
            y = s.yamen[name]
            fac_name = self._FACTION_ALIAS.get(y["faction"], y["faction"])
            leader = s.factions[fac_name]["leader"] if fac_name in s.factions else ""
            cards.append((
                self._minister_card_data(leader or f"{name}堂官", f"尚书·{name}"),
                self._minister_kind(leader or f"{name}堂官"),
                lambda m=leader or f"{name}堂官", nm=name: self._open_overlay(
                    lambda: self._panel_dialogue(m, role=f"尚书·{nm}"), f"召对 · {m}")))
        if cards:
            yc = self._card(inner)
            yc.pack(fill="x", padx=10, pady=4)
            self._minister_card_grid(yc, cards)

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


# 对话口谕内帑调拨：金额解析（支持「50万」「500000」「五十万」→ 贯整数；失败返回 None）
_CN_NUM = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6,
           "七": 7, "八": 8, "九": 9, "十": 10, "百": 100, "千": 1000, "万": 10000}


def _cn_amount(s: str):
    """中文数字 → int（五十万=500000、十二万=120000、三千=3000）。"""
    total, num = 0, 0
    for ch in s:
        v = _CN_NUM.get(ch)
        if v is None:
            return None
        if v == 10000:
            total = (total + num if (total or num) else 1) * 10000
            num = 0
        elif v >= 10:
            total += (num if num else 1) * v
            num = 0
        else:
            num = v
    return total + num


def _parse_inner_amount(text: str):
    """从召对输入提取内帑调拨金额（贯）；支持 500000 / 50万 / 五十万；失败返回 None。"""
    t = str(text).replace(",", "").replace("，", "")
    import re
    m = re.search(r"(\d+)\s*万", t)
    if m:
        return int(m.group(1)) * 10000
    m = re.search(r"\d+", t)
    if m:
        return int(m.group(0))
    m = re.search(r"[零一二两三四五六七八九十百千万]+", t)
    if m:
        return _cn_amount(m.group(0))
    return None
