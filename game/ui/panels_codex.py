# -*- coding: utf-8 -*-
"""宋祚 · GUI 图鉴（wiki）面板 Mixin。

8 类别左列表 + 右条目详情的只读图鉴：
  建筑 / 大臣 / 官职 / 科技 / 兵种 / 区域 / 机制 / 事件
- 数据源：content/data.py 常量（单一权威源）+ content/ministers + core/
  机制数据 + content/codex_text.py（史翰青 A14 文案落地）；
- 图鉴只读常量：条目内容与当前游戏数值无关，不写状态；
- 脱敏：loyalty / corruption 绝不出现；数值用区间/档位词或可见静态数据；
- 关联跳转：建筑↔科技↔兵种 条目间可点击跳转（links 语义）。
"""
import tkinter as tk

from ui.gui_common import (PAPER, PAPER2, CARD, INK, DIM, RED, RED_D, GOLD, GREEN,
    BORDER, SEAL_BG, KAI, SANS)

# 类别注册表：key → (标题, 条目构建函数名)
_CATEGORIES = [
    ("building", "建 筑"),
    ("minister", "大 臣"),
    ("org", "官 职"),
    ("tech", "科 技"),
    ("branch", "兵 种"),
    ("region", "区 域"),
    ("mechanism", "国 策"),
    ("event", "事 件"),
]


# ============================================================
# 条目数据构建（只读常量，惰性缓存）
# ============================================================
_CODEX_DATA = {}


def _tech_name(node_id: str) -> str:
    """科技节点 id → 节点名（链接显示用；不存在返回原 id）。"""
    try:
        from content.data import TECH_NODES
        for t in TECH_NODES:
            if t[0] == node_id:
                return t[3]
    except Exception:
        pass
    return node_id


def _build_building():
    """建筑：BUILDING_STD 官造 + POP_BUILDING_TYPES 民业 + 科技解锁（BLUEPRINTS / TECH_BUILDING_MAP）。"""
    from content.data import (BUILDING_STD, POP_BUILDING_TYPES, BUILDING_BLUEPRINTS,
                              TECH_BUILDING_MAP, TECH_NODES)
    from content.codex_text import CODEX_BUILDING_DESC, CODEX_BUILDING_EFFECT
    _tech_ids = {t[0] for t in TECH_NODES}
    # TECH_BUILDING_MAP 的语义键 → 真实科技节点 id（对齐 TECH_NODES 实数）
    _semantic = {"hydraulics": "M1_noria", "gunpowder": "C1_gunpowder",
                 "iron": "M3_bellows"}
    items = []
    for name, spec in BUILDING_STD.items():
        eff = CODEX_BUILDING_EFFECT.get(spec.get("effect", ""), spec.get("effect", ""))
        fields = [("效果", eff),
                  ("营造", f"约 {int(spec.get('base_cost', 0) or 0) // 10000} 万贯起")]
        links = []
        for tid, (bname, _thr) in TECH_BUILDING_MAP.items():
            if bname == name:
                node = _semantic.get(tid, tid)
                if node in _tech_ids:
                    links.append(("tech", node, _tech_name(node)))
        items.append({"key": name, "name": name, "sub": "官造",
                      "desc": CODEX_BUILDING_DESC.get(name, ""), "fields": fields, "links": links})
    for name in POP_BUILDING_TYPES:
        items.append({"key": name, "name": name, "sub": "民业",
                      "desc": CODEX_BUILDING_DESC.get(name, ""),
                      "fields": [("规格", "逐级增益，封顶两倍")], "links": []})
    for tid, bp in BUILDING_BLUEPRINTS.items():
        bname = bp.get("name", tid)
        cost = bp.get("cost", {}) or {}
        fields = [("营造", f"约 {int(cost.get('silver', 0) or 0) // 10000} 万贯 / {cost.get('months', 0)} 月")]
        items.append({"key": bname, "name": bname, "sub": f"新业·{bp.get('kind', '')}",
                      "desc": CODEX_BUILDING_DESC.get(bname, "科技解锁之新业。"),
                      "fields": fields, "links": [("tech", tid, _tech_name(tid))]})
    # 补 TECH_BUILDING_MAP 中未入上表的科技解锁建筑（火器作坊/铁作/市舶司）
    seen = {i["name"] for i in items}
    for tid, (bname, thr) in TECH_BUILDING_MAP.items():
        if bname not in seen:
            node = _semantic.get(tid, tid)
            links = [("tech", node, _tech_name(node))] if node in _tech_ids else []
            items.append({"key": bname, "name": bname, "sub": "新业·科技解锁",
                          "desc": CODEX_BUILDING_DESC.get(bname, "科技解锁之新业。"),
                          "fields": [("解锁", f"{_tech_name(tid)} 至 {thr} 级")],
                          "links": links})
    return items


