# -*- coding: utf-8 -*-
"""宋祚 · 利益集团「声量权重」（core/faction_voice.py）—— **只读**

依据（2026-09-19 用户定稿）：**官职的声量就是它的权限大小**——
官员的声量来自官职，派系的声量来自其官员；故
`派系声量 = Σ (旗下官员所任官职的权限权重)`。

链条（**单一权威，不另立机构权重表**）：
    事权（AUTHORITY_MATTERS） → 机构固有事权（central_orgs[*].authority）
      → 官职声量（org_voice） → 官员声量 → 派系声量（voice_seats/voice_share）

好处：玩家**改革官职**（改权限 / 越权授权 / 新建官职 / 裁撤机构）时，
`state.central_orgs` 一变，声量**自动跟随**，无需另接一条通道。

本模块只读，不写任何状态。
"""
from __future__ import annotations

import logging
from math import log1p as _log1p
from typing import Any, Dict, Optional, Tuple

from core.numeric import clamp as _clamp

log = logging.getLogger("faction_voice")

__all__ = ["MATTER_VOICE_WEIGHT", "DEFAULT_MATTER_WEIGHT", "VOICE_FULL", "org_voice",
           "voice_seats", "voice_norm", "voice_share", "total_voice"]

# 事权权重（史实锚点，可调）：衡量"这项权限有多大"。
# 口径：决策/军国与言路最重（一言可动朝局），财权次之，庶政再次。
MATTER_VOICE_WEIGHT: Dict[str, float] = {
    # —— 决策 / 军国（权柄最重）
    "官制": 4.0, "人事除授": 4.0, "朝政决策": 4.0,
    "调兵": 4.0, "边防": 3.5, "诏令封驳": 3.5, "政令审议": 3.0,
    "六部行政": 3.5, "政令奉行": 3.0, "禁军": 3.0,
    # —— 言路（人少声大：台谏一言重于百吏）
    "监察百官": 4.0, "言路": 3.5, "草诏": 3.0,
    # —— 财权
    "国库": 3.5, "钱粮户籍": 3.0, "赋税": 3.0, "度支调度": 3.0,
    "盐铁专营": 3.0, "财政勾稽": 2.5,
    # —— 庶政
    "官吏铨选": 3.0, "官员考课": 2.5, "科举": 2.5, "外事": 2.5,
    "武官铨选": 2.5, "军籍": 2.0, "刑狱": 2.5, "工程营造": 2.0, "礼仪": 2.0,
    # —— 近侍 / 京畿
    "内廷": 3.0, "京畿": 2.5,
    # —— 补全：机构 authority 里出现但上表未列的庶务/军务
    "军务机要": 3.0, "弹劾": 3.5, "谏诤": 3.0, "内制": 3.0,
    "禁中庶务": 2.5, "京城防务": 2.5, "北边防务": 2.5, "京城治安": 2.5,
    "律令": 2.5, "军需后勤": 2.0, "屯田": 2.0, "山泽": 2.0, "内地屯驻": 2.0,
}
DEFAULT_MATTER_WEIGHT = 1.0

#: 声量刻度：达到此绝对量视为「影响力充分」。
#: 注意声量是**绝对影响力**（可同时高/低），**不是份额**（不要求各派系相加为 100）——
#: 故本模块不做 Σ=1 归一，只用**边际递减**把它映射到 0–1 供 influence 消费。
VOICE_FULL = 50.0


def org_voice(org: Any) -> float:
    """机构声量 = Σ 其**固有事权**的权重（权限越大 → 声量越大）。

    事权取 `authority`（缺失时回落 `matter_keys`）。改制改了 `authority`，
    此处立刻反映——这正是"改革官职 → 声量挂钩"的实现点。
    """
    if not isinstance(org, dict):
        return 0.0
    matters = org.get("authority")
    if not matters:
        matters = org.get("matter_keys")
    if not isinstance(matters, (list, tuple, set)):
        return 0.0
    return sum(MATTER_VOICE_WEIGHT.get(str(m), DEFAULT_MATTER_WEIGHT) for m in matters)


