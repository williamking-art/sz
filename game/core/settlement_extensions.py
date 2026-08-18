# -*- coding: utf-8 -*-
"""宋祚 · 五层承接层月度钩子（机制槽 / 研发管线 / 机构经济生命周期）

拆分自原 settlement.py。设计铁律：纯加成/减耗/累加，不侵入推演内核既有数值折算公式。
"""
from typing import Any

from content.data import (
    CHANGPING_HIGH, CHANGPING_LOW,
)


# 层②机制槽注册表：键为玩家圣旨可声明的机制名，值为结算加成函数标识。
# 仅做轻量、可解释的修正，不替换任何既有结算分支。
MECHANISMS = {
    "复式记账": {"desc": "钱粮出入双簿相核，月结精度提升，隐性亏空下降", "effect": "finance_precision"},
    "运票": {"desc": "票物一致方可核销，转运损耗下降", "effect": "transport_loss_down"},
    "常平粜籴": {"desc": "丰敛歉粜，平抑粮价波动", "effect": "grain_price_smooth"},
    "工训营": {"desc": "召流民为工，训以匠艺，育理工人才", "effect": "train_craftsman"},
    "市舶抽解": {"desc": "海舶抽税，增市舶之利", "effect": "maritime_tax_up"},
}


def _settle_mechanisms(state, log):
    """层②机制槽：依据 state.mechanisms 注册项，施加纯加成/减耗修正。"""
    for mname, m in state.mechanisms.items():
        spec = MECHANISMS.get(mname)
        if not spec:
            continue
        eff = spec["effect"]
        org = m.get("org", "")
        if eff == "finance_precision":
            o = state.central_orgs.get(org)
            if o:
                o["efficiency"] = min(1.2, round(o["efficiency"] + 0.02, 2))
        elif eff == "transport_loss_down":
            state.land["canal_eff"] = min(0.98, state.land.get("canal_eff", 0.7) + 0.01)
        elif eff == "grain_price_smooth":
            if state.grain_price > CHANGPING_HIGH:
                state.grain_price = max(CHANGPING_HIGH, state.grain_price - 2)
            elif state.grain_price < CHANGPING_LOW:
                state.grain_price = min(CHANGPING_LOW, state.grain_price + 2)
        elif eff == "train_craftsman":
            o = state.central_orgs.get(org)
            if o and o.get("net", 0) >= 0:
                for proj in state.tech.get("projects", {}).values():
                    proj["masters"] = proj.get("masters", 0) + 1
        elif eff == "maritime_tax_up":
            state.statistics["total_income"] += int(state.calc_commerce() * 0.01)


def _settle_tech(state, log):
    """层③研发管线：tech["projects"] 中可研项目按 资源×时间×人才 推进。"""
    projects = state.tech.get("projects", {})
    if not projects:
        return
    for pname, proj in projects.items():
        if proj.get("done"):
            continue
        masters = proj.get("masters", 0)
        monthly = proj.get("monthly_cost", 0)
        if monthly <= 0:
            continue
        if state.treasury >= monthly:
            state.change_treasury(-int(monthly))
            talent = 1.0 + min(masters, 20) * 0.1
            proj["progress"] = proj.get("progress", 0) + int(50 * talent)
            if proj["progress"] >= 1000:
                proj["progress"] = 1000
                proj["done"] = True
                log.append(f"[研发] {pname} 研成！匠术精进，国力稍增")
                if "unlocked" not in state.tech:
                    state.tech["unlocked"] = []
                if pname not in state.tech["unlocked"]:
                    state.tech["unlocked"].append(pname)
        else:
            log.append(f"[研发] {pname} 月费不济（需 {monthly}贯），进度停滞")


def _settle_org_economy(state, log):
    """层④机构经济生命周期：汇总各机构 budget_in/out 算 net，走 change_treasury，
    受 TREASURY_COLLAPSE_LINE 约束（不可绕过 game_over）。"""
    for oname, o in state.central_orgs.items():
        if o.get("abolished"):
            o["budget_in"] = o["budget_out"] = o["net"] = 0
            continue
        base_grant = 2 + len(o.get("matter_keys", [])) * 1
        o["budget_in"] = base_grant
        out = 1 + len(o.get("posts", [])) * 0.5 + len(o.get("branches", {})) * 0.3
        o["budget_out"] = round(out, 2)
        # 国库记账为整数贯：net 先取整再入账（"文"级精度只存在于物价体系，不进国库）
        net = int(round(o["budget_in"] - o["budget_out"]))
        o["net"] = net
        if net != 0:
            state.change_treasury(net)
    org_net = sum(o.get("net", 0) for o in state.central_orgs.values() if not o.get("abolished"))
    state.statistics.setdefault("org_net", 0)
    state.statistics["org_net"] = round(org_net, 2)
