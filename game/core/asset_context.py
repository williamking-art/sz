# -*- coding: utf-8 -*-
"""宋祚 · 资产上下文与科技结算层

设计原则（专家团定稿）：
  - 资产（科技/建筑/器物）统一抽象为「能力标签」集合。
  - AI 只拥有「引用权 + 提议权」：可引用已得资产、可提议新标签，
    但数值永远由程序按 CAPABILITY_EFFECTS 查表 / 档位换算 / 封顶掷定。
  - 三级结算：预置标签查表给精确值 → 动态标签按登记结算 → 全新标签走档位换算并登记。
  - 按需注入：build_asset_summary 便宜，should_inject 决定是否注入到本次 AI 调用（省 token）。
"""
from content.data import (
    TECH_NODES, TECH_ERAS, TECH_LINES, CAPABILITY_EFFECTS,
    get_tech_node, tech_cost_with_era, DEFAULT_UNLOCKED,
    TECH_DOMAIN_NODES, TECH_NODE_DEPLOY, TECH_NODE_MAINTENANCE,
    TECH_ADOPTION_DEFAULT, TECH_ADOPTION_MAX, TECH_ADOPTION_PER_LEVEL,
    TECH_ADOPTION_DECAY, TECH_WEST_SOURCES, TECH_WEST_MAX,
    TECH_RESEARCH_BUDGET_RATIO,
)


# ============================================================
# 查询工具
# ============================================================
def _tech(state) -> dict:
    return state.tech if isinstance(state.tech, dict) else {}


def is_node_unlocked(state, node_id: str) -> bool:
    return node_id in _tech(state).get("unlocked", [])


def current_era(state) -> int:
    return int(_tech(state).get("era", 0))


def node_prereqs_met(state, node) -> bool:
    """前置节点 + 总体 level + 副指标 是否满足。

    承接模式（言枢密设计）：**去 west 硬门槛**——("west",N) 副指标跳过（玩家可承接
    天马行空研发）；west 保留为跨时代加速因子（_settle_tech_research rate × (1+west×系数)）。
    """
    tid = node[0]
    tech = _tech(state)
    for pre in node[5]:
        if pre not in tech.get("unlocked", []):
            return False
    # 整改④.1：总体 level 只作综合读数，不再充当能力关卡；
    # 能力由前置节点链 + 副指标（火药/冶金/水利/历法/航海/财政/医学农学…）判定。
    for dim, need in node[7]:
        if dim == "west":
            continue   # 去 west 硬门槛（承接模式）
        if int(tech.get(dim, 0)) < need:
            return False
    return True


# 状态：intentionally_unwired（有意未接线）—— 2026-09-19 代码质量全检确认零引用。
# 接线位置：资产节点状态：待接科技/资产面板
def node_status(state, node_id: str) -> str:
    """节点状态：unlocked(已点亮) / researchable(可研究) / researching(攻关中) / locked(未达前置)。"""
    tech = _tech(state)
    if node_id in tech.get("unlocked", []):
        return "unlocked"
    if node_id in tech.get("researching", {}):
        return "researching"
    node = get_tech_node(node_id)
    if node and node_prereqs_met(state, node):
        return "researchable"
    return "locked"


def era_switch(state):
    """根据年份更新当前时代序号（叙事标签，非硬门槛）。"""
    year = getattr(state, "year", 1101)
    era = 0
    for idx, name, lo, hi, _ in TECH_ERAS:
        if lo <= year <= hi:
            era = idx
            break
    _tech(state)["era"] = era
    return era


# ============================================================
# 攻关 / 点亮
# ============================================================
# 历史：国库拨银曾强制会签（AWAIT_SIGNOFF）。设计定稿：有钱即可研，门槛已移除。

def _research_guard(state, node_id: str):
    """统一研发前置校验（prepare/start 共用）：查无此制/已得/前置未备/已在攻关。

    返回 (node, tech, error_reason|None)。error_reason 非空即校验失败。
    """
    tech = _tech(state)
    node = get_tech_node(node_id)
    if not node:
        return None, tech, "查无此新制。"
    if is_node_unlocked(state, node_id):
        return None, tech, "此新制已得，不必再研。"
    if not node_prereqs_met(state, node):
        return None, tech, "前置未备，暂不可研。"
    if node_id in tech.get("researching", {}):
        return None, tech, "此新制已在攻关中。"
    return node, tech, None