def _faction_of(name: str) -> Optional[str]:
    """在任人名 → 集团（主键）；查不到/无派系 → None。"""
    if not name:
        return None
    try:
        from content.ministers.data import MINISTERS
        fig = MINISTERS.get(str(name)) or {}
        fac = fig.get("faction")
        if not fac or str(fac) in ("无", "未知"):
            return None
        return str(fac)
    except Exception as e:  # noqa: BLE001
        log.debug("faction_voice 取人物失败：%s", e)
        return None


def _orgs(state) -> Dict[str, Any]:
    orgs = getattr(state, "central_orgs", None)
    if isinstance(orgs, dict) and orgs:
        return orgs
    try:
        from content.ministers.data import CENTRAL_ORG_INFO
        return CENTRAL_ORG_INFO
    except Exception:  # noqa: BLE001
        return {}


def voice_seats(state) -> Dict[str, float]:
    """各集团声量 = Σ (其**官员个人**的声量)。只读；空 holder / 无派系不计。

    **一人一份声量（2026-09-19 修复）**：每位在任官员只按其**最高权限职位**计一次，
    兼任多个职位**不叠加**——依据用户定稿"官员的声量来自官职，派系的声量来自其官员"：
    **官员才是载体**，一个人的政治影响力不会因为多挂一个头衔而翻倍。

    原实现按"每个职位都取机构权限累加"（`Σ holder×org_voice`），会让兼任者的机构权限
    重复计入：实证 `王古` 兼 `户部·户部尚书`（19.0）与 `户部·抵当所提举`（19.0）→ 38.0，
    `曾布` 兼中书侍郎（12.0）与尚书右仆射（6.5）→ 18.5；结果中立派声量虚高到 67.0，
    把"朝堂声量最大者"判给了它（影响 `_examiner_faction` 的知贡举举荐权归属）。
    修正后：中立派 41.5 < 旧党 53.5（旧党在朝八人各领一职，声量来自**人数**，不是兼任）。

    注：**不采用**"同机构去重"口径 —— 那会同时砍掉旧党（御史台/谏院/尚书省各有两人），
    把"人多势众"这一真实政治优势抹掉；按人计权才与"官员是载体"自洽。
    """
    best: Dict[str, Tuple[float, str]] = {}      # 人名 → (最高权限, 派系)
    for org_name, o in _orgs(state).items():
        if not isinstance(o, dict) or o.get("abolished"):
            continue
        w = org_voice(o)
        if w <= 0:
            continue
        holders = o.get("holders") or {}
        if not isinstance(holders, dict):
            continue
        for _title, holder in holders.items():
            fac = _faction_of(holder)
            if not fac or not holder:
                continue
            prev = best.get(str(holder))
            if prev is None or w > prev[0]:
                best[str(holder)] = (w, fac)
    out: Dict[str, float] = {}
    for _holder, (w, fac) in best.items():
        out[fac] = out.get(fac, 0.0) + w
    return out


def total_voice(state) -> float:
    """**朝堂总声量**（宏观读数）：各派系声量之和。

    它不是"分割比"而是"朝堂被多少权柄分割"的绝对刻度——
    总声量高＝权柄分散（皇权弱），总声量低＝权柄集中于一身（皇权强）。
    """
    return sum(voice_seats(state).values())


def voice_norm(state, name: str) -> float:
    """该集团声量（**绝对影响力**）→ 0–1，用**边际递减**映射（不是份额）。

    `norm = ln(1+raw) / ln(1+VOICE_FULL)`：避免顶部堆叠，且**不与其他派系此消彼长**
    （两个派系可以同时很高）。
    """
    raw = voice_seats(state).get(name, 0.0)
    if raw <= 0:
        return 0.0
    return _clamp(_log1p(raw) / _log1p(VOICE_FULL), 0.0, 1.0)


# 兼容旧调用名（语义已改为"绝对影响力的 0–1 映射"，非份额）
def voice_share(state, name: str) -> float:
    """已改名 `voice_norm`；保留别名以便既有调用平滑迁移。"""
    return voice_norm(state, name)
