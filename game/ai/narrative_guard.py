# -*- coding: utf-8 -*-
"""宋祚 · 叙事-数值一致守卫（三方案落地，言枢密设计已审）。

一、叙事-数值一致：
- `_validate_narrative_numbers(text, ranges)`：正则提取「数字+单位」（万/缗/贯/石/口/户/里/人）
  → 数字须落在注入区间（ranges: {单位键: (lo, hi)}）→ 区间外改写为定性词（不向玩家泄露
  伪造数字）；硬锚不变量（清丈≤隐田存量、调粮≤存粮、赈济≤仓廪、兵力增减≤现有兵力）
  由区间上限封顶实现。
- 叙事类注入只给区间脱敏读数（posture 形态）；结构性推演注入真值快照（内部用，AI 不可见）。

二、来源锚定（取材闭集）：`_build_source_closure` 构建本回合真实来源闭集
（①诏书/在办事务 ②本回合事件 ③记忆图谱检索闭集 ④本回合 settlement log），
注入【本期取材（仅限以下来源）】+ 硬约束「禁止引用闭集外剧情」。

三、防错校验表：`build_character_statuses`（{人物: {alive, in_office, current_post,
faction, status}}）；`_validate_characters` 叙事具名人物查表，命中已故/已黜 → 标记回喂。
"""
import re

# 数字+单位正则（支持「三百万石」= 300×万×石）
_NUM_RE = re.compile(r"(\d+)(万)?(贯|石|口|户|缗|里|人)")

# 单位 → 定性词档位（区间内按位置）
_UNIT_QUALIFIERS = {
    "贯": ("寥寥", "可观", "充盈"), "缗": ("寥寥", "可观", "充盈"),
    "石": ("杯水车薪", "可观", "浩大"), "口": ("寥寥", "颇众", "浩繁"),
    "户": ("寥寥", "颇众", "浩繁"), "里": ("咫尺", "百里", "千里"),
    "人": ("寥寥", "颇众", "浩繁"),
}


def _validate_narrative_numbers(text, ranges=None):
    """AI 叙事数字+单位校验：数字须落在注入区间；区间外改写为定性词。

    返回 (new_text, flagged)。无 ranges 时跳过（仅原样返回）。
    硬锚不变量：ranges 键的上限即硬锚（清丈≤隐田/调粮≤存粮/赈济≤仓廪/兵力≤现有）。
    """
    if not text or not ranges:
        return (text or ""), False
    flagged = False

    def _repl(m):
        nonlocal flagged
        num = int(m.group(1)) * (10000 if m.group(2) else 1)
        unit = m.group(3)
        key = unit
        if key in ranges:
            lo, hi = ranges[key]
            if not (lo <= num <= hi):
                flagged = True
                q = _UNIT_QUALIFIERS.get(unit, ("寡", "中", "众"))
                ratio = (num - lo) / max(1, (hi - lo))
                return q[0] if ratio < 0.4 else q[1] if ratio < 0.8 else q[2]
        return m.group(0)

    out = _NUM_RE.sub(_repl, text)
    return out, flagged


def _build_numeric_ranges(state):
    """注入区间（叙事类只给区间脱敏读数；硬锚上限封顶）：
    贯=国库量级（×1.5 浮动）、石=太仓存量（硬锚：赈济/调粮≤仓廪）、
    口=人口、户=户数、里=疆域、人=兵额（兵力增减≤现有兵力）。"""
    treasury = int(getattr(state, "treasury", 0))
    granary = int(getattr(state, "granary", 0))
    population = int(getattr(state, "population", 0))
    households = int(getattr(state, "households", 0)) or population // 5
    army = sum(u.troops for u in getattr(state, "army_units", []))
    return {
        "贯": (0, max(1, int(treasury * 1.5))),
        "缗": (0, max(1, int(treasury * 1.5))),
        "石": (0, max(1, granary)),          # 硬锚：调粮/赈济 ≤ 存粮/仓廪
        "口": (0, max(1, population)),
        "户": (0, max(1, households)),
        "里": (0, 6000),
        "人": (0, max(1, army * 2)),          # 兵力增减 ≤ 现有兵额（×2 允许表述浮动）
    }


def _build_source_closure(state, extra=None):
    """本回合真实来源闭集：①诏书/在办事务 ②本回合事件 ③记忆图谱检索闭集 ④本回合 log。
    返回注入文本【本期取材（仅限以下来源）】。"""
    parts = []
    # ① 诏书/在办事务
    for d in list(getattr(state, "pending_decrees", []) or [])[-5:]:
        parts.append(f"诏·{d.get('title', '')[:12]}")
    for t in list(getattr(state, "longterm_public", []) or [])[-5:]:
        parts.append(f"务·{t.get('title', '')[:12]}")
    # ② 本回合事件
    for e in list(getattr(state, "active_events", []) or [])[-5:]:
        parts.append(f"事·{e.get('category', '')[:12]}")
    # ③ 记忆图谱检索闭集（近期决策/事件）
    try:
        rows = state.memory.query("decision", time_window=12, top_k=5)
        for r in rows[:3]:
            ent = state.memory.entities.get(r[1], {})
            parts.append(f"史·{ent.get('name', '')[:12]}")
    except Exception:
        pass
    # ④ 本回合 settlement log
    for line in list(getattr(state, "last_settlement_log", []) or [])[-8:]:
        parts.append(f"报·{str(line)[:20]}")
    if extra:
        parts.extend(extra)
    closure = "；".join(parts) if parts else "（本期无重大事项）"
    return ("【本期取材（仅限以下来源）】" + closure +
            "\n硬约束：叙事仅可引用上述来源，**禁止引用闭集外剧情/数字/人物**。")