# 状态：intentionally_unwired（有意未接线）—— 2026-09-19 代码质量全检确认零引用。
# 接线位置：研究预备：待接科技结算步
def prepare_research(state, node_id: str, silver_in: int = 0,
                     fund: str = "treasury", source: str = "panel") -> dict:
    """国库拨银研发的会签前置查询：校验可行性并算出费用，**不扣钱**。

    返回 {ok, reason, node_id, name, silver, months, masters, idea}
    或 {ok: False, reason: "..."}。供 GUI 在弹会签窗口前先探明是否可行。
    """
    node, tech, err = _research_guard(state, node_id)
    if err:
        return {"ok": False, "reason": err}
    cost = tech_cost_with_era(node, current_era(state))
    if cost.get("idea"):
        return {"ok": True, "node_id": node_id, "name": node[3], "desc": node[4],
                "silver": 0, "months": cost["months"], "masters": 0,
                "idea": True, "fund": "none"}
    silver = silver_in if silver_in > 0 else cost["silver"]
    if fund == "inner":
        if getattr(state, "imperial_treasury", 0) < silver:
            return {"ok": False, "reason": "内帑不足，难拨此费。"}
    else:
        if getattr(state, "treasury", 0) < silver:
            return {"ok": False, "reason": "国库不足，难拨此费。"}
    return {"ok": True, "node_id": node_id, "name": node[3], "desc": node[4],
            "silver": silver, "months": cost["months"], "masters": cost["masters"],
            "idea": False, "fund": fund, "cost_orig": cost["silver"]}


# 状态：intentionally_unwired（有意未接线）—— 2026-09-19 代码质量全检确认零引用。
# 接线位置：研究签核留痕：待接科技结算步
def record_research_signoff(state, node_id: str, review: dict) -> None:
    """记录一次研发会签结论（供 GUI 准奏后登记，避免重复会签）。"""
    tech = _tech(state)
    tech.setdefault("signoffs", {})[node_id] = {
        "year": getattr(state, "year", 0),
        "month": getattr(state, "month", 1),
        "verdict": (review or {}).get("verdict", "可准"),
    }


def start_research(state, node_id: str, silver_in: int = 0,
                   fund: str = "treasury", source: str = "panel",
                   signoff: bool = False) -> str:
    """统一研发立项端口（面板直点 / 圣旨推演 / 对话献策 三入口共用）。

    - fund: "treasury" 国库拨银 / "inner" 内帑独断
    - source: "panel" 面板直点 / "decree" 圣旨推演 / "council" 对话献策嘉纳
    - signoff: 历史参数，保留兼容；**不再作为立项门槛**（设计定稿：有钱即可研，
      会签仅作叙事/日志可选）。观念类（idea）仍不花钱直接颁布。
    """
    node, tech, err = _research_guard(state, node_id)
    if err:
        return err

    cost = tech_cost_with_era(node, current_era(state))
    is_idea = cost.get("idea")

    if is_idea:
        # 观念革新：不花钱、直接颁布推行
        state.change_treasury(0)
        tech.setdefault("researching", {})[node_id] = {
            "progress": 0.0, "silver_in": 0,
            "months": cost["months"], "masters": 0,
            "idea": True, "source": source, "fund": "none",
        }
        return f"「{node[3]}」乃观念之革，不费帑藏，已下诏颁行天下。"
    if silver_in <= 0:
        silver_in = cost["silver"]

    # 立项首月经费：**守恒转移**（国库/内帑 → 学者·工匠 POP wealth），
    # 不再是无对手方的 `change_treasury(-silver)` 销毁（整改④.2 / POP 挂载律）。
    from content.data import TECH_RESEARCH_PAY_TO
    from core.settlement_steps import transfer_public_funds_to_pops
    _acct = "imperial_treasury" if fund == "inner" else "treasury"
    if int(getattr(state, _acct, 0) or 0) < silver_in:
        return "内帑不足，难拨此费。" if fund == "inner" else "国库不足，难拨此费。"
    _paid = transfer_public_funds_to_pops(
        state, silver_in, TECH_RESEARCH_PAY_TO,
        f"研发立项：{node[3]}", source_account=_acct)
    if _paid <= 0:
        return "帑藏不足，研发经费未能拨付，立项中止。"

    tech.setdefault("researching", {})[node_id] = {
        "progress": 0.0, "silver_in": _paid,
        # 月度研发经费（整改④.2）：researching 每月消耗预算与人才时间，中断保留进度。
        "monthly_cost": max(1, int(_paid * TECH_RESEARCH_BUDGET_RATIO)),
        "months": cost["months"], "masters": cost["masters"],
        "idea": False, "source": source, "fund": fund,
        "idle_months": 0,
    }
    src_note = {"panel": "陛下亲定", "decree": "圣旨推演", "council": "大臣献策嘉纳"}.get(source, "朝议")
    return f"已拨帑 {silver_in:.0f}贯（{src_note}），立「{node[3]}」之研。"