def _build_minister():
    """大臣：MINISTERS 档案（脱敏——loyalty/corruption 绝不显示）+ A14 九人简介。"""
    from content.ministers.data import MINISTERS
    from content.codex_text import CODEX_MINISTER_BIO
    items = []
    for name, fig in MINISTERS.items():
        status = "在朝" if fig.get("in_office") else "在野/未显"
        fields = [("派系", fig.get("faction", "—")), ("职司", fig.get("role", "—"))]
        if fig.get("traits"):
            fields.append(("性情", fig.get("traits", "")))
        items.append({"key": name, "name": name, "sub": status,
                      "desc": CODEX_MINISTER_BIO.get(name, ""), "fields": fields, "links": []})
    return items


def _build_org():
    """官职：CENTRAL_ORG_INFO 机构树 + A14 官职说明。"""
    from content.ministers.data import CENTRAL_ORG_INFO
    from content.codex_text import CODEX_ORG_DESC
    items = []
    for name, info in CENTRAL_ORG_INFO.items():
        fields = [("职掌", info.get("scope", "—"))]
        auth = "、".join(info.get("authority", [])[:4])
        if auth:
            fields.append(("事权", auth))
        posts = "、".join(p.get("title", "") for p in info.get("posts", []))
        if posts:
            fields.append(("官缺", posts))
        holders = "、".join(f"{t}：{h}" for t, h in info.get("holders", {}).items() if h)
        if holders:
            fields.append(("在任", holders))
        items.append({"key": name, "name": name, "sub": info.get("belong", ""),
                      "desc": CODEX_ORG_DESC.get(name, ""), "fields": fields, "links": []})
    return items


def _codex_effect_label(k, v):
    """科技/建筑效果键 → 玩家可读中文（如 production 0.2 → 产能+20%）。"""
    from ui.panels_economy import _TECH_EFFECT_LABELS
    label = _TECH_EFFECT_LABELS.get(str(k), str(k))
    if isinstance(v, (int, float)) and v != 0:
        pct = f"{'+' if v > 0 else ''}{int(v * 100)}%" if abs(v) < 2 else f"{'+' if v > 0 else ''}{v}"
        return f"{label}{pct}"
    return f"{label}{v}"


def _build_tech():
    """科技：TECH_NODES 45 节点 + A14 注记 + 科技→兵种关联（BRANCH_TECH_GATE）。"""
    from content.data import TECH_NODES
    from content.codex_text import CODEX_TECH_NOTE, CODEX_TECH_OVERVIEW
    _era_name = {0: "初代", 1: "二代", 2: "三代", 3: "四代", 4: "五代", 5: "六代", 6: "七代"}
    items = [{"key": "overview", "name": "科技总览", "sub": "概览",
              "desc": CODEX_TECH_OVERVIEW, "fields": [("节点", f"{len(TECH_NODES)} 个")], "links": []}]
    _branch_gate = {"gunpowder": "器械兵", "archery": "弓弩兵", "cavalry": "重骑兵"}
    for t in TECH_NODES:
        nid, line, era, name, desc, prereq, _thr, gates, cost, effect = t
        fields = [("门类", line), ("时代", _era_name.get(era, f"第{era + 1}代"))]
        if prereq:
            fields.append(("前置", "、".join(_tech_name(p) for p in prereq)))
        eff_txt = "、".join(_codex_effect_label(k, v) for k, v in effect.items())
        if eff_txt:
            fields.append(("效果", eff_txt))
        links = []
        for gk, gv in (gates or []):
            if gk in _branch_gate:
                links.append(("branch", _branch_gate[gk], _branch_gate[gk]))
        items.append({"key": nid, "name": name, "sub": line,
                      "desc": CODEX_TECH_NOTE.get(nid, desc), "fields": fields, "links": links})
    return items