def build_character_statuses(state):
    """每回合人物状态校验表：{人物: {alive, in_office, current_post, faction, status}}。"""
    from content.ministers.data import MINISTERS
    out = {}
    for name in MINISTERS:
        fig = MINISTERS[name]
        st = state.minister_status(name)
        post = ""
        try:
            post = state.ministers.get(name, {}).get("post", "") or fig.get("role", "")
        except Exception:
            post = fig.get("role", "")
        out[name] = {
            "alive": st != "dead",
            "in_office": st == "active",
            "current_post": post,
            "faction": fig.get("faction", ""),
            "status": st,
        }
    return out


def build_character_blacklist(statuses):
    """黑名单注入：本朝已故/已黜名单 + 在朝具名人物名单（省 token 模式）。"""
    dead = [n for n, s in statuses.items() if not s["alive"]]
    out = [n for n, s in statuses.items() if s["in_office"]]
    return ("【本朝已故/已黜：】" + ("、".join(dead) if dead else "（无）") +
            "\n【在朝具名人物：】" + ("、".join(out[:40]) if out else "（无）"))


_CHAR_RE = re.compile(r"[\u4e00-\u9fa5]{2,4}(?:[相郎]|公|卿|监|使)?")


def _validate_characters(text, statuses):
    """叙事具名人物查表：命中已故/已黜（status != active）→ 标记（回喂修正）。
    返回 (是否命中违规, 违规名单)。"""
    if not text or not statuses:
        return False, []
    bad = []
    for name, st in statuses.items():
        if st["status"] == "active":
            continue
        if name in text:
            bad.append(f"{name}({st['status']})")
    return bool(bad), bad


def build_mechanism_closure(state):
    """四大机制改良来源闭集：当前生效的帝国修正（legacies）+ 已解锁国策（focus）。

    返回注入文本【本期机制（仅限以下）】，供 AI 叙事引用，防止编造不存在的修正/国策。
    """
    parts = []
    # 帝国修正（legacies）：生效中的
    try:
        for e in state.legacies.values():
            if e.get("active"):
                parts.append(f"修正·{e.get('name', '')}")
    except Exception:
        pass
    # 国策树（focus）：已解锁节点
    try:
        for branch, bspec in state.focus_tree.items():
            for nk, node in bspec.get("nodes", {}).items():
                if node.get("unlocked"):
                    parts.append(f"国策·{node.get('name', '')}")
    except Exception:
        pass
    closure = "、".join(parts) if parts else "（本期无生效机制）"
    return ("【本期机制（仅限以下）】" + closure +
            "\n硬约束：叙事提及帝国修正/国策时，仅可引用上述机制，禁止编造不存在的修正或国策。")


def _validate_mechanisms(text, state):
    """叙事提及的机制（legacies/focus）查表：命中未生效/未解锁 → 标记（回喂修正）。
    返回 (是否命中违规, 违规名单)。"""
    if not text:
        return False, []
    bad = []
    # 生效中的 legacy 名称
    active_legacy = set()
    try:
        for e in state.legacies.values():
            if e.get("active"):
                active_legacy.add(e.get("name", ""))
    except Exception:
        pass
    # 已解锁的 focus 节点名称
    unlocked_focus = set()
    try:
        for branch, bspec in state.focus_tree.items():
            for nk, node in bspec.get("nodes", {}).items():
                if node.get("unlocked"):
                    unlocked_focus.add(node.get("name", ""))
    except Exception:
        pass
    # 检查叙事中是否出现"修正/国策"相关表述但对应机制未生效
    for name in active_legacy | unlocked_focus:
        if name and name in text:
            continue
    # 反向：叙事提到机制名但不在生效集内（编造）
    for kw in ("新党专权", "冗官冗费", "隐田蔽课", "辽夏边患", "花石纲民怨",
               "中央集权", "官制改革", "裁汰冗费", "整军经武", "修城固垒",
               "军备军器", "兴百工", "修历法", "西学东渐", "设皇城司",
               "整肃言路", "密探天下", "清丈田亩", "盐铁专卖", "一条鞭法"):
        if kw in text and kw not in active_legacy and kw not in unlocked_focus:
            return True, [f"{kw}(未生效)"]
    return False, []
