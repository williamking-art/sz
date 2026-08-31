# -*- coding: utf-8 -*-
"""宋祚 · 月度结算主流程（合并原 settlement_extensions.py / settlement_reform.py）

结构：
  - run_monthly_settlement 主流水线（Step 0 ~ 11）
  - MECHANISMS 注册表 + 五层承接层月度钩子（机制槽 / 研发管线 / 机构经济生命周期）
  - settle_reform 机构改制后果推演（reform_org 类圣旨）

各 Step 结算函数见 core/settlement_steps.py；本文件 re-export 常用符号保持
既有 import 兼容（commands / panels 等）。
"""
import random
from typing import Any

from content.data import (
    TREASURY_CRISIS_LINE, TREASURY_COLLAPSE_LINE,
    CHANGPING_HIGH, CHANGPING_LOW,
)
from core.game_state import _next_month

from core.settlement_steps import (
    _settle_decrees, _apply_decree_effect,
    _settle_factions,
    _settle_economy, _settle_land_local, _settle_extensions,
    _settle_longterm_decrees, _simulate_external,
    _settle_granary,
    _settle_finance,
    _settle_projects, _settle_workshops,
    _settle_treasury,
    _evaluate_timeline_breaks,
    _settle_military_diplomacy,
    _settle_events,
    _normalize_disaster_region, _settle_disaster,
    _settle_emperor_personal,
    _settle_hidden,
)

# 兼容旧调用方可能直接引用这些符号
__all__ = [
    "run_monthly_settlement",
    "settle_reform",
    "_apply_decree_effect",
    "_normalize_disaster_region",
    "MECHANISMS",
]


# ============================================================
# 五层承接层（原 settlement_extensions.py）
# ============================================================
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


# ============================================================
# 机构改制后果推演（原 settlement_reform.py）
# ============================================================
def settle_reform(state, decree: dict) -> dict:
    """结算一道 reform_org 类圣旨的后果。

    后果完全由 AI 依「威望 + 相关大臣隐藏忠诚度 + 派系立场」推演决定，
    不做写死的规则拒绝。返回叙事字典供 UI 展示（绝不泄露忠诚度数值）。
    """
    from ai.client import AIClient, _load_prompt, _clean_text

    reform = decree.get("reform") or {}
    rtype = reform.get("reform_type", "")
    target = reform.get("target_org", "")
    matter = reform.get("matter", "")

    related = set()
    if target and target in state.central_orgs:
        lead = state.central_orgs[target].get("lead")
        if lead:
            related.add(lead)
    if matter and matter in state.authority_matters:
        owner = state.authority_matters[matter].get("owner", "")
        if owner in state.central_orgs:
            l = state.central_orgs[owner].get("lead")
            if l:
                related.add(l)
    related = list(related)

    fs = decree.get("faction_stances", {})
    faction_text = "；".join(f"{k}：{v}" for k, v in fs.items()) or "（无显著派系反应）"

    authority_brief = state.authority_brief_for_ai(target_org=target, target_ministers=related)
    reform_text = decree.get("body") or decree.get("text") or decree.get("title", "")

    client = AIClient.load_saved()
    if client is None:
        res = _fallback_reform(state, reform, related)
        _apply_reform_result(state, decree, reform, res, related)
        return res

    sys_p = _load_prompt("reform_settle",
                         reform_text=reform_text[:600],
                         is_zhongzhi="是（御笔中旨强推）" if decree.get("is_zhongzhi") else "否（明发诏书）",
                         authority_brief=authority_brief,
                         faction_stance=faction_text)

    def validate(o):
        if not isinstance(o, dict) or "outcome" not in o:
            return None
        o["outcome"] = o.get("outcome", "smooth")
        o["court_report"] = _clean_text(str(o.get("court_report", "")))[:300]
        o["gazette"] = _clean_text(str(o.get("gazette", "")))[:160]
        o["loyalty_delta"] = o.get("loyalty_delta", {}) if isinstance(o.get("loyalty_delta"), dict) else {}
        o["corruption_delta"] = o.get("corruption_delta", {}) if isinstance(o.get("corruption_delta"), dict) else {}
        o["org_effects"] = o.get("org_effects", {}) if isinstance(o.get("org_effects"), dict) else {}
        o["faction_effects"] = o.get("faction_effects", {}) if isinstance(o.get("faction_effects"), dict) else {}
        return o

    user_p = "请依契约推演上述机构改制的落地后果。"
    raw = client._call(sys_p, user_p, temperature=0.9, max_tokens=800)
    res = client._postprocess(raw, validate, lambda: _fallback_reform(state, reform, related))
    if res is None:
        res = _fallback_reform(state, reform, related)

    _apply_reform_result(state, decree, reform, res, related)
    return res