def _build_branch():
    """兵种：BRANCH_BASE 7 类 + 装备配给 + 新兵种机制条目 + 兵种→科技关联。"""
    from content.data import BRANCH_BASE, EQUIP_STD, BRANCH_ANCHORS
    from content.codex_text import CODEX_BRANCH_DESC, CODEX_BRANCH_NEW, CODEX_EQUIP_NAME
    items = []
    for name, base in BRANCH_BASE.items():
        eq = EQUIP_STD.get(name, {}) or {}
        eq_txt = "、".join(f"{CODEX_EQUIP_NAME.get(k, k)}{int(v * 100)}%" for k, v in eq.items() if v > 0)
        fields = [("粮饷", f"月粮 {base['grain']} 石 / 月饷 {base['pay']} 贯（禁军基准）")]
        if eq_txt:
            fields.append(("配给", eq_txt))
        links = []
        if eq.get("火器", 0) > 0:
            links.append(("tech", "C1_gunpowder", _tech_name("C1_gunpowder")))
        items.append({"key": name, "name": name, "sub": "兵种",
                      "desc": CODEX_BRANCH_DESC.get(name, ""), "fields": fields, "links": links})
    items.append({
        "key": "新兵种", "name": "新兵种（自设）", "sub": "机制",
        "desc": CODEX_BRANCH_NEW,
        "fields": [("史实锚", "、".join(BRANCH_ANCHORS))],
        "links": [("tech", "C1_gunpowder", _tech_name("C1_gunpowder")),
                  ("building", "火器作坊", "火器作坊")],
    })
    return items


def _build_region():
    """区域：12 路（驻军依 ARMY_UNIT_INIT 静态）+ 外邦（EXTERNAL_FORCES 静态初值）。"""
    from content.data import PREFECTURE_LIST, ARMY_UNIT_INIT, EXTERNAL_FORCES
    from content.codex_text import CODEX_REGION_NOTE, CODEX_EXTERNAL_DESC
    items = []
    for name in PREFECTURE_LIST:
        gar = ARMY_UNIT_INIT.get(name, {}) or {}
        gar_txt = "、".join(
            f"{k} {v // 10000}万" if v >= 10000 else f"{k} {v}" for k, v in gar.items() if v > 0)
        items.append({"key": name, "name": name, "sub": "路分",
                      "desc": CODEX_REGION_NOTE.get(name, ""),
                      "fields": [("驻军", gar_txt or "—")], "links": []})
    for name, ex in EXTERNAL_FORCES.items():
        items.append({"key": name, "name": name, "sub": "外邦",
                      "desc": CODEX_EXTERNAL_DESC.get(name, ""),
                      "fields": [("国力", int(ex.get("power", 0))),
                                 ("态度", int(ex.get("attitude", 0)))], "links": []})
    return items


def _build_mechanism():
    """机制：MECHANISMS 注册表（desc 为玩家可读说明）。"""
    from core.settlement import MECHANISMS
    items = [{"key": m, "name": m, "sub": "机制槽",
              "desc": spec.get("desc", ""), "fields": [], "links": []}
             for m, spec in MECHANISMS.items()]
    return items


def _build_event():
    """事件：HISTORICAL_EVENTS 史实事件（含年份范围）+ 随机事件池。"""
    from core.events import HISTORICAL_EVENTS, RANDOM_EVENTS
    items = []
    for ev in HISTORICAL_EVENTS:
        yr = ev.get("year_range", (0, 0))
        sub = f"{yr[0]}~{yr[1]}年" if yr and yr[0] else "—"
        items.append({"key": ev.get("id", ev.get("title", "")),
                      "name": ev.get("title", ""), "sub": f"史实 · {sub}",
                      "desc": ev.get("desc", ""),
                      "fields": [("类别", ev.get("category", ""))], "links": []})
    for ev in RANDOM_EVENTS:
        items.append({"key": f"rnd_{ev.get('title', '')}", "name": ev.get("title", ""),
                      "sub": "随机", "desc": ev.get("desc", ""),
                      "fields": [("类别", ev.get("category", ""))], "links": []})
    return items


_BUILDERS = {
    "building": _build_building, "minister": _build_minister, "org": _build_org,
    "tech": _build_tech, "branch": _build_branch, "region": _build_region,
    "mechanism": _build_mechanism, "event": _build_event,
}


def get_codex_data():
    """返回 {类别key: [条目, ...]}（惰性缓存；只读，不依赖运行 state）。"""
    if not _CODEX_DATA:
        for key, builder in _BUILDERS.items():
            try:
                _CODEX_DATA[key] = builder()
            except Exception:
                _CODEX_DATA[key] = []
    return _CODEX_DATA