def _pop_invention(state, index: int):
    """从 pending_inventions 弹出第 index 条；越界返回 None。approve/reject 共用。"""
    tech = _tech(state)
    pend = tech.get("pending_inventions", [])
    if not 0 <= index < len(pend):
        return None
    return pend.pop(index)


def approve_invention(state, index: int, fund: str = "treasury",
                      signoff: bool = False) -> str:
    """嘉纳工部献策：把 pending_inventions 中第 index 条转为研究立项。

    若献策指向已有节点，直接立项；全新发明则注册 generated 节点再立项。
    国库有钱即可立（不再强制会签）；signoff 参数保留兼容。
    """
    inv = _pop_invention(state, index)
    if inv is None:
        return "查无此献策。"
    name = inv.get("name", "")
    node_id = _match_node_by_hint(inv)
    if node_id:
        return start_research(state, node_id, fund=fund, source="council",
                              signoff=signoff)
    gid = _register_generated_node(state, inv)
    return start_research(state, gid, fund=fund, source="council",
                          signoff=signoff)


def reject_invention(state, index: int) -> str:
    """驳回献策：移出待审区（可记录驳回原因）。"""
    inv = _pop_invention(state, index)
    if inv is None:
        return "查无此献策。"
    return f"已驳回「{inv.get('name','新制')}」之献。"


def _match_node_by_hint(inv: dict) -> str:
    """把献策 name/prereq_hint 匹配到既有科技节点 id。"""
    name = inv.get("name", "")
    hint = inv.get("prereq_hint", "")
    for node in TECH_NODES:
        if name and (name in node[0] or node[3] in name or name in node[3]):
            return node[0]
    for node in TECH_NODES:
        if hint and (hint in node[3] or node[3] in hint or hint in node[0]):
            return node[0]
    return ""


def _register_generated_node(state, inv: dict) -> str:
    """把 AI 献策的全新发明注册为一个生成节点，返回新节点 id。"""
    import hashlib
    name = inv.get("name", "新制")
    gid = "gen_" + hashlib.md5(name.encode("utf-8")).hexdigest()[:8]
    tech = _tech(state)
    # 若同名已生成过，直接复用
    if gid in tech.get("generated_nodes", {}):
        return gid
    effect_dim = inv.get("effect_dim", "production")
    tier_map = {"无": 0.0, "微": 0.08, "小": 0.15, "中": 0.25, "大": 0.40}
    val = tier_map.get(inv.get("effect_tier", "微"), 0.08)
    # 生成节点：观念/工程混合，成本保守（献策方建议档位决定效果），默认走工程投入
    node = (
        gid, inv.get("kind", "科技") if inv.get("kind") in TECH_LINES else "观念与制度",
        int(tech.get("era", 0)), name, inv.get("desc", "工部新献之制"),
        [], 0, [], {"silver": 300000, "months": 12, "masters": 3},
        {effect_dim: val},
    )
    tech.setdefault("generated_nodes", {})[gid] = {
        "name": name, "desc": inv.get("desc", ""),
        "minister": inv.get("minister", ""),
        "effect_dim": effect_dim, "effect_tier": inv.get("effect_tier", "微"),
        # 完整节点元组也随存档保存：读档时据此重建，保证「聊出来的发明」读档不丢
        "node": node,
    }
    # 把生成节点并入 content.data 的全局节点表（供 get_tech_node 查询）
    _register_generated_node_global(gid, node)
    return gid