def _apply_reform_result(state, decree, reform, res, related):
    """把 AI 推演结果回写：隐藏忠诚度变动、机构运行联动、机构树变更、派系联动。"""
    for name, delta in res.get("loyalty_delta", {}).items():
        if name in state.loyalty and isinstance(delta, (int, float)):
            state.loyalty[name] = max(0.0, min(1.0, state.loyalty[name] + float(delta)))

    for name, delta in res.get("corruption_delta", {}).items():
        if name in state.corruption and isinstance(delta, (int, float)):
            state.corruption[name] = max(0.0, min(1.0, state.corruption[name] + float(delta)))

    for oname, eff in res.get("org_effects", {}).items():
        o = state.central_orgs.get(oname)
        if not o:
            continue
        if "efficiency" in eff and isinstance(eff["efficiency"], (int, float)):
            o["efficiency"] = max(0.1, round(o["efficiency"] + float(eff["efficiency"]), 2))
        if "backlog" in eff and isinstance(eff["backlog"], (int, float)):
            o["backlog"] = max(0, int(o["backlog"] + float(eff["backlog"])))

    fe = res.get("faction_effects", {})
    fs = decree.setdefault("faction_stances", {})
    for fname, d in fe.items():
        if isinstance(d, (int, float)):
            fs[fname] = max(-1.0, min(1.0, float(fs.get(fname, 0)) + float(d)))

    rtype = reform.get("reform_type", "")
    target = reform.get("target_org", "")
    if rtype == "改名" and target in state.central_orgs and reform.get("new_name"):
        state.central_orgs[reform["new_name"]] = state.central_orgs.pop(target)
    elif rtype == "裁撤" and target in state.central_orgs:
        state.central_orgs[target]["abolished"] = True
        state.central_orgs[target]["efficiency"] = 0.0
        state.central_orgs[target].setdefault("comissions", [])
    elif rtype == "新建" and reform.get("new_org"):
        new_org = reform["new_org"]
        branches = reform.get("branches") or []
        matter_raw = reform.get("matter", []) or []
        matter_keys = [matter_raw] if isinstance(matter_raw, str) else list(matter_raw)
        state.central_orgs[new_org] = {
            "lead": "", "belong": "皇帝", "scope": reform.get("new_name", "新置机构"),
            "authority": [], "matter_keys": matter_keys, "posts": [], "holders": {},
            "comissions": [], "abolished": False,
            "efficiency": 0.6, "backlog": 0,
            "branches": {road: [f"{new_org}·{road}分司"] for road in branches},
            "budget_in": 0, "budget_out": 0, "net": 0,
        }
        for road in branches:
            if road in state.prefectures:
                state.prefectures[road].setdefault("orgs", [])
                if new_org not in state.prefectures[road]["orgs"]:
                    state.prefectures[road]["orgs"].append(new_org)
        for m in (reform.get("mechanisms") or []):
            if m in MECHANISMS and m not in state.mechanisms:
                state.mechanisms[m] = {"org": new_org, "params": {}, "progress": 0}
    elif rtype == "新建官职" and target in state.central_orgs and reform.get("new_post"):
        org = state.central_orgs[target]
        org.setdefault("posts", [])
        org.setdefault("holders", {})
        post_title = reform["new_post"]
        if not any(p.get("title") == post_title for p in org["posts"] if isinstance(p, dict)):
            org["posts"].append({"title": post_title})
            holder = reform.get("holder", "") or ""
            org["holders"][post_title] = holder
            if not org.get("lead"):
                org["lead"] = holder
    elif rtype == "改下辖" and target in state.central_orgs and reform.get("new_belong"):
        state.central_orgs[target]["belong"] = reform["new_belong"]
    elif rtype in ("改权限", "越权授权") and reform.get("matter") and reform.get("new_owner"):
        m = reform["matter"]
        if m in state.authority_matters:
            state.authority_matters[m]["owner"] = reform["new_owner"]


def _fallback_reform(state, reform, related) -> dict:
    """AI 不可用时的极简退路：仅依威望与（隐藏）忠诚度给定性后果，绝不暴露数值。"""
    pi = state.get_prestige_info()
    level = pi.get("level", "中")
    avg = sum(state.loyalty.get(n, 0.5) for n in related) / len(related) if related else 0.5
    if level in ("高", "极高") and avg >= 0.6:
        outcome = "smooth"
        report = "诏下，相关衙门奉命惟谨，事权更易井然。"
    elif avg < 0.4:
        outcome = "sabotage"
        report = "诏书虽颁，然有臣僚迁延观望，政务颇有积压。"
    else:
        outcome = "evade"
        report = "诸司受诏，外示奉行而内多斟酌，推行稍缓。"
    # 记忆知识库（Phase 3a）：机构改制写入图谱（org 实体 + governs）
    try:
        target = reform.get("target_org", "")
        rtype = reform.get("reform_type", "")
        if target:
            state.memory.add_entity(f"org_{target}", "org", target, turn=state.turn)
            state.memory.add_relation(f"org_{target}", f"reform_{rtype}",
                                      "governs", weight=1.0, turn=state.turn,
                                      note=f"{rtype}·{outcome}")
    except Exception:
        pass
    return {
        "outcome": outcome,
        "court_report": report,
        "gazette": "朝廷更定官制，以肃庶务。",
        "loyalty_delta": {},
        "org_effects": {},
        "faction_effects": {},
    }