# ============================================================
# 图鉴面板 Mixin
# ============================================================
class PanelsCodexMixin:
    def _build_active_policies(self):
        """国策：只显示已实施的国策（从运行态读——长期机制 + 政策开关）。"""
        s = getattr(self, "state", None)
        items = []
        if s is None:
            return items
        # 长期机制（已实施/推行中的国策）
        for it in getattr(s, "longterm_effects", []) or []:
            if not isinstance(it, dict):
                continue
            name = it.get("name") or it.get("title") or "国策"
            dur = it.get("duration", 0)
            progress = it.get("progress", 100) if dur else 100
            items.append({
                "key": f"policy_{len(items)}", "name": name, "sub": "国策",
                "desc": str(it.get("desc", "") or ""),
                "fields": [("状态", "永行" if not dur else f"推行中 {progress}%")], "links": [],
            })
        # 政策开关（已实施的关键国策）
        policy_flags = [
            ("single_whip", "一条鞭法", "田赋改征折银，本色折色分流"),
            ("pay_reform", "俸禄改制", "俸禄发放改制（本色/折色/发钞）"),
        ]
        for attr, name, desc in policy_flags:
            v = getattr(s, attr, None)
            if v:
                items.append({
                    "key": f"flag_{name}", "name": name, "sub": "国策",
                    "desc": desc, "fields": [("状态", "已实施")], "links": [],
                })
        return items

    def _panel_codex(self, initial_category=None, initial_key=None):
        """图鉴（wiki）：8 类别左列表 + 右条目详情；搜索 + 关联跳转。"""
        inner = self._panel_shell("图 鉴 · 大宋典制", with_back=True)
        data = get_codex_data()
        # 国策类别为动态：只显示已实施的国策（从运行态读，非静态机制定义）
        try:
            policy = self._build_active_policies()
            data = dict(data)
            data["mechanism"] = policy
        except Exception:
            pass

        # —— 顶部：类别 tab + 搜索框 ——
        top = tk.Frame(inner, bg=PAPER)
        top.pack(fill="x", padx=10, pady=(2, 6))
        tab_frame = tk.Frame(top, bg=PAPER)
        tab_frame.pack(side="left")
        tab_btns = {}
        state = {"cat": initial_category or "building", "query": "", "sel": None}

        search_var = tk.StringVar()
        search_box = tk.Entry(top, textvariable=search_var, bg="#fffdf8", fg=INK,
                              relief="flat", font=self._font(SANS, 10), width=16,
                              insertbackground=INK, highlightthickness=1,
                              highlightbackground=BORDER)
        search_box.pack(side="right", padx=(8, 0), pady=4)
        self._label(top, "检索：", fg=DIM, bg=PAPER, font=self._font(SANS, 10)).pack(side="right")

        def _on_search(*_a):
            state["query"] = (search_var.get() or "").strip()
            _fill_list()

        search_var.trace_add("write", _on_search)
        search_box.bind("<Return>", lambda e: _fill_list())

        for key, title in _CATEGORIES:
            b = self._btn(tab_frame, title, lambda k=key: _select_category(k),
                          width=8, ghost=(key != state["cat"]))
            b.pack(side="left", padx=3)
            tab_btns[key] = b

        # —— 中部：左列表 + 右详情 ——
        main = tk.Frame(inner, bg=PAPER)
        main.pack(fill="both", expand=True, padx=10, pady=4)

        left = tk.Frame(main, bg=PAPER, width=230)
        left.pack(side="left", fill="y", padx=(0, 10))
        self._label(left, "条 目", fg=RED_D, bg=PAPER, font=self._font(KAI, 12, "bold"),
                    anchor="w").pack(fill="x", pady=(0, 2))
        list_card = self._card(left)
        list_card.pack(fill="both", expand=True)
        lb = tk.Listbox(list_card, bg=CARD, fg=INK, selectbackground=RED,
                        selectforeground="#f3e6c4", font=self._font(SANS, 11),
                        relief="flat", bd=0, highlightthickness=0)
        lb.pack(fill="both", expand=True, padx=8, pady=8)

        right = tk.Frame(main, bg=PAPER)
        right.pack(side="left", fill="both", expand=True)
        detail_card = self._card(right)
        detail_card.pack(fill="both", expand=True)
        d_title = self._title(detail_card, "请选择条目", fg=RED, bg=CARD,
                               font=self._font(KAI, 15, "bold"), anchor="center")
        d_title.pack(pady=(10, 2))
        d_sub = self._label(detail_card, "", fg=DIM, bg=CARD, font=self._font(SANS, 10),
                            anchor="center")
        d_sub.pack(pady=(0, 6))
        d_body = self._label(detail_card, "", fg=INK, bg=CARD, font=self._font(KAI, 12),
                             wraplength=520, justify="left", anchor="w")
        d_body.pack(anchor="w", padx=18, pady=4)
        d_fields = tk.Frame(detail_card, bg=CARD)
        d_fields.pack(fill="x", padx=18, pady=(2, 4))
        d_links = tk.Frame(detail_card, bg=CARD)
        d_links.pack(fill="x", padx=18, pady=(0, 10))

        def _cat_title(key):
            return next((t for k, t in _CATEGORIES if k == key), key)

        def _fill_list():
            cat = state["cat"]
            q = state["query"]
            lb.delete(0, "end")
            state["sel"] = None
            rows = []
            for e in data.get(cat, []):
                hay = f"{e['name']} {e['sub']} {e['desc']} {' '.join(str(v) for _l, v in e.get('fields', []))}"
                if q and q not in hay:
                    continue
                rows.append(e)
            for e in rows:
                lb.insert("end", f"{e['name']}　{e['sub']}")
            if rows:
                lb.selection_set(0)
                _render_entry(rows[0])
            else:
                _render_empty(f"未找到「{q}」相关条目。")

        def _render_empty(msg):
            d_title.config(text="（无条目）")
            d_sub.config(text="")
            d_body.config(text=msg)
            for w in d_fields.winfo_children():
                w.destroy()
            for w in d_links.winfo_children():
                w.destroy()

        def _render_entry(entry):
            state["sel"] = entry.get("key")
            d_title.config(text=entry.get("name", ""))
            d_sub.config(text=entry.get("sub", ""))
            d_body.config(text=entry.get("desc", "") or "（暂无说明）")
            for w in d_fields.winfo_children():
                w.destroy()
            for w in d_links.winfo_children():
                w.destroy()
            for lab, val in entry.get("fields", []):
                row = tk.Frame(d_fields, bg=CARD)
                row.pack(fill="x", pady=1)
                self._label(row, f"{lab}：", fg=RED_D, bg=CARD,
                            font=self._font(SANS, 10, "bold"), anchor="w").pack(side="left")
                self._label(row, str(val), fg=INK, bg=CARD, font=self._font(SANS, 10),
                            anchor="w").pack(side="left")
            links = entry.get("links", [])
            if links:
                self._label(d_links, "关联：", fg=RED_D, bg=CARD,
                            font=self._font(SANS, 10, "bold"), anchor="w").pack(side="left", padx=(0, 4))
                for tkey, ekey, ename in links:
                    b = self._btn(d_links, ename,
                                  lambda tk2=tkey, ek2=ekey: _jump(tk2, ek2),
                                  width=10, ghost=True)
                    b.pack(side="left", padx=3)

        def _select_category(key):
            state["cat"] = key
            for k, b in tab_btns.items():
                try:
                    b.configure(bg=(RED if k == key else CARD),
                                fg=("#f3e6c4" if k == key else RED_D),
                                relief=("sunken" if k == key else "raised"))
                except Exception:
                    pass
            _fill_list()

        def _jump(tkey, ekey):
            """关联跳转：切类别 + 定位条目 + 渲染。"""
            state["cat"] = tkey
            for k, b in tab_btns.items():
                try:
                    b.configure(bg=(RED if k == tkey else CARD),
                                fg=("#f3e6c4" if k == tkey else RED_D),
                                relief=("sunken" if k == tkey else "raised"))
                except Exception:
                    pass
            rows = list(data.get(tkey, []))
            idx = next((i for i, e in enumerate(rows) if e.get("key") == ekey), None)
            lb.delete(0, "end")
            for e in rows:
                lb.insert("end", f"{e['name']}　{e['sub']}")
            if idx is not None:
                lb.selection_clear(0, "end")
                lb.selection_set(idx)
                lb.see(idx)
                _render_entry(rows[idx])
            else:
                _render_empty(f"未找到关联条目。")

        def _on_select(event=None):
            sel = lb.curselection()
            if not sel:
                return
            rows = []
            cat = state["cat"]
            q = state["query"]
            for e in data.get(cat, []):
                if q and q not in f"{e['name']} {e['sub']} {e['desc']}":
                    continue
                rows.append(e)
            if sel[0] < len(rows):
                _render_entry(rows[sel[0]])

        lb.bind("<<ListboxSelect>>", _on_select)

        # 初始渲染
        _select_category(state["cat"])
        if initial_key:
            _jump(state["cat"], initial_key)
