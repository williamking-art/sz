# -*- coding: utf-8 -*-
"""宋祚 · 朝局简报可行动项（程序规则生成，UI 展示层）

纯确定性规则：从 GameState 推导「陛下此刻可做之事」，无 AI、无随机。
- 用途：月报面板顶部「朝局简报」段 + 开局引导；
- 边界：只做「建议与跳转语义」，不写状态、不改数值；
- 脱敏：输出只含定性词/区间/可见数值（国库/太仓为游戏可见），
  loyalty / corruption 等隐藏数值绝不出现；
- AI 缺失不降级伪造：本模块与 AI 无关，离线同样可用。
"""
from __future__ import annotations

from typing import Any, Dict, List

from content.data import TREASURY_CRISIS_LINE

# 可行动项跳转语义（UI 层负责映射到具体面板）：
#   decree   拟旨颁布（拟诏/会签/施政）
#   audience 召对（群臣面板）
#   tech     科技树
#   army     军政机务（建新军/整军）
#   todo     在办事务
DECREE = "decree"
AUDIENCE = "audience"
TECH = "tech"
ARMY = "army"
TODO = "todo"


def _active_minister_count(state) -> int:
    """在朝可召对大臣数（未薨/未罢黜）。"""
    n = 0
    try:
        for name in state.loyalty:
            try:
                if state.minister_status(name) == "active":
                    n += 1
            except Exception:
                n += 1
    except Exception:
        # 无 loyalty 表时退回派系领袖统计
        try:
            n = len({f.get("leader") for f in state.factions.values() if f.get("leader")})
        except Exception:
            n = 0
    return n


def _min_external_attitude(state) -> int:
    """最不安定的外部政权态度（越低越敌视）；无外部则 50。"""
    best = 50
    try:
        for k, ex in state.external.items():
            att = int(ex.get("attitude", 50))
            best = min(best, att)
    except Exception:
        pass
    return best


def build_briefing_actions(state) -> List[Dict[str, Any]]:
    """从当前 GameState 确定性推导「朝局简报 · 可行动项」。

    返回按优先级排序的列表，每项：
      {key, title, desc, goto, urgent(bool)}
    - title  行动名（短）
    - desc   一句说明（定性/区间，脱敏）
    - goto   跳转语义（DECREE/AUDIENCE/TECH/ARMY/TODO）
    - urgent 是否高优（朱批急色渲染）
    """
    actions: List[Dict[str, Any]] = []
    s = state

    # —— 急务（红色高优）——
    try:
        # B3：破产判据为「累计亏空深度」（国库禁穿底，负余额不可达）
        _deficit = int(getattr(s, "treasury_deficit", 0) or 0)
        if _deficit > TREASURY_CRISIS_LINE:
            actions.append({
                "key": "treasury_crisis", "title": "库藏告急",
                "desc": "国库空虚，中外忧惧——宜开源节流，理盐铁、裁冗费。",
                "goto": DECREE, "urgent": True,
            })
    except Exception:
        pass
    try:
        if int(getattr(s, "disaster_severity", 0) or 0) > 0:
            actions.append({
                "key": "disaster", "title": "赈济灾黎",
                "desc": f"{getattr(s, 'disaster_region', '某路') or '某路'}灾情未平，"
                        "宜下诏开仓赈济、蠲免赋役。",
                "goto": DECREE, "urgent": True,
            })
    except Exception:
        pass
    try:
        if _min_external_attitude(s) < 40:
            actions.append({
                "key": "border", "title": "整饬边防",
                "desc": "四邻态度不善，边烽有警——宜备边严守、修城储粮。",
                "goto": ARMY, "urgent": True,
            })
    except Exception:
        pass
    try:
        if float(getattr(s, "population_satisfaction", 50) or 50) < 45:
            actions.append({
                "key": "mood", "title": "抚恤民情",
                "desc": "民心浮动，天下鼎沸之兆——宜宽恤民力、平抑物价。",
                "goto": DECREE, "urgent": True,
            })
    except Exception:
        pass

    # —— 常务（按优先级）——
    try:
        if len(getattr(s, "edict_drafts", []) or []) > 0:
            n = len(s.edict_drafts)
            actions.append({
                "key": "sign", "title": "御前廷议",
                "desc": f"待签诏草 {n} 道在案——宜及早会签定夺。",
                "goto": DECREE, "urgent": False,
            })
    except Exception:
        pass
    try:
        bandwidth = int(getattr(s, "decree_bandwidth", 3) or 3)
        pending = len(getattr(s, "pending_decrees", []) or [])
        if pending < bandwidth:
            actions.append({
                "key": "decree", "title": "颁行新政",
                "desc": "诏令尚有余力——可拟诏施政，抚民、理财、兴文教。",
                "goto": DECREE, "urgent": False,
            })
    except Exception:
        pass
    if _active_minister_count(s) > 0:
        actions.append({
            "key": "audience", "title": "垂询臣工",
            "desc": "朝臣在列——可召对问政，察其心迹、用其才具。",
            "goto": AUDIENCE, "urgent": False,
        })
    try:
        # 研科技：国库足以支撑最低研费即可（观念类节点近零成本）
        if getattr(s, "tech", None):
            actions.append({
                "key": "tech", "title": "格物致知",
                "desc": "匠学可进——研科技以开新技，点亮蓝图、练新军。",
                "goto": TECH, "urgent": False,
            })
    except Exception:
        pass
    try:
        if getattr(s, "army_units", None):
            actions.append({
                "key": "army", "title": "整军经武",
                "desc": "诸军在营——可募兵益军、整练新军、缮修兵甲。",
                "goto": ARMY, "urgent": False,
            })
    except Exception:
        pass
    try:
        n_todo = len(getattr(s, "longterm_public", []) or []) + \
            len(getattr(s, "longterm_secret", []) or [])
        if n_todo > 0:
            actions.append({
                "key": "todo", "title": "在办要务",
                "desc": f"诏令推行中 {n_todo} 项——宜查其进度、督其成效。",
                "goto": TODO, "urgent": False,
            })
    except Exception:
        pass

    # 稳定性兜底：极端下也保证至少一条建议（拟诏）
    if not actions:
        actions.append({
            "key": "decree", "title": "颁行新政",
            "desc": "可拟诏施政，抚民、理财、兴文教。",
            "goto": DECREE, "urgent": False,
        })
    return actions


