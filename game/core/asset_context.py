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
    """前置节点 + 总体 level + 副指标 是否满足。"""
    tid = node[0]
    tech = _tech(state)
    for pre in node[5]:
        if pre not in tech.get("unlocked", []):
            return False
    if int(tech.get("level", 0)) < node[6]:
        return False
    for dim, need in node[7]:
        if int(tech.get(dim, 0)) < need:
            return False
    return True


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
_SIGNOFF_MSG = "AWAIT_SIGNOFF"


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

    - fund: "treasury" 国库拨银（走会签）/ "inner" 内帑乾纲独断（免会签担风险）
    - source: "panel" 面板直点 / "decree" 圣旨推演 / "council" 对话献策嘉纳
    - signoff: 是否已通过会签。国库拨银立项默认须先会签（signoff=True 才扣钱），
      否则返回 _SIGNOFF_MSG 标记等待 GUI 弹会签；内帑免会签、观念类免会签。
    观念类节点（idea=True）不花钱、不走会签，直接"颁布推行"（source 不影响其立项）。
    """
    node, tech, err = _research_guard(state, node_id)
    if err:
        return err

    cost = tech_cost_with_era(node, current_era(state))
    is_idea = cost.get("idea")

    if is_idea:
        # 观念革新：不花钱、不走会签，直接颁布推行（只需国库不为负即可）
        state.change_treasury(0)
        tech.setdefault("researching", {})[node_id] = {
            "progress": 0.0, "silver_in": 0,
            "months": cost["months"], "masters": 0,
            "idea": True, "source": source, "fund": "none",
        }
        return f"「{node[3]}」乃观念之革，不费帑藏，已下诏颁行天下。"
    if silver_in <= 0:
        silver_in = cost["silver"]

    if fund == "inner":
        # 内帑乾纲独断：免会签，但花皇帝私库、担研发失败/效果打折风险
        if getattr(state, "imperial_treasury", 0) < silver_in:
            return "内帑不足，难拨此费。"
        state.change_imperial_treasury(-silver_in)
    else:
        # 国库拨银乃朝廷公帑，须经会签（圣旨推演已走诏令会签，此处视为已会签）。
        # 未会签时仅返回等待标记，绝不扣钱。
        if source in ("panel", "council") and not signoff:
            if node_id not in tech.get("signoffs", {}):
                return _SIGNOFF_MSG
        if getattr(state, "treasury", 0) < silver_in:
            return "国库不足，难拨此费。"
        state.change_treasury(-silver_in)

    tech.setdefault("researching", {})[node_id] = {
        "progress": 0.0, "silver_in": silver_in,
        "months": cost["months"], "masters": cost["masters"],
        "idea": False, "source": source, "fund": fund,
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

    若献策指向已有节点（name 命中节点名/id 或 prereq_hint 命中），直接立项该节点；
    若是全新发明，则生成一个新节点（generated）入库并立项。
    国库拨银立项默认须会签：未会签时返回 _SIGNOFF_MSG 待会签标记（不扣钱），
    并保留生成节点，供会签准奏后以 signoff=True 再次调用立项。
    """
    inv = _pop_invention(state, index)
    if inv is None:
        return "查无此献策。"
    name = inv.get("name", "")
    node_id = _match_node_by_hint(inv)
    if node_id:
        # 该献策指向既有科技：直接立项（观念类不花钱，工程类按资金通道）
        return start_research(state, node_id, fund=fund, source="council",
                              signoff=signoff)
    # 全新发明：生成节点入库（未会签也先登记节点，准奏后再立项）
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


def _apply_node_effect(state, node) -> None:
    """把节点 effect 的实际增益回写全局数值（数值钩子）。"""
    effect = node[9] or {}
    tech = _tech(state)
    land = getattr(state, "land", {})
    if isinstance(land, dict):
        if effect.get("yield_bonus"):
            land["yield"] = min(2.5, land.get("yield", 1.0) + effect["yield_bonus"])
        if effect.get("build_cost"):
            pass  # build_cost 由工程结算统一读取资产汇总
    # 各维度增益落到 tech 副指标（供 calc_commerce / calc_maritime_trade 等读取）
    for k, v in effect.items():
        if k in tech and isinstance(v, (int, float)):
            tech[k] = max(0, min(100, int(tech[k]) + v))


def unlock_node(state, node_id: str, narrative: str = "") -> str:
    """正式点亮节点：入 unlocked、记里程碑、应用效果。返回叙事文本。"""
    tech = _tech(state)
    node = get_tech_node(node_id)
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
    _apply_node_effect(state, node)
    # 资产登记：科技节点入库（带能力标签推导）
    tech.setdefault("assets", {})[node_id] = {
        "kind": "科技", "name": node[3], "desc": node[4],
        "era": node[2], "capabilities": _derive_capabilities(node),
    }
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