# ------------------------------------------------------------
# 主流水线
# ------------------------------------------------------------
def run_monthly_settlement(state, seed_offset: int = 0) -> list:
    """执行月度结算，返回本轮结算日志列表。

    seed_offset 用于确定性复现：以 (state.turn + seed_offset) 派生随机种子，
    使相同回合+offset 的结算结果可复现，为 dev/replay 回放与平衡 A/B 对比打基础。
    """
    random.seed(state.turn * 1000003 + seed_offset)
    log = []

    # 更新年号
    state.update_era_name()
    from core.asset_context import era_switch
    era_switch(state)

    # ---- Step 0: 破产兜底（在其它步骤补血国库前，先按真实库藏判定）----
    if state.treasury < TREASURY_COLLAPSE_LINE:
        state.game_over = True
        state.game_result = "国用耗竭，天下鼎沸——大宋府库空虚，纲纪尽弛"
        log.append("[民生] 国库崩坏至不可复救，国用耗竭，天下鼎沸！")
        return log
    if state.treasury < TREASURY_CRISIS_LINE and not any(
            e.get("title") == "库藏空虚" for e in state.active_events):
        state.population_satisfaction = max(0, state.population_satisfaction - 2)
        log.append("[民生] 库藏空虚，中外忧惧，民怨渐起")
        crisis = {
            "title": "库藏空虚",
            "category": "crisis",
            "desc": "国库亏空日深，府库空虚，中外忧惧。陛下当决断出处：",
            "choices": [
                {"text": "增征商税，权宜聚财", "effects": {"commerce_tax": 0.30}},
                {"text": "裁汰冗费，省浮节流", "effects": {"curtail_waste": 1}},
                {"text": "发内帑，以私蓄济公",
                 "effects": {"treasury": min(state.imperial_treasury, 5000000),
                             "imperial_treasury": -min(state.imperial_treasury, 5000000)}},
                {"text": "卖度牒，权宜救急", "effects": {"treasury": 1000000}},
            ],
        }
        state.active_events.append({"title": crisis["title"], "message": crisis["desc"], "choices": crisis["choices"]})

    # ---- Step 1: 诏令执行 ----
    _settle_decrees(state, log)

    # ---- Step 2: 派系结算 ----
    _settle_factions(state, log)

    # ---- Step 3: 经济（人口→田土→工商） ----
    _settle_economy(state, log)

    # ---- Step 3.5: 田亩与地方州县 ----
    _settle_land_local(state, log)

    # ---- Step 3.6: 扩展维度自然演进（金融/科举/科技/外交） ----
    _settle_extensions(state, log)

    # ---- Step 3.7: 长期拟旨（公开 / 密令）推进与外部政权简单模拟 ----
    _settle_longterm_decrees(state, log)
    _simulate_external(state, log)

    # ---- Step 3.8: 仓廪漕运 ----
    _settle_granary(state, log)

    # ---- Step 4: 财政 ----
    _settle_finance(state, log)

    # ---- Step 4.5: 工程 / 制作系统 ----
    _settle_projects(state, log)
    _settle_workshops(state, log)

    # ---- Step 5: 国库 ----
    _settle_treasury(state, log)

    # ---- Step 6: 军事/外交 ----
    _settle_military_diplomacy(state, log)

    # ---- Step 6.5: 历史改写位评估 ----
    _evaluate_timeline_breaks(state, log)

    # ---- Step 6.8: 五层承接层月度钩子 ----
    _settle_mechanisms(state, log)      # 层②机制槽：纯加成/减耗
    _settle_tech(state, log)            # 层③研发管线：资源×时间×人才推进
    _settle_org_economy(state, log)     # 层④机构经济生命周期：受崩盘线约束

    # ---- Step 7: 事件压力 ----
    _settle_events(state, log)

    # ---- Step 8: 灾荒 ----
    _settle_disaster(state, log)

    # ---- Step 9: 皇帝个人 ----
    _settle_emperor_personal(state, log)

    # ---- Step 10: 隐藏状态 ----
    _settle_hidden(state, log)

    # ---- Step 11: 记录与回合推进 ----
    # 将月份/年份推进收敛到结算函数内部，确保与 Rust 后端（settle.rs）的推进位置一致，
    # 避免 commands 层再次推进导致双端月份各推一次的漂移。
    state.settlement_log.append(log)
    state.turn += 1
    state.year, state.month = _next_month(state.year, state.month)
    state.update_era_name()
    # 金融推演价格系数：月度重置（不落档，运行时态；下月按新金融词重新调制）
    state._price_mult = 1.0

    return log
