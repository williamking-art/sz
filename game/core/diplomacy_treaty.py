# -*- coding: utf-8 -*-
"""宋祚 · 外交协议落地（diplomacy_dialogue 契约 → 蔡权衡系数表应用）。

- `apply_treaty(state, target, type, terms)`：协议落地——关系换算（_DIPLO_ATT →
  attitude 变化，CAP ±15）+ 和亲嫁妆（DOWRY_BASE 内帑出守恒，>内帑拒绝/降档）+
  岁币倍率（SUI_GONG_MULT → state._sui_gong_mult，停 → 战争风险）+ 榷场月入
  （TRADE_INCOME 国库入，不重复计税）+ 战争标记（state._at_war[邦] + 边患概率）。
- `state.treaties`：{势力: [{type, terms, turn, year, month}]}（存档持久化）。
- 守恒：嫁妆/岁币 = 内帑/国库出（外流设计，reason 记账）；榷场 = 外部钱入（来源榷场）。
"""
from content.data import (_DIPLO_ATT, DIPLO_ATT_CAP, DOWRY_BASE, SUI_GONG_MULT,
                          TRADE_INCOME, WAR_RISK_BOOST)

# 协议类型白名单（diplomacy_dialogue agreement 校验）
TREATY_TYPES = ("和亲", "岁币", "榷场", "盟约", "纳贡", "战争")


def _att_delta(type_: str, terms: dict) -> int:
    """关系换算：_DIPLO_ATT[type][档位] → attitude 变化（CAP ±15）。"""
    table = _DIPLO_ATT.get(type_, {})
    tier = str(terms.get("tier", "中"))
    delta = table.get(tier, 0)
    return max(-DIPLO_ATT_CAP, min(DIPLO_ATT_CAP, delta))


def apply_treaty(state, target: str, type_: str, terms: dict = None,
                 year: int = 0, month: int = 1) -> dict:
    """落地一项协议（拒绝式：嫁妆超内帑 → 拒绝/降档；未知协议 → 拒绝）。

    返回 {"ok", "msg", "attitude_delta", "cost"}。
    """
    terms = dict(terms or {})
    if target not in ("辽", "金", "西夏"):
        return {"ok": False, "msg": "协议对象须为辽/金/西夏", "attitude_delta": 0, "cost": 0}
    if type_ not in TREATY_TYPES:
        return {"ok": False, "msg": f"未知协议类型：{type_}", "attitude_delta": 0, "cost": 0}
    reg = (getattr(state, "external", None) or {}).get(target)
    if not reg:
        return {"ok": False, "msg": f"无此势力：{target}", "attitude_delta": 0, "cost": 0}

    cost = 0
    extra = []
    # 1) 和亲嫁妆（内帑出守恒；嫁妆 > 内帑 → 降档到可支付，仍不足 → 拒绝）
    if type_ == "和亲":
        tier = str(terms.get("tier", "中"))
        dowry = DOWRY_BASE.get(tier, DOWRY_BASE["中"])
        if state.imperial_treasury < dowry:
            _fallback = None
            for _t, _v in sorted(DOWRY_BASE.items(), key=lambda kv: kv[1]):
                if _v <= state.imperial_treasury:
                    _fallback = (_t, _v)
            if _fallback:
                tier, dowry = _fallback
                extra.append(f"嫁妆降档至{tier}（内帑不足）")
            else:
                return {"ok": False, "msg": "内帑不足以支和亲嫁妆", "attitude_delta": 0, "cost": 0}
        state.imperial_treasury -= dowry
        cost += dowry
        state.treaties.setdefault(target, []).append(
            {"type": "和亲", "terms": {"tier": tier}, "turn": getattr(state, "turn", 0),
             "year": year, "month": month})
    # 2) 岁币倍率（专用档位 增/减/停，对齐 SUI_GONG_MULT 键；停 → 战争风险）
    elif type_ == "岁币":
        mult = SUI_GONG_MULT.get(str(terms.get("岁币") or terms.get("tier", "停")), 1.0)
        state._sui_gong_mult[target] = mult
        state.treaties.setdefault(target, []).append(
            {"type": "岁币", "terms": {"tier": str(terms.get("岁币") or terms.get("tier", "停"))},
             "turn": getattr(state, "turn", 0), "year": year, "month": month})
    # 3) 榷场月入（国库，外部钱入——来源榷场，不重复计税；档位 开/扩/停 对齐 _DIPLO_ATT）
    elif type_ == "榷场":
        tier = str(terms.get("榷场") or terms.get("tier", "开"))
        if tier == "停":
            income = 0
            state._trade_income.pop(target, None)
        else:
            income = TRADE_INCOME.get({"开": "小", "扩": "中"}.get(tier, "小"), TRADE_INCOME["小"])
            state.treasury += income
            state._trade_income[target] = income
        cost = -income   # 负 = 收入
        state.treaties.setdefault(target, []).append(
            {"type": "榷场", "terms": {"tier": tier}, "turn": getattr(state, "turn", 0),
             "year": year, "month": month})
    # 4) 盟约 / 纳贡
    elif type_ == "盟约":
        on = str(terms.get("tier", "结")) == "结"
        state.treaties.setdefault(target, []).append(
            {"type": "盟约", "terms": {"结": on}, "turn": getattr(state, "turn", 0),
             "year": year, "month": month})
    # 5) 战争（_at_war 标记 + WAR_RISK_BOOST 消费：invasion_will +10——边患事件压力提升）
    elif type_ == "战争":
        state._at_war[target] = 1
        _reg = (getattr(state, "external", None) or {}).get(target) or {}
        _reg["invasion_will"] = int(_reg.get("invasion_will", 0) or 0) + 10   # 边患载体提升（消费 WAR_RISK_BOOST）
        state.treaties.setdefault(target, []).append(
            {"type": "战争", "terms": {"tier": str(terms.get("tier", "中"))},
             "turn": getattr(state, "turn", 0), "year": year, "month": month})

    # 关系换算（所有类型）
    delta = _att_delta(type_, terms)
    reg["attitude"] = max(0, min(100, int(reg.get("attitude", 50)) + delta))
    msg = f"与{target}{type_ if type_ != '榷场' else '榷场'}已定"
    if cost > 0:
        msg += f"（费 {cost:,} 贯）"
    elif cost < 0:
        msg += f"（月入 {-cost:,} 贯）"
    if extra:
        msg += "；" + "；".join(extra)
    return {"ok": True, "msg": msg, "attitude_delta": delta, "cost": cost}
