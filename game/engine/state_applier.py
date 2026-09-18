# -*- coding: utf-8 -*-
"""宋祚 · 世界状态应用层（engine/state_applier.py）

AI（多 Agent）返回的结构化 changes 在此统一处理：
  验证 → 多 Agent 冲突合并 → 本地 Cascade 追加 → 原子写入世界状态 → 返回叙事层素材。

铁律：AI 只通过 changes 改状态；本模块是唯一写状态的应用层入口之一；
      叙事文本（narrative）不产生任何状态变化。

通道边界（审查 P2-34 文档化）：受控写状态通道共两条，各自校验、互不调用——
  ① 本模块（applier_pipeline）：AI 契约 changes → 路径白名单 + ΣΔ 守恒 + 原子写库 + 回滚；
  ② core/free_effect.py：free_effect 契约（mode/effects/cost）与大臣自设工具
     （core/tool_registry.execute_tool）→ 字段白名单 + FREE_EFFECT_CAP + 成本成对划转。
**新增写状态能力必须二选一并复用其校验**，不得绕开另起第三套
（历史教训：平行白名单/守恒规则长期必然漂移）。
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
    # ---- 四大机制改良（legacies / focus / 地区深化）----
    "land.hidden_rate", "land.hidden_households",
    "waste_reform.active", "waste_reform.savings",
    "defense_lines.*.fortification", "defense_lines.*.garrison",
    "legacies.*.active", "legacies.*.progress",
    # 审查修复（移除死通道）：原写 "focus.*.unlocked" / "focus.*.power_level"，
    # 但 GameState 并无 `focus` 字段 —— 国策树是 state.focus_tree（「分支 → nodes →
    # 节点」嵌套，静态定义只有 power_level、无 unlocked），在办国策是
    # state.active_focus（可为 None）。该两条路径 `_locate_path` 必然失败，而本模块
    # 采用「整批回滚 + 抛异常」语义 → AI 一旦产出即连带同批合法变更一并作废。
    # 此处不再宣告不存在的能力；国策进度的 AI 写入通道待与 focus_mechanic 一并设计
    # （须先解决 active_focus 为 None 的寻址问题）。
    "prefectures.*.public_support", "prefectures.*.gentry_resistance",
    "prefectures.*.city_defense", "prefectures.*.controlled_by",
]

# 0-1 范围字段（修改后自动 clamp [0,1]）
# T2 修复：wealth/satisfaction/influence 均非 0-1 比率（wealth 为贯、满意度 0-100），
# 原 CLAMP_01 把它们 clamp 到 1 会毁掉守恒——清空（真 0-1 字段如有再加）。
# D 说明：本表当前为空 → 对应的 clamp 分支为**有意保留的空通道**（非缺陷，
# 亦非漏写）。真 0-1 字段（如 oversight）如需 AI 写入，在此登记即可自动生效。
CLAMP_01_FIELDS: List[str] = []

# 0-100 百分制字段（修改后 clamp [0,100]，set 负值直接拒绝）
# 审查 P1-4 修复：原实现仅校验「是数值」，AI 可 set population_satisfaction=-50 / 9999，
# 越界值直接进入状态并污染评价/结算。此处恢复区间校验（字段范围与 game_state 一致）。
RANGE_100_FIELDS: List[str] = [
    "prestige", "population_satisfaction", "art_mastery",
    "prefectures.*.mood", "prefectures.*.govern", "prefectures.*.unrest",
    "prefectures.*.public_support", "prefectures.*.gentry_resistance",
    "prefectures.*.city_defense",
    "factions.*.satisfaction", "factions.*.influence",
]

# 非负字段（数值不能为负数）
NON_NEG_PREFIXES: List[str] = [
    "treasury", "imperial_treasury", "granary", "prefectures.*.grain",
    "prefectures.*.storage", "prefectures.*.pops.*.wealth",
    "prefectures.*.pops.*.grain",
    # 审查 P1-4：百分制 / 规模 / 进度类字段同样非负（防 AI 写负数）
    "prestige", "population_satisfaction", "art_mastery",
    "prefectures.*.mood", "prefectures.*.govern", "prefectures.*.unrest",
    "prefectures.*.public_support", "prefectures.*.gentry_resistance",
    "prefectures.*.city_defense", "prefectures.*.refugees",
    "factions.*.satisfaction", "factions.*.influence",
    "defense_lines.*.garrison",
    "land.hidden_households",
    "waste_reform.savings",
    "legacies.*.progress",
    # D 修复：原含 "focus.*.power_level" —— focus 路径已从 VALID_PATHS 移除
    # （GameState 无 focus 字段），该条永不命中，属失效配置。
]

# 支持的操作
OPS = ("set", "add", "mul", "remove", "push")

# 0-1 / 0-100 字段集合（用于 clamp）
_CLAMP_01_SET = set(CLAMP_01_FIELDS)
_RANGE_100_SET = set(RANGE_100_FIELDS)


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


def _is_range100(path: str) -> bool:
    """path 是否 0-100 百分制字段（clamp 上限 100）。"""
    for pat in _RANGE_100_SET:
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
            elif _is_range100(path):
                # 审查 P1-4：百分制字段越界钳制（保持原 int/float 类型）
                value = max(0, min(100, value))
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


@cascade_rule("prefectures.*.pops.农.wealth")
def _cascade_farmer_wealth(state, ch):
    """农 wealth 变化 → 微调役钱可征（tax_compliance 近似：0-1 clamp）。

    占位实现（有意返回空）：保留注册点以便后续扩展；空返回不影响任何行为。
    """
    return []  # 占位：可扩展


# D 修复（删除死规则）：原注册了 `@cascade_rule("factions.*.power")`，但
#   ① `factions.*.power` 不在 VALID_PATHS（白名单只有 satisfaction/influence），
#      validate_changes 会先拒绝该路径；
#   ② FactionState 本身也没有 `power` 字段（只有 influence/satisfaction/cohesion…）。
# 故 `apply_cascade` 永不匹配到该规则（合并后的 changes 里不可能出现 factions.X.power），
# 属永不触发的死代码；且一旦被误配白名单会因寻址失败触发「整批回滚」。
# 已整体移除。def _resolve_path_value(state, path: str):
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
# 豁免字段（状态类，无守恒约束，只 clamp/非负）——保留作文档说明：
# _group_of 未命中 MONEY/GRAIN_PATHS 的路径即豁免，不再引用本常量（审查 P2：死代码消除）。
NO_CONSERVATION_PATHS = None


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
#   - 役钱 → 农减；田赋折色 → **农60%/士绅40% 减**；俸禄/俸给 → 官僚/兵减（接收方入组）；
#   - 酒课 → **工匠60%/商人40% 减**（对照 settlement_steps.py:2971 的权威口径）；
#     ⚠ 一条规则可返回 **list**（各项带 `share`）以拆分归属：按 share 归一化分配，
#       **末项吃尾差** → 逐条取整也不破 ΣΔ==0。其余条目仍返单个 dict。
#     ⚠ 百分比仅为**归属比例**：金额在消费端被 `-Δ` 精确覆盖（见 apply_conservation_fix），
#       故规则里的 `* 0.6` 之类系数只是文档性参考，**不参与计算**（曾因此被误判为守恒缺口）。
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
    ("田赋", lambda ch: [
        {"path": "prefectures.*.pops.农.wealth", "op": "add",
         "value": -float(ch.get("value", 0)) * 0.6,
         "reason": "cascade: 田赋折色补来源（农 60%）", "share": 0.6,
         "source_agent": "cascade"},
        {"path": "prefectures.*.pops.士绅.wealth", "op": "add",
         "value": -float(ch.get("value", 0)) * 0.4,
         "reason": "cascade: 田赋折色补来源（士绅 40%）", "share": 0.4,
         "source_agent": "cascade"},
    ]),
    ("俸禄", lambda ch: {
        "path": "prefectures.*.pops.官僚.wealth", "op": "add",
        "value": -float(ch.get("value", 0)), "reason": "cascade: 俸禄补来源（官僚）",
        "source_agent": "cascade"}),
    ("俸给", lambda ch: {
        "path": "prefectures.*.pops.兵.wealth", "op": "add",
        "value": -float(ch.get("value", 0)), "reason": "cascade: 俸给补来源（兵）",
        "source_agent": "cascade"}),
    ("酒课", lambda ch: [
        {"path": "prefectures.*.pops.工匠.wealth", "op": "add",
         "value": -float(ch.get("value", 0)) * 0.6,
         "reason": "cascade: 酒课补来源（工匠 60%）", "share": 0.6,
         "source_agent": "cascade"},
        {"path": "prefectures.*.pops.商人.wealth", "op": "add",
         "value": -float(ch.get("value", 0)) * 0.4,
         "reason": "cascade: 酒课补来源（商人 40%）", "share": 0.4,
         "source_agent": "cascade"},
    ]),
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
        # 审查修复：原只展开 prefectures.* / factions.*，而白名单里
        # defense_lines.*.fortification|garrison、legacies.*.active|progress 同样带通配
        # → 原样透传后 _locate_path 取不到字面键 "*" → 抛异常并**整批回滚**
        # （同批合法变更一并作废）。现统一按「前缀容器 → 展开为每个具体键一条」。
        _containers = {
            "prefectures": getattr(state, "prefectures", None),
            "factions": getattr(state, "factions", None),
            "defense_lines": getattr(state, "defense_lines", None),
            "legacies": getattr(state, "legacies", None),
        }
        _box = _containers.get(parts[0])
        if not isinstance(_box, dict):
            out.append(ch)          # 无可展开容器：原样透传，交由白名单/寻址层裁定
            continue
        for k in list(_box.keys()):
            if k == "*":
                continue
            np = ".".join(k if p == "*" else p for p in parts)
            out.append(dict(ch, path=np, reason=f"{ch.get('reason','')}（{k}）"))
    return out


def apply_conservation_fix(changes: List[dict], state=None) -> List[dict]:
    """按 reason 补记账：单边钱粮变更（组内 Σ≠0）按 reason 关键词补来源/去向。

    审查 P1-1 修复：fix 的 path 含 `*` 通配时，按 state 展开数（路数/派系数）预分摊 value，
    使 fix 总额 = 原单边变更金额（守恒闭合）。原实现 fix 用全额 value 但展开成 N 路，
    导致总额放大 N 倍、钱凭空消失 (N-1)×单笔。

    审查 P1-5 修复（重复补记）：原实现对「每一条命中关键词的 change」逐条生成反向 fix，
    当同批存在互为配对但金额不等的多条 change（或共享同一 reason 关键词）时，会重复补记、
    抹平本意净变动 / 放大来源。现改为：
      ① 按守恒组计算净缺口 ΣΔ（仅缺口组才补）；
      ② 取组内 |Δ| 最大的一条作「代表」，用其 reason 关键词选择补记路径；
      ③ 补记金额强制 = -ΣΔ（精确闭合，不再复用单条 change.value 或模板系数），
         通配路径按 state 展开数分摊，保证二次校验 ΣΔ==0。
    """
    extra: List[dict] = []
    for grp in ("money", "grain"):
        members = [ch for ch in changes if _group_of(ch.get("path", "")) == grp]
        if not members:
            continue
        total = sum(_delta_of(c) for c in members)
        if abs(total) <= 1:
            continue  # 已闭合
        # 配对识别：金额互为相反数（容差 ±1）的两条视为已配对 → 跳过补记。
        # 配对项自身对 Σ 贡献为 0，跳过不影响闭合；未配对项各补 -Δ 后 Σ 精确归零。
        paired = set()
        for i in range(len(members)):
            if i in paired:
                continue
            for j in range(i + 1, len(members)):
                if j in paired:
                    continue
                if abs(_delta_of(members[i]) + _delta_of(members[j])) <= 1:
                    paired.add(i)
                    paired.add(j)
                    break
        for idx, ch in enumerate(members):
            if idx in paired:
                continue  # 已配对的不再二次反向补记（审查 P1-5）
            reason = str(ch.get("reason", ""))
            if not reason:
                continue
            # 同 reason 可命中**组**规则（按 share 拆归属，如酒课 工匠60%/商人40%）
            _fixes = []
            for kw, fix_fn in CASCADE_REASON_FIX:
                if kw in reason:
                    _r = fix_fn({"value": ch.get("value", 0), "reason": reason})
                    if isinstance(_r, dict):
                        _fixes = [_r] if _r.get("path") else []
                    elif isinstance(_r, list):
                        _fixes = [f for f in _r if isinstance(f, dict) and f.get("path")]
                    break
            if not _fixes:
                continue
            # 金额精确 = -该条 Δ（忽略模板系数，保证二次校验 ΣΔ==0）
            _need = round(-_delta_of(ch), 4)
            _shares = [max(0.0, float(f.get("share", 0) or 0)) for f in _fixes]
            if len(_fixes) == 1 or sum(_shares) <= 0:
                _amts = [_need]
            else:
                _tot = sum(_shares)
                # 末条吃尾差 → 合计精确等于 -Δ（逐条取整也不破 ΣΔ==0）
                _amts = [round(_need * _s / _tot, 4) for _s in _shares[:-1]]
                _amts.append(round(_need - sum(_amts), 4))
            for _f, _amt in zip(_fixes, _amts):
                _f = {_k: _v for _k, _v in _f.items() if _k != "share"}
                _f["value"] = _amt
                # 通配 fix 按 state 展开数预分摊 value（展开为 N 条后总额仍 = -Δ）
                if state is not None and "*" in str(_f.get("path", "")):
                    _parts = _f["path"].split(".")
                    if _parts[0] == "prefectures":
                        _n = max(1, len(getattr(state, "prefectures", {}) or {}))
                    elif _parts[0] == "factions":
                        _n = max(1, len(getattr(state, "factions", {}) or {}))
                    else:
                        _n = 1
                    if _n > 1:
                        _f = dict(_f, value=round(_f["value"] / _n, 4))
                extra.append(_f)
    return extra


# ---------------------------------------------------------------------------
# 4. 原子写入世界状态 + 变更日志
# ---------------------------------------------------------------------------
CHANGE_LOG: List[dict] = []  # 变更日志（path, old, new, reason, source_agent）


def _locate_path(state, path: str):
    """定位 path 的最终写入容器与键。

    返回 (container, key, existed, old)：
      - 路径可写：container 为 dict 或对象，key 为键/属性名，existed 表示键是否已存在；
      - 中间层缺失（不可写）：(None, None, False, None)。

    审查 P2-6 修复：原 _set_path 对不存在的路/派系会拿一次性临时 dict 写入
    （值被丢弃却记为「已应用」）→ 审计与实态不一致。现改为显式判定不可写，
    由 apply_to_state 整批回滚并报错。
    """
    if "." not in path:
        return state, path, hasattr(state, path), getattr(state, path, None)
    parts = path.split(".")
    cur = state
    for seg in parts[:-1]:
        if isinstance(cur, dict):
            nxt = cur.get(seg)
        else:
            nxt = getattr(cur, seg, None)
        if nxt is None:
            return None, None, False, None
        cur = nxt
    last = parts[-1]
    if isinstance(cur, dict):
        return cur, last, last in cur, cur.get(last)
    return cur, last, hasattr(cur, last), getattr(cur, last, None)


def _set_path(state, path: str, value) -> None:
    """按 path 写入值；路径不可写时抛 KeyError（由 apply_to_state 整批回滚）。"""
    container, key, _existed, _old = _locate_path(state, path)
    if container is None:
        raise KeyError(f"状态路径不可写（中间层缺失）: {path}")
    if isinstance(container, dict):
        container[key] = value
    else:
        setattr(container, key, value)


_UNSET = object()


def _apply_op(state, path: str, op: str, value, cur=_UNSET) -> Any:
    """执行单个 op，返回新值。cur 可由调用方预先定位传入（避免重复解析）。"""
    if cur is _UNSET:
        cur = _resolve_path_value(state, path)
    if op == "set":
        return value
    if op == "add":
        return (cur or 0) + value
    if op == "mul":
        # 审查 P2-7：区分 None（无现值 → 乘法单位元 1）与 0（0×x == 0），
        # 原 `(cur or 1)` 把 0 当 1 造成错误放大。
        return (1.0 if cur is None else float(cur)) * value
    if op == "remove":
        return 0
    if op == "push":
        return value
    return cur


def _simulate_underflow(state, merged: List[dict]) -> List[str]:
    """穿底预检（审查 P0-6）：非负守恒路径的 add 若令终值 < 0，clamp 会截断实际增量，
    造成「配对方照常落地 + 本方被截」→ 净造币。写入前模拟终值，穿底即整单拒绝
    （返回错误清单；空 = 通过）。set 负值已在验证层拒绝；mul/remove 在守恒路径被禁。"""
    errs: List[str] = []
    net: Dict[str, float] = {}
    for ch in merged:
        path = ch.get("path", "")
        op = ch.get("op")
        # 审查修正：穿底拒绝只适用于**守恒组内**路径（钱/粮）——它们成对落地，
        # clamp 截断会使配对方净造币。非守恒字段（refugees/progress/mood 等）
        # 减少到 0 只是数值钳制，不破坏守恒，不应整单拒绝（否则赈济安置流民等被误杀）。
        if op != "add" or not _is_non_neg(path) or _group_of(path) is None:
            continue
        # 审查 P3-19：用 path in net 判定是否已初始化（原 `cur == 0.0` 在累计恰为 0 时
        # 会重复解析 base 并覆盖已有累计）。
        if path not in net:
            base = _resolve_path_value(state, path)
            if base is None:
                continue
            net[path] = float(base)
        net[path] = net[path] + float(ch.get("value", 0))
    for path, val in sorted(net.items()):
        if val < 0:
            errs.append(
                f"余额不足：{path} 变更后将穿底（{val:.0f} < 0）——"
                f"请提供足额来源（守恒拒绝，防 clamp 截断净造币）")
    return errs


def apply_to_state(state, final_changes: List[dict]) -> List[dict]:
    """原子写入：逐条应用 op（先 set 后 add 的顺序已在合并时保证），
    记录变更日志（path, old, new, reason, source_agent）。返回应用记录。

    审查 P0-1 修复（原子性/回滚）：写入前记录每条 change 的回滚点
    （container/key/旧值/键是否原存），任一条失败（路径不可写、类型异常等）
    → 逆序回滚本批已写入的全部变更后再抛出，保证「要么全落地、要么全不落地」，
    杜绝半批写入造成净造币/净造粮（守恒校验通过后写入期仍可能失败）。
    """
    applied: List[dict] = []
    undo: List[Tuple[Any, str, bool, Any]] = []
    try:
        for ch in final_changes:
            path, op = ch["path"], ch["op"]
            container, key, existed, old = _locate_path(state, path)
            if container is None:
                raise KeyError(f"状态路径不可写（中间层缺失）: {path}")
            new = _apply_op(state, path, op, ch.get("value"), old)
            if _is_clamp01(path):
                new = max(0.0, min(1.0, float(new)))
            elif _is_range100(path) and isinstance(new, (int, float)):
                new = max(0, min(100, new))
            if _is_non_neg(path) and isinstance(new, (int, float)) and new < 0:
                # 审查 P0-6：正常路径已由 _simulate_underflow 前置拒绝；此处仅防御。
                # 若仍触发说明有漏网穿底，记日志以便审计（不静默造币）。
                log.warning("apply_to_state 非负截断：%s %s→0（old=%r）", path, op, old)
                new = 0
            # 记录回滚点后写入（dict 容器写键；对象写属性）
            undo.append((container, key, existed, old))
            if isinstance(container, dict):
                container[key] = new
            else:
                setattr(container, key, new)
            applied.append({
                "path": path, "old": old, "new": new,
                "reason": ch.get("reason", ""), "source_agent": ch.get("source_agent", ""),
            })
    except Exception as e:  # noqa: BLE001
        for container, key, existed, old in reversed(undo):
            try:
                if existed:
                    if isinstance(container, dict):
                        container[key] = old
                    else:
                        setattr(container, key, old)
                elif isinstance(container, dict):
                    container.pop(key, None)
                else:
                    try:
                        delattr(container, key)
                    except AttributeError:
                        pass
            except Exception as re:  # noqa: BLE001
                log.error("回滚失败（需人工检查）：%s.%s: %s", type(container).__name__, key, re)
        log.error("apply_to_state 写入失败，已回滚 %d 条变更：%s", len(undo), e)
        raise
    # 全部成功后才写入审计日志（避免半批记录）
    CHANGE_LOG.extend(applied)
    # 审查 P2：CHANGE_LOG 是模块级全局，无限追加会膨胀（长局内存泄漏）。
    # 只保留最近 5000 条（审计用），旧的丢弃。
    if len(CHANGE_LOG) > 5000:
        del CHANGE_LOG[: len(CHANGE_LOG) - 5000]
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

    # 3.5b) 穿底预检（审查 P0-6）：add 后非负路径终值为负 → clamp 截断会净造币，
    # 故在写入前整单拒绝（守恒不闭合时同样硬拒绝，语义一致）。
    under = _simulate_underflow(state, merged)
    if under:
        errors.extend(under)
        return {
            "applied": [],
            "rejected": errors,
            "narrative_hint": "",
            "errors": errors,
            "conservation_failed": True,
        }

    # 4) 原子写入 + 变更日志
    applied = apply_to_state(state, merged)

    # 审查 P2-37 修复（diff 唤醒接线）：把本轮实际落地的变更写回 state，
    # 供下一回合 agent_router._wake_by_diff 按路径唤醒 —— 原实现只读不写
    # （_last_agent_diff 全库无写入点），导致 diff 唤醒整链失效。
    try:
        state._last_agent_diff = applied
    except Exception:  # noqa: BLE001
        pass

    # 5) 返回叙事层素材
    hint = "；".join(h for h in (narrative_hints or []) if h)
    return {
        "applied": applied,
        "rejected": errors,
        "narrative_hint": hint[:500],
        "errors": errors,
    }