def _register_generated_node_global(gid: str, node: tuple) -> None:
    """把生成节点并入 content.data 的全局节点表（供 get_tech_node 查询）。"""
    try:
        from content.data import _TECH_NODE_MAP as _map
        _map[gid] = node
    except Exception:
        pass


def _apply_effect_delta(state, node, delta: float) -> None:
    """把节点 effect 按 **adoption 覆盖率增量** 回写全局数值（数值钩子）。

    delta = 新覆盖率 − 旧覆盖率：解锁/部署推进时 delta>0，维护欠费折损时 delta<0。
    同一节点反复结算只累加增量，不重复全额计账（收益有容量、折旧可逆）。
    """
    if not delta:
        return
    effect = node[9] or {}
    tech = _tech(state)
    land = getattr(state, "land", {})
    if isinstance(land, dict):
        if effect.get("yield_bonus"):
            _yv = float(land.get("yield", 1.0) or 1.0) + float(effect["yield_bonus"]) * delta
            land["yield"] = max(0.5, min(2.5, _yv))
        if effect.get("build_cost"):
            pass  # build_cost 由工程结算统一读取资产汇总
    # 各维度增益落到 tech 副指标（供 calc_commerce / calc_maritime_trade 等读取）
    for k, v in effect.items():
        if k in tech and isinstance(v, (int, float)) and not isinstance(v, bool):
            tech[k] = max(0, min(100, int(tech[k]) + v * delta))


def _apply_node_effect(state, node) -> None:
    """兼容旧签名：一次性施加全额效果（adoption = 1.0）。"""
    _apply_effect_delta(state, node, 1.0)


def node_adoption_coverage(state, node_id: str) -> float:
    """节点「全国部署覆盖率」（0~1，整改④.3）。

    解锁 ≠ 全国生效：声明了部署建筑的节点，须该建筑/作坊/军队**建成运行**方可覆盖。
    覆盖率 = min(1.0, Σ(部署建筑等级) × TECH_ADOPTION_PER_LEVEL)；
    未声明部署路径的节点视为技艺已内化于现有作坊/衙署（coverage = 默认值）。
    """
    deploy = TECH_NODE_DEPLOY.get(node_id)
    if not deploy:
        return TECH_ADOPTION_DEFAULT
    lv = 0
    projects = getattr(state, "projects", None)
    if isinstance(projects, dict):
        _projs = list(projects.values())
    elif isinstance(projects, list):
        _projs = list(projects)
    else:
        _projs = []
    for pj in _projs:
        if not isinstance(pj, dict):
            continue
        name = str(pj.get("name") or pj.get("type") or "")
        if name != deploy:
            continue
        if pj.get("abandoned") or pj.get("status") == "abandoned":
            continue
        if pj.get("status") in ("operating", "degraded") or pj.get("done"):
            lv += max(1, int(pj.get("level", 1) or 1))
    prefs = getattr(state, "prefectures", None)
    if isinstance(prefs, dict):
        for p in prefs.values():
            if not isinstance(p, dict):
                continue
            b = p.get("buildings") or {}
            if isinstance(b, dict):
                lv += max(0, int(b.get(deploy, 0) or 0))
    return min(TECH_ADOPTION_MAX, lv * TECH_ADOPTION_PER_LEVEL)


