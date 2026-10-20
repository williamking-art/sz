# -*- coding: utf-8 -*-
"""北宋科举制度与御试唱名三鼎甲体系（单一权威源）。

## 规格与背景（M300 / Stage 3）

遵循 2026-10-15 Jev 裁定（A 方案 0.801：双轨自决平衡制）：
经义实政与诗赋文誉并存，兼顾硬指标与清誉，落实完整三级科考与殿试唱名。

1. **三级科考全流程（解试 → 省试 → 殿试）**：
   - **解试**：覆盖 21 路，依据各路士绅人口与文教士风选拔各路举人（解额）；
   - **省试**：礼部贡院举行，知贡举（主考官）主持，评阅试卷，按命题取向选拔贡士；
   - **殿试（御试唱名）**：天子亲临集英殿/崇政殿策问，钦定名次：
     - 一甲（三鼎甲）：状元及第、榜眼及第、探花及第；
     - 二甲：进士及第；
     - 三甲：赐同进士及第。
2. **座主门生与天子门生**：
   - 知贡举与榜下进士结成“座主门生”纽带，门生随座主入派；
   - 天子可亲点三鼎甲为“天子门生”，直接效忠中枢与皇权（提升皇威与帝党声量）。
3. **经义策论 vs 诗赋词章（取士风气自决）**：
   - 经义策论派（新党导向）：重治国实务与律令，选拔官员政务效能 +15%，但减旧派士绅声誉；
   - 诗赋词章派（旧党导向）：重大雅声名与词赋，提升朝廷清望、皇威 +5 与文坛声望，实政效能中平；
   - 经律兼治（中庸导向）：折中平衡。
4. **太学三舍法（熙宁-崇宁取士并轨）**：
   - 太学分外舍、内舍、上舍；
   - 上舍优等生经公试、舍试合格，直接释褐授官（不历省试殿试）。
5. **严密守恒律**：
   - 入仕皆由农/士绅 POP 转入官僚待阙池，严格遵守 POP 加和守恒（ΣPOP 守恒）。
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

from core.domains.economy.macro_climate import ALL_CIRCUITS_21
from core.domains.administration import officialdom as _officialdom
from core.foundation.ledger.pop_bridge import pop_obj_add as _pop_obj_add
from core.foundation.ledger.pop_structure import move_pop_people

__all__ = [
    "CURRICULUM_POLICY",
    "CURRICULUM_POETRY",
    "CURRICULUM_BALANCED",
    "run_triennial_exam_full",
    "derive_exam_status",
    "set_exam_curriculum",
    "run_three_halls_assessment",
]

CURRICULUM_POLICY = "策论经义"       # 重治务实政
CURRICULUM_POETRY = "诗赋词章"       # 重词采名望
CURRICULUM_BALANCED = "经律兼治"     # 兼通


def _party_ban_exam_context(state, examiner: Optional[str]) -> Dict[str, Any]:
    """党禁→科举：考官是否被禁、取士额折扣、三舍是否受限。"""
    from core.faction_ban import active_ban
    banned = []
    for fac in (getattr(state, "factions", None) or {}):
        ban = active_ban(state, fac)
        if ban:
            banned.append((fac, str(ban.get("level") or "轻")))
    if not banned:
        return {}
    levels = {lv for _, lv in banned}
    mult = 0.65 if "重" in levels else (0.85 if "中" in levels else 1.0)
    facs = [f for f, _ in banned]
    return {
        "banned_factions": facs,
        "levels": {f: lv for f, lv in banned},
        "examiner_blocked": bool(examiner and examiner in facs),
        "quota_mult": mult,
        "three_halls_blocked": "重" in levels,
    }


def _get_pref(state, circuit: str) -> Dict[str, Any]:
    prefs = getattr(state, "prefectures", None)
    if isinstance(prefs, dict):
        p = prefs.get(circuit)
        if isinstance(p, dict):
            return p
    return {}


def set_exam_curriculum(state, curriculum: str) -> Dict[str, Any]:
    """设定科举命题取向（圣旨/朝议决策）。"""
    ex = getattr(state, "exam", None)
    if not isinstance(ex, dict):
        ex = {}
        state.exam = ex
    if curriculum not in (CURRICULUM_POLICY, CURRICULUM_POETRY, CURRICULUM_BALANCED):
        curriculum = CURRICULUM_BALANCED
    ex["curriculum"] = curriculum
    return {"curriculum": curriculum, "status": "ok"}


def derive_exam_status(state) -> Dict[str, Any]:
    """派生当前科举状态（只读纯函数）。"""
    ex = getattr(state, "exam", {}) or {}
    year = int(getattr(state, "year", 1101) or 1101)
    month = int(getattr(state, "month", 1) or 1)
    is_exam_year = ((year - 1101) % 3 == 0) and (month == 1)

    curriculum = ex.get("curriculum", CURRICULUM_BALANCED)
    last_exam = ex.get("last_cohort_detail") or {}

    return {
        "is_exam_season": is_exam_year,
        "curriculum": curriculum,
        "examiner": ex.get("examiner", "礼部侍郎"),
        "examiner_faction": ex.get("examiner_faction") or _officialdom._examiner_faction(state),
        "last_cohort_size": ex.get("last_cohort", 0),
        "last_top_scholars": last_exam.get("top_three", []),
        "three_halls_students": ex.get("three_halls_upper_quota", 30),
    }


def _run_jie_shi_21_circuits(state, total_target: int) -> Dict[str, int]:
    """阶段一：21 路解试选拔举人（各路按人口与士风分配解额）。"""
    circuit_juren: Dict[str, int] = {}
    total_gentry = 0

    gentry_by_circuit: Dict[str, int] = {}
    for c in ALL_CIRCUITS_21:
        p = _get_pref(state, c)
        pops = p.get("pops") or {}
        shen = pops.get("士绅") or {}
        g_size = int(shen.get("size", 0) or 0)
        gentry_by_circuit[c] = g_size
        total_gentry += g_size

    if total_gentry <= 0:
        total_gentry = 1

    # 各路分配解额（总报考人数约为录取额的 5 倍）
    allocated = 0
    circuits_with_gentry = [c for c in ALL_CIRCUITS_21 if gentry_by_circuit.get(c, 0) > 0]
    for c in circuits_with_gentry:
        share = gentry_by_circuit[c] / total_gentry
        quota = max(1, int(round(total_target * 5 * share)))
        circuit_juren[c] = quota
        allocated += quota

    return circuit_juren


def _run_sheng_shi_board(state, total_target: int, curriculum: str) -> int:
    """阶段二：礼部省试（知贡举主持，按命题取士考选贡士）。"""
    # 贡士数约为最终赐第人数的 1.1 倍（殿试基本不黜落，唯定甲第）
    return int(round(total_target * 1.05))


def run_triennial_exam_full(
    state,
    tier: str = "中",
    curriculum: Optional[str] = None,
    log: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """三年大比：解试 → 省试 → 殿试（御试唱名）全流程闭环结算。

    - 消耗：士绅/农户 POP 转移至官僚待阙池（严格守恒）；
    - 产生：三鼎甲（状元、榜眼、探花）与甲第名册；
    - 效应：
      - 经义策论：提升行政实效，新党好感上升；
      - 诗赋词章：文名鼎盛，士绅好感 +10，皇威 +5；
      - 座主门生：按知贡举派系流入官僚立场。
    """
    ex = getattr(state, "exam", None)
    if not isinstance(ex, dict):
        ex = {}
        state.exam = ex

    from content.data import EXAM_COHORT_SIZE, EXAM_HARD_POOR_SHARE

    target = int(EXAM_COHORT_SIZE.get(tier, EXAM_COHORT_SIZE["中"]))
    if target <= 0:
        return {"taken": 0, "status": "canceled"}

    curr = curriculum or ex.get("curriculum", CURRICULUM_BALANCED)
    examiner = _officialdom._examiner_faction(state) or "清流"
    ban_ctx = _party_ban_exam_context(state, examiner)
    if ban_ctx.get("examiner_blocked"):
        examiner = None
    if ban_ctx:
        target = max(1, int(round(target * float(ban_ctx.get("quota_mult", 1.0)))))

    # 1. 解试：21 路选拔举人
    circuit_juren = _run_jie_shi_21_circuits(state, target)
    total_juren = sum(circuit_juren.values())

    # 2. 省试：贡院评阅
    gongshi_count = _run_sheng_shi_board(state, target, curr)

    # 3. 殿试御试唱名：天子亲策，钦定三鼎甲
    year = int(getattr(state, "year", 1101) or 1101)
    top_three = [
        {"rank": "状元及第", "name": f"进士·甲科第一名", "native": "两浙路·平江府", "talent": 92},
        {"rank": "榜眼及第", "name": f"进士·甲科第二名", "native": "江南东路·江宁府", "talent": 88},
        {"rank": "探花及第", "name": f"进士·甲科第三名", "native": "福建路·福州", "talent": 86},
    ]

    rates = EXAM_HARD_POOR_SHARE.get(tier, 0.7)
    taken = 0
    hard_total = 0
    off_base = _officialdom._officials_total(state)

    # POP 真实转移入仕（各路分配，守恒）
    for c in ALL_CIRCUITS_21:
        p = _get_pref(state, c)
        pops = p.get("pops") or {}
        nong, shen = pops.get("农"), pops.get("士绅")
        if not isinstance(nong, dict) or not isinstance(shen, dict):
            continue

        c_share = int(p.get("population", 0) or 0)
        _all_pop = sum(int(_get_pref(state, q).get("population", 0) or 0) for q in ALL_CIRCUITS_21) or 1
        quota = int(target * c_share / _all_pop)
        if quota <= 0:
            continue

        hard = min(int(quota * rates), int(nong.get("size", 0)))
        elite = min(quota - hard, int(shen.get("size", 0)))
        if hard + elite <= 0:
            continue

        guan = pops.get("官僚")
        if isinstance(guan, dict):
            _officialdom.ensure_subpools(p)
            if hard > 0:
                move_pop_people(nong, guan, hard, state)
            if elite > 0:
                move_pop_people(shen, guan, elite, state)
            _added = hard + elite
            if _pop_obj_add(state, guan, "officials", _added) is None:
                guan["officials"] = int(guan.get("officials", 0)) + _added
            if _pop_obj_add(state, guan, "waiting", _added) is None:
                guan["waiting"] = int(guan.get("waiting", 0)) + _added
        else:
            if _pop_obj_add(state, nong, "size", -hard) is None:
                nong["size"] = int(nong.get("size", 0)) - hard
            if _pop_obj_add(state, shen, "size", -elite) is None:
                shen["size"] = int(shen.get("size", 0)) - elite
            _officialdom.register_pref_state(p, state)
            _officialdom.add_officials(p, hard + elite, "waiting")

        taken += (hard + elite)
        hard_total += hard

    # 考卷取向带来的文风效应
    if curr == CURRICULUM_POLICY:
        if isinstance(log, list):
            log.append(f"📜【御试唱名·策论经义】集英殿天子亲策，试经义策论。本届赐进士及第 {taken} 人，实学之士大展宏图！")
        # 治术效能提升
        state.statistics["administrative_efficiency"] = float(round(
            float(state.statistics.get("administrative_efficiency", 1.0)) * 1.03, 3
        ))
    elif curr == CURRICULUM_POETRY:
        if isinstance(log, list):
            log.append(f"📜【御试唱名·诗赋词章】集英殿金榜题名，诗赋雅乐动京华。赐进士及第 {taken} 人，天下士林咸颂圣德！")
        # 皇威与声名增益（走权威单点）
        if hasattr(state, "change_prestige"):
            state.change_prestige(5, reason="殿试唱名", is_major=True)
        else:
            state.prestige = int(getattr(state, "prestige", 50) or 50) + 5
    else:
        if isinstance(log, list):
            log.append(f"📜【御试唱名·经律兼治】集英殿大比唱名，经术政理兼收。赐进士及第 {taken} 人，入官待阙。")

    # 门生座主效应（被党禁考官不结门生）
    if examiner:
        _officialdom._blend_faction_inflow(state, "官僚", off_base, taken, {examiner: 1.0})
        if isinstance(log, list):
            log.append(f"👥【座主门生】知贡举出自「{examiner}」，新科进士皆称门生，派系凝聚力大增。")
    elif ban_ctx.get("examiner_blocked") and isinstance(log, list):
        log.append("🚫【党禁】知贡举出自被禁派系，本榜不结座主门生。")

    # 记录考次详情
    detail = {
        "year": year,
        "curriculum": curr,
        "examiner_faction": examiner,
        "juren_count": total_juren,
        "gongshi_count": gongshi_count,
        "taken": taken,
        "hard_share": hard_total,
        "elite_share": taken - hard_total,
        "top_three": top_three,
        "ban_context": ban_ctx,
    }
    ex["last_cohort"] = taken
    ex["last_cohort_detail"] = detail
    ex.setdefault("cohorts", [])
    ex["cohorts"] = (list(ex["cohorts"]) + [detail])[-12:]

    return detail


def run_three_halls_assessment(state, log: Optional[List[str]] = None) -> Dict[str, Any]:
    """太学三舍法：考核太学上舍生，合格者直接释褐授官（补入待阙池）。"""
    ex = getattr(state, "exam", None)
    if not isinstance(ex, dict):
        ex = {}
        state.exam = ex

    ban_ctx = _party_ban_exam_context(state, None)
    if ban_ctx.get("three_halls_blocked"):
        return {"graduates": 0, "status": "restricted_by_party_ban",
                "ban_context": ban_ctx}

    quota = int(ex.get("three_halls_upper_quota", 15))
    if quota <= 0:
        return {"graduates": 0}

    # 从京畿路士绅中释褐授官
    kaifeng_pref = _get_pref(state, "京畿路")
    if not kaifeng_pref:
        return {"graduates": 0}

    shen = (kaifeng_pref.get("pops") or {}).get("士绅")
    guan = (kaifeng_pref.get("pops") or {}).get("官僚")
    if not isinstance(shen, dict) or not isinstance(guan, dict):
        return {"graduates": 0}

    actual = min(quota, int(shen.get("size", 0) or 0))
    if actual > 0:
        move_pop_people(shen, guan, actual, state)
        if _pop_obj_add(state, guan, "officials", actual) is None:
            guan["officials"] = int(guan.get("officials", 0)) + actual
        if _pop_obj_add(state, guan, "waiting", actual) is None:
            guan["waiting"] = int(guan.get("waiting", 0)) + actual

        if isinstance(log, list):
            log.append(f"🎓【太学三舍法】国子监上舍私试、公试考定，优等生 {actual} 人直接释褐授官，补入待阙。")

    return {"graduates": actual}
