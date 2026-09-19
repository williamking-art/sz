# -*- coding: utf-8 -*-
"""宋祚 · 利益集团 ↔ POP 归属（core/faction_basis.py）—— **只读派生**

依据：POP 挂载律（《游戏机制说明》§五）＋用户定稿（2026-09）：

1. **集团不新开账本**：每个集团的势力来源必须是 POP（人口与财赋），故每个集团都声明
   自己的 `pop_basis`：哪些 POP 类（`pop_classes`）、哪些路（`routes`，None=全国）、
   哪个子池（`pool` ∈ `officials|clerks|clan`）。表在 `content/data.FACTION_POP_BASIS`。
2. **改革会改变 POP → 改变集团，也可能催生新集团**：`content/data.REFORM_POP_BASIS`
   声明每项**已实现**的改革（诏令效果键或国策 node_key）使哪些 POP 类受益/受损、
   并可能新生成哪个集团（新集团同样必须带 `pop_basis`）。
3. 本模块只读：不写 `factions` / POP / 任何存量；v2 结算据此派生满意度与影响力增量
   （受益则升、受损则降），**禁止**凭空加减。

边界：投影层（`core/situations.py`）与 `/api/readouts` 消费本模块；
算法单点在此，前端不复制。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from content.data import (
    FACTION_DISPLAY_NAMES, FACTION_KINDS, FACTION_NAMES, FACTION_POP_BASIS,
    GRAIN_CONSUME_PER_CAPITA, PREFECTURE_LIST, POP_POOLS_VALID, REFORM_POP_BASIS,
)
from core.numeric import parse_number as _num

log = logging.getLogger("faction_basis")

__all__ = [
    "POP_POOLS", "POP_CLASS_NAMES", "SUBSET_KINDS", "validate_faction_basis",
    "validate_faction_table", "resolve_faction_key", "faction_display_name",
    "basis_routes", "basis_readout", "build_faction_channels", "emerging_from_reforms",
    "FACTION_KINDS", "FACTION_DISPLAY_NAMES",
]

POP_POOLS = POP_POOLS_VALID
POP_CLASS_NAMES = tuple(GRAIN_CONSUME_PER_CAPITA)      # 6 类 POP 的权威来源
SUBSET_KINDS = ("national", "pool", "route", "pool+route", "faction")


def _prefs(state) -> Dict[str, Any]:
    p = getattr(state, "prefectures", None)
    return p if isinstance(p, dict) else {}


def validate_faction_basis(name: str, spec: Any) -> List[str]:
    """校验一条集团归属声明；返回错误清单（空 = 合法）。

    用于**新集团登记**（改革催生）与回归测试：没声明 POP 基本盘的集团不予登记，
    否则就会回到"无源影响力"的旧路（用户明确否定的做法）。
    **集团必须是某阶级（或某子池）的子集**：`subset_of ⊆ pop_classes` 且 `subset_kind` 合枚举。
    """
    errs: List[str] = []
    if not name:
        errs.append("集团名为空")
    if not isinstance(spec, dict):
        return errs + [f"{name}: 归属声明必须是 dict"]
    classes = spec.get("pop_classes")
    if not isinstance(classes, list) or not classes:
        errs.append(f"{name}: 必须声明 pop_classes（POP 基本盘）")
    else:
        for c in classes:
            if c not in POP_CLASS_NAMES:
                errs.append(f"{name}: 非法 POP 类 {c!r}（应为 {POP_CLASS_NAMES}）")
    pool = spec.get("pool")
    if pool is not None and pool not in POP_POOLS:
        errs.append(f"{name}: 非法子池 {pool!r}（应为 {POP_POOLS} 或 None）")
    routes = spec.get("routes")
    if routes is not None:
        if not isinstance(routes, list) or not routes:
            errs.append(f"{name}: routes 应为 None（全国）或非空路名列表")
        else:
            for r in routes:
                if r not in PREFECTURE_LIST:
                    errs.append(f"{name}: 非法路名 {r!r}")
    subset_of = spec.get("subset_of")
    kind = spec.get("subset_kind")
    if not isinstance(subset_of, list) or not subset_of:
        errs.append(f"{name}: 必须声明 subset_of（集团 ⊆ 哪个 POP 阶级）")
    elif isinstance(classes, list):
        for c in subset_of:
            if c not in POP_CLASS_NAMES:
                errs.append(f"{name}: subset_of 含非法 POP 类 {c!r}")
            elif c not in classes:
                errs.append(f"{name}: subset_of {c!r} 不在 pop_classes 内（集团只能是其阶级的子集）")
    if kind not in SUBSET_KINDS:
        errs.append(f"{name}: subset_kind 应为 {SUBSET_KINDS}，得到 {kind!r}")
    elif isinstance(subset_of, list) and subset_of:
        # **组合校验**（2026-09-19 测试项审查补充）：subset_kind 必须与实际字段一致，
        # 否则会出现"声明为 pool 子集却没有 pool"这类**语义空洞**——展示时无法判定
        # 它究竟取了哪一部分，等于把"子集"退化回"整个阶级"（也就是本次要修的旧毛病）。
        has_pool = bool(pool)
        has_routes = bool(routes)
        if kind == "faction":
            # 立场切片：不得再按地域（routes 必须为 None）。
            # 注意：**不得提前 return** —— 后面还有元数据校验（kind/aliases/…）要跑。
            if has_routes:
                errs.append(f"{name}: subset_kind='faction' 不得再按地域切（routes 必须为 None）")
        else:
            want = {"national": (False, False), "pool": (True, False),
                    "route": (False, True), "pool+route": (True, True)}[kind]
            if (has_pool, has_routes) != want:
                errs.append(
                    f"{name}: subset_kind={kind!r} 要求 pool={want[0]} / routes={want[1]}，"
                    f"实际 pool={has_pool} / routes={has_routes}")
    # ---- 集团模型元数据（2026-09-19 方案第 1 步）----
    # 均为**可选**：提供则强校验，缺失不报错——以保证既有集团与改革催生集团的
    # 登记行为不变（本步只加元数据与校验，不改任何结算读写）。
    kind = spec.get("kind")
    if kind is not None and kind not in FACTION_KINDS:
        errs.append(f"{name}: 非法 kind {kind!r}（应为 {FACTION_KINDS}）")
    aliases = spec.get("aliases")
    if aliases is not None:
        if not isinstance(aliases, list) or not aliases:
            errs.append(f"{name}: aliases 应为非空字符串列表")
        else:
            seen_alias = set()
            for a in aliases:
                if not isinstance(a, str) or not a.strip():
                    errs.append(f"{name}: alias 必须是非空字符串，得到 {a!r}")
                elif a in seen_alias:
                    errs.append(f"{name}: alias 重复 {a!r}")
                else:
                    seen_alias.add(a)
    interests = spec.get("interests")
    if interests is not None:
        if not isinstance(interests, list):
            errs.append(f"{name}: interests 应为列表")
        else:
            for i, it in enumerate(interests):
                if not isinstance(it, dict):
                    errs.append(f"{name}: interests[{i}] 必须是 dict")
                    continue
                if it.get("pop_class") not in POP_CLASS_NAMES:
                    errs.append(f"{name}: interests[{i}] 非法 pop_class "
                                f"{it.get('pop_class')!r}")
                if not str(it.get("topic") or "").strip():
                    errs.append(f"{name}: interests[{i}] 缺 topic")
                d = it.get("direction")
                if isinstance(d, bool) or not isinstance(d, (int, float)) or d == 0:
                    errs.append(f"{name}: interests[{i}] direction 应为非零数值"
                                f"（+1 支持 / −1 反对），得到 {d!r}")
    red_lines = spec.get("red_lines")
    if red_lines is not None and (not isinstance(red_lines, list) or any(
            not isinstance(x, str) or not x.strip() for x in red_lines)):
        errs.append(f"{name}: red_lines 应为字符串列表（允许空列表）")
    subs = spec.get("subchannels")
    if subs is not None:
        if not isinstance(subs, list):
            errs.append(f"{name}: subchannels 应为列表")
        else:
            for i, sc in enumerate(subs):
                if not isinstance(sc, dict):
                    errs.append(f"{name}: subchannels[{i}] 必须是 dict")
                    continue
                if not str(sc.get("name") or "").strip():
                    errs.append(f"{name}: subchannels[{i}] 缺 name")
                pc = sc.get("pop_class")
                if pc not in POP_CLASS_NAMES:
                    errs.append(f"{name}: subchannels[{i}] 非法 pop_class {pc!r}")
                elif isinstance(classes, list) and pc not in classes:
                    errs.append(f"{name}: subchannels[{i}] 的 pop_class {pc!r} "
                                f"不在 pop_classes 内（子通道必须落在本集团基本盘）")
    th = spec.get("thresholds")
    if th is not None:
        if not isinstance(th, dict):
            errs.append(f"{name}: thresholds 应为 dict")
        else:
            share = th.get("population_share")
            if share is not None and (isinstance(share, bool)
                                      or not isinstance(share, (int, float))
                                      or not (0 <= share <= 1)):
                errs.append(f"{name}: thresholds.population_share 应为 0–1 数值")
            for k in ("cohesion", "exposure_months"):
                v = th.get(k)
                if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))
                                      or v < 0):
                    errs.append(f"{name}: thresholds.{k} 应为非负数值")
    overlaps = spec.get("overlaps")
    if overlaps is not None and (not isinstance(overlaps, list) or any(
            not isinstance(x, str) or not x.strip() for x in overlaps)):
        errs.append(f"{name}: overlaps 应为字符串列表（允许空列表）")

    return errs


def validate_faction_table(table: Any = None) -> List[str]:
    """**全局**校验集团表：逐条 pop_basis + 别名唯一 + 重叠指向存在。

    `validate_faction_basis` 只能看**单条**，发现不了“两个集团抢同一个别名”与
    “overlaps 指向未登记集团”这类**跨条**错误；而它们会让 `resolve_faction_key` 归一出错、
    关系图画出悬空边，故单列此全局校验（只读，不写状态）。
    """
    tbl = FACTION_POP_BASIS if table is None else table
    errs: List[str] = []
    if not isinstance(tbl, dict):
        return ["集团表必须是 dict"]
    keys = [k for k in tbl if isinstance(k, str)]
    key_set = set(keys)
    owner: Dict[str, str] = {}
    for name in keys:
        spec = tbl.get(name)
        errs.extend(validate_faction_basis(name, spec))
        if not isinstance(spec, dict):
            continue
        for alias in (spec.get("aliases") or []):
            if not isinstance(alias, str):
                continue
            if alias in key_set:
                errs.append(f"{name}: alias {alias!r} 与已登记的集团键冲突")
            elif alias in owner and owner[alias] != name:
                errs.append(f"{name}: alias {alias!r} 与 {owner[alias]!r} 的别名冲突")
            else:
                owner[alias] = name
    for name in keys:
        spec = tbl.get(name)
        if not isinstance(spec, dict):
            continue
        for other in (spec.get("overlaps") or []):
            if other == name:
                errs.append(f"{name}: overlaps 不得自指")
            elif other not in key_set:
                errs.append(f"{name}: overlaps 指向未登记的集团 {other!r}")
    return errs


def resolve_faction_key(name: Any, table: Any = None) -> Optional[str]:
    """把 **权威键 / 显示名 / 旧名 / 内部 ID** 归一到权威键；未登记返回 None。

    用途（方案第 4 步铺路）：AI/前端/存档迁移把任意历史写法解析到同一集团，
    避免“两个名字两个集团”的静默分叉。**只读**，不写任何状态。
    """
    tbl = FACTION_POP_BASIS if table is None else table
    if not isinstance(tbl, dict) or not isinstance(name, str):
        return None
    if name in tbl:
        return name
    for key, spec in tbl.items():
        if isinstance(spec, dict) and name in (spec.get("aliases") or []):
            return key
    for key, disp in FACTION_DISPLAY_NAMES.items():   # 推荐显示名也可解析
        if disp == name:
            return key
    return None


def faction_display_name(name: Any) -> str:
    """权威键 → 推荐显示名（未登记时原样返回，绝不编造）。"""
    key = resolve_faction_key(name)
    if key is None:
        return str(name or "")
    return FACTION_DISPLAY_NAMES.get(key, key)


def basis_routes(spec: Dict[str, Any]) -> List[str]:
    """该集团基本盘覆盖的路（None → 全部 20 路）。"""
    routes = (spec or {}).get("routes")
    if not routes:
        return list(PREFECTURE_LIST)
    return [r for r in routes if r in PREFECTURE_LIST]


def basis_readout(state: Dict[str, Any], spec: Dict[str, Any],
                  name: Optional[str] = None) -> Dict[str, Any]:
    """基本盘 POP 的**只读**读数：**子集**规模 / 母集规模 / 占比 / 心气。

    集团不是与 POP 并列的实体，而是**某阶级（或某子池、某路域）的子集**——故返回值
    同时给出 `parent_*`（母集）与 `share`（占母集比例），并附一句中文 `subset_note`，
    面板/AI 据此写成"西军集团＝兵 POP 的路域子集，占全国兵额 X%"，不得并列展示。
    全部取自既有字段，不重算算法、不写 state。
    """
    prefs = _prefs(state)
    routes = basis_routes(spec)
    classes = list((spec or {}).get("pop_classes") or [])
    subset_of = list((spec or {}).get("subset_of") or classes)
    pool = (spec or {}).get("pool")

    def _sum(route_list: List[str], cls_list: List[str], pool_key: Optional[str]) -> int:
        total = 0
        for route in route_list:
            p = prefs.get(route)
            if not isinstance(p, dict):
                continue
            pops = p.get("pops") or {}
            if not isinstance(pops, dict):
                continue
            for cls in cls_list:
                pop = pops.get(cls)
                if not isinstance(pop, dict):
                    continue
                total += max(0, int(_num(pop.get(pool_key) if pool_key else pop.get("size"))))
        return total

    pop_size = _sum(routes, classes, None)
    pool_size = _sum(routes, classes, pool) if pool else pop_size
    # 立场切片（subset_kind="faction"）：人数由**立场占比**算，
    # 委托给单一权威 `core.faction_metrics.faction_slice`（不另写一套算法）。
    if str((spec or {}).get("subset_kind")) == "faction":
        try:
            from core.faction_metrics import faction_slice as _fslice
            pop_size = pool_size = _fslice(state, spec, name or "")["population"]
        except Exception as e:  # noqa: BLE001
            log.warning("basis_readout 立场切片失败：%s", e)
    # 母集（该集团所归属的 POP 阶级 / 子池）在全国的规模
    parent_pop = _sum(list(PREFECTURE_LIST), subset_of, None)
    parent_total = _sum(list(PREFECTURE_LIST), subset_of, pool) if pool else parent_pop
    share = round(pool_size / parent_total, 4) if parent_total > 0 else None

    troops = 0
    morale_w = 0.0
    if "兵" in classes:
        for u in (getattr(state, "army_units", None) or []):
            if getattr(u, "station", None) in routes:
                t = max(0, int(getattr(u, "troops", 0) or 0))
                troops += t
                morale_w += _num(getattr(u, "morale", 0)) * t

    support: List[float] = []
    gentry: List[float] = []
    for route in routes:
        p = prefs.get(route)
        if not isinstance(p, dict):
            continue
        if p.get("public_support") is not None:
            support.append(_num(p.get("public_support")))
        if p.get("gentry_resistance") is not None:
            gentry.append(_num(p.get("gentry_resistance")))

    # 子集说明（展示用；路线/pool/阶级三要素齐备，避免"无源势力"的并列观感）
    where = "全国" if len(routes) >= len(PREFECTURE_LIST) else "/".join(routes)
    what = f"{'/'.join(subset_of)} POP" + (f" · {pool} 子池" if pool else "")
    subset_note = f"{name or '该集团'} ⊆ {what}（{where}）"
    if share is not None:
        subset_note += f"，占 {share * 100:.1f}%"
    if troops:
        subset_note += f"；兵额 {troops:,} 人"

    return {
        "routes": routes if len(routes) < len(PREFECTURE_LIST) else None,
        "routes_count": len(routes),
        "pop_classes": classes,
        "subset_of": subset_of,
        "subset_kind": (spec or {}).get("subset_kind"),
        "pool": pool,
        "pop_size": pop_size,
        "pool_size": pool_size,
        "parent_pop_size": parent_pop,
        "parent_total": parent_total,
        "share": share,
        "subset_note": subset_note,
        "troops": troops,
        "morale": round(morale_w / troops, 2) if troops > 0 else None,
        "public_support_avg": round(sum(support) / len(support), 1) if support else None,
        "gentry_resistance_avg": round(sum(gentry) / len(gentry), 1) if gentry else None,
    }


def emerging_from_reforms(state) -> List[Dict[str, Any]]:
    """当前**在场**的改革（在办国策 + 长期诏 + 已完成国策）→ 可能催生的新集团。

    只读扫描（不写状态）：`active_focus.node_key` / `longterm_effects[*].effects` /
    `completed_focuses[*].node_key`，命中 `REFORM_POP_BASIS` 即列出该改革的 POP 得失
    与新生集团（带 `pop_basis`，可直接交 `validate_faction_basis` 校验）。
    """
    keys: List[str] = []

    af = getattr(state, "active_focus", None)
    if isinstance(af, dict) and af.get("node_key"):
        keys.append(str(af["node_key"]))
    for item in (getattr(state, "longterm_effects", None) or []):
        if not isinstance(item, dict):
            continue
        eff = item.get("effects")
        if isinstance(eff, dict):
            keys.extend(str(k) for k in eff)
    for item in (getattr(state, "completed_focuses", None) or []):
        if isinstance(item, dict) and item.get("node_key"):
            keys.append(str(item["node_key"]))

    out: List[Dict[str, Any]] = []
    seen = set()
    for key in keys:
        spec = REFORM_POP_BASIS.get(key)
        if not spec or key in seen:
            continue
        seen.add(key)
        emergent = []
        for f in (spec.get("emergent") or []):
            basis = {k: v for k, v in f.items() if k != "name" and k != "desc"}
            emergent.append({
                "name": f.get("name"),
                "desc": f.get("desc"),
                "pop_basis": basis,
                "basis_errors": validate_faction_basis(str(f.get("name") or ""), basis),
            })
        out.append({
            "reform": key,
            "label": spec.get("label") or key,
            "gain": list(spec.get("gain") or []),
            "lose": list(spec.get("lose") or []),
            "emergent": emergent,
        })
    return out


def build_faction_channels(state) -> Dict[str, Any]:
    """集团 ↔ POP 归属的完整只读视图（供局势面板 / AI 权衡）。

    返回 `{"factions": {name: {...}}, "emerging": [...], "basis_table": {...},
    "basis_errors": [...], "declared": bool}`。
    `basis_errors` 非空表示有集团没声明（或声明非法）POP 基本盘——**必须可见**，
    否则"势力无源"的旧问题会悄悄回来。
    """
    factions = getattr(state, "factions", None) or {}
    basis_errors: List[str] = []
    # 全局校验（别名唯一 / 重叠指向）并入可见错误——“无源势力”与“悬空关系”都不得静默
    try:
        basis_errors.extend(validate_faction_table())
    except Exception as e:  # noqa: BLE001
        basis_errors.append(f"faction_table: {type(e).__name__}")
    rows: Dict[str, Any] = {}
    for name in list(FACTION_NAMES) + [n for n in factions if n not in FACTION_NAMES]:
        spec = FACTION_POP_BASIS.get(name)
        errs = validate_faction_basis(name, spec) if spec is not None else \
            [f"{name}: 未声明 POP 基本盘（REFORM 催生的新集团必须先声明 pop_basis）"]
        basis_errors.extend(errs)
        f = factions.get(name) if isinstance(factions, dict) else None
        rows[name] = {
            "influence": _num((f or {}).get("influence")) if isinstance(f, dict) else None,
            "satisfaction": _num((f or {}).get("satisfaction")) if isinstance(f, dict) else None,
            "cohesion": _num((f or {}).get("cohesion")) if isinstance(f, dict) else None,
            "leader": (f or {}).get("leader") if isinstance(f, dict) else None,
            "pop_basis": spec,
            "basis_readout": basis_readout(state, spec, name) if spec else None,
            "basis_errors": errs,
            # 方案第 1 步：下发历史化显示名与模型元数据（供面板/关系图消费）
            "display_name": faction_display_name(name),
            "kind": (spec or {}).get("kind") if isinstance(spec, dict) else None,
            "aliases": list((spec or {}).get("aliases") or []) if isinstance(spec, dict) else [],
            "interests": list((spec or {}).get("interests") or []) if isinstance(spec, dict) else [],
            "red_lines": list((spec or {}).get("red_lines") or []) if isinstance(spec, dict) else [],
            "subchannels": list((spec or {}).get("subchannels") or []) if isinstance(spec, dict) else [],
            "overlaps": list((spec or {}).get("overlaps") or []) if isinstance(spec, dict) else [],
            "thresholds": dict((spec or {}).get("thresholds") or {}) if isinstance(spec, dict) else {},
        }
    try:
        emerging = emerging_from_reforms(state)
    except Exception as e:  # noqa: BLE001  只读派生失败不得中断面板
        log.warning("faction_basis 推导在场改革失败：%s", e)
        emerging = []
    return {
        "factions": rows,
        "emerging": emerging,
        "basis_table": FACTION_POP_BASIS,
        "display_names": FACTION_DISPLAY_NAMES,
        "basis_errors": basis_errors,
        "declared": not basis_errors,
    }
