# -*- coding: utf-8 -*-
"""宋祚 · 机构改制后果推演（reform_org 类圣旨结算）

拆分自原 settlement.py 的 settle_reform / _apply_reform_result / _fallback_reform。
依赖 core.game_state.GameState 提供的 central_orgs / authority_matters / loyalty / corruption 等。
"""
from typing import Any

from content.ministers import (
    MINISTERS, loyalty_init, corruption_init, CENTRAL_ORG_INFO, AUTHORITY_MATTERS, REFORM_TYPES,
    org_lead,
)
from core.settlement_extensions import MECHANISMS


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
    return {
        "outcome": outcome,
        "court_report": report,
        "gazette": "朝廷更定官制，以肃庶务。",
        "loyalty_delta": {},
        "org_effects": {},
        "faction_effects": {},
    }
