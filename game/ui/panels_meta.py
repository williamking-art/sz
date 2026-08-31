# -*- coding: utf-8 -*-
"""宋祚 · GUI meta 面板 Mixin。

存档 / 读档 / 设置 / AI 配置 / 事件等杂项面板。共享常量与工具见 ui.gui_common。
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


class PanelsMetaMixin:
    def _panel_save_load(self, mode=None):
        """存档/读档面板。mode 可选 'save'/'load'，用于高亮对应操作按钮。"""
        inner = self._panel_shell("存档 · 读档")
        slots = self.backend.save_slots()

        def slot_label(s):
            if s.get("empty"):
                return f"[{s['slot']}] 空槽位"
            return f"[{s['slot']}] {s['time']} | {s['era']}{s['year']}年{s['month']}月"

        card = self._card(inner)
        card.pack(fill="x", padx=10, pady=4)
        lb = tk.Listbox(card, bg=CARD, fg=INK, selectbackground=RED, selectforeground="#f3e6c4",
                        font=self._font(SANS, 11), relief="flat", height=10, bd=0, highlightthickness=0)
        lb.pack(fill="x", padx=14, pady=10)
        for s in slots:
            lb.insert("end", slot_label(s))

        def do_save():
            sel = lb.curselection()
            if not sel:
                self.self.messagebox.showinfo("提示", "请选择槽位。")
                return
            slot = slots[sel[0]]["slot"]
            if self.backend.save(self.state, slot):
                self.self.messagebox.showinfo("完成", f"已保存至槽位 {slot}。")
                self._switch_panel(self._panel_overview, "朝堂一览")
            else:
                self.self.messagebox.showerror("失败", "存档失败。")

        def do_load():
            sel = lb.curselection()
            if not sel:
                self.self.messagebox.showinfo("提示", "请选择槽位。")
                return
            slot = slots[sel[0]]
            if slot.get("empty"):
                self.self.messagebox.showinfo("提示", "该槽位为空。")
                return
            loaded = self.backend.load(slot["slot"])
            if loaded is None:
                self.self.messagebox.showerror("失败", "读档失败，存档可能已损坏。")
                return
            self.state = loaded
            self._pending_logs = []
            self._inited = False
            self._switch_panel(self._panel_overview, "朝堂一览")

        bar = tk.Frame(inner, bg=PAPER)
        bar.pack(pady=10)
        save_btn = self._seal_btn(bar, "保 存", do_save, big=True)
        save_btn.pack(side="left", padx=8)
        load_btn = self._seal_btn(bar, "读 档", do_load, big=True)
        load_btn.pack(side="left", padx=8)
        # 依入口 mode 高亮对应操作（存档入口高亮保存，加载入口高亮读档）
        if mode == "save":
            save_btn.configure(bg=GOLD, fg=INK, activebackground="#d9b25a", activeforeground=INK)
        elif mode == "load":
            load_btn.configure(bg=GOLD, fg=INK, activebackground="#d9b25a", activeforeground=INK)

    def _panel_settings(self):
        """设置浮层：聚合 存档 / 加载 / 主菜单 / 设置 四个入口。"""
        inner = self._panel_shell("设 置")

        def open_save():
            self._open_overlay(lambda: self._panel_save_load("save"), "存档 · 读档")
        def open_load():
            self._open_overlay(lambda: self._panel_save_load("load"), "存档 · 读档")
        def back_menu():
            # 直接回主菜单（关掉设置浮层由 _build_main_menu 的 _clear_all 处理）
            self._ui_back_to_menu()
        def open_misc():
            self._open_overlay(self._panel_misc, "设 置")
        def open_ai():
            self._open_overlay(lambda: self._panel_ai_config("settings"), "AI 配 置")

        menu = tk.Frame(inner, bg=PAPER)
        menu.pack(expand=True, fill="both", padx=40, pady=24)
        entries = [
            ("存 档", open_save),
            ("加 载", open_load),
            ("AI 配 置", open_ai),
            ("主菜单", back_menu),
            ("设 置", open_misc),
        ]
        for text, fn in entries:
            self._seal_btn(menu, text, fn, big=True).pack(pady=10, ipadx=40)

    # ---------- 杂项设置（音量占位 / 界面字号档位）----------
    def _misc_config_path(self):
        if getattr(sys, "frozen", False):
            base = os.path.dirname(os.path.abspath(sys.executable))
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "ui_config.json")

    def _misc_get(self, key, default=None):
        try:
            import json
            with open(self._misc_config_path(), encoding="utf-8") as f:
                return json.load(f).get(key, default)
        except Exception:
            return default

    def _misc_set(self, **kw):
        try:
            import json
            p = self._misc_config_path()
            data = {}
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
            data.update(kw)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _panel_misc(self):
        """杂项设置浮层：音量（占位）+ 界面字号档位。"""
        inner = self._panel_shell("设 置")
        # —— 音量 ——
        self._section(inner, "声 音")
        self._label(inner, "音频系统尚未接入，调节暂不影响实际声音（预留）。",
                    fg=DIM, bg=PAPER).pack(padx=30, pady=(4, 2), anchor="w")
        vol = tk.IntVar(value=int(self._misc_get("volume", 60)))

        def _vol_cb(v):
            self._misc_set(volume=int(v))

        sc = tk.Scale(inner, from_=0, to=100, orient="horizontal", variable=vol,
                      command=_vol_cb, bg=PAPER, fg=INK, troughcolor=PAPER2,
                      highlightthickness=0, font=self._font(SANS, 10), length=240)
        sc.pack(padx=30, pady=(2, 16), anchor="w")
        # —— 字体（T10：楷体太细 → 可换宋体/黑体/雅黑/自定义；KAI 默认加粗）——
        self._section(inner, "字 体")
        self._label(inner, "界面字体：楷体 / 宋体 / 黑体 / 雅黑 / 系统默认（含 assets/fonts 自定义字体）",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 9)).pack(padx=30, pady=(4, 2), anchor="w")
        ff_var = tk.StringVar(value=getattr(self, "_font_family_choice", "楷体"))
        ff_row = tk.Frame(inner, bg=PAPER)
        ff_row.pack(padx=30, pady=(2, 8), anchor="w")
        self._label(ff_row, "字 体：", fg=INK, bg=PAPER, font=self._font(SANS, 11)).pack(side="left")
        ff_menu = tk.OptionMenu(ff_row, ff_var, *[k for k, _lab in self._font_options()])
        ff_menu.config(bg=CARD, fg=INK, relief="flat", font=self._font(SANS, 11),
                       highlightthickness=0, activebackground=PAPER2)
        ff_menu["menu"].config(bg=CARD, fg=INK, font=self._font(SANS, 10))
        ff_menu.pack(side="left", padx=8)

        def _ff_cb(*_a):
            key = ff_var.get()
            self._misc_set(font_family=key)
            self._font_family_choice = key
            self._apply_kai_family()
            self.messagebox.showinfo("字体已更新",
                                     f"界面字体已切换为「{key}」，新开面板即生效（已开面板需重开）。")

        ff_var.trace_add("write", _ff_cb)
        # —— 界面字号 ——
        self._section(inner, "界 面 字 号")
        self._label(inner, "字号档位：小 / 中 / 大 / 特大（改后即时作用于新开面板）",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 9)).pack(padx=30, pady=(4, 2), anchor="w")
        fs = tk.IntVar(value=int(self._misc_get("font_scale", 1)))
        from ui.panels_basic import _FONT_SCALE_TABLE as _FST

        def _font_cb():
            self._misc_set(font_scale=int(fs.get()))
            self._font_scale = _FST.get(int(fs.get()), 1.0)   # 实时生效（新开面板）

        row = tk.Frame(inner, bg=PAPER)
        row.pack(padx=30, pady=(2, 8), anchor="w")
        for lab, val in [("小", 0), ("中", 1), ("大", 2), ("特大", 3)]:
            tk.Radiobutton(row, text=lab, variable=fs, value=val, command=_font_cb,
                           bg=PAPER, fg=INK, font=self._font(SANS, 10), anchor="w").pack(
                side="left", padx=12)
        # —— Token 计量（工程可见性；命中率明细不占 HUD）——
        self._section(inner, "工 程 可 见 性")
        tk_row = tk.Frame(inner, bg=PAPER)
        tk_row.pack(padx=30, pady=(2, 10), anchor="w")
        self._btn(tk_row, "Token 用量",
                  lambda: self._open_overlay(self._panel_token_meter, "Token 用量"),
                  width=14, gold=True).pack(side="left", padx=4)
        self._btn(tk_row, "清零计量", self._reset_token_meter, width=10,
                  ghost=True).pack(side="left", padx=4)
        self._label(inner, "token 明细与召对命中率见「Token 用量」表；顶栏只保留总量。",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 9)).pack(padx=30, pady=(0, 8), anchor="w")

    # 契约方法 → 显示分组（Token 计量表；按调用类型聚合，单一映射源）
    _TOKEN_GROUPS = {
        "召对·AI": {"dialogue"},
        "拟旨": {"polish_decree", "draft_decree", "parse_decree"},
        "会签": {"council_review"},
        "推演": {"economy_decide", "diplomacy_decide", "military_decide", "relief_decide",
                 "finance_decide", "treasury_decide", "granary_decide", "faction_decide",
                 "land_local_decide", "era_decide", "invest_decide", "free_effect_decide",
                 "survey_settle", "decree_execute_decide", "emperor_personal_decide",
                 "hidden_state_decide", "build_new_branch_decide", "research_decide"},
        "月报叙事": {"monthly_report", "event_narrative", "advice", "final_eval"},
    }
    _TOKEN_GROUP_ORDER = ("拟旨", "会签", "推演", "月报叙事")

    @staticmethod
    def _token_group_of(method: str) -> str:
        """契约方法名 → 显示分组（未命中归「其它」）；纯静态，供 UI 与测试共用。"""
        for grp, methods in PanelsMetaMixin._TOKEN_GROUPS.items():
            if method in methods:
                return grp
        return "其它"

    def _token_meter_rows(self):
        """组装 Token 计量表行（含召对命中行与合计行）。

        数据源：AIClient.meter_summary()（按方法分桶 token）+ state._dialogue_stats
        （召对预过滤/缓存命中与 AI 调用次数）+ token_usage（总桶）。
        """
        st = getattr(self.state, "_dialogue_stats", None) or {}
        pre = int(st.get("prefilter_hits", 0) or 0)
        ch = int(st.get("cache_hits", 0) or 0)
        ai_calls = int(st.get("ai_calls", 0) or 0)
        rows = [
            ("召对·预过滤命中", pre, 0, 0, pre),
            ("召对·缓存命中", ch, 0, 0, ch),
        ]
        meter = self.ai_client.meter_summary() if self.ai_client else {
            "total": {"prompt": 0, "completion": 0, "calls": 0}, "by_method": {}}
        by = meter.get("by_method", {})
        groups = {}
        for m, b in by.items():
            g = groups.setdefault(self._token_group_of(m),
                                  {"calls": 0, "prompt": 0, "completion": 0})
            g["calls"] += int(b.get("calls", 0) or 0)
            g["prompt"] += int(b.get("prompt", 0) or 0)
            g["completion"] += int(b.get("completion", 0) or 0)
        # 召对·AI：次数以 _dialogue_stats.ai_calls 为准（token 取 dialogue 分桶）
        d = groups.pop("召对·AI", {"calls": 0, "prompt": 0, "completion": 0})
        rows.append(("召对·AI", ai_calls, d["prompt"], d["completion"], 0))
        for grp in self._TOKEN_GROUP_ORDER:
            g = groups.pop(grp, {"calls": 0, "prompt": 0, "completion": 0})
            rows.append((grp, g["calls"], g["prompt"], g["completion"], 0))
        if groups:
            calls = sum(g["calls"] for g in groups.values())
            p = sum(g["prompt"] for g in groups.values())
            c = sum(g["completion"] for g in groups.values())
            rows.append(("其它", calls, p, c, 0))
        total = meter.get("total", {})
        hit_all = pre + ch
        call_all = hit_all + ai_calls
        rate = (hit_all / call_all * 100) if call_all else 0.0
        rows.append(("合计", int(total.get("calls", 0) or 0),
                     int(total.get("prompt", 0) or 0),
                     int(total.get("completion", 0) or 0),
                     f"{rate:.0f}%（召对）"))
        return rows

    def _panel_token_meter(self):
        """Token 计量表（可滚动）：调用类型/次数/Prompt/Completion/命中 + 合计行。"""
        import tkinter.ttk as ttk
        inner = self._panel_shell("Token 用 量")
        self._label(inner,
                    "AI 调用 token 计量（按契约方法分桶；召对命中 = 预过滤/缓存拦截免调 AI）",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 10), anchor="w").pack(
            padx=12, pady=(4, 6))
        try:
            style = ttk.Style()
            style.configure("Songzuo.Treeview", background=CARD, fieldbackground=CARD,
                            foreground=INK, rowheight=24, borderwidth=0,
                            font=self._font(SANS, 10))
            style.configure("Songzuo.Treeview.Heading", background=RED,
                            foreground="#f3e6c4", font=self._font(SANS, 10, "bold"))
        except Exception:
            pass
        frame = tk.Frame(inner, bg=PAPER)
        frame.pack(fill="both", expand=True, padx=12, pady=4)
        tree = ttk.Treeview(frame, style="Songzuo.Treeview",
                            columns=("type", "calls", "prompt", "completion", "hit"),
                            show="headings", height=12)
        for cid, txt, w, anchor in (
                ("type", "调用类型", 210, "w"), ("calls", "次数", 70, "e"),
                ("prompt", "Prompt tokens", 130, "e"),
                ("completion", "Completion tokens", 150, "e"),
                ("hit", "命中", 110, "e")):
            tree.heading(cid, text=txt)
            tree.column(cid, width=w, anchor=anchor)
        vsb = tk.Scrollbar(frame, orient="vertical", command=tree.yview, bg=PAPER2,
                           troughcolor=PAPER, activebackground=GOLD)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for r in self._token_meter_rows():
            tree.insert("", "end", values=r, tags=("total",) if r[0] == "合计" else ())
        tree.tag_configure("total", background="#f1e7cf",
                           font=self._font(SANS, 10, "bold"))
        self._label(inner,
                    "说明：召对命中行不消耗 token（预过滤/缓存拦截）；Prompt/Completion 按方法分桶累计；"
                    "合计行命中列 = 召对省调率。",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 9), anchor="w").pack(
            padx=12, pady=(4, 10))

    def _reset_token_meter(self):
        """清零 token 计量（客户端分桶 + 召对统计；状态内缓存命中一并清）。"""
        if self.ai_client is not None:
            self.ai_client.reset_meter()
        st = getattr(self.state, "_dialogue_stats", None)
        if isinstance(st, dict):
            st.update({"prefilter_hits": 0, "cache_hits": 0, "ai_calls": 0})
        self.messagebox.showinfo("清零完成", "Token 计量与召对命中统计已清零。")

    def _panel_ai_config(self, return_to):
        self._clear_all()
        f = self.container
        ban = tk.Frame(f, bg=RED)
        ban.pack(fill="x")
        self._title(ban, "AI 叙 事 配 置", fg="#f3e6c4", bg=RED, font=self._font(KAI, 20, "bold"),
                    anchor="center").pack(pady=16)

        # 预填：优先已保存的实例字段
        if self.ai_client:
            init_cfg = {
                "api_key": self.ai_client.api_key,
                "base_url": self.ai_client.base_url,
                "model": self.ai_client.model,
            }
            saved = "（已保存配置，下次启动自动载入）" if os.path.exists(
                self._resource("ai_config.json")) else ""
        else:
            init_cfg = {"api_key": "", "base_url": "https://api.openai.com/v1", "model": "gpt-3.5-turbo"}
            saved = "（当前未配置 AI 叙事）"
        self._label(f, f"配置 OpenAI 兼容 API 以启用召对/拟诏叙事\n留空则关闭 AI 叙事（叙事由错误提示替代）。{saved}",
                    fg=DIM, bg=PAPER, anchor="center", justify="center").pack(pady=10)
        entries = {}
        for text, key in [("API Key", "api_key"), ("API URL", "base_url"), ("模型名", "model")]:
            self._label(f, text, fg=INK, bg=PAPER, font=self._font(SANS, 11), anchor="w").pack(padx=120, pady=(8, 0), anchor="w")
            e = tk.Entry(f, bg=CARD, fg=INK, insertbackground=INK, relief="flat", width=44,
                         font=self._font(SANS, 11), bd=1, highlightthickness=0)
            e.insert(0, init_cfg.get(key, ""))
            e.pack(padx=120, pady=2)
            entries[key] = e

        # 函数调用（大臣办差工具）开关：自动探测 / 强制开 / 强制关
        self._label(f, "大臣办差工具（function calling）", fg=INK, bg=PAPER,
                    font=self._font(SANS, 11), anchor="w").pack(padx=120, pady=(8, 0), anchor="w")
        fc_var = tk.StringVar(value=getattr(self.ai_client, "enable_tools", "auto") or "auto")
        fc_frame = tk.Frame(f, bg=PAPER)
        fc_frame.pack(padx=120, pady=2, anchor="w")
        for val, lab in [("auto", "自动（探测端点）"), ("on", "强制开启"), ("off", "关闭")]:
            tk.Radiobutton(fc_frame, text=lab, variable=fc_var, value=val,
                           bg=PAPER, fg=INK, font=self._font(SANS, 10), anchor="w").pack(side="left", padx=8)

        def do():
            api_key = entries["api_key"].get().strip()
            base_url = entries["base_url"].get().strip() or "https://api.openai.com/v1"
            model = entries["model"].get().strip() or "gpt-3.5-turbo"
            enable_tools = fc_var.get() or "auto"
            if not api_key:
                self.ai_client = None
                AIClient().save_config()  # 离线：清空已保存配置
                self.self.messagebox.showinfo("完成", "已关闭 AI 叙事（叙事由错误提示替代），已清除已保存配置。")
            else:
                self.ai_client = AIClient(api_key, base_url, model, enable_tools=enable_tools)
                ok = self.ai_client.save_config()
                if ok:
                    # 保存后做连通性自检（强制联网，不受缓存影响）
                    good, msg = self.ai_client.probe(force=True)
                    if good:
                        self.self.messagebox.showinfo("完成", f"AI 叙事已启用，配置已保存。\n模型自检通过：{msg}")
                    else:
                        self.messagebox.showwarning(
                            "配置已保存但模型不可用",
                            f"配置已写入 ai_config.json，但模型自检未通过：\n{msg}\n\n"
                            f"请确认 API Key / base_url / 模型名正确后再开始游戏。")
                else:
                    self.messagebox.showwarning("注意", "AI 叙事已启用，但配置写入文件失败，本次仅在内存中生效。")
            return_to()

        bar = tk.Frame(f, bg=PAPER)
        bar.pack(pady=14)
        self._seal_btn(bar, "保存并启用", do, big=True).pack(side="left", padx=8)
        self._btn(bar, "返 回", return_to, width=14, ghost=True).pack(side="left", padx=8)

    def _ui_next_turn(self):
        s = self.state
        # 防止结算期间重复点击
        if getattr(self, '_settling', False):
            return
        # 结算前快照（用于演出式涨跌对比）
        snap = dict(treasury=s.treasury, imperial_treasury=s.imperial_treasury, population_satisfaction=s.population_satisfaction,
                    imperial_prestige=s.prestige)
        from backend.client import LocalBackend
        if isinstance(self.backend, LocalBackend) and self.ai_client and self.ai_client.available:
            # T6 本地拆分：后台 AI 推演族 → 主线程 12 步结算 → 叙事后补（UI 不卡驻）
            self._ui_next_turn_split(s, snap)
        elif isinstance(self.backend, LocalBackend):
            # 无 AI：同步快速路径（settle_turn 拒绝式提示配置）
            try:
                events, log, report, new_state = self.backend.advance(s, self.ai_client)
            except _AIRuntimeError as e:
                self.messagebox.showerror("AI 叙事中断", str(e))
                return
            self._finish_settle(events, log, report, new_state, snap)
        else:
            # 远程后端：整包 advance 后台执行，避免网络调用冻结 UI（既有路径）
            self._settling = True
            tl, body = self._overlay("结 算 中", width=320, height=140)
            self._title(body, "御 案 结 算 中 …",
                        fg=RED, bg=PAPER, font=self._font(KAI, 16, "bold"),
                        anchor="center").pack(pady=(24, 8))
            import threading
            def _worker():
                try:
                    result = self.backend.advance(s, self.ai_client)
                except Exception as e:
                    result = e
                self.root.after(0, lambda: self._on_settle_done(result, snap, tl))
            threading.Thread(target=_worker, daemon=True).start()

    def _ui_next_turn_split(self, s, snap):
        """T6 本地结算拆分：事件触发（主线程）→ AI 推演族（后台，不写 state）
        → 12 步本地结算（主线程）→ 月报叙事后补（不阻塞结算完成）。"""
        self._settling = True
        # ① 主线程本地事件触发（确定性、无网络）
        try:
            events = self.backend.advance_month(s) or []
        except Exception:
            events = []
        # 路由：按玩家政令/状态唤醒领域契约（主线程读 state；失败退化为 P1 三契约保底）
        woken = None
        try:
            from core.agent_router import route_agents
            _hint = ""
            try:
                _decs = getattr(s, "pending_decrees", []) or []
                _hint = " ".join(str(d.get("title", "")) for d in _decs[-3:])
            except Exception:
                _hint = ""
            woken = route_agents(_hint, s, getattr(s, "_last_agent_diff", None))
        except Exception:
            woken = None
        # 结算中浮层 + AI 加载环
        tl, body = self._overlay("结 算 中", width=360, height=190)
        self._title(body, "御 案 结 算 中 …",
                    fg=RED, bg=PAPER, font=self._font(KAI, 16, "bold"),
                    anchor="center").pack(pady=(26, 6))
        ring, set_loading = self._busy_ring(body)
        ring.pack(pady=(4, 4))
        set_loading(True)

        def _on_success(results):
            self._on_settle_ai_done(results, events, snap, tl)

        def _on_error(exc):
            self._settling = False
            try:
                tl.destroy()
            except Exception:
                pass
            if isinstance(exc, _AIRuntimeError):
                self.messagebox.showerror("AI 叙事中断", str(exc))
            else:
                self.messagebox.showerror("结算错误", str(exc))

        from core.async_ai import run_settlement_ai
        run_settlement_ai(self.ai_client, s.posture, s, woken,
                          ui=self.root, on_success=_on_success, on_error=_on_error)

    def _on_settle_ai_done(self, results, events, snap, tl):
        """后台 AI 推演族完成后回到主线程：落地槽位 → 12 步本地结算 → 呈现 → 叙事后补。"""
        self._settling = False
        try:
            tl.destroy()
        except Exception:
            pass
        s = self.state
        try:
            log, new_state = self.backend.settle_local(s, results)
        except Exception as e:
            if isinstance(e, _AIRuntimeError):
                self.messagebox.showerror("AI 叙事中断", str(e))
            else:
                self.messagebox.showerror("结算错误", str(e))
            return
        self.state = new_state
        self._finish_settle(events, log, "", new_state, snap)
        if not new_state.game_over:
            # ③ 叙事后补：不阻塞结算完成
            self._settle_narrative_postfill(new_state)

    def _settle_narrative_postfill(self, state):
        """结算完成后的月报叙事后补：后台生成，主线程追加展示；失败不阻塞、不伪造。"""
        if not (self.ai_client and getattr(self.ai_client, "available", False)):
            return
        try:
            from core.commands import monthly_report_args
            args = monthly_report_args(state)
        except Exception:
            args = (state.year, state.month, state.era_name, state.posture)

        def _on_success(report):
            text = report.get("report", "") if isinstance(report, dict) else str(report or "")
            if text:
                self._settle_narrative_show(text)

        def _on_error(exc):
            # 叙事后补失败不阻断结算：明确提示缺月折，不伪造
            self._log(f"〔月折〕AI 月报生成失败：{exc}")
            self._settle_narrative_show("（本月月折暂缺：AI 月报生成失败）")

        from core.async_ai import run_ai_call
        run_ai_call(self.ai_client, "monthly_report", *args,
                    on_success=_on_success, on_error=_on_error, ui=self.root)

    def _settle_narrative_show(self, text):
        """把后补月折追加到结算浮层（若仍开）或写入待办日志。"""
        append = getattr(self, "_settle_late_append", None)
        if append is not None:
            if append(text):
                return
        self._pending_logs.append(f"【丞相月折（AI）】\n{text}")
        self._log(f"〔月折〕{str(text)[:60]}")

    def _on_settle_done(self, result, snap, overlay_tl):
        """后台结算完成后回到主线程的回调。"""
        self._settling = False
        try:
            overlay_tl.destroy()
        except Exception:
            pass
        if isinstance(result, Exception):
            if isinstance(result, _AIRuntimeError):
                self.messagebox.showerror("AI 叙事中断", str(result))
            else:
                self.messagebox.showerror("结算错误", str(result))
            return
        events, log, report, new_state = result
        self._finish_settle(events, log, report, new_state, snap)

    def _finish_settle(self, events, log, report, new_state, snap):
        """结算完成后的 UI 更新（主线程）。"""
        self.state = new_state
        s = self.state
        if s.game_over:
            self._ui_game_over()
            return
        # 组装结算条目（动作→结算→反馈 仪式感）
        lines = [f"── {s.era_name}{s.year}年{s.month}月 · 御案结算 ──"]
        for entry in log:
            lines.append("  " + entry)
        if report:
            lines.append("【丞相月折（AI）】")
            lines.append(report)
        self._settle_show(lines, snap, events)

    def _log_pending(self):
        for m in self._pending_logs:
            self._log(m)
        self._pending_logs = []

    def _settle_show(self, lines, snap, events):
        import ui.theme as theme
        tl, body = self._overlay("御 案 结 算", width=640, height=560)
        head = self._title(body, "御 案 结 算",
                           fg=RED, bg=PAPER, font=self._font(KAI, 18, "bold"), anchor="center")
        head.pack(pady=(10, 4))

        log_frame = tk.Frame(body, bg=PAPER)
        log_frame.pack(fill="both", expand=True, padx=16, pady=6)
        log_sb = tk.Scrollbar(log_frame, bg=PAPER2, troughcolor=PAPER)
        log_cv = tk.Canvas(log_frame, bg=PAPER, highlightthickness=0,
                           yscrollcommand=log_sb.set)
        log_inner = tk.Frame(log_cv, bg=PAPER)
        log_inner.bind("<Configure>",
                       lambda e: log_cv.configure(scrollregion=log_cv.bbox("all")))
        log_cv.create_window((0, 0), window=log_inner, anchor="nw")
        log_sb.configure(command=log_cv.yview)
        log_cv.pack(side="left", fill="both", expand=True)
        log_sb.pack(side="right", fill="y")

        bar = tk.Frame(body, bg=PAPER)
        bar.pack(pady=(4, 10))
        btn = self._seal_btn(bar, "继 续", lambda: None, big=True)
        btn.pack(side="left", padx=8)
        btn.configure(state="disabled")

        idx = {"i": 0}

        def fmt_delta(v0, v1, div=1.0):
            d = (v1 - v0) / div
            return d

        def reveal():
            if idx["i"] < len(lines):
                ln = lines[idx["i"]]
                fg = INK
                if ln.startswith("  +"):
                    fg = theme.DX_GOOD
                elif ln.startswith("  -"):
                    fg = theme.DX_URGENT
                self._label(log_inner, ln, fg=fg, bg=PAPER,
                            font=self._font(SANS, 11), anchor="w").pack(anchor="w", pady=1)
                log_cv.yview_moveto(1.0)
                idx["i"] += 1
                body.after(220, reveal)
            else:
                # 数值涨跌小结
                s = self.state
                deltas = [
                    ("国库", snap["treasury"], s.treasury, 1.0, "贯"),
                    ("内帑", snap["imperial_treasury"], s.imperial_treasury, 1.0, "贯"),
                    ("民心", snap["population_satisfaction"], s.population_satisfaction, 1.0, ""),
                    ("皇威", snap["imperial_prestige"], s.prestige, 1.0, ""),
                ]
                self._label(log_inner, "── 本月损益 ──", fg=RED_D, bg=PAPER,
                            font=self._font(KAI, 12, "bold")).pack(anchor="w", pady=(8, 2))
                for nm, a, b, div, unit in deltas:
                    d = fmt_delta(a, b, div)
                    if abs(d) < 0.5:
                        txt, fg = f"{nm}：持平", theme.DX_NORMAL
                    elif d > 0:
                        txt, fg = f"{nm}：▲ +{d:.0f}{unit}", theme.DX_GOOD
                    else:
                        txt, fg = f"{nm}：▼ {d:.0f}{unit}", theme.DX_URGENT
                    self._label(log_inner, "  " + txt, fg=fg, bg=PAPER,
                                font=self._font(SANS, 11, "bold")).pack(anchor="w", pady=1)
                log_cv.yview_moveto(1.0)
                btn.configure(state="normal")

        def cont():
            tl.destroy()
            self._settle_late_append = None
            self._refresh_head()
            self._refresh_hud()  # 回合结算后实时刷新顶部胶囊（威望/民心/国库/内帑等）
            if events:
                self._present_events(events, 0)
            else:
                self._switch_panel(self._panel_overview, "朝堂一览")

        btn.configure(command=cont)

        def _append_late(text):
            """结算浮层仍开时追加一行（T6 月报叙事后补用）；浮层已关返回 False。"""
            try:
                self._label(log_inner, f"【丞相月折（AI）】\n{text}", fg=RED_D, bg=PAPER,
                            font=self._font(KAI, 11), justify="left",
                            anchor="w").pack(anchor="w", pady=(4, 1))
                log_cv.yview_moveto(1.0)
                return True
            except Exception:
                return False

        self._settle_late_append = _append_late
        body.after(300, reveal)

    def _present_events(self, events, idx):
        if idx >= len(events):
            self._refresh_hud()  # 事件链结束回主界面时刷新顶部胶囊
            self._switch_panel(self._panel_overview, "朝堂一览")
            return
        self._panel_event(events[idx], lambda: self._present_events(events, idx + 1))

    def _panel_event(self, event, on_done):
        tl, body = self._overlay(event.get("title", "事件"), width=720, height=620)
        self._title(body, event.get("title", "事件"), fg=RED, bg=PAPER,
                    font=self._font(KAI, 18, "bold"), anchor="center").pack(pady=(8, 4))
        # 战略决策点角标（枢密院/军机密奏，需陛下朱批改史）
        if event.get("_break_id"):
            self._label(body, "〔军机·战略决策〕候陛下朱批定夺", fg=theme.DX_URGENT,
                        bg=PAPER, font=self._font(KAI, 12, "bold")).pack(pady=(0, 2))
        # 事件插图（每个事件配专属图 + 朱批语义边框）
        from ui import assets as res
        import ui.theme as theme
        ev_img = res.event_image(event.get("id", ""), size=(260, 340))
        if ev_img:
            # 依事件性质定边框朱批色（灾/战=急 朱红；祥瑞=吉 绿；常=褐）
            # 复用 audio.EVENT_AUDIO_CLASS 作为事件分类的单一权威源，
            # 保证 UI 朱批色与音频槽位选择永不漂移。
            from audio.manifest import audio_class_for
            eid = event.get("id", "")
            _cls = audio_class_for(eid)
            if _cls == "urgent":
                fcol = theme.DX_URGENT
            elif _cls == "auspicious":
                fcol = theme.DX_GOOD
            else:
                fcol = theme.DX_NORMAL
            img_frame = tk.Frame(body, bg=PAPER, relief="ridge", bd=2,
                                 highlightbackground=fcol, highlightthickness=2)
            img_frame.pack(pady=(2, 6))
            # 内留白宣纸衬
            pad = tk.Frame(img_frame, bg="#fffdf6", relief="flat", bd=1,
                           highlightbackground=fcol, highlightthickness=1)
            pad.pack(padx=5, pady=5)
            tk.Label(pad, image=ev_img, bg="#fffdf6").pack()
            # 类型铭牌
            _lab = "灾异" if _cls == "urgent" else ("祥瑞" if _cls == "auspicious" else "朝务")
            self._label(img_frame, f"〔{_lab}〕", fg=fcol, bg=PAPER,
                        font=self._font(KAI, 11, "bold")).pack(pady=(0, 3))
        desc_card = self._card(body)
        desc_card.pack(fill="x", padx=12, pady=6)
        self._label(desc_card, event.get("desc", ""), fg=INK, bg=CARD, font=self._font(KAI, 12),
                    wraplength=600, justify="left").pack(anchor="w", padx=16, pady=12)

        choices = event.get("choices", [])
        choice_var = tk.IntVar(value=-1)
        cf = tk.Frame(body, bg=PAPER)
        cf.pack(fill="x", padx=12, pady=6)
        import ui.theme as theme
        for i, ch in enumerate(choices):
            text = ch.get("text", f"选项{i+1}")
            eff = _format_effects(ch.get("effects", {}))
            # 依选项优劣染朱批色（选项优劣高亮）
            good, bad = _judge_effects(ch.get("effects", {}))
            if good > bad:
                col = theme.DX_GOOD
            elif bad > good:
                col = theme.DX_URGENT
            else:
                col = theme.DX_NORMAL
            row = tk.Frame(cf, bg=CARD, relief="ridge", bd=1,
                           highlightbackground=col, highlightthickness=2)
            row.pack(fill="x", padx=8, pady=4)
            tk.Radiobutton(row, variable=choice_var, value=i, bg=CARD,
                           selectcolor=PAPER, activebackground=CARD, bd=0,
                           highlightthickness=0, width=2).pack(side="left", padx=4)
            self._label(row, f"  {text}" + (f"\n  （{eff}）" if eff else ""),
                        fg=INK, bg=CARD, font=self._font(SANS, 11), anchor="w",
                        justify="left").pack(side="left", fill="x", expand=True,
                                             padx=4, pady=6)

        def do():
            ci = choice_var.get()
            if ci < 0:
                self.self.messagebox.showinfo("提示", "请选择一个选项。")
                return
            try:
                res, self.state = self.backend.resolve_event(self.state, event, ci, self.ai_client)
            except _AIRuntimeError as e:
                self.self.messagebox.showerror("AI 叙事中断", str(e))
                return
            self._pending_logs.append(f"事件《{event.get('title','')}》抉择：{choices[ci].get('text','')}")
            for line in res.split("\n"):
                if line.strip():
                    self._pending_logs.append("  " + line)
            tl.destroy()
            if self.state.game_over:
                self._ui_game_over()
            else:
                on_done()

        bar = tk.Frame(body, bg=PAPER)
        bar.pack(pady=8)
        self._seal_btn(bar, "决 断", do, big=True).pack(side="left", padx=8)