def settle_adoption(state, log=None) -> dict:
    """月度结算：按部署建筑重算各已解锁节点的 adoption 覆盖率并施加增量效果。

    维护 → 折旧：维持费欠缴（_settle_upkeep 的 arrears 增长）时，有维护声明的节点
    覆盖率按月折损 TECH_ADOPTION_DECAY；恢复全额维持后按建筑存量回升。
    返回 {"changed": n, "degraded": n}，供日志/审计（失败不静默）。
    """
    tech = _tech(state)
    assets = tech.get("assets", {})
    if not isinstance(assets, dict) or not assets:
        return {"changed": 0, "degraded": 0}
    stats = getattr(state, "statistics", None)
    arrears = int(stats.get("upkeep_arrears", 0) or 0) if isinstance(stats, dict) else 0
    prev = tech.get("_adoption_arrears_seen")
    if prev is None:
        tech["_adoption_arrears_seen"] = arrears
        prev = arrears
    else:
        tech["_adoption_arrears_seen"] = arrears
    maintained = arrears <= int(prev)
    changed = degraded = 0
    for nid, a in list(assets.items()):
        if not isinstance(a, dict):
            continue
        node = get_tech_node(nid)
        if node is None:
            try:
                from core.registries import node_entry
                node = node_entry(state, nid)
            except Exception:
                node = None
        if not node:
            continue
        cov = node_adoption_coverage(state, nid)
        if (not maintained) and TECH_NODE_MAINTENANCE.get(nid, 0.0) > 0:
            cov = max(0.0, cov - TECH_ADOPTION_DECAY)   # 维护欠费 → 折旧
            degraded += 1
        old_cov = float(a.get("adoption", 0.0) or 0.0)
        if abs(cov - old_cov) > 1e-9:
            _apply_effect_delta(state, node, cov - old_cov)
            a["adoption"] = round(cov, 4)
            changed += 1
    if changed and isinstance(log, list):
        log.append(f"[科技] 部署覆盖率更新 {changed} 项（维护{'到位' if maintained else '欠费'}）")
    return {"changed": changed, "degraded": degraded}


def accrue_west(state, log=None) -> float:
    """西学（west）来源制（整改④.4）：只从贸易/使团/书籍/工匠/战争累积。

    贸易来源：海路既开且确有贸易额；其余四类由事件/AI 显式登记
    `tech["west_sources"][kind]`（未登记则不计）。west 不再每月凭空 +0.01，
    也不再是万能加速器（对研发仅 ×≤TECH_WEST_ACCEL_CAP）。
    """
    tech = _tech(state)
    # 本月**活跃来源**（不复用上月）：有来源才计入，无来源则 west 不增长。
    src = {}
    mari = getattr(state, "maritime", None)
    if isinstance(mari, dict) and mari.get("open"):
        try:
            trade = float(state.calc_maritime_trade())
        except Exception:
            trade = 0.0
        if trade > 0:
            src["trade"] = 1
    # 使团/书籍/工匠/战争：由事件/AI 显式登记的一次性来源（west_pending_sources）
    pending = tech.pop("west_pending_sources", None)
    if isinstance(pending, dict):
        for kind in TECH_WEST_SOURCES:
            if pending.get(kind):
                src[kind] = 1
    elif isinstance(pending, (list, tuple, set)):
        for kind in pending:
            if kind in TECH_WEST_SOURCES:
                src[kind] = 1
    tech["west_sources"] = src
    gain = sum(float(rate) for kind, rate in TECH_WEST_SOURCES.items() if src.get(kind))
    if gain <= 0:
        return 0.0
    old = float(tech.get("west", 0) or 0)
    nw = round(min(TECH_WEST_MAX, old + gain), 4)
    tech["west"] = nw
    return round(nw - old, 4)


def unlock_node(state, node_id: str, narrative: str = "") -> str:
    """正式点亮节点：入 unlocked、记里程碑、应用效果。返回叙事文本。"""
    tech = _tech(state)
    node = get_tech_node(node_id)
    if node is None:
        # 承接模式：玩家注册节点（tech_registry）兼容
        try:
            from core.registries import node_entry
            node = node_entry(state, node_id)
        except Exception:
            node = None
    if not node:
        return "查无此新制。"
    if is_node_unlocked(state, node_id):
        return "此新制已得。"
    tech.setdefault("unlocked", []).append(node_id)
    tech["researching"].pop(node_id, None)
    tech.setdefault("milestones", {})[node_id] = {
        "year": getattr(state, "year", 0),
        "month": getattr(state, "month", 1),
        "name": node[3],
        "narrative": narrative or f"{node[3]}告成",
    }
    # 资产登记：科技节点入库（能力标签 + 部署/维护声明）
    _cov = node_adoption_coverage(state, node_id)
    tech.setdefault("assets", {})[node_id] = {
        "kind": "科技", "name": node[3], "desc": node[4],
        "era": node[2], "capabilities": _derive_capabilities(node),
        "deploy": TECH_NODE_DEPLOY.get(node_id, ""),
        "maintain": TECH_NODE_MAINTENANCE.get(node_id, 0.0),
        "adoption": round(_cov, 4),
    }
    # 解锁 ≠ 全国生效：只对已部署（coverage>0）的部分施加效果（整改④.3）。
    _apply_effect_delta(state, node, _cov)
    return f"「{node[3]}」已成，技进于器。"