def build_weighing_note(state) -> str:
    """**AI 权衡用的一句话**：诏令实际效果的三通道（口径单点在 `core/decree_effect.py`）。

    用户定稿（2026-09-19）：
      · **吏治是唯一强关联**（会签执行率本身即吏治的表达 ＋ 吏胥折扣）；
      · 民心 / 文书到账效率是**弱关联**（幅度小）；
      · **军队是条件加成而非必须**——只有军政/边事类诏令才吃军队督行，民政诏令与之无关。
    AI 只据此给档位与叙事，数值一律由程序算；无可用读数时对应项缺席（**不编造**）。
    """
    bits: List[str] = []
    try:
        from core.decree_effect import effect_channels
        ch = effect_channels(state)
        c = ch.get("clerks") or {}
        if ch.get("clerks_mult") is not None:
            bits.append(f"吏治（**强关联**）折扣 ×{ch['clerks_mult']:.2f}"
                        f"（吏怨 {float(c.get('grievance') or 0):.0f}、把持度 {float(c.get('grip') or 0):.2f}）")
        sup = ch.get("official_support") or {}
        if sup.get("weighted") is not None:
            bits.append(f"官场配合度代理（满意度加权 {sup['weighted']:.0f}，最低 {sup['min']:.0f}"
                        f"·{sup.get('min_faction')}）——代理，不是执行率")
        if ch.get("civil_mult") is not None:
            bits.append(f"民心/文书（弱关联）×{ch['civil_mult']:.2f}")
        mil = ch.get("military") or {}
        if mil.get("applies"):
            bits.append(f"军队督行（**仅军政/边事类**加成）×{float(mil.get('mult') or 1):.2f}"
                        if mil.get("mult") is not None else "军队督行：无驻军读数（未计入）")
        else:
            bits.append("军队不参与（民政诏令）")
    except Exception as e:  # noqa: BLE001
        import logging as _lg
        _lg.getLogger("briefing").warning("build_weighing_note 取效果通道失败：%s", e)
    try:
        from core.officialdom import totals as _off_totals
        o = _off_totals(state) or {}
        pool = int(o.get("officials", 0) or 0)
        quota = int(o.get("posts_quota", 0) or 0)
        if pool > 0 and quota > 0:
            bits.append(f"冗官率 {max(0, pool - quota) / pool:.0%}"
                        f"、待阙率 {int(o.get('waiting', 0) or 0) / pool:.0%} → 事权落地")
    except Exception:  # noqa: BLE001
        pass
    if not bits:
        return ""
    return ("【权衡变数（下诏≠办事；吏治为强关联，军队仅对军政边事类加成）】"
            + "；".join(bits)
            + "。注意：若吏治折扣低，正是该项事务本月办不动的**理由**，请写进叙事，勿谎报已办。")


__all__ = ["build_briefing_actions", "build_weighing_note",
           "DECREE", "AUDIENCE", "TECH", "ARMY", "TODO"]
