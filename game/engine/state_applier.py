# -*- coding: utf-8 -*-
"""宋祚 · 世界状态应用层（engine/state_applier.py）

AI（多 Agent）返回的结构化 changes 在此统一处理：
  验证 → 多 Agent 冲突合并 → 本地 Cascade 追加 → 原子写入世界状态 → 返回叙事层素材。

铁律：AI 只通过 changes 改状态；本模块是唯一写状态的应用层入口之一；
      叙事文本（narrative）不产生任何状态变化。
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger("state_applier")

# ---------------------------------------------------------------------------
# 1. 合法路径白名单（path 前缀 + 通配）
#    世界状态 = GameState 顶层键 / prefectures[路] / factions[派系] / pops[阶层] 等。
#    此处定义**允许 AI 修改**的路径白名单（前缀匹配，* 通配路/派系/阶层名）。
# ---------------------------------------------------------------------------
VALID_PATHS: List[str] = [
    "treasury", "imperial_treasury", "granary", "prestige",
    "population_satisfaction", "art_mastery", "era_state.",
    "prefectures.*.mood", "prefectures.*.govern", "prefectures.*.unrest",
    "prefectures.*.grain", "prefectures.*.storage",
    "prefectures.*.pops.农.wealth", "prefectures.*.pops.农.grain",
    "prefectures.*.pops.士绅.wealth", "prefectures.*.pops.士绅.grain",
    "prefectures.*.pops.工匠.wealth", "prefectures.*.pops.商人.wealth",
    "prefectures.*.pops.官僚.wealth", "prefectures.*.pops.兵.wealth",
    "prefectures.*.refugees",
    "factions.*.satisfaction", "factions.*.influence",
]

# 0-1 范围字段（修改后自动 clamp [0,1]）
# T2 修复：wealth/satisfaction/influence 均非 0-1 比率（wealth 为贯、满意度 0-100），
# 原 CLAMP_01 把它们 clamp 到 1 会毁掉守恒——清空（真 0-1 字段如有再加）。
CLAMP_01_FIELDS: List[str] = []

# 非负字段（数值不能为负数）
NON_NEG_PREFIXES: List[str] = [
    "treasury", "imperial_treasury", "granary", "prefectures.*.grain",
    "prefectures.*.storage", "prefectures.*.pops.*.wealth",
    "prefectures.*.pops.*.grain",
]

# 支持的操作
OPS = ("set", "add", "mul", "remove", "push")

# 0-1 字段集合（用于 clamp）
_CLAMP_01_SET = set(CLAMP_01_FIELDS)


def _path_ok(path: str) -> bool:
    """path 是否命中白名单（前缀匹配 + * 通配）。"""
    if not isinstance(path, str) or not path:
        return False
    for pat in VALID_PATHS:
        if pat == path:
            return True
        # 前缀匹配（如 era_state. 开头）
        if pat.endswith(".") and path.startswith(pat):
            return True
        # * 通配：拆段匹配（prefectures.*.mood 匹配 prefectures.两浙路.mood）
        p_parts, w_parts = path.split("."), pat.split(".")
        if len(p_parts) != len(w_parts):
            continue
        if all(w == "*" or w == p for w, p in zip(w_parts, p_parts)):
            return True
    return False


def _is_clamp01(path: str) -> bool:
    for pat in _CLAMP_01_SET:
        if pat == path:
            return True
        p_parts, w_parts = path.split("."), pat.split(".")
        if len(p_parts) == len(w_parts) and all(
            w == "*" or w == p for w, p in zip(w_parts, p_parts)):
            return True
    return False


def _is_non_neg(path: str) -> bool:
    for pre in NON_NEG_PREFIXES:
        if pre == path or path.startswith(pre):
            return True
        p_parts, w_parts = path.split("."), pre.split(".")
        if len(p_parts) == len(w_parts) and all(
            w == "*" or w == p for w, p in zip(w_parts, p_parts)):
            return True
    return False


# ---------------------------------------------------------------------------
# 1. 验证层
# ---------------------------------------------------------------------------
def validate_changes(changes: List[dict]) -> Tuple[List[dict], List[str]]:
    """验证每条 change：
      - path ∈ 白名单
      - op ∈ OPS 枚举
      - value 类型与 op 匹配（set/add/mul 数值，remove/push 无值或任意）
      - 0-1 字段 clamp；数值非负
    返回 (合法列表, 错误列表)。验证失败的错误收集返回调用方（供 AI 重试）。
    """
    valid: List[dict] = []
    errors: List[str] = []
    for i, ch in enumerate(changes):
        if not isinstance(ch, dict):
            errors.append(f"change[{i}] 非对象")
            continue
        path = ch.get("path")
        op = ch.get("op")
        value = ch.get("value")
        reason = ch.get("reason", "")
        if not _path_ok(path):
            errors.append(f"change[{i}] path 非法: {path!r}（不在白名单）")
            continue
        if op not in OPS:
            errors.append(f"change[{i}] op 非法: {op!r}（应为 {OPS}）")
            continue
        if op in ("set", "add", "mul"):
            if not isinstance(value, (int, float)):
                errors.append(f"change[{i}] {op} 需要数值 value: {value!r}")
                continue
            if _is_non_neg(path) and op == "set" and value < 0:
                errors.append(f"change[{i}] {path} 不能为负: {value}")
                continue
            if _is_clamp01(path):
                value = max(0.0, min(1.0, float(value)))
            ch = dict(ch)
            ch["value"] = value
        elif op == "remove" and value is not None:
            errors.append(f"change[{i}] remove 不应带 value")
            continue
        # 强制 reason（因果说明）
        if not reason or not str(reason).strip():
            errors.append(f"change[{i}] 缺少 reason 因果说明")
            continue
        valid.append(ch)
    return valid, errors


# ---------------------------------------------------------------------------
# 2. 多 Agent 冲突合并
# ---------------------------------------------------------------------------
def merge_changes(all_agent_changes: List[Tuple[str, List[dict]]]) -> List[dict]:
    """合并多 Agent 的 changes：
      - 按 path 分组
      - 同一 path 多个 add → 累加
      - 同一 path 有 set 又有 add → 先 set 再 add
      - 记录合并日志
    输入：[(agent, changes), ...]；输出：合并后的 changes 列表（已排序）。
    """
    grouped: Dict[str, List[dict]] = {}
    merge_log: List[str] = []
    for agent, changes in all_agent_changes:
        for ch in changes:
            path = ch["path"]
            # 记录来源 agent
            ch = dict(ch, source_agent=agent)
            grouped.setdefault(path, []).append(ch)

    merged: List[dict] = []
    for path, items in grouped.items():
        sets = [i for i in items if i["op"] == "set"]
        adds = [i for i in items if i["op"] == "add"]
        muls = [i for i in items if i["op"] == "mul"]
        others = [i for i in items if i["op"] in ("remove", "push")]
        if sets and adds:
            merge_log.append(f"{path}: set({sets[-1]['value']}) 后 add 累加 "
                             f"({sum(a['value'] for a in adds)})")
        if sets:
            merged.append(dict(sets[-1]))  # 先 set（多 set 取最后一个）
        if adds:
            merged.append({
                "path": path, "op": "add",
                "value": sum(a["value"] for a in adds),
                "reason": "；".join(f"[{a.get('source_agent','')}]{a.get('reason','')}"
                                    for a in adds) or f"{len(adds)} 个 Agent 累加",
                "source_agent": "merge",
            })
        if muls:
            # 多个 mul 相乘
            prod = 1.0
            for m in muls:
                prod *= m["value"]
            merged.append({
                "path": path, "op": "mul", "value": prod,
                "reason": f"{len(muls)} 个 Agent 连乘",
                "source_agent": "merge",
            })
        for o in others:
            merged.append(o)
    if merge_log:
        log.info("合并日志: %s", " | ".join(merge_log))
    return merged


# ---------------------------------------------------------------------------
# 3. 本地 Cascade 规则（可配置函数映射，不硬编码）
#    path 模式 → 级联函数(state, merged_change) -> [额外 changes]
# ---------------------------------------------------------------------------
CASCADE_RULES: Dict[str, Callable] = {}


def cascade_rule(pattern: str):
    """装饰器：注册 cascade 规则（path 模式匹配）。"""
    def deco(fn: Callable):
        CASCADE_RULES[pattern] = fn
        return fn
    return deco


@cascade_rule("factions.*.power")
def _cascade_faction_power(state, ch):
    """派系 power 变化 → 自动反向调整对立派系 power（此项目用 influence 近似）。"""
    parts = ch["path"].split(".")
    faction = parts[1]
    delta = ch["value"] if ch["op"] == "add" else 0
    if not delta:
        return []
    out = []
    for other in getattr(state, "factions", {}):
        if other != faction:
            # 对立派系反向：delta * -0.3
            out.append({
                "path": f"factions.{other}.influence",
                "op": "add", "value": round(-delta * 0.3, 4),
                "reason": f"cascade: {faction} power 变化反作用于 {other}",
                "source_agent": "cascade",
            })
    return out


@cascade_rule("prefectures.*.pops.农.wealth")
def _cascade_farmer_wealth(state, ch):
    """农 wealth 变化 → 微调役钱可征（tax_compliance 近似：0-1 clamp）。"""
    return []  # 占位：可扩展


def _resolve_path_value(state, path: str):
    """按 path 解析状态中的当前值（* 通配返回 None 表示多目标）。"""
    if "." not in path:
        return getattr(state, path, None)
    parts = path.split(".")
    if parts[0] == "prefectures":
        road = parts[1]
        if road == "*":
            return None
        p = state.prefectures.get(road)
        if p is None:
            return None
        cur: Any = p
        for seg in parts[2:]:
            if isinstance(cur, dict):
                cur = cur.get(seg)
            else:
                return None
        return cur
    if parts[0] == "factions":
        fac = parts[1]
        if fac == "*":
            return None
        f = getattr(state, "factions", {}).get(fac)
        if f is None:
            return None
        cur = f
        for seg in parts[2:]:
            if isinstance(cur, dict):
                cur = cur.get(seg)
            else:
                return None
        return cur
    return None


def apply_cascade(state, merged_changes: List[dict]) -> List[dict]:
    """AI changes 合并后，运行本地 cascade 规则，追加额外 changes。"""
    extra: List[dict] = []
    for ch in merged_changes:
        for pattern, fn in CASCADE_RULES.items():
            p_parts, w_parts = ch["path"].split("."), pattern.split(".")
            if len(p_parts) == len(w_parts) and all(
                w == "*" or w == p for w, p in zip(w_parts, p_parts)):
                try:
                    extra.extend(fn(state, ch) or [])
                except Exception as e:  # noqa: BLE001
                    log.warning("cascade %s 失败: %s", pattern, e)
    return extra


# ---------------------------------------------------------------------------
# 3.5 守恒校验（来源=去向，不凭空造灭）
# ---------------------------------------------------------------------------
# 守恒分组：钱组 / 粮组（AI changes 的钱粮变动必须组内 ΣΔ==0）
# T2：补 官僚/兵（俸禄接收方）——俸禄/俸给变动需同组成对
MONEY_PATHS = [
    "treasury", "imperial_treasury",
    "prefectures.*.pops.农.wealth", "prefectures.*.pops.士绅.wealth",
    "prefectures.*.pops.工匠.wealth", "prefectures.*.pops.商人.wealth",
    "prefectures.*.pops.官僚.wealth", "prefectures.*.pops.兵.wealth",
]
GRAIN_PATHS = [
    "granary",
    "prefectures.*.grain", "prefectures.*.storage",
    "prefectures.*.pops.农.grain", "prefectures.*.pops.士绅.grain",
]
# 豁免字段（状态类，无守恒约束，只 clamp/非负）
NO_CONSERVATION_PATHS = [
    "prefectures.*.mood", "prefectures.*.govern", "prefectures.*.unrest",
    "prestige", "era_state.", "art_mastery", "population_satisfaction",
]


def _match_pattern(path: str, pattern: str) -> bool:
    """path 是否匹配模式（前缀 / * 通配）。"""
    if pattern == path:
        return True
    if pattern.endswith(".") and path.startswith(pattern):
        return True
    p_parts, w_parts = path.split("."), pattern.split(".")
    if len(p_parts) == len(w_parts) and all(
        w == "*" or w == p for w, p in zip(w_parts, p_parts)):
        return True
    return False


def _group_of(path: str) -> Optional[str]:
    """返回 path 所属守恒组（money/grain/None 豁免）。"""
    for p in MONEY_PATHS:
        if _match_pattern(path, p):
            return "money"
    for p in GRAIN_PATHS:
        if _match_pattern(path, p):
            return "grain"
    return None


def _delta_of(ch: dict) -> float:
    """change 的数值变动（set: value；add/mul: value；remove: 现值清零需查 state）。"""
    op, value = ch.get("op"), ch.get("value")
    if op == "set":
        return float(value)
    if op == "add":
        return float(value)
    if op == "mul":
        return float(value)  # mul 无法精确 Σ，按 value 记录（调用方按需处理）
    if op == "remove":
        return -1e9  # 标记：remove 不参与守恒（视为移除，需 reason）
    return 0.0


def validate_conservation(changes: List[dict]) -> Tuple[bool, List[str]]:
    """分组守恒校验：钱组/粮组内 ΣΔ == 0（来源=去向，不凭空造灭）。

    T2（蔡权衡复核）：
      - 守恒组路径禁止 set/mul/remove（目标值非增量/依赖现值/凭空清零无法守恒校验）
        → 拒绝并提示用 add 成对变更；set/mul 仅限豁免字段；
      - 错误可读：附 path/reason 明细（如「money 组守恒失败 ΣΔ=-40000：
        treasury 军饷(-40000) 缺来源——请补充成对变更（reason: 税征/俸给划转）」）。
    返回 (通过, 错误列表)。失败的错误返回调用方供 AI 重试。
    """
    groups = {"money": [], "grain": []}
    errors: List[str] = []
    for ch in changes:
        path = ch.get("path", "")
        grp = _group_of(path)
        if grp is None:
            continue  # 豁免字段
        op = ch.get("op")
        # T2：守恒组路径只允许 add（成对变更）；set/mul/remove 拒绝
        if op != "add":
            errors.append(
                f"{grp} 组路径 {path} 禁止 {op}（守恒路径须用 add 成对变更，"
                f"请补来源/去向，reason: 税征/俸给划转）")
            continue
        groups[grp].append(ch)
    for grp, chs in groups.items():
        total = sum(_delta_of(c) for c in chs)
        if abs(total) > 1:  # 容差 ±1（int 截断）
            detail = "，".join(
                f"{c['path']} {c.get('reason','')[:8]}({_delta_of(c):+.0f})" for c in chs[:4])
            errors.append(
                f"{grp} 组守恒失败 ΣΔ={total:+.0f}：{detail} 缺来源——"
                f"请补充成对变更（reason: 税征/俸给划转）")
    return not errors, errors


# reason 驱动的补记账规则（AI 常报单边变更 → 按 reason 补来源/去向）
# T2 扩展（蔡权衡复核）：
#   - 役钱 → 农减；田赋折色 → 农/士绅减；俸禄/俸给 → 官僚/兵减（接收方入组）；
#   - 酒课 → 工匠/商人减；
#   - 岁币/销币 → 豁免（外部销币，非组内来源）；和籴/赈济 → 跨组豁免（reason 含"转换"）；
#   - 抄没田 → 官田加（grain 组）。
# 补记账 fix 的 path 含 `*` 通配——由 _expand_wildcards 在写入前统一展开（T2 P0 修复）。
CASCADE_REASON_FIX = [
    # ---- 粮组（抄没田 → 官田加）——**置于「抄没」之前**（reason「抄没田」含「抄没」，须先精确匹配）----
    ("抄没田", lambda ch: {
        "path": "prefectures.*.storage", "op": "add",
        "value": -float(ch.get("value", 0)), "reason": "cascade: 抄没田入官田（grain 组）",
        "source_agent": "cascade"}),
    # ---- 钱组（来源补记）----
    ("抄没", lambda ch: {
        "path": "prefectures.*.pops.士绅.wealth", "op": "add",
        "value": -float(ch.get("value", 0)), "reason": "cascade: 抄没补来源",
        "source_agent": "cascade"}),
    ("市舶税", lambda ch: {
        "path": "prefectures.*.pops.商人.wealth", "op": "add",
        "value": -float(ch.get("value", 0)), "reason": "cascade: 市舶税补来源",
        "source_agent": "cascade"}),
    ("发内帑", lambda ch: {
        "path": "imperial_treasury", "op": "add",
        "value": -float(ch.get("value", 0)), "reason": "cascade: 发内帑补来源",
        "source_agent": "cascade"}),
    ("商税", lambda ch: {
        "path": "prefectures.*.pops.商人.wealth", "op": "add",
        "value": -float(ch.get("value", 0)), "reason": "cascade: 商税补来源",
        "source_agent": "cascade"}),
    ("役钱", lambda ch: {
        "path": "prefectures.*.pops.农.wealth", "op": "add",
        "value": -float(ch.get("value", 0)), "reason": "cascade: 役钱补来源（农）",
        "source_agent": "cascade"}),
    ("田赋", lambda ch: {
        "path": "prefectures.*.pops.农.wealth", "op": "add",
        "value": -float(ch.get("value", 0)) * 0.6, "reason": "cascade: 田赋折色补来源（农）",
        "source_agent": "cascade"}),
    ("俸禄", lambda ch: {
        "path": "prefectures.*.pops.官僚.wealth", "op": "add",
        "value": -float(ch.get("value", 0)), "reason": "cascade: 俸禄补来源（官僚）",
        "source_agent": "cascade"}),
    ("俸给", lambda ch: {
        "path": "prefectures.*.pops.兵.wealth", "op": "add",
        "value": -float(ch.get("value", 0)), "reason": "cascade: 俸给补来源（兵）",
        "source_agent": "cascade"}),
    ("酒课", lambda ch: {
        "path": "prefectures.*.pops.工匠.wealth", "op": "add",
        "value": -float(ch.get("value", 0)) * 0.6, "reason": "cascade: 酒课补来源（工匠）",
        "source_agent": "cascade"}),
    ("销币", lambda ch: {
        "path": "prefectures.*.pops.商人.wealth", "op": "add",
        "value": -float(ch.get("value", 0)), "reason": "cascade: 销币补来源（商人）",
        "source_agent": "cascade"}),
]


def _expand_wildcards(state, changes: List[dict]) -> List[dict]:
    """T2 P0 修复：把含 `*` 通配的 path 按 state 展开为具体路径（每路/每派系一条）。
    否则 _set_path 会把 `prefectures.*.pops.士绅.wealth` 当字面键写进死 dict。"""
    out: List[dict] = []
    for ch in changes:
        path = ch.get("path", "")
        if "*" not in path:
            out.append(ch)
            continue
        parts = path.split(".")
        if parts[0] == "prefectures":
            roads = list(getattr(state, "prefectures", {}).keys())
            for road in roads:
                np = ".".join(road if p == "*" else p for p in parts)
                out.append(dict(ch, path=np, reason=f"{ch.get('reason','')}（{road}）"))
        elif parts[0] == "factions":
            facs = list(getattr(state, "factions", {}).keys())
            for fac in facs:
                np = ".".join(fac if p == "*" else p for p in parts)
                out.append(dict(ch, path=np, reason=f"{ch.get('reason','')}（{fac}）"))
        else:
            out.append(ch)
    return out


def apply_conservation_fix(changes: List[dict], state=None) -> List[dict]:
    """按 reason 补记账：单边钱粮变更（组内 Σ≠0）按 reason 关键词补来源/去向。

    审查 P1-1 修复：fix 的 path 含 `*` 通配时，按 state 展开数（路数/派系数）预分摊 value，
    使 fix 总额 = 原单边变更金额（守恒闭合）。原实现 fix 用全额 value 但展开成 N 路，
    导致总额放大 N 倍、钱凭空消失 (N-1)×单笔。
    """
    extra: List[dict] = []
    for ch in changes:
        reason = str(ch.get("reason", ""))
        if not reason:
            continue
        for kw, fix_fn in CASCADE_REASON_FIX:
            if kw in reason:
                fix = fix_fn(ch)
                # 审查 P1-1 修复：通配 fix 按 state 展开数预分摊 value（守恒闭合）
                if state is not None and "*" in str(fix.get("path", "")):
                    _parts = fix["path"].split(".")
                    if _parts[0] == "prefectures":
                        _n = max(1, len(getattr(state, "prefectures", {}) or {}))
                    elif _parts[0] == "factions":
                        _n = max(1, len(getattr(state, "factions", {}) or {}))
                    else:
                        _n = 1
                    if _n > 1 and isinstance(fix.get("value"), (int, float)):
                        fix = dict(fix, value=round(fix["value"] / _n, 4))
                extra.append(fix)
                break
    return extra


# ---------------------------------------------------------------------------
# 4. 原子写入世界状态 + 变更日志
# ---------------------------------------------------------------------------
CHANGE_LOG: List[dict] = []  # 变更日志（path, old, new, reason, source_agent）


def _set_path(state, path: str, value) -> None:
    if "." not in path:
        setattr(state, path, value)
        return
    parts = path.split(".")
    cur = state
    for seg in parts[:-1]:
        if seg == "prefectures":
            cur = state.prefectures
        elif seg == "factions":
            cur = state.factions
        elif isinstance(cur, dict):
            nxt = cur.get(seg)
            if isinstance(nxt, dict):
                cur = nxt
            else:
                # 路级：prefectures[路]
                cur = state.prefectures.get(seg, {})
        else:
            cur = getattr(cur, seg, {})
    last = parts[-1]
    if isinstance(cur, dict):
        cur[last] = value
    else:
        setattr(cur, last, value)


def _apply_op(state, path: str, op: str, value) -> Any:
    """执行单个 op，返回新值。"""
    cur = _resolve_path_value(state, path)
    if op == "set":
        return value
    if op == "add":
        return (cur or 0) + value
    if op == "mul":
        return (cur or 1) * value
    if op == "remove":
        return 0
    if op == "push":
        return value
    return cur


def apply_to_state(state, final_changes: List[dict]) -> List[dict]:
    """原子写入：逐条应用 op（先 set 后 add 的顺序已在合并时保证），
    记录变更日志（path, old, new, reason, source_agent）。返回应用记录。"""
    applied: List[dict] = []
    for ch in final_changes:
        path, op = ch["path"], ch["op"]
        old = _resolve_path_value(state, path)
        new = _apply_op(state, path, op, ch.get("value"))
        if _is_clamp01(path):
            new = max(0.0, min(1.0, float(new)))
        if _is_non_neg(path) and isinstance(new, (int, float)) and new < 0:
            new = 0
        _set_path(state, path, new)
        record = {
            "path": path, "old": old, "new": new,
            "reason": ch.get("reason", ""), "source_agent": ch.get("source_agent", ""),
        }
        CHANGE_LOG.append(record)
        applied.append(record)
    return applied


# ---------------------------------------------------------------------------
# 5. 完整管道：验证 → 合并 → cascade → 写库 → 返回叙事层素材
# ---------------------------------------------------------------------------
def applier_pipeline(state, all_agent_changes: List[Tuple[str, List[dict]]],
                     narrative_hints: Optional[List[str]] = None) -> dict:
    """多 Agent changes 完整应用管道。

    返回（供叙事层）：
      {"applied": [...], "rejected": [...], "narrative_hint": "...", "errors": [...]}
    """
    # 1) 验证（逐 Agent）
    all_valid: List[Tuple[str, List[dict]]] = []
    errors: List[str] = []
    for agent, changes in all_agent_changes:
        valid, errs = validate_changes(changes)
        errors.extend(errs)
        if valid:
            all_valid.append((agent, valid))

    # 2) 冲突合并
    merged = merge_changes(all_valid)

    # 3) 本地 cascade 追加
    extra = apply_cascade(state, merged)
    if extra:
        merged = merged + extra

    # T2 P0 修复（审查 P1-1）：写入前统一展开 wildcard（prefectures.* / factions.* → 每路/每派系一条），
    # 否则 _set_path 把通配当字面键写进死 dict。
    # **必须在守恒校验之前展开**——补记账 fix 用通配路径，校验时按 1 条通过但展开成 N 路，
    # 导致钱/粮凭空消失 (N-1)×单笔金额。展开后对每条具体路径守恒校验，杜绝通配放水。
    merged = _expand_wildcards(state, merged)

    # 3.5) 守恒校验 + reason 补记账（来源=去向，不凭空造灭）——对展开后的具体路径逐条校验
    con_ok, con_errors = validate_conservation(merged)
    if not con_ok:
        # 补记账后重校验（fix 按 state 路数预分摊 value，再展开为具体路径，并入校验）
        fixes = apply_conservation_fix(merged, state)
        if fixes:
            fixes = _expand_wildcards(state, fixes)
            merged = merged + fixes
            con_ok2, con_errors2 = validate_conservation(merged)
            if con_ok2:
                con_errors = []
            else:
                errors.extend(con_errors2)
                # T2：补记账后重校验仍不闭合 → 硬拒绝（该批不落地，返回 rejected + 可读错误）
                return {
                    "applied": [],
                    "rejected": errors,
                    "narrative_hint": "",
                    "errors": errors,
                    "conservation_failed": True,
                }
        else:
            errors.extend(con_errors)
            # T2：无可补记账 fix 且守恒失败 → 硬拒绝（不再 warn-only 照常 apply）
            return {
                "applied": [],
                "rejected": errors,
                "narrative_hint": "",
                "errors": errors,
                "conservation_failed": True,
            }

    # 4) 原子写入 + 变更日志
    applied = apply_to_state(state, merged)

    # 5) 返回叙事层素材
    hint = "；".join(h for h in (narrative_hints or []) if h)
    return {
        "applied": applied,
        "rejected": errors,
        "narrative_hint": hint[:500],
        "errors": errors,
    }
