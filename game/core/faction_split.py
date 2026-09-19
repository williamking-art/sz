# -*- coding: utf-8 -*-
"""宋祚 · 利益集团「立场占比」（core/faction_split.py）—— 给 POP 加政治派系标签

口径（2026-09-19 用户定稿）：
- **立场跟派系，不跟地域**（地域只是官僚的出身）→ 占比是**类级**，不按路分；
- 它是**比率**（Σ=1），**不是人口账本**：集团人数 = Σ_路 Σ_类 (基数人数 × split[集团])；
- 农 / 工匠**无集团** —— 沉默的多数，只经「民心」这一弱通道表达。

边界：本模块是 `state.faction_split` 的**唯一写入点**（第 2 期的人员流动 / 科举座主门生
也接在这里，负责把"人"在各派系间转移，且保持 Σ=1 不与 POP 人口账本重复）。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from content.data import FACTION_NAMES, FACTION_SPLIT_INIT
from core.numeric import parse_number as _num

log = logging.getLogger("faction_split")

__all__ = ["ensure_faction_split", "normalize_split", "validate_split", "split_of",
           "faction_of_class", "set_split", "blend_entrants", "shift_split",
           "exit_faction_members", "defect_toward_satisfaction"]

TOL = 1e-6


def normalize_split(split: Any) -> Dict[str, float]:
    """归一为 Σ=1（丢弃未知集团/非正项）；空或全非法 → {}。"""
    if not isinstance(split, dict):
        return {}
    out: Dict[str, float] = {}
    for k, v in split.items():
        if k not in FACTION_NAMES:
            continue
        f = _num(v, 0.0)
        if f > 0:
            out[k] = float(f)
    tot = sum(out.values())
    if tot <= 0:
        return {}
    return {k: v / tot for k, v in out.items()}


def validate_split(split: Any) -> List[str]:
    """校验一条占比表（结构 + Σ=1）。"""
    errs: List[str] = []
    if not isinstance(split, dict):
        return ["立场占比必须是 dict"]
    tot = 0.0
    for k, v in split.items():
        if k not in FACTION_NAMES:
            errs.append(f"未知集团 {k!r}（不在 FACTION_NAMES）")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
            errs.append(f"{k}: 占比必须是非负数值，得到 {v!r}")
        else:
            tot += float(v)
    if split and abs(tot - 1.0) > 0.01:
        errs.append(f"占比之和应为 1，得到 {tot:.4f}")
    return errs


def ensure_faction_split(state) -> int:
    """幂等补齐 `state.faction_split`（缺类 → 开局锚点；已存在 → 归一 Σ=1）。"""
    cur = getattr(state, "faction_split", None)
    if not isinstance(cur, dict):
        cur = {}
        state.faction_split = cur
    fixed = 0
    for cls, anchor in FACTION_SPLIT_INIT.items():
        got = normalize_split(cur.get(cls))
        if not got:
            cur[cls] = dict(anchor)
            fixed += 1
        else:
            cur[cls] = got
    return fixed


def split_of(state, pop_class: str) -> Dict[str, float]:
    """该 POP 类的立场占比（缺省回落开局锚点；只读）。"""
    cur = getattr(state, "faction_split", None)
    if isinstance(cur, dict):
        got = normalize_split(cur.get(pop_class))
        if got:
            return got
    return dict(FACTION_SPLIT_INIT.get(pop_class) or {})


def faction_of_class(state, pop_class: str) -> Dict[str, float]:
    """`split_of` 的别名（语义化：这个阶级的立场分布）。"""
    return split_of(state, pop_class)


def set_split(state, pop_class: str, split: Any) -> bool:
    """写入某 POP 类的立场占比（**唯一写入点**）；非法/空 → 拒绝并返回 False。"""
    errs = validate_split(split)
    if errs:
        log.warning("faction_split.set_split 拒绝 %s：%s", pop_class, errs)
        return False
    norm = normalize_split(split)
    if not norm:
        return False
    cur = getattr(state, "faction_split", None)
    if not isinstance(cur, dict):
        cur = {}
        state.faction_split = cur
    cur[pop_class] = norm
    return True

# ---------------------------------------------------------------- 二期：人员进出口流动
# 口径：**只改比率、绝不碰 POP size**（人仍在同一 POP 的 size 里）；唯一写入点仍是
# `set_split`，故 Σ=1 恒成立。基数人数（base）由调用方从 POP 现读，**不另立账本**。
def blend_entrants(state, pop_class: str, base: Any, entrants: Any) -> Dict[str, float]:
    """入口流动：把一批**已知派系归属**的新成员并入某 POP 类的立场占比（二期）。

    设现有占比 `cur`、基数人数 `base`（该类相关子池现读）、新到各派系人数 `e_f`（Σe=E）：
        new_f = (cur_f × base + e_f) / (base + E)
    `base <= 0`（空盘/旧档）→ 退化为 `entrants` 归一。返回写入后的占比；
    无新增 / 写入被拒 → 原样返回（不静默改数）。
    """
    cur = split_of(state, pop_class)
    ent: Dict[str, float] = {}
    if isinstance(entrants, dict):
        for k, v in entrants.items():
            if k not in FACTION_NAMES:
                continue
            f = _num(v, 0.0)
            if f > 0:
                ent[k] = ent.get(k, 0.0) + float(f)
    total_in = sum(ent.values())
    if total_in <= 0:
        return dict(cur)
    if not cur:
        new: Dict[str, float] = dict(ent)
    else:
        b = max(0.0, _num(base, 0.0))
        if b <= 0:
            new = dict(ent)
        else:
            den = b + total_in
            new = {k: (cur.get(k, 0.0) * b + ent.get(k, 0.0)) / den
                   for k in set(cur) | set(ent)}
    if not set_split(state, pop_class, new):
        log.warning("faction_split.blend_entrants 写入被拒：%s", pop_class)
        return dict(cur)
    return split_of(state, pop_class)


def shift_split(state, pop_class: str, src: str, dst: str, amount: Any) -> Dict[str, float]:
    """零和转移：把 `src` 的 `amount`（占比绝对量）转给 `dst`（三期「转投」单笔）。

    转出量钳到 src 现有占比（不转负）；src/dst 未登记或 amount <= 0 → 原样返回。
    """
    cur = split_of(state, pop_class)
    if src not in cur or dst not in cur or src == dst:
        return dict(cur)
    amt = _num(amount, 0.0)
    if amt <= 0:
        return dict(cur)
    amt = min(amt, cur[src])
    new = dict(cur)
    new[src] = cur[src] - amt
    new[dst] = cur[dst] + amt
    if not set_split(state, pop_class, new):
        return dict(cur)
    return split_of(state, pop_class)


def exit_faction_members(state, pop_class: str, faction: str,
                         amount: Any) -> Dict[str, float]:
    """定向退出：某派系 `amount`（占比绝对量）成员退出本类政治盘（贬谪/处死/清算）。

    退出后其余派系按剩余量**重新归一**（Σ=1）；只改比率，不动任何 POP size——
    人头侧（POP size / 子池）由官制步负责，本函数只回答「退出后该阶级的立场结构」。
    这是给 `core/events.py` 点名清算预留的接口（事件层调用即接；接口不接不生效）。
    """
    cur = split_of(state, pop_class)
    if faction not in cur:
        return dict(cur)
    amt = _num(amount, 0.0)
    if amt <= 0:
        return dict(cur)
    remain = dict(cur)
    remain[faction] = max(0.0, cur[faction] - amt)
    norm = normalize_split(remain)
    if not norm:
        return dict(cur)
    if not set_split(state, pop_class, norm):
        return dict(cur)
    return split_of(state, pop_class)


def defect_toward_satisfaction(state, satisfaction: Any, rate: float = 0.02,
                               min_gap: float = 2.0) -> Dict[str, Dict[str, float]]:
    """三期「转投」：低满意度派系成员按小比例转向满意度更高的派系。

    对每个 POP 类，按**同一快照**成对计算流量
        flow(src→dst) = rate · s_src · s_dst · max(0, sat_dst − sat_src) / 100
    再一次性写回 → 零和（Σ 占比恒 = 1），且每个 src 月流出 ≤ rate·s_src（不会转负）。
    只读 `state.factions[*].satisfaction`（由 faction_settle 派生），只写 `faction_split`。
    返回 `{pop_class: {...审计...}}`；单派系类（兵/商）无转投对象 → 跳过。
    """
    splits = getattr(state, "faction_split", None)
    if not isinstance(splits, dict) or not isinstance(satisfaction, dict):
        return {}
    out: Dict[str, Dict[str, float]] = {}
    for pop_class in list(splits.keys()):
        cur = split_of(state, pop_class)
        if len(cur) < 2:
            continue
        sat = {f: _num(satisfaction.get(f), 50.0) for f in cur}
        new = dict(cur)
        flow_total = 0.0
        for src in cur:
            for dst in cur:
                if src == dst:
                    continue
                gap = sat[dst] - sat[src]
                if gap <= min_gap:
                    continue
                amt = rate * cur[src] * cur[dst] * gap / 100.0
                if amt <= 0:
                    continue
                new[src] -= amt
                new[dst] += amt
                flow_total += amt
        if flow_total <= 0:
            continue
        new = {k: max(0.0, v) for k, v in new.items()}
        if not set_split(state, pop_class, new):
            continue
        out[pop_class] = {"moved": round(flow_total, 8)}
    return out