# 节点 → 能力标签推导（依据 effect 键与主干线粗配）
_CAP_BY_LINE = {
    "机械动力": ["动力", "制造"],
    "能源与材料": ["动力", "冶金"],
    "化学化工": ["化学", "制造"],
    "信息通讯": ["印刷", "通讯"],
    "生命医学": ["医学"],
}
_EFFECT_CAP_HINT = {
    "yield_bonus": ["农业", "灌溉"],
    "trade_income": ["纺织", "航海", "道路"],
    "mining_income": ["开矿", "动力"],
    "army_power": ["军事", "军工", "冶炼"],
    "build_cost": ["建材", "冶炼"],
    "canal_efficiency": ["运输", "道路"],
    "production": ["动力", "化学", "建材"],
    "exam_talent": ["印刷", "天文"],
    "decree_speed": ["通讯", "印刷"],
    "epidemic_risk": ["医学", "防水"],
    "calendar_bonus": ["天文"],
}


def _derive_capabilities(node) -> list:
    """从节点 effect 键 + 主干线推导能力标签（供资产登记）。"""
    caps = list(_CAP_BY_LINE.get(node[1], []))
    for k in (node[9] or {}).keys():
        for cap in _EFFECT_CAP_HINT.get(k, []):
            if cap not in caps:
                caps.append(cap)
    return caps


# ============================================================
# 三级结算：预置标签 → 动态标签 → 档位换算
# ============================================================
# 状态：intentionally_unwired（有意未接线）—— 2026-09-19 代码质量全检确认零引用。
# 接线位置：资产效果落地：待接资产结算步
def resolve_asset_effect(state, capabilities: list, domain: str) -> dict:
    """AI 引用某资产能力用于某领域 → 结算增益字典（clamp 封顶）。

    返回 {effect_key: value}，未命中则返回 {}（AI 叙事照写，数值给微/0）。
    """
    tech = _tech(state)
    out = {}
    for cap in capabilities:
        key = (cap, domain)
        if key in CAPABILITY_EFFECTS:
            for ek, ev in CAPABILITY_EFFECTS[key].items():
                out[ek] = out.get(ek, 0) + ev
        else:
            # 动态标签：查已登记
            dyn = tech.get("dynamic_capabilities", {}).get(cap)
            if dyn and dyn.get("effect_dim") == domain:
                dim = dyn["effect_dim"]
                from ai.client import tier_to_value
                v = tier_to_value(dim, dyn.get("tier", "微"), 1.0)
                out[dim] = out.get(dim, 0) + v
            else:
                # 全新标签：AI 无权直接定数值，仅记录待登记（由调用方给档位）
                out.setdefault("_unknown_cap", 0)
    return out


# ============================================================
# 按需注入：资产摘要
# ============================================================
def build_asset_summary(state) -> str:
    """构建「本朝已得之器」摘要（便宜，供按需注入）。"""
    tech = _tech(state)
    assets = tech.get("assets", {})
    if not assets:
        return ""
    lines = []
    for aid, a in assets.items():
        caps = "、".join(a.get("capabilities", [])) or "工巧"
        lines.append(f"{a['name']}（可{caps}）")
    return "本朝已得：" + "、".join(lines) + "。"


def should_inject(player_input: str = "", interaction: str = "") -> bool:
    """判断本次 AI 调用是否注入资产摘要（省 token）。"""
    kw = ("科技", "营造", "工部", "工程", "水泥", "修路", "筑城", "水利",
          "新制", "发明", "造", "机器", "蒸汽", "铁路", "电报", "印刷",
          "兵甲", "军械", "矿", "冶金", "纺织", "航海", "疫苗", "医")
    txt = f"{player_input or ''} {interaction or ''}"
    return any(k in txt for k in kw)
