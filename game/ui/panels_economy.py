# -*- coding: utf-8 -*-
"""宋祚 · GUI economy 面板 Mixin。

州县 / 仓廪 / 会计 / 军政 / 科技 / 工程等经济与内政面板。共享常量与工具见 ui.gui_common。
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
from ui.gui_common import (humanize_grain_price, humanize_grain,
                             humanize_coin, humanize_households, humanize_land)
from ui.panels_military import _fmt_count, EQUIP_KEYS


# 科技效用字段中文映射
_TECH_EFFECT_LABELS = {
    "production": "产能",
    "yield_bonus": "田产加成",
    "mining_income": "矿冶收入",
    "build_cost": "营造成本",
    "canal_efficiency": "漕运效率",
    "army_power": "军力",
    "training": "操练",
    "equipment": "武备",
    "morale": "士气",
    "epidemic_risk": "疫病风险",
    "prestige": "皇威",
    "prestige_gain": "皇威增益",
    "exam_talent": "科举才俊",
    "granary_cap": "扩仓容",
    "workshop_output": "增作坊产出",
    "trade_income": "贸易收入",
    "build_speed": "建造速度",
    "decree_speed": "政令速率",
    "bandwidth_bonus": "圣裁带宽",
    "treasury": "国库",
    "tax": "税入",
    "grain": "粮储",
    "unrest": "民乱",
    "loyalty": "忠诚",
    "satisfaction": "满意度",
    "influence": "势力",
    "power": "实力",
    "population": "人口",
    "trade_income": "市舶收入",
    "ship_capacity": "舟运运力",
    "naval_power": "水师",
    "firepower": "火力",
    "fortification": "城防",
    "garrison": "驻军",
    "art_gain": "艺术造诣",
    "health_cost": "健康消耗",
    "taoism_gain": "道术造诣",
    "pleasure_gain": "逸乐",
    "clergy_satisfaction": "僧道满意度",
}


def _format_tech_effect(effect):
    if not effect:
        return "无"
    parts = []
    for k, v in effect.items():
        label = _TECH_EFFECT_LABELS.get(k, k.replace("_", " "))
        try:
            num = float(v)
            if num > 0:
                sign = "+"
            elif num < 0:
                sign = "−"
            else:
                sign = ""
            val = f"{sign}{abs(num):.2f}".rstrip("0").rstrip(".")
        except (TypeError, ValueError):
            val = str(v)
        parts.append(f"{label}{val}")
    return "、".join(parts) if parts else "无"


class PanelsEconomyMixin:
    def _panel_prefectures(self):
        inner = self._panel_shell("地方州县")
        self._label(inner, "诸路安则社稷安。田亩户籍、劝农赈灾、平盗减税，皆由此出。",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 11), anchor="w").pack(padx=12, pady=(2, 8))

        # 田亩户籍总览（合并原「田亩户籍」入口）
        ov = tk.Frame(inner, bg=PAPER)
        ov.pack(fill="x", padx=10, pady=2)
        self._btn(ov, "田 亩 户 籍 总 览", lambda: self._panel_land(), width=20,
                  gold=True).pack(side="left", padx=4)

        card = self._card(inner)
        card.pack(fill="x", padx=10, pady=6)
        lb = tk.Listbox(card, bg=CARD, fg=INK, selectbackground=RED, selectforeground="#f3e6c4",
                        font=self._font(SANS, 11), relief="flat", height=9, bd=0, highlightthickness=0)
        lb.pack(fill="x", padx=14, pady=10)
        for i, name in enumerate(PREFECTURE_LIST, 1):
            p = self.state.prefectures[name]
            lb.insert("end", f"[{i}] {name}　{humanize_households(p['households'])} {humanize_land(p['land'])} 粮{humanize_grain(p['grain'])} 民情{p['mood']} 治{p['govern']}")

        def select():
            sel = lb.curselection()
            if not sel:
                self.self.messagebox.showinfo("提示", "请选择一路。")
                return
            self._panel_prefecture(PREFECTURE_LIST[sel[0]])

        bar = tk.Frame(inner, bg=PAPER)
        bar.pack(pady=12)
        self._seal_btn(bar, "查 看 路 情", select, big=True).pack(side="left", padx=8)

    def _panel_prefecture(self, pref_name):
        inner = self._panel_shell(
            pref_name,
            back_cmd=lambda: self._close_overlay())
        p = self.state.prefectures[pref_name]
        card = self._card(inner)
        card.pack(fill="x", padx=10, pady=4)
        self._label(card, (f"户数：{humanize_households(p['households'])}\n垦田：{humanize_land(p['land'])}\n粮产：{humanize_grain(p['grain'])}\n"
                           f"民情：{_bar(int(p['mood']),20)} {p['mood']}\n治理：{_bar(int(p['govern']),20)} {p['govern']}"),
                    fg=INK, bg=CARD, font=self._font(SANS, 11), anchor="w").pack(anchor="w", padx=16, pady=12)
        self._label(inner, "地方之政（劝农、赈灾、平盗、减税等）请经「拟旨」系统拟诏施行，效果由中枢推演落地。",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 10), anchor="w").pack(padx=12, pady=10)


    def _panel_land(self):
        inner = self._panel_shell(
            "田亩户籍总览",
            back_cmd=lambda: self._close_overlay())
        s = self.state
        lines = []
        lines.append(f"全国垦田：{humanize_land(s.land['cultivated'])}（隐漏率 {int(s.land['hidden_rate']*100)}%）")
        lines.append(f"在籍户数：{humanize_households(s.land['households'])}　约 {humanize_pop(s.population)}")
        lines.append(f"荒闲田土：{humanize_land(s.land['wasteland'])}　亩产系数：{s.land['yield']:.2f}")
        lines.append("")
        lines.append("【诸路概要】")
        for name in PREFECTURE_LIST:
            p = s.prefectures[name]
            lines.append(f"  {name}：{humanize_households(p['households'])} {humanize_land(p['land'])} 粮{humanize_grain(p['grain'])} 民情{p['mood']}")
        # POP 人口分层（维多利亚式六类）：人数（万）
        lines.append("")
        lines.append("【诸路 POP 人口】（万：农/绅/工/商/官/兵）")
        _w = lambda v: f"{v/1e4:.0f}" if v >= 1e4 else str(v)
        for name in PREFECTURE_LIST:
            pops = s.prefectures[name]["pops"]
            lines.append(f"  {name}：农{_w(pops['农']['size'])} 绅{_w(pops['士绅']['size'])} 工{_w(pops['工匠']['size'])} "
                         f"商{_w(pops['商人']['size'])} 官{_w(pops['官僚']['size'])} 兵{_w(pops['兵']['size'])}")
        # 全国 POP 钱粮汇总
        _tot = {"wealth": 0, "grain": 0}
        for name in PREFECTURE_LIST:
            for pop in s.prefectures[name]["pops"].values():
                _tot["wealth"] += pop.get("wealth", 0)
                _tot["grain"] += pop.get("grain", 0)
        lines.append("")
        lines.append(f"【民间 POP 汇总】持钱 {humanize_coin(_tot['wealth'])}　"
                     f"存粮 {humanize_grain(_tot['grain'])}")
        card = self._card(inner)
        card.pack(fill="both", expand=True, padx=10, pady=4)
        txt = self._scrolled(card, bg=CARD, font=self._font(SANS, 11), padx=16, pady=14)
        txt._text.insert("1.0", "\n".join(lines))
        txt._text.configure(state="disabled")
        txt.pack(fill="both", expand=True, padx=12, pady=12)

    # 皇帝行动效果键 → 中文名（详情卡预览；与 content.data 契约键对齐）
    _IMPERIAL_EFFECT_NAMES = {
        "prestige": "威望", "population_satisfaction": "民心", "emperor_health": "健康",
        "pleasure_leaning": "心情", "art_mastery": "艺术造诣", "taoism_leaning": "道门倾向",
        "bandwidth_bonus": "圣旨额度", "faction_change": "派系",
    }
    _IMPERIAL_RISK_FG = {"低": "DX_GOOD", "中": "DX_WARN", "高": "DX_URGENT"}

    def _panel_personal(self):
        """个人行止 · 全矩阵：地点（宫里/京城/出京）× 方式（公开/微服）→ 行动白名单。

        数据驱动自 content.data.IMPERIAL_ACTION_MATRIX（P0 权威，不写死行动名）；
        约束（时代门槛/微服限次/出京准备期/距离核算）、开销（公开→国库/微服→内帑）、
        风险档全部展示；旧 4 固定动作经 do_personal_action 通道仍兼容（映射宫里·公开格）。
        """
        from content.data import (IMPERIAL_ACTION_MATRIX, IMPERIAL_LOCATIONS, IMPERIAL_MODES,
                                  IMPERIAL_DISTANCE_MONTHS, imperial_distance,
                                  imperial_prep_months)
        from ui.gui_common import humanize_coin
        inner = self._panel_shell("个 人 行 止")
        s = self.state

        # —— 顶部：当前行止状态 ——
        stat = tk.Frame(inner, bg=PAPER)
        stat.pack(fill="x", padx=10, pady=(2, 6))
        _pending = getattr(s, "pending_imperial_trip", None)
        _cur = getattr(s, "imperial_action", None) or {}
        if _pending is not None:
            self._label(stat,
                        f"大驾出京准备中：「{_pending.get('action', '')}」尚余 "
                        f"{int(_pending.get('pending_months', 1))} 月（准备期内不可另定行止）",
                        fg=theme.DX_URGENT, bg=PAPER, font=self._font(KAI, 12, "bold"),
                        anchor="w").pack(anchor="w", padx=4, pady=2)
        elif _cur and _cur.get("action"):
            self._label(stat,
                        f"本回合已定行止：{_cur.get('location', '')}·{_cur.get('mode', '')}"
                        f"·{_cur.get('action', '')}（月末结算生效）",
                        fg=RED_D, bg=PAPER, font=self._font(KAI, 12, "bold"),
                        anchor="w").pack(anchor="w", padx=4, pady=2)
        else:
            self._label(stat, "择地点与行止方式，钦定陛下本回合行止（每月一次）。",
                        fg=DIM, bg=PAPER, font=self._font(SANS, 10),
                        anchor="w").pack(anchor="w", padx=4, pady=2)

        # —— 主区：左地点 / 右方式+行动 ——
        main = tk.Frame(inner, bg=PAPER)
        main.pack(fill="both", expand=True, padx=10, pady=4)
        left = tk.Frame(main, bg=PAPER, width=180)
        left.pack(side="left", fill="y", padx=(0, 10))
        self._label(left, "行止地点", fg=RED_D, bg=PAPER, font=self._font(KAI, 12, "bold"),
                    anchor="w").pack(fill="x", pady=(0, 2))
        state = {"loc": "宫里", "mode": "公开", "sel": None, "target": ""}
        loc_btns = {}

        def _set_loc(key):
            state["loc"] = key
            # 宫里无微服：切回公开（微服置灰）
            if key == "宫里" and state["mode"] == "微服":
                state["mode"] = "公开"
                _set_mode("公开")
            for k, b in loc_btns.items():
                try:
                    b.configure(bg=(RED if k == key else CARD),
                                fg=("#f3e6c4" if k == key else RED_D),
                                relief=("sunken" if k == key else "raised"))
                except Exception:
                    pass
            loc_note_lbl.config(text=_loc_note.get(key, ""))
            _refresh_mode()
            _refresh_actions()

        for loc in IMPERIAL_LOCATIONS:
            b = self._btn(left, loc, lambda k=loc: _set_loc(k), width=10,
                          ghost=(loc != state["loc"]))
            b.pack(fill="x", pady=3)
            loc_btns[loc] = b
        _loc_note = {"宫里": "宫中视事，政务闲暇", "京城": "汴京内外，四方辐辏",
                     "出京": "离京巡幸，需备銮驾"}
        loc_note_lbl = self._label(left, _loc_note.get(state["loc"], ""), fg=DIM, bg=PAPER,
                                   font=self._font(SANS, 9), anchor="w", wraplength=160,
                                   justify="left")
        loc_note_lbl.pack(fill="x", pady=(6, 0))

        right = tk.Frame(main, bg=PAPER)
        right.pack(side="left", fill="both", expand=True)

        # —— 行止方式行 ——
        mode_row = tk.Frame(right, bg=PAPER)
        mode_row.pack(fill="x", pady=(0, 4))
        self._label(mode_row, "行止方式：", fg=INK, bg=PAPER,
                    font=self._font(SANS, 11)).pack(side="left")
        mode_btns = {}

        def _set_mode(key):
            state["mode"] = key
            for k, b in mode_btns.items():
                try:
                    b.configure(bg=(RED if k == key else CARD),
                                fg=("#f3e6c4" if k == key else RED_D),
                                relief=("sunken" if k == key else "raised"))
                except Exception:
                    pass
            _refresh_actions()

        def _refresh_mode():
            """宫里无微服：微服方式置灰（跨格子非法提示）。"""
            no_micro = state["loc"] == "宫里"
            try:
                mode_btns["微服"].configure(state="disabled" if no_micro else "normal")
            except Exception:
                pass
            mode_note_lbl.config(text="宫里不设微服（宫中即陛下起居之地）。" if no_micro else
                                 "微服出行开销走内帑，暴露风险较高。")

        for md in IMPERIAL_MODES:
            lab = "公开大驾" if md == "公开" else "微服便服"
            b = self._btn(mode_row, lab, lambda k=md: _set_mode(k), width=12,
                          ghost=(md != state["mode"]))
            b.pack(side="left", padx=4)
            mode_btns[md] = b
        mode_note_lbl = self._label(mode_row, "", fg=DIM, bg=PAPER, font=self._font(SANS, 9),
                                    anchor="w")
        mode_note_lbl.pack(side="left", padx=(8, 0))

        # —— 行动列表 + 详情 ——
        act_row = tk.Frame(right, bg=PAPER)
        act_row.pack(fill="both", expand=True, pady=(4, 0))
        act_card = self._card(act_row)
        act_card.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._card_title(act_card, "可 行 之 事")
        lb = tk.Listbox(act_card, bg=CARD, fg=INK, selectbackground=RED,
                        selectforeground="#f3e6c4", font=self._font(SANS, 11),
                        relief="flat", bd=0, highlightthickness=0, height=10)
        lb.pack(fill="both", expand=True, padx=10, pady=(2, 10))

        det_card = self._card(act_row)
        det_card.pack(side="left", fill="y", padx=(0, 0))
        self._card_title(det_card, "细 目")
        det_name = self._title(det_card, "（请选行动）", fg=RED, bg=CARD,
                               font=self._font(KAI, 13, "bold"), anchor="center")
        det_name.pack(pady=(4, 2))
        det_desc = self._label(det_card, "", fg=INK, bg=CARD, font=self._font(KAI, 11),
                               wraplength=270, justify="left", anchor="w")
        det_desc.pack(anchor="w", padx=12, pady=2)
        det_meta = tk.Frame(det_card, bg=CARD)
        det_meta.pack(fill="x", padx=12, pady=(2, 2))
        det_note = self._label(det_card, "", fg=theme.DX_WARN, bg=CARD,
                               font=self._font(SANS, 9), wraplength=270, justify="left",
                               anchor="w")
        det_note.pack(anchor="w", padx=12, pady=(0, 8))
        # 微服他地：目标路名输入（距离核算）
        target_row = tk.Frame(det_card, bg=CARD)
        target_row.pack(fill="x", padx=12, pady=(0, 8))
        self._label(target_row, "目标路：", fg=INK, bg=CARD,
                    font=self._font(SANS, 10)).pack(side="left")
        target_var = tk.StringVar()
        target_entry = tk.Entry(target_row, textvariable=target_var, bg="#fffdf8", fg=INK,
                                relief="flat", font=self._font(SANS, 10), width=12,
                                insertbackground=INK, highlightthickness=1,
                                highlightbackground=BORDER)
        target_entry.pack(side="left", padx=4)
        target_hint = self._label(target_row, "", fg=DIM, bg=CARD, font=self._font(SANS, 9),
                                  anchor="w")
        target_hint.pack(side="left")
        target_row.pack_forget()   # 默认隐藏，仅微服他地显示

        def _target_updated(*_a):
            t = (target_var.get() or "").strip()
            if t:
                d = imperial_distance(t)
                m = IMPERIAL_DISTANCE_MONTHS.get(d, 1)
                target_hint.config(text=f"「{d}」备 {m} 月")
            else:
                target_hint.config(text="")
        target_var.trace_add("write", _target_updated)

        rows = []

        def _refresh_actions():
            nonlocal rows
            lb.delete(0, "end")
            rows = []
            matrix = IMPERIAL_ACTION_MATRIX.get(state["loc"], {}).get(state["mode"], {})
            blocked = getattr(s, "pending_imperial_trip", None) is not None
            micro_used = int(getattr(s, "imperial_micro_count", 0) or 0) >= 1
            for name, cell in matrix.items():
                disabled, reason = "", ""
                if blocked:
                    disabled, reason = "blocked", "大驾出京准备中，不可另定行止"
                elif cell.get("micro_once") and micro_used:
                    disabled, reason = "micro", "陛下本月已微服出宫，只可一次"
                elif cell.get("era_gate") is not None and s.year < cell["era_gate"]:
                    disabled, reason = "era", f"未至该时代（{cell['era_gate']} 年起可行）"
                cost = int(cell.get("base_cost", 0) or 0)
                fund = cell.get("fund", "treasury")
                fund_lab = "国库" if fund == "treasury" else "内帑"
                prefix = "〔不可〕" if disabled else "　"
                lb.insert("end", f"{prefix}{name}　·　{fund_lab} {humanize_coin(cost)}　·　风险{cell.get('risk', '低')}")
                rows.append({"action": name, "cell": cell, "disabled": disabled, "reason": reason})
                if disabled:
                    try:
                        lb.itemconfig("end", fg="#b0a181")
                    except Exception:
                        pass
            if not rows:
                lb.insert("end", "（该格子无可行行动）")
            if rows:
                lb.selection_set(0)
                _render_detail(0)
            else:
                _render_empty()

        def _render_empty():
            det_name.config(text="（无行动）")
            det_desc.config(text="该地点与方式下无可行动项（跨格子非法）。")
            for w in det_meta.winfo_children():
                w.destroy()
            det_note.config(text="")
            target_row.pack_forget()

        def _render_detail(idx):
            if idx >= len(rows):
                return
            row = rows[idx]
            cell = row["cell"]
            name = row["action"]
            det_name.config(text=name)
            det_desc.config(text=cell.get("desc", ""))
            for w in det_meta.winfo_children():
                w.destroy()
            cost = int(cell.get("base_cost", 0) or 0)
            fund = cell.get("fund", "treasury")
            fund_lab = "国库" if fund == "treasury" else "内帑"
            risk = cell.get("risk", "低")
            self._label(det_meta, f"开销：{fund_lab} {humanize_coin(cost)}",
                        fg=INK, bg=CARD, font=self._font(SANS, 10), anchor="w").pack(fill="x", pady=1)
            fg = getattr(theme, self._IMPERIAL_RISK_FG.get(risk, "DX_NORMAL"), theme.DX_NORMAL)
            self._label(det_meta, f"风险：{risk}（{_risk_prob(risk)}）",
                        fg=fg, bg=CARD, font=self._font(SANS, 10, "bold"), anchor="w").pack(fill="x", pady=1)
            eff = cell.get("base_effects") or {}
            if eff:
                parts = []
                for k, v in eff.items():
                    if k == "faction_change":
                        fc = "、".join(f"{fn}{val:+d}" for fn, val in (v or {}).items())
                        parts.append(f"派系 {fc}")
                        continue
                    parts.append(f"{self._IMPERIAL_EFFECT_NAMES.get(k, k)}{v:+d}")
                self._label(det_meta, "预期：" + "，".join(parts), fg=RED_D, bg=CARD,
                            font=self._font(SANS, 10), anchor="w").pack(fill="x", pady=1)
            if cell.get("bandwidth_cost"):
                self._label(det_meta, "圣旨额度 -1（大驾在途，远程批奏）", fg=DIM, bg=CARD,
                            font=self._font(SANS, 9), anchor="w").pack(fill="x", pady=1)
            if cell.get("micro_once"):
                self._label(det_meta, "微服限次：每月 1 次", fg=DIM, bg=CARD,
                            font=self._font(SANS, 9), anchor="w").pack(fill="x", pady=1)
            if cell.get("prep"):
                self._label(det_meta, f"准备期：{int(cell['prep'])} 月（銮驾备毕成行）", fg=DIM,
                            bg=CARD, font=self._font(SANS, 9), anchor="w").pack(fill="x", pady=1)
            det_note.config(text=row["reason"] or "")
            # 微服他地：距离核算输入
            if cell.get("distance"):
                target_row.pack(fill="x", padx=12, pady=(0, 8))
                target_hint.config(text="")
            else:
                target_row.pack_forget()

        def _risk_prob(risk):
            from content.data import IMPERIAL_RISK_PROB
            return f"{int(IMPERIAL_RISK_PROB.get(risk, 0.02) * 100)}%"

        def _on_select(event=None):
            sel = lb.curselection()
            if sel and sel[0] < len(rows):
                _render_detail(sel[0])

        lb.bind("<<ListboxSelect>>", _on_select)

        def _confirm():
            sel = lb.curselection()
            if not sel or sel[0] >= len(rows):
                self.messagebox.showinfo("提示", "请先选择一项行止。")
                return
            row = rows[sel[0]]
            if row["disabled"]:
                self.messagebox.showinfo("不可行", row["reason"] or "此行动暂不可行。")
                return
            target = ""
            if row["cell"].get("distance"):
                target = (target_var.get() or "").strip()
                if not target:
                    self.messagebox.showinfo("提示", "请填写微服目标州路（如「两浙路」）。")
                    return
            msg, self.state = self.backend.action(
                self.state, "choose_imperial_action",
                {"location": state["loc"], "mode": state["mode"], "action": row["action"],
                 "target": target, "prepared": False})
            self._pending_logs.append(f"行止《{state['loc']}·{state['mode']}·{row['action']}》：{msg}")
            self._log(f"〔行止〕{msg}")
            self._refresh_hud()
            self.messagebox.showinfo("钦定行止", msg)
            self._close_overlay()
            self._switch_panel(self._panel_overview, "朝堂一览")

        bar = tk.Frame(inner, bg=PAPER)
        bar.pack(pady=10)
        self._seal_btn(bar, "钦 定 行 止", _confirm, big=True).pack(side="left", padx=8)
        self._btn(bar, "返 回", lambda: self._close_overlay(), width=12, ghost=True).pack(side="left", padx=8)

        # 初始渲染
        _refresh_mode()
        _refresh_actions()

    # 六类 POP 顺序与显示名（民生面板单一权威源）
    _POP_CLASSES = ("农", "士绅", "工匠", "商人", "官僚", "兵")

    def _pop_aggregate(self):
        """全国六类 POP 聚合：{类: {size, wealth, grain, goods, 窖银}}（只读 state）。"""
        agg = {k: {"size": 0, "wealth": 0, "grain": 0, "goods": 0, "窖银": 0}
               for k in self._POP_CLASSES}
        for p in self.state.prefectures.values():
            for name, pop in (p.get("pops") or {}).items():
                if name not in agg:
                    continue
                a = agg[name]
                a["size"] += int(pop.get("size", 0) or 0)
                a["wealth"] += int(pop.get("wealth", 0) or 0)
                a["grain"] += int(pop.get("grain", 0) or 0)
                a["goods"] += sum(int(v) for v in (pop.get("goods") or {}).values())
                a["窖银"] += int(pop.get("窖银", 0) or 0)
        return agg

    def _panel_pop(self):
        """民生 · 六类人口经济总览：全国总览（表格）+ 关键指标 + 诸路明细（按路折叠）。

        数据源：state.prefectures[路].pops（六类 POP 的 size/wealth/grain/goods/窖银）。
        """
        from ui.gui_common import humanize_coin, humanize_grain
        inner = self._panel_shell("民 生")
        self._label(inner,
                    "天下生民，六等之众：农、士绅、工匠、商人、官僚、兵。钱粮货物，皆在民焉。",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 11), anchor="w").pack(
            padx=12, pady=(2, 8))
        s = self.state
        agg = self._pop_aggregate()

        # —— 全国六类总览（表格卡片）——
        self._card_title2(inner, "全 国 六 类 人 口 总 览")
        card = self._card(inner)
        card.pack(fill="x", padx=10, pady=4)
        cols = [("类 别", "w"), ("人 数", "e"), ("持 钱", "e"), ("存 粮", "e"),
                ("商 品", "e")]
        for c, (txt, anchor) in enumerate(cols):
            self._label(card, txt, fg=RED_D, bg=CARD, font=self._font(SANS, 10, "bold"),
                        anchor=anchor).grid(row=0, column=c, padx=10, pady=(8, 2), sticky="we")
        for r, name in enumerate(self._POP_CLASSES, 1):
            a = agg[name]
            vals = [
                name,
                f"{a['size']:,} 人",
                humanize_coin(a["wealth"]),
                humanize_grain(a["grain"]),
                f"{a['goods']:,} 件",
            ]
            for c, v in enumerate(vals):
                self._label(card, v, fg=(INK if c else RED_D), bg=CARD,
                            font=self._font(SANS, 10, "bold" if c == 0 else ""),
                            anchor=cols[c][1]).grid(row=r, column=c, padx=10, pady=2, sticky="we")
        for c in range(len(cols)):
            card.grid_columnconfigure(c, weight=1)

        # —— 关键指标（民间经济健康）——
        self._card_title2(inner, "关 键 指 标 · 民 间 经 济")
        ind = self._card(inner)
        ind.pack(fill="x", padx=10, pady=4)
        tot = {"wealth": 0, "grain": 0, "goods": 0, "窖银": 0}
        for a in agg.values():
            tot["wealth"] += a["wealth"]
            tot["grain"] += a["grain"]
            tot["goods"] += a["goods"]
            tot["窖银"] += a["窖银"]
        ind_row = tk.Frame(ind, bg=CARD)
        ind_row.pack(fill="x", padx=12, pady=8)
        for lab, v, unit in (
                ("民间总持钱", humanize_coin(tot["wealth"]), "贯"),
                ("民间总存粮", humanize_grain(tot["grain"]), "石"),
                ("商品存量", f"{tot['goods']:,}", "件")):
            cell = tk.Frame(ind_row, bg=CARD, relief="ridge", bd=1,
                            highlightbackground=GOLD, highlightthickness=1)
            cell.pack(side="left", expand=True, fill="x", padx=4)
            self._label(cell, lab, fg=DIM, bg=CARD, font=self._font(SANS, 9),
                        anchor="center").pack(pady=(6, 0))
            self._label(cell, v, fg=RED_D, bg=CARD, font=self._font(KAI, 12, "bold"),
                        anchor="center").pack(pady=(0, 6))
        self._label(inner, "（民间钱粮为民生之基；藏富之银不入市，察之者自明。）",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 9)).pack(padx=12, pady=(2, 6), anchor="w")

        # —— 诸路明细（按路折叠）——
        self._card_title2(inner, "诸 路 民 生 明 细")
        open_st = {}
        for name, p in s.prefectures.items():
            pop = p.get("pops") or {}
            disp = p.get("name", name)
            wrap = tk.Frame(inner, bg=PAPER)
            wrap.pack(fill="x", padx=10, pady=2)

            def _tot_line(popd):
                sizes = sum(int(x.get("size", 0) or 0) for x in popd.values())
                wealth = sum(int(x.get("wealth", 0) or 0) for x in popd.values())
                grain = sum(int(x.get("grain", 0) or 0) for x in popd.values())
                goods = sum(sum(int(v) for v in (x.get("goods") or {}).values())
                            for x in popd.values())
                return (f"共 {sizes:,} 人　持钱 {humanize_coin(wealth)}　"
                        f"存粮 {humanize_grain(grain)}　商品 {goods:,} 件")

            hdr = tk.Frame(wrap, bg=PAPER)
            hdr.pack(fill="x")
            self._title(hdr, disp, fg=RED, bg=PAPER, font=self._font(KAI, 12, "bold"),
                        anchor="w").pack(side="left")
            self._label(hdr, _tot_line(pop), fg=DIM, bg=PAPER, font=self._font(SANS, 9),
                        anchor="e").pack(side="right")
            open_st[name] = {"open": False, "btn": None}

            def _toggle(nm=name, wd=wrap, pd=pop):
                open_st[nm]["open"] = not open_st[nm]["open"]
                for w in list(wd.winfo_children()):
                    if w is not hdr:
                        w.destroy()
                if open_st[nm]["open"]:
                    detail = tk.Frame(wd, bg=CARD, relief="ridge", bd=1,
                                      highlightbackground=BORDER, highlightthickness=1)
                    detail.pack(fill="x", pady=(2, 2))
                    for cls in self._POP_CLASSES:
                        x = pd.get(cls)
                        if not x:
                            continue
                        row = tk.Frame(detail, bg=CARD)
                        row.pack(fill="x", padx=10, pady=1)
                        self._label(row, f"　{cls}", fg=RED_D, bg=CARD,
                                    font=self._font(KAI, 11, "bold"), anchor="w").pack(side="left")
                        self._label(row,
                                    f"{int(x.get('size', 0) or 0):,} 人　持钱 "
                                    f"{humanize_coin(int(x.get('wealth', 0) or 0))}　存粮 "
                                    f"{humanize_grain(int(x.get('grain', 0) or 0))}　商品 "
                                    f"{sum(int(v) for v in (x.get('goods') or {}).values()):,} 件",
                                    fg=INK, bg=CARD, font=self._font(SANS, 9), anchor="w").pack(
                            side="left", padx=(8, 0))
                btn = open_st[nm]["btn"]
                if btn is not None:
                    try:
                        btn.config(text="－ 收 起" if open_st[nm]["open"] else "＋ 明 细")
                    except Exception:
                        pass

            open_st[name]["btn"] = self._btn(hdr, "＋ 明 细", _toggle, width=8, ghost=True)
            open_st[name]["btn"].pack(side="right", padx=4)

    def _panel_military_affairs(self):
        """军政 = 真正的军事事务（军队实体/防线/战事/武库），无任何一键施政。"""
        inner = self._panel_shell("军 政 机 务")
        self._label(inner, "军机事务：诸军实体、边防线、战事、中央武库。凡军国诏令皆下诏推演。",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 11), anchor="w").pack(padx=12, pady=(4, 10))
        self._render_armies(inner)
        self._render_defense(inner)
        self._render_war_report(inner)
        self._render_arsenal(inner)

    def _render_armies(self, parent):
        """军队实体列表：按路排列，内联全量字段（番号/兵种/兵额/装备率/士气/训练/防线）。"""
        s = self.state
        self._card_title2(parent, "诸 军 实 体")
        card = self._card(parent)
        card.pack(fill="x", padx=10, pady=4)
        # 按驻地分组
        by_station: dict = {}
        for u in s.army_units:
            by_station.setdefault(u.station, []).append(u)
        for station in s.prefectures:
            units = by_station.get(station, [])
            if not units:
                continue
            sub = tk.Frame(card, bg=CARD)
            sub.pack(fill="x", padx=12, pady=(4, 2))
            self._title(sub, s.prefectures[station].get("name", station), fg=RED, bg=CARD,
                        font=self._font(KAI, 12, "bold"), anchor="w").pack(anchor="w")
            for u in sorted(units, key=lambda x: (x.tier != "禁军", -x.troops)):
                row = tk.Frame(card, bg=CARD)
                row.pack(fill="x", padx=24, pady=1)
                # 左：番号（军籍·兵种构成）
                brs = "/".join(f"{b}{n}" for b, n in u.branches.items() if n > 0)
                self._label(row, f"{u.name}（{brs}）", fg=INK, bg=CARD,
                            font=self._font(SANS, 10), anchor="w").pack(side="left")
                # 右：兵额 / 装备率 / 士气 / 训练 / 防线
                equip_rate = int(u.equip_rate() * 100)
                self._label(row,
                            f"{_fmt_count(u.troops, '人')}  备{equip_rate}%  气{u.morale}  训{u.training}  {u.defense_line}",
                            fg=DIM, bg=CARD, font=self._font(SANS, 9), anchor="e").pack(side="right")

    def _render_defense(self, parent):
        """边防线：防区驻防兵额 + 城防质量（由 army_units 聚合派生）。"""
        s = self.state
        s._derive_defense_lines()
        self._card_title2(parent, "边 防 要 线")
        card = self._card(parent)
        card.pack(fill="x", padx=10, pady=4)
        for ln, l in s.defense_lines.items():
            row = tk.Frame(card, bg=CARD)
            row.pack(fill="x", padx=12, pady=4)
            self._title(row, ln, fg=RED, bg=CARD, font=self._font(KAI, 13, "bold"), anchor="w").pack(side="left")
            self._label(row, f"驻防{_fmt_count(l['garrison'], '人')}  城防{l['fortification']}",
                        fg=INK, bg=CARD, font=self._font(SANS, 10), anchor="e").pack(side="right")

    def _render_war_report(self, parent):
        """战事动态：取最近一期结算日志。"""
        s = self.state
        self._card_title2(parent, "战 事 动 态")
        card = self._card(parent)
        card.pack(fill="x", padx=10, pady=4)
        log = getattr(s, "settlement_log", [])
        if log:
            for entry in log[-1]:
                self._label(card, f"· {entry}", fg=INK, bg=CARD, font=self._font(SANS, 10),
                            anchor="w").pack(anchor="w", padx=12, pady=2)
        else:
            self._label(card, "— 边境无事，海内承平 —", fg=DIM, bg=CARD, font=self._font(SANS, 10),
                        anchor="w").pack(anchor="w", padx=12, pady=6)

    def _render_arsenal(self, parent):
        """中央武库被动库存视图（7 项实物）。"""
        s = self.state
        self._card_title2(parent, "中 央 武 库")
        card = self._card(parent)
        card.pack(fill="x", padx=10, pady=4)
        stock = s.central_arsenal.stock
        parts = []
        for k in EQUIP_KEYS:
            parts.append(f"{k}{_fmt_count(stock.get(k, 0), '件' if k not in ('战马','舟船') else ('匹' if k=='战马' else '艘'))}")
        self._label(card, "  ".join(parts), fg=INK, bg=CARD, font=self._font(SANS, 9),
                    anchor="w").pack(anchor="w", padx=12, pady=6)

    def _panel_detail(self):
        inner = self._panel_shell("详情评览")
        s = self.state
        lines = []
        lines.append("【财政统计】")
        lines.append(f"  累计收入: {humanize_coin(s.statistics['total_income'])}")
        lines.append(f"  累计支出: {humanize_coin(s.statistics['total_expenditure'])}")
        lines.append(f"  总颁诏令: {s.statistics['total_decrees']}条")
        lines.append(f"  经历战事: {s.statistics['total_wars']}次")
        lines.append("")
        lines.append("【各路驻军】")
        from collections import defaultdict as _dd
        by_station = _dd(dict)
        for u in s.army_units:
            by_station[u.station][u.tier] = by_station[u.station].get(u.tier, 0) + u.troops
        for name in s.prefectures:
            g = by_station.get(name)
            if g:
                lines.append(f"  {s.prefectures[name].get('name', name)}: " +
                             " ".join(f"{k}{_fmt_count(v, '人')}" for k, v in g.items()))
        lines.append("")
        lines.append("【军旅锐气】")
        for u in s.army_units:
            lines.append(f"  {u.name}: 气{u.morale} 训{u.training} 备{int(u.equip_rate()*100)}%")
        lines.append("")
        lines.append("【防线】")
        for ln, l in s.defense_lines.items():
            lines.append(f"  {ln}: 驻防{_bar(int(l['garrison']/10),10)} {l['garrison']}  城防{l['fortification']}")
        lines.append("")
        lines.append("【密探渗透】")
        for name, level in s.spy_network.items():
            lines.append(f"  {name}: {_bar(int(level*100),15)} {level:.0%}")
        lines.append("")
        if s.settlement_log:
            lines.append("【近期大事】")
            for entry in s.settlement_log[-1]:
                lines.append(f"  {entry}")
        card = self._card(inner)
        card.pack(fill="both", expand=True, padx=10, pady=4)
        txt = self._scrolled(card, bg=CARD, font=self._font(SANS, 11), padx=16, pady=14)
        txt._text.insert("1.0", "\n".join(lines))
        txt._text.configure(state="disabled")
        txt.pack(fill="both", expand=True, padx=12, pady=12)

    def _panel_tech(self):
        """科技树：树状拓扑（浮于舆图之上的书页展开）。"""
        # scroll=False：直接占满浮层卡片内容区，避免外层滚动画布把树谱压成一条
        inner = self._panel_shell("科 技 树", scroll=False)
        self._label(inner, "天下技艺积累，皆聚于此。新制兴工：国库拨银须经廷议，内帑乾纲独断则免。",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 11), anchor="w").pack(padx=12, pady=(4, 10))

        # ---- 科技树谱（树状拓扑，占满面板并自带滚动）----
        tree_card = self._card(inner)
        tree_card.pack(fill="both", expand=True, padx=10, pady=4)
        holder = tk.Frame(tree_card, bg=PAPER)
        holder.pack(fill="both", expand=True, padx=4, pady=4)
        holder.grid_rowconfigure(0, weight=1)
        holder.grid_columnconfigure(0, weight=1)

        cv = tk.Canvas(holder, bg=PAPER, highlightthickness=0)
        cv.grid(row=0, column=0, sticky="nsew")
        sb = tk.Scrollbar(holder, command=cv.yview, bg=PAPER2, troughcolor=PAPER,
                          highlightbackground=PAPER, activebackground=GOLD)
        sb.grid(row=0, column=1, sticky="ns")
        cv.configure(yscrollcommand=sb.set)
        cv._sb = sb  # 供 _draw_tech_tree 控制显隐
        cv.bind("<MouseWheel>", lambda e: cv.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        cv.bind("<Enter>", lambda e: cv.focus_set())
        # 延迟绘制，等待 Canvas 完成 layout 拿到真实尺寸再算列宽
        cv.after(120, lambda: self._draw_tech_tree(cv))

    def _draw_tech_tree(self, cv):
        """在 Canvas 上按 6 干线分列、节点按 era 排布的树状图绘制。"""
        cv.delete("all")
        try:
            from core.asset_context import node_status
            from content.data import TECH_NODES, TECH_LINES, tech_cost_with_era
        except Exception:
            return
        s = self.state
        cv.update_idletasks()          # 强制完成 pending 的几何计算
        w = cv.winfo_width() or 900
        h = cv.winfo_height() or 480
        # Canvas 还没拿到真实尺寸（首帧常返回 1）→ 延迟重试，绝不在错误尺寸下缓存
        if w < 200 or h < 150:
            cv.after(120, lambda: self._draw_tech_tree(cv))
            return
        # 尺寸缓存：尺寸合理且与上次一致才跳过，避免重复绘制
        last = getattr(cv, "_tech_last_size", None)
        if last == (w, h):
            return
        cv._tech_last_size = (w, h)
        nlines = len(TECH_LINES)
        col_w = w / nlines
        pad_top = 14
        pad_bot = 14
        # 节点框尺寸
        node_w = max(90, col_w - 18)
        node_h = 34
        # 按 era 计算行高（era 0..6）
        eras = [nd[2] for nd in TECH_NODES if not nd[0].startswith("gen_")]
        max_era = max(eras) if eras else 6
        avail_h = max(220, h - pad_top - pad_bot)
        row_h = max(50, avail_h / (max_era + 1))
        # 列标题 y
        head_h = 22

        # 预计算每个节点的几何中心
        geom = {}
        # 先按 line 分列，再按 era 排序（同 era 按原序）
        ordered = [nd for nd in TECH_NODES if not nd[0].startswith("gen_")]
        for li, line in enumerate(TECH_LINES):
            col_nodes = [nd for nd in ordered if nd[1] == line]
            col_nodes.sort(key=lambda n: (n[2], ordered.index(n)))
            cx = col_w * li + col_w / 2
            for i, nd in enumerate(col_nodes):
                cy = pad_top + head_h + nd[2] * row_h + row_h / 2
                geom[nd[0]] = (cx, cy)

        # 配色（四态）
        def colors(st):
            if st == "unlocked":
                return "#7a1f1a", GOLD, "#f3e6c4"      # 朱红填充 + 描金 + 米白字
            if st == "researchable":
                return "#f3e6c4", GOLD, "#3a2a17"       # 米白底 + 金边 + 墨字
            if st == "researching":
                return "#1f4a5a", "#7fd4e6", "#eaf7fb"   # 青蓝 + 亮蓝边
            return "#cfc6b4", "#9c9486", "#6b6151"    # 灰墨（locked）

        # 先画连线（prereq）
        for nd in ordered:
            nid = nd[0]
            if nid not in geom:
                continue
            x2, y2 = geom[nid]
            for pre in (nd[5] or []):
                if pre in geom:
                    x1, y1 = geom[pre]
                    # 折线：从前置底 → 当前顶
                    mid_y = (y1 + y2) / 2
                    cv.create_line(x1, y1 + node_h / 2, x1, mid_y,
                                   x2, mid_y, x2, y2 - node_h / 2,
                                   smooth=False, fill="#9c8e72", width=1.2, dash=(3, 2))

        # 再画节点 + 列标题
        for li, line in enumerate(TECH_LINES):
            cx = col_w * li + col_w / 2
            cv.create_text(cx, pad_top + head_h / 2, text=line,
                           font=self._font(KAI, 11, "bold"), fill=INK)
        for nd in ordered:
            nid = nd[0]
            if nid not in geom:
                continue
            x, y = geom[nid]
            try:
                st = node_status(s, nid)
            except Exception:
                st = "locked"
            fill, edge, fg = colors(st)
            x1, y1 = x - node_w / 2, y - node_h / 2
            x2, y2 = x + node_w / 2, y + node_h / 2
            theme.round_rect(cv, x1, y1, x2, y2, 8, fill=fill, outline=edge, width=2)
            # 名称（过长截断）
            nm = nd[3]
            if len(nm) > 7:
                nm = nm[:6] + "…"
            cv.create_text(x, y, text=nm, font=self._font(SANS, 9, "bold"), fill=fg)
            # 点击命中区
            tag = f"node::{nid}"
            cv.create_rectangle(x1, y1, x2, y2, fill="", outline="", tags=(tag,))
            cv.tag_bind(tag, "<Enter>", lambda e, t=tag: cv.config(cursor="hand2"))
            cv.tag_bind(tag, "<Leave>", lambda e: cv.config(cursor=""))
            cv.tag_bind(tag, "<Button-1>", lambda e, n=nid: self._tech_detail(n))

        # 更新滚动区；内容未超出可视高度时隐藏滚动条
        cv.update_idletasks()
        bbox = cv.bbox("all")
        if bbox:
            cv.configure(scrollregion=bbox)
            sb = getattr(cv, "_sb", None)
            if sb:
                view_h = cv.winfo_height()
                if bbox[3] - bbox[1] <= view_h + 1:
                    sb.grid_remove()
                else:
                    sb.grid()

    def _tech_detail(self, node_id):
        """点击树节点 → 在主浮层栈上叠一张详情卡片（前置 / 成本 / 会签入口）。"""
        from content.data import get_tech_node, tech_cost_with_era
        nd = get_tech_node(node_id)
        if nd is None:
            return
        nid, line, era, name, desc, prereq, _, _, cost, effect = nd[:10]
        try:
            from core.asset_context import node_status
            st = node_status(self.state, nid)
        except Exception:
            st = "locked"
        cur_era = getattr(self.state, "era", 0) or 0
        real_cost = tech_cost_with_era(nd, cur_era)
        silver = int(real_cost.get("silver", 0) or 0)
        months = int(real_cost.get("months", 0) or 0)

        def _build_detail():
            body = self.main
            self._title(body, f"〔{line}〕{name}", fg=RED, font=self._font(KAI, 16, "bold")).pack(pady=8)
            st_txt = {"unlocked": "已点亮", "researchable": "可研发",
                      "researching": "攻关中", "locked": "未解锁"}.get(st, st)
            self._label(body, f"状态：{st_txt}　·　时代层级：{era}",
                        fg=INK, bg=PAPER, font=self._font(SANS, 11)).pack(pady=(0, 6))
            # 描述
            self._label(body, desc, fg=INK, bg=PAPER, font=self._font(SANS, 11),
                        anchor="w", wraplength=660).pack(fill="x", padx=20, pady=(0, 8))
            # 前置
            pre_names = []
            for p in (prereq or []):
                pn = get_tech_node(p)
                pre_names.append(pn[3] if pn else p)
            self._label(body, "前置：" + ("、".join(pre_names) if pre_names else "无"),
                        fg=DIM, bg=PAPER, font=self._font(SANS, 10), anchor="w").pack(fill="x", padx=20, pady=2)
            # 成本（皇帝只关心耗帑与工期，匠役归工部将作监调度）
            cost_txt = f"耗帑 {humanize_coin(silver)}　·　工期 {months}月　·　工部领办，匠役由将作监调拨" if (silver or months) else "近零成本（观念/基础）"
            self._label(body, cost_txt, fg=DIM, bg=PAPER, font=self._font(SANS, 10), anchor="w").pack(fill="x", padx=20, pady=2)
            # 效果（简述）
            if effect:
                eff_txt = _format_tech_effect(effect)
                self._label(body, f"效用：{eff_txt}", fg=DIM, bg=PAPER, font=self._font(SANS, 10), anchor="w").pack(fill="x", padx=20, pady=2)

            # 操作按钮
            bar = tk.Frame(body, bg=PAPER)
            bar.pack(side="bottom", pady=12)
            if st == "researchable":
                self._btn(bar, "国库拨银（会签）", lambda: self._research_signing(nid),
                          gold=True).pack(side="left", padx=6)
                self._btn(bar, "内帑独断", lambda: self._research_inner(nid),
                          ghost=True).pack(side="left", padx=6)
            else:
                self._label(bar, "（当前不可立项）", fg=DIM, bg=PAPER, font=self._font(SANS, 10)).pack(side="left", padx=6)
                self._btn(bar, "关 闭", lambda: self._close_overlay(), ghost=True).pack(side="left", padx=6)

        self._open_overlay(_build_detail, f"科技 · {name}")

    def _research_inner(self, node_id):
        """内帑乾纲独断研发：免会签，直扣皇帝私库立项。"""
        try:
            msg, self.state = self.backend.action(
                self.state, "start_tech_research",
                {"node_id": node_id, "silver": 0, "fund": "inner", "source": "panel"},
                self.ai_client)
        except _AIRuntimeError as e:
            self.messagebox.showerror("AI 叙事中断", str(e))
            return
        self._log(f"〔内帑独断〕{msg}")
        self._refresh_hud()
        self._close_overlay()
        self._switch_panel(self._panel_tech, "科技树")
        self.messagebox.showinfo("已立项", msg)

    def _research_signing(self, node_id):
        """国库拨银研发：先探明费用，弹会签窗口，准奏才真正拨帑立项。"""
        from core.asset_context import prepare_research
        pre = prepare_research(self.state, node_id, 0, fund="treasury", source="panel")
        if not pre.get("ok"):
            self.messagebox.showinfo("不可研", pre.get("reason", "暂不可研。"))
            return
        if pre.get("idea"):
            # 观念类：不花钱不走会签，直接颁布
            try:
                msg, self.state = self.backend.action(
                    self.state, "start_tech_research",
                    {"node_id": node_id, "silver": 0, "fund": "treasury",
                     "source": "panel", "signoff": True}, self.ai_client)
            except _AIRuntimeError as e:
                self.self.messagebox.showerror("AI 叙事中断", str(e))
                return
            self._log(msg)
            self._refresh_hud()
            self._close_overlay()
            self._switch_panel(self._panel_tech, "科技树")
            self.messagebox.showinfo("已颁行", msg)
            return

        name = pre.get("name", "")
        silver = pre.get("silver", 0)
        title = f"廷议 · 国库拨银研「{name}」"

        def _build_signing():
            body = self.main
            self._title(body, f"〔廷议〕国库拨银研「{name}」",
                        fg=RED, font=self._font(KAI, 16, "bold")).pack(pady=6)

            # 依职权相关大臣回话（工部职掌工程营造，领衔入对）
            try:
                rel = self.state.org_ministers("工部")
            except Exception:
                rel = []
            if rel:
                self._label(body, f"依职权相关大臣：{'、'.join(rel)}（工部领衔，已据所司回话）",
                            fg=RED_D, bg=PAPER, font=self._font(KAI, 12, "bold"),
                            anchor="w").pack(fill="x", padx=16, pady=(2, 2))

            # 钦点入对：可召其他朝臣廷前对质
            try:
                all_names = [n for n in self.state.loyalty
                             if n not in rel and self.state.minister_status(n) == "active"]
            except Exception:
                all_names = []
            summon_row = tk.Frame(body, bg=PAPER)
            summon_row.pack(fill="x", padx=16, pady=2)
            self._label(summon_row, "钦点入对：", fg=INK, bg=PAPER,
                        font=self._font(SANS, 11)).pack(side="left")
            summon_var = tk.StringVar(value="（请选）")
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
                self._close_overlay()        # 暂收会签层
                self._open_overlay(
                    lambda: self._panel_dialogue(who, role=f"廷前入对·研「{name}」"),
                    f"廷议召对 · {who}")

            self._btn(summon_row, "召 入 对 质", _summon, width=12, gold=True).pack(side="left", padx=8)

            sc = self._scrolled(body, bg=CARD, font=self._font(KAI, 12), height=14)
            sc.pack(fill="both", expand=True, padx=14, pady=6)
            t = sc._text
            t.tag_configure("h", foreground=RED_D, font=self._font(KAI, 12, "bold"))
            t.tag_configure("b", foreground=INK, font=self._font(KAI, 12))

            # 会用专家团（council_review）生成三省六部意见；AI 未接入时明确提示（不静默降级）
            fallback = {"memo": f"工部奏请以国库拨银 {humanize_coin(silver)}，兴「{name}」之研，期{pre.get('months')}月。",
                        "objections": "户部核库：国库尚有此力，度支可行。",
                        "executions": "工部承领营造，度支司按月拨给，工毕核销。",
                        "verdict": "可准", "revised_effects": []}

            def _render_review(review):
                t.delete("1.0", "end")
                t.insert("end", "【中书省拟稿】\n", "h")
                t.insert("end", f"{review.get('memo','')}\n\n", "b")
                t.insert("end", "【门下省封驳】\n", "h")
                t.insert("end", f"{review.get('objections','')}\n\n", "b")
                t.insert("end", "【尚书省·六部执行】\n", "h")
                t.insert("end", f"{review.get('executions','')}\n\n", "b")
                t.insert("end", f"【廷议结论】{review.get('verdict','可准')}\n", "h")
                t.insert("end", f"\n拨帑 {humanize_coin(silver)}（国库），工期 {pre.get('months')} 月；工部领办，匠役由将作监调拨。",
                         "b")

            if not (self.ai_client and getattr(self.ai_client, "available", False)):
                self.messagebox.showwarning(
                    "AI 未接入", "未接入 AI，请配置 OpenAI 兼容 API（base_url/api_key/model）：游戏设置 → AI 配置。会签以规则意见代替。")
                _render_review(fallback)
            else:
                # T6 异步会签：先渲染"推演中"，完成后主线程回填（UI 不卡驻）
                _render_review({"memo": "（廷议推演中…）", "objections": "（门下省核议中…）",
                                "executions": "（六部承旨待办中…）", "verdict": "—", "revised_effects": []})
                summary = self.state.get_state_summary()

                def _on_success(rev):
                    try:
                        _render_review(rev)
                    except Exception:
                        pass

                def _on_error(e):
                    try:
                        _render_review(fallback)
                    except Exception:
                        pass
                    self.messagebox.showerror("AI 叙事中断", str(e))

                from core.async_ai import run_ai_call
                run_ai_call(
                    self.ai_client, "council_review",
                    {"title": f"国库拨银研「{name}」", "body": pre.get("desc", ""),
                     "effects": [{"dim": "treasury", "value": -silver}],
                     "org_hint": "政府"},
                    summary, state=self.state,
                    on_success=_on_success, on_error=_on_error, ui=self.root)

            bb = tk.Frame(body, bg=PAPER)
            bb.pack(pady=10)

            def _approve():
                from core.asset_context import record_research_signoff
                record_research_signoff(self.state, node_id, review)
                try:
                    msg, self.state = self.backend.action(
                        self.state, "start_tech_research",
                        {"node_id": node_id, "silver": silver, "fund": "treasury",
                         "source": "panel", "signoff": True}, self.ai_client)
                except _AIRuntimeError as e:
                    self.self.messagebox.showerror("AI 叙事中断", str(e))
                    return
                self._pending_logs.append(f"会签准奏·研「{name}」：{msg}")
                self._log(f"〔会签·准奏〕研「{name}」：{msg}")
                self._refresh_hud()
                self._close_overlay()        # 关闭会签层
                self._close_overlay()        # 关闭科技详情层
                self._switch_panel(self._panel_tech, "科技树")
                self.self.messagebox.showinfo("已立项", f"陛下准奏，{msg}")

            def _reject():
                self._pending_logs.append(f"会签打回·研「{name}」")
                self._close_overlay()        # 关闭会签层，返回科技详情
                self.self.messagebox.showinfo("打回", f"「{name}」之请，已打回工部另议，未动帑藏。")

            self._seal_btn(bb, "准 奏 拨 帑", _approve, big=True).pack(side="left", padx=8)
            self._btn(bb, "打 回 重 议", _reject, width=12, ghost=True).pack(side="left", padx=8)

        self._open_overlay(_build_signing, title)

    def _panel_engineering(self):
        """工程展示：可建工程类别 + 已开工工程（只读，纯展示不施政）。"""
        inner = self._panel_shell("工 程 营 造")
        self._label(inner, "山川城邑，营建之事。凡兴土工役之诏，皆由圣旨推演。",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 11), anchor="w").pack(padx=12, pady=(4, 10))
        s = self.state

        # 可建工程类别（具体清单：政府建筑 + 科技蓝图）
        self._card_title2(inner, "可 建 工 程")
        cat = self._card(inner)
        cat.pack(fill="x", padx=10, pady=4)
        from content.data import BUILDING_STD, BUILDING_BLUEPRINTS
        items = []
        for bname, bcfg in (BUILDING_STD or {}).items():
            cost = bcfg.get("base_cost", 0)
            eff = _TECH_EFFECT_LABELS.get(str(bcfg.get("effect", "")), str(bcfg.get("effect", "")))
            items.append((bname, cost, eff))
        for bid, bcfg in (BUILDING_BLUEPRINTS or {}).items():
            nm = bcfg.get("name", bid)
            cost = (bcfg.get("cost") or {}).get("silver", 0)
            eff = bcfg.get("effect", "")
            if isinstance(eff, dict):
                # 科技蓝图 effect 为 dict：逐键映射中文（如 {'trade_income': 0.15} → 贸易收入+15%）
                parts = []
                for k, v in eff.items():
                    label = _TECH_EFFECT_LABELS.get(str(k), str(k))
                    if isinstance(v, (int, float)) and v != 0:
                        pct = f"{'+' if v > 0 else ''}{int(v*100)}%" if abs(v) < 2 else f"{'+' if v > 0 else ''}{v}"
                        parts.append(f"{label}{pct}")
                    else:
                        parts.append(f"{label}{v}")
                eff = "、".join(parts)
            else:
                eff = _TECH_EFFECT_LABELS.get(str(eff), str(eff))
            items.append((nm, cost, eff))
        if items:
            shown = 0
            for name, cost, eff in items:
                if shown >= 12:
                    break
                self._label(cat, f"· {name}（{cost//10000}万贯）{eff}",
                            fg=INK, bg=CARD, font=self._font(SANS, 10), anchor="w",
                            justify="left").pack(anchor="w", padx=12, pady=2)
                shown += 1
            self._label(cat, "（拟诏「营造」某建筑以兴工；工程类诏令经圣旨推演落地）",
                        fg=DIM, bg=CARD, font=self._font(SANS, 9), anchor="w").pack(anchor="w", padx=12, pady=(4, 6))
        else:
            self._label(cat, "— 暂无可见工程 —", fg=DIM, bg=CARD, font=self._font(SANS, 10),
                        anchor="w").pack(anchor="w", padx=12, pady=8)

        # 已开工工程（从在办筛“工程”类）
        self._card_title2(inner, "已 开 工")
        wc = self._card(inner)
        wc.pack(fill="x", padx=10, pady=4)
        opened = []
        for grp in ("longterm_public", "longterm_secret"):
            for it in getattr(s, grp, []):
                if isinstance(it, dict) and "工程" in str(it.get("cat", "")) or \
                   isinstance(it, dict) and "工程" in str(it.get("title", "")):
                    opened.append(it)
        if opened:
            for it in opened[:10]:
                self._label(wc, f"· {it.get('title', it.get('cat', '工程'))}：承办 {it.get('owner', '—')}　进度 {it.get('progress', 0)}%",
                            fg=INK, bg=CARD, font=self._font(SANS, 10), anchor="w").pack(anchor="w", padx=12, pady=3)
        else:
            self._label(wc, "— 暂无开工之役 —", fg=DIM, bg=CARD, font=self._font(SANS, 10),
                        anchor="w").pack(anchor="w", padx=12, pady=8)

    def _panel_accounting(self):
        """会计录：名义岁入 vs 实际到库、月用度、库藏/货币/物价读数。
        三冗不可见不可直裁——用度只呈总盘，对治须走变法长期政务。"""
        inner = self._panel_shell("会 计 录")
        s = self.state
        fin = s.finance_readout()   # 后端权威读数（含 tax_rate_desc/shortage_desc/price_trend）
        self._label(inner, "会计录：岁入盈亏，一目了然。然朝廷用度止呈总盘，冗费深藏其中，非省浮费、裁冗员之变法不足以治之。",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 11), anchor="w").pack(padx=12, pady=(2, 8))

        # 征率与税负口径
        rate_card = self._card(inner)
        rate_card.pack(fill="x", padx=10, pady=4)
        self._card_title(rate_card, "工 商 征 率")
        self._label(rate_card,
                    f"当前征率：{self._format_rate(s.commerce_tax_rate)}",
                    fg=INK, bg=CARD, font=self._font(SANS, 11, "bold"), anchor="w").pack(anchor="w", padx=14, pady=(6, 2))
        self._label(rate_card,
                    "口径：0.05~0.40 为综合税负（商税+榷货+坊场钱），非单一商税。调征率请经拟旨（如「征三成」「0.13」）。",
                    fg=DIM, bg=CARD, font=self._font(SANS, 9), anchor="w").pack(anchor="w", padx=14, pady=(2, 4))

        # 岁入读数
        # （fin 已在上方读取，供下方各卡片复用）
        inc_card = self._card(inner)
        inc_card.pack(fill="x", padx=10, pady=4)
        self._card_title(inc_card, "岁 入 盈 虚")
        self._label(inc_card,
                    f"名义岁入：{humanize_coin(fin['nominal_annual'])}/年（账面，贴史实）",
                    fg=INK, bg=CARD, font=self._font(SANS, 11, "bold"), anchor="w").pack(anchor="w", padx=14, pady=(4, 2))
        self._label(inc_card,
                    f"实际月入：{humanize_coin(fin['monthly_in'])}/月　"
                    f"（工商 {humanize_coin(fin['commerce'])} + 役钱 {humanize_coin(fin['poll'])}"
                    + (f" + 市舶 {humanize_coin(fin['maritime'])}" if fin['maritime'] > 0 else "")
                    + f" + 二税折色 {humanize_coin(fin['tax_color'])} + 盐课 {humanize_coin(fin['salt_coin'])}）",
                    fg=INK, bg=CARD, font=self._font(SANS, 10), anchor="w").pack(anchor="w", padx=14, pady=2)
        diff = fin['nominal_annual'] / 12 - fin['monthly_in']
        self._label(inc_card,
                    f"差额 {humanize_coin(diff)}/月即「隐漏与拖欠」——账面名义与实到之距，正田赋隐漏、胥吏侵蚀之漏出。",
                    fg=DIM, bg=CARD, font=self._font(SANS, 9), anchor="w").pack(anchor="w", padx=14, pady=(2, 4))

        # 用度（总盘）
        out_card = self._card(inner)
        out_card.pack(fill="x", padx=10, pady=4)
        self._card_title(out_card, "月 用 度")
        self._label(out_card,
                    f"月用度：{humanize_coin(fin['total_out'])}/月　"
                    f"（常支 {humanize_coin(fin['expenditure'])}"
                    + (f" + 军费 {humanize_coin(fin['army_cash'])}" if fin['army_cash'] > 0 else "")
                    + (f" + 官俸 {humanize_coin(fin['official_cash'])}" if fin['official_cash'] > 0 else "")
                    + (f" + 岁币 {humanize_coin(fin['sui_gong'])}" if fin['sui_gong'] > 0 else "")
                    + f"）",
                    fg=INK, bg=CARD, font=self._font(SANS, 10), anchor="w").pack(anchor="w", padx=14, pady=(4, 2))
        prb = getattr(s, "payraise_budget", 0)
        if prb > 0:
            self._label(out_card,
                        f"厚禄养廉：加俸预算尚余 {humanize_coin(prb)}，逐月摊还驱动诸路俸给充足。",
                        fg=DIM, bg=CARD, font=self._font(SANS, 9), anchor="w").pack(anchor="w", padx=14, pady=2)
        wr = getattr(s, "waste_reform", None) or {}
        if wr.get("active"):
            self._label(out_card,
                        f"变法{ '裁汰冗员' if wr.get('kind')=='reduce_office' else '省浮费' }推进中：月省 {humanize_coin(wr.get('savings',0))}，用度渐降。",
                        fg=DIM, bg=CARD, font=self._font(SANS, 9), anchor="w").pack(anchor="w", padx=14, pady=2)
        self._label(out_card,
                    "用度止呈总盘——冗官冗费深藏其中，账目无从分辨。欲治三冗，唯经拟旨下「省浮费/裁汰冗员」长期变法。",
                    fg=DIM, bg=CARD, font=self._font(SANS, 9), anchor="w").pack(anchor="w", padx=14, pady=(2, 4))
        net = fin['net']
        net_txt = f"月结余 {humanize_coin(net)}" if net >= 0 else f"月亏空 {humanize_coin(abs(net))}"
        self._label(out_card, f"净额：{net_txt}", fg=(INK if net >= 0 else RED), bg=CARD,
                    font=self._font(SANS, 11, "bold"), anchor="w").pack(anchor="w", padx=14, pady=(2, 4))

        # 库藏 / 货币 / 物价
        lib = self._card(inner)
        lib.pack(fill="x", padx=10, pady=4)
        self._card_title(lib, "库 藏 泉 货")
        self._label(lib,
                    f"国库：{humanize_coin(s.treasury)}　内帑：{humanize_coin(s.imperial_treasury)}"
                    + (f"（含酒课月 {humanize_coin(fin.get('wine_coin',0))}）" if fin.get('wine_coin') else ""),
                    fg=INK, bg=CARD, font=self._font(SANS, 10), anchor="w").pack(anchor="w", padx=14, pady=(4, 2))
        self._label(lib,
                    f"货币供给：{humanize_coin(getattr(s,'money_supply',0))}　物价：{round(s.price_level,2)}（钱/物之比）　"
                    f"钱荒：{fin['shortage_desc']}",
                    fg=DIM, bg=CARD, font=self._font(SANS, 10), anchor="w").pack(anchor="w", padx=14, pady=2)

    def _format_rate(self, rate):
        """征率 0~1 小数 → 中文/百分比展示。"""
        r = round(rate, 2)
        ones = {0.05: "半成", 0.10: "一成", 0.15: "一成五", 0.20: "二成", 0.25: "二成五",
                0.30: "三成", 0.35: "三成五", 0.40: "四成"}
        name = ones.get(r, f"{r*100:.0f}%")
        return f"{name}（{r*100:.0f}%）"

    def _panel_granary(self):
        """仓廪漕运：太仓虚实、诸路储粮、漕运阻塞、粮价/通货趋势读数，及仓廪施政。
        皇帝不事事亲为——重大仓廪之政应经拟旨；此处供单机便捷施政（同诏令效果键）。"""
        inner = self._panel_shell("仓 廪 漕 运")
        s = self.state
        self._label(inner, "仓廪虚实，系乎国运。田赋本色征粟入诸路，漕运输太仓，折变换钱养朝廷。",
                    fg=DIM, bg=PAPER, font=self._font(SANS, 11), anchor="w").pack(padx=12, pady=(2, 8))

        # 太仓虚实
        card = self._card(inner)
        card.pack(fill="x", padx=10, pady=4)
        self._card_title(card, "太 仓 虚 实")
        util = s.granary_capacity_used()
        self._meter(card, s.granary, max(s.granary_cap, 1), width=260,
                    label=f"太仓存粮 {humanize_grain(s.granary)} / {humanize_grain(s.granary_cap)}")
        # 太仓净储（月入=田赋本色，月出=军粮+官禄+吏禄×pay_ratio+雀鼠耗+贪腐损耗）
        grain_in_total, _ = s.calc_monthly_grain()
        army_g, _ = s.calc_army_grain()
        off_g, _ = s.calc_official_grain()
        clerk_g, _ = s.calc_clerk_grain()
        self._label(card,
                    f"太仓月入（田赋本色）：{humanize_grain(grain_in_total)}　"
                    f"月出（军粮{army_g:.0f}+官禄{off_g:.0f}+吏禄{clerk_g:.0f}+雀鼠耗+贪腐损耗）",
                    fg=DIM, bg=CARD, font=self._font(SANS, 9), anchor="w").pack(anchor="w", padx=14, pady=(2, 4))
        # 趋势读数：走后端 finance_readout 的 price_trend（基于认知层，消除前端自比真实层的口径漂移与信息泄漏）
        fin = s.finance_readout()
        trend = fin["price_trend"]
        self._label(card, f"米价趋势：{trend}　|　米价约 {humanize_grain_price(s.grain_price)}　"
                          f"|　漕运：{'阻塞' if s.canal_block >= 40 else '通畅'}"
                          f"（{s.canal_block}）", fg=DIM, bg=CARD, font=self._font(SANS, 10),
                    anchor="w").pack(anchor="w", padx=14, pady=(4, 2))

        # 泉货 / 通货
        qc = self._card(inner)
        qc.pack(fill="x", padx=10, pady=4)
        self._card_title(qc, "泉 货 通 滞")
        from content.data import desensitize_shortage, desensitize_granary
        self._label(qc, f"钱荒：{desensitize_shortage(s.coin.get('shortage', 0.3))}　"
                        f"|　物价水平：{round(s.price_level, 2)}（钱/物之比）　"
                        f"|　俸禄：{s.pay_system.get('mode','本色折色')}　"
                        f"|　{'一条鞭（折银）' if s.single_whip else '本色征粮'}",
                    fg=INK, bg=CARD, font=self._font(SANS, 10), anchor="w").pack(anchor="w", padx=14, pady=(6, 2))

        # 诸路储粮（取主要几路）
        self._card_title2(inner, "诸 路 储 粮")
        pc = self._card(inner)
        pc.pack(fill="x", padx=10, pady=4)
        for name in PREFECTURE_LIST[:6]:
            p = s.prefectures[name]
            # prefectures 是 dict，必须用 dict.get 而非 getattr（getattr 对 dict 永远返回默认值）
            gp = p.get("grain_price", s.grain_price)
            self._label(pc, f"· {name}　储粮 {humanize_grain(p.get('storage',0))}　"
                            f"粮产 {humanize_grain(p.get('grain',0))}　米价 {humanize_grain_price(gp)}",
                        fg=INK, bg=CARD, font=self._font(SANS, 10), anchor="w").pack(anchor="w", padx=12, pady=2)

        # 仓廪施政（折变/和籴/开仓赈济/兴漕运/扩建仓储等）请经「拟旨」系统拟诏施行；
        # 常平仓粜籴为地方自动平抑机制（随粮价高低自动运作），不经此处。
        self._card_title2(inner, "仓 廪 之 政")
        gc = self._card(inner)
        gc.pack(fill="x", padx=10, pady=4)
        self._label(gc, "仓廪调度（折变、和籴、赈济、漕运、扩建仓储）与颁一条鞭/方田均税等大政，请经「拟旨」系统施行，由中枢推演落地。",
                    fg=DIM, bg=CARD, font=self._font(SANS, 10), anchor="w").pack(anchor="w", padx=14, pady=8)

