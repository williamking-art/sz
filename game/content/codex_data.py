# -*- coding: utf-8 -*-
"""宋祚 · 图鉴数据（迁移自 ui/panels_codex.py；Tk 废弃后独立成模块）。

8 类别条目构建：建筑 / 大臣 / 官职 / 科技 / 兵种 / 区域 / 国策 / 事件。
只读常量（惰性缓存），不依赖运行 state、不写状态。
"""

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
    from content.data import TECH_EFFECT_LABELS as _TECH_EFFECT_LABELS
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
