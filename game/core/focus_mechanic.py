# -*- coding: utf-8 -*-
"""宋祚 · 国策树机制（core/focus_mechanic.py）

参考《明末：捞金模拟器》的国策树（focus）：五大分支（政务/军事/科学/内卫/税务），
带权力等级、互斥分支、解锁建筑与长期效果，替代/补充现有零散施政。

与 state.MAJOR_POLICIES / REFORM_TYPES 不同，国策树是「五大分支、权力等级、
互斥、解锁建筑」的全新体系。本模块只做定义 + 结算推进 + 解锁判定，不写状态；
由 settlement.run_monthly_settlement 在 Step 6.9 之后调用。

设计原则：
- 每分支节点带 power_level（权力等级），高等级节点需前置节点已解锁；
- 互斥分支：政务 vs 军事（重文轻武 vs 重武轻文），选择一方则另一方对应节点降权；
- 解锁建筑：节点解锁后写入 state.tech["assets"] 或 state.central_orgs 相关字段；
- 长期效果：节点解锁后月度施加确定性修正（非守恒字段），不破坏经济守恒。
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. 国策树定义（FOCUS_TREE）
#    每分支：{branch_key, branch_name, nodes: {node_key: {name, desc, power_level,
#            prereq(前置节点), unlock(解锁建筑/效果), effect(长期效果), exclusive_with}}}
# ---------------------------------------------------------------------------

FOCUS_TREE = {
    "govern": {
        "name": "政务",
        "desc": "整饬吏治，裁汰冗费，以固朝纲。",
        "nodes": {
            "g1_centralize": {
                "name": "中央集权",
                "desc": "收揽权柄，政令出于中枢。",
                "power_level": 1,
                "duration": 3,
                "cost_per_month": 10000,
                "prereq": None,
                "unlock": "吏治清明",
                "effect": "govern_eff",
                "narrative_memory": "朝廷行中央集权大策，收天下之权聚于中枢，政令划一，文臣出巡监州县。",
            },
            "g2_reform": {
                "name": "官制改革",
                "desc": "厘正官制，裁汰冗员。",
                "power_level": 2,
                "duration": 6,
                "cost_per_month": 25000,
                "prereq": "g1_centralize",
                "unlock": "新官制",
                "effect": "govern_eff",
                "narrative_memory": "改定官制新典，澄清铨选，裁汰冗官闲曹，士大夫恪尽职守不敢懈怠。",
            },
            "g3_curtail": {
                "name": "裁汰冗费",
                "desc": "省浮节流，以实府库。",
                "power_level": 3,
                "duration": 12,
                "cost_per_month": 50000,
                "prereq": "g2_reform",
                "unlock": "省费令",
                "effect": "govern_eff",
                "narrative_memory": "省费令大颁天下，斩断三冗积弊，节缩浮费入实库，帝国财赋大见丰盈。",
            },
        },
    },
    "military": {
        "name": "军事",
        "desc": "整军经武，修城固垒，以御外侮。",
        "nodes": {
            "m1_garrison": {
                "name": "整军经武",
                "desc": "整饬军旅，充实边备。",
                "power_level": 1,
                "duration": 3,
                "cost_per_month": 15000,
                "prereq": None,
                "unlock": "边军",
                "effect": "military_eff",
                "narrative_memory": "整饬边军纪律，增设边防马监，塞上甲兵精熟，烽燧戒严以防戎狄。",
            },
            "m2_fortify": {
                "name": "修城固垒",
                "desc": "增修城防，坚壁清野。",
                "power_level": 2,
                "duration": 6,
                "cost_per_month": 35000,
                "prereq": "m1_garrison",
                "unlock": "城防",
                "effect": "military_eff",
                "narrative_memory": "九边重镇与险要关隘坚筑重堡，城堞险固，连营千里，筑成北疆铁壁。",
            },
            "m3_war_machine": {
                "name": "军备军器",
                "desc": "广造军器，火器军用。",
                "power_level": 3,
                "duration": 12,
                "cost_per_month": 60000,
                "prereq": "m2_fortify",
                "unlock": "军器监",
                "effect": "military_eff",
                "narrative_memory": "军器监广开火药局与神臂弓监，火器成列，劲弩如林，大宋甲兵冠绝东亚。",
            },
        },
    },
    "science": {
        "name": "科学",
        "desc": "兴百工，修历法，奖掖技艺。",
        "nodes": {
            "s1_tech": {
                "name": "兴百工",
                "desc": "奖掖工匠，兴修水利机械。",
                "power_level": 1,
                "duration": 3,
                "cost_per_month": 10000,
                "prereq": None,
                "unlock": "工坊",
                "effect": "science_eff",
                "narrative_memory": "奖掖民间匠巧与水利器械，开作坊于诸道，营造工技日新月异。",
            },
            "s2_calendar": {
                "name": "修历法",
                "desc": "校勘历法，精于天文。",
                "power_level": 2,
                "duration": 6,
                "cost_per_month": 20000,
                "prereq": "s1_tech",
                "unlock": "司天监",
                "effect": "science_eff",
                "narrative_memory": "司天监测定新历与仪象台，圭臬周全，节候大准，格物致知蔚然成风。",
            },
            "s3_west": {
                "name": "西学东渐",
                "desc": "聘西洋匠，开机器局。",
                "power_level": 3,
                "duration": 12,
                "cost_per_month": 50000,
                "prereq": "s2_calendar",
                "unlock": "机器局",
                "effect": "science_eff",
                "narrative_memory": "设机器局汇通西域与海外绝艺，制造重器推行水运机械，百工开化领袖寰宇。",
            },
        },
    },
    "internal": {
        "name": "内卫",
        "desc": "设密司，整肃言路，密探天下。",
        "nodes": {
            "i1_spy": {
                "name": "设皇城司",
                "desc": "设皇城司，刺探内外。",
                "power_level": 1,
                "duration": 3,
                "cost_per_month": 12000,
                "prereq": None,
                "unlock": "皇城司",
                "effect": "internal_eff",
                "narrative_memory": "皇城司缇骑四出，布密网于京华，内外奸伪莫能相欺，君侧隐患早察。",
            },
            "i2_censor": {
                "name": "整肃言路",
                "desc": "整肃台谏，钳制异论。",
                "power_level": 2,
                "duration": 6,
                "cost_per_month": 25000,
                "prereq": "i1_spy",
                "unlock": "御史台",
                "effect": "internal_eff",
                "narrative_memory": "台谏改制整饬，消解朋党倾轧与无端攻讦，清流杂音屏除，朝令得以一意贯通。",
            },
            "i3_control": {
                "name": "密探天下",
                "desc": "密探遍布，防患未然。",
                "power_level": 3,
                "duration": 12,
                "cost_per_month": 45000,
                "prereq": "i2_censor",
                "unlock": "密探网",
                "effect": "internal_eff",
                "narrative_memory": "密探网潜布天下诸路与外藩邸阁，巨细必报，内外叛乱异谋尽在圣裁洞烛之中。",
            },
        },
    },
    "tax": {
        "name": "税务",
        "desc": "清丈田亩，盐铁专卖，一条鞭法。",
        "nodes": {
            "t1_land_survey": {
                "name": "清丈田亩",
                "desc": "检括隐田，厘正田赋。",
                "power_level": 1,
                "duration": 3,
                "cost_per_month": 15000,
                "prereq": None,
                "unlock": "清册",
                "effect": "tax_eff",
                "narrative_memory": "诸路官吏清丈经界，搜剔地主隐瞒膏腴，鱼鳞图册大定，贫民免遭包税侵渔。",
            },
            "t2_salt_iron": {
                "name": "盐铁专卖",
                "desc": "盐铁官营，利归公帑。",
                "power_level": 2,
                "duration": 6,
                "cost_per_month": 30000,
                "prereq": "t1_land_survey",
                "unlock": "盐铁司",
                "effect": "tax_eff",
                "narrative_memory": "榷盐茶铁禁，严缉私枭，盐铁司归总泉流，国帑岁入倍增而利归朝廷。",
            },
            "t3_single_whip": {
                "name": "一条鞭法",
                "desc": "田赋折银，一条鞭征。",
                "power_level": 3,
                "duration": 12,
                "cost_per_month": 55000,
                "prereq": "t2_salt_iron",
                "unlock": "一条鞭",
                "effect": "tax_eff",
                "narrative_memory": "天下两税与赋役总括折银，行一条鞭之制，革除积年繁苛苛敛，财赋通达百世。",
            },
        },
    },
}

# 互斥分支：选择政务则军事降权，反之亦然（重文轻武 vs 重武轻文）
MUTUAL_EXCLUSIVE = {
    "govern": "military",
    "military": "govern",
}

# 分支 → 长期效果施加函数
_BRANCH_EFFECTS = {
    "govern": "govern_eff",
    "military": "military_eff",
    "science": "science_eff",
    "internal": "internal_eff",
    "tax": "tax_eff",
}


# ---------------------------------------------------------------------------
# 2. 初始化与查询
# ---------------------------------------------------------------------------

def init_focus_tree(state) -> None:
    """开局初始化国策树：全部分支未解锁，权力等级 0。"""
    state.focus_tree = {}
    for branch, spec in FOCUS_TREE.items():
        state.focus_tree[branch] = {
            "name": spec["name"],
            "desc": spec["desc"],
            "nodes": {
                nk: {
                    "name": nd["name"],
                    "desc": nd["desc"],
                    "power_level": 0,          # 0=未解锁，1~3=已解锁等级
                    "unlocked": False,
                    "unlock": nd.get("unlock", ""),
                    "duration": nd.get("duration", 3),
                    "cost_per_month": nd.get("cost_per_month", 10000),
                    "narrative_memory": nd.get("narrative_memory", ""),
                }
                for nk, nd in spec["nodes"].items()
            },
        }
    if not hasattr(state, "active_focus"):
        state.active_focus = None
    if not hasattr(state, "completed_focuses"):
        state.completed_focuses = []


def can_unlock(state, branch: str, node_key: str) -> tuple:
    """判断某节点是否可开启施行。返回 (可开办, 原因)。"""
    branch_spec = FOCUS_TREE.get(branch)
    if not branch_spec:
        return False, "无此分支"
    node_spec = branch_spec["nodes"].get(node_key)
    if not node_spec:
        return False, "无此节点"
    cur = state.focus_tree.get(branch, {}).get("nodes", {}).get(node_key, {})
    if cur.get("unlocked"):
        return False, "大策已成，毋庸再议"
    # 中枢当前是否已有在办大策
    active = getattr(state, "active_focus", None)
    if active and active.get("status") == "in_progress":
        if active.get("node_key") == node_key:
            return False, "此策方在推行施行之中"
        return False, f"中枢正全力施行【{active.get('name', '他策')}】，需待功成或降旨中止"
    # 前置节点检查
    prereq = node_spec.get("prereq")
    if prereq:
        pre = state.focus_tree.get(branch, {}).get("nodes", {}).get(prereq, {})
        if not pre.get("unlocked"):
            return False, f"需先功成「{FOCUS_TREE[branch]['nodes'][prereq]['name']}」"
    # 互斥分支：若互斥分支已解锁同等级或更高，则不可解锁
    mutex = MUTUAL_EXCLUSIVE.get(branch)
    if mutex:
        mutex_nodes = state.focus_tree.get(mutex, {}).get("nodes", {})
        if any(n.get("unlocked") for n in mutex_nodes.values()):
            return False, f"与「{FOCUS_TREE[mutex]['name']}」分支互斥"
    return True, ""


def start_focus(state, branch: str, node_key: str) -> dict:
    """下旨施行国策，挂载为中枢在办大策（历经时延推进）。"""
    ok, reason = can_unlock(state, branch, node_key)
    if not ok:
        return {"ok": False, "message": reason}
    node_spec = FOCUS_TREE[branch]["nodes"][node_key]
    total_turns = node_spec.get("duration", 3)
    cost = node_spec.get("cost_per_month", 10000)

    state.active_focus = {
        "branch": branch,
        "node_key": node_key,
        "name": node_spec["name"],
        "desc": node_spec["desc"],
        "power_level": node_spec["power_level"],
        "elapsed_turns": 0,
        "total_turns": total_turns,
        "progress": 0,
        "cost_per_month": cost,
        "status": "in_progress",
        "narrative_memory": node_spec.get("narrative_memory", ""),
    }
    return {
        "ok": True,
        "message": f"中枢已立案宣旨施行【{node_spec['name']}】，预计历时 {total_turns} 月，月耗度支约 {cost} 贯。",
        "active_focus": state.active_focus,
    }


def cancel_focus(state) -> dict:
    """中途撤回/中止正在施行的国策。"""
    active = getattr(state, "active_focus", None)
    if not active or active.get("status") != "in_progress":
        return {"ok": False, "message": "当前中枢无施行中的大策"}
    old_name = active.get("name", "国策")
    state.active_focus = None
    return {"ok": True, "message": f"已降旨停办【{old_name}】，中枢大政归于从容。"}


def unlock_focus(state, branch: str, node_key: str) -> dict:
    """兼容旧接口：直接转发至 start_focus。"""
    return start_focus(state, branch, node_key)


def _complete_focus(state, log, branch: str, node_key: str, node_spec: dict) -> None:
    """国策施行圆满完成：激活效果并深植 AI 长期记忆图谱。"""
    cur = state.focus_tree.get(branch, {}).get("nodes", {}).get(node_key, {})
    cur["unlocked"] = True
    cur["power_level"] = node_spec["power_level"]

    # 1. 施加解锁效果（建筑/科技）
    _apply_unlock(state, branch, node_key, node_spec)

    # 2. 沉淀进 completed_focuses 历史纪录
    history_entry = {
        "branch": branch,
        "node_key": node_key,
        "name": node_spec["name"],
        "power_level": node_spec["power_level"],
        "year": state.year,
        "month": state.month,
        "turn": state.turn,
        "narrative_memory": node_spec.get("narrative_memory", ""),
    }
    if not hasattr(state, "completed_focuses"):
        state.completed_focuses = []
    state.completed_focuses.append(history_entry)

    # 3. 沉淀至 MemoryGraph（图谱长期记忆）
    try:
        mem = getattr(state, "memory", None)
        if mem and hasattr(mem, "add_entity"):
            ent_id = f"focus_{branch}_{node_key}"
            mem_name = f"大策·{node_spec['name']}"
            desc = node_spec.get("narrative_memory", "") or node_spec.get("desc", "")
            mem.add_entity(ent_id, "decision", mem_name, attrs={"desc": desc}, turn=getattr(state, "turn", 0))
            if hasattr(mem, "add_relation"):
                mem.add_relation(ent_id, "song_empire", "governs", weight=2.0, turn=getattr(state, "turn", 0), note=f"施行{node_spec['name']}")
    except Exception:
        pass

    # 4. 广播纪年大事记
    log_msg = f"【基本国策告成】中枢历经数月经略，《{node_spec['name']}》大策告成！{node_spec.get('narrative_memory','')}"
    log.append(log_msg)
    state.active_focus = None


def _apply_unlock(state, branch, node_key, node_spec) -> None:
    """解锁建筑/长期效果：写入 state.tech.assets 或相关字段。"""
    unlock = node_spec.get("unlock", "")
    if not unlock:
        return
    # 写入科技资产（建筑/器物统一）
    try:
        state.tech.setdefault("assets", {})[f"focus_{branch}_{node_key}"] = {
            "name": unlock,
            "kind": "focus_building",
            "branch": branch,
            "node": node_key,
        }
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 3. 月度结算（长期效果施加）
# ---------------------------------------------------------------------------

def settle_focus(state, log) -> None:
    """月度结算：
    1. 推进正在施行的中枢国策进度，扣减相应月度度支；满期则触发大策告成并沉淀 AI 记忆。
    2. 对已施行完成的节点持续施加长期效果。
    """
    # 1. 推进在办国策进度
    active = getattr(state, "active_focus", None)
    if active and active.get("status") == "in_progress":
        branch = active.get("branch")
        node_key = active.get("node_key")
        node_spec = FOCUS_TREE.get(branch, {}).get("nodes", {}).get(node_key, {})
        cost = active.get("cost_per_month", 10000)

        # 扣除月度施行度支（若国库充足）
        if state.treasury >= cost:
            state.change_treasury(-cost)
            state.statistics["total_expense"] = state.statistics.get("total_expense", 0) + cost
        else:
            log.append(f"[国策度支] 国库紧绌，推行【{active.get('name')}】经费有所掣肘")

        active["elapsed_turns"] = active.get("elapsed_turns", 0) + 1
        tot = max(1, active.get("total_turns", 3))
        active["progress"] = min(100, int(active["elapsed_turns"] * 100 / tot))

        if active["elapsed_turns"] >= tot:
            # 功成圆满
            _complete_focus(state, log, branch, node_key, node_spec)
        else:
            left = tot - active["elapsed_turns"]
            log.append(f"[基本国策推进] 中枢推行【{active.get('name')}】进度已达 {active['progress']}%（尚余 {left} 月大成）")

    # 2. 已解锁大策长期效果结算
    if not state.focus_tree:
        return
    for branch, bspec in state.focus_tree.items():
        for nk, node in bspec.get("nodes", {}).items():
            if not node.get("unlocked"):
                continue
            eff = _BRANCH_EFFECTS.get(branch)
            if eff:
                _apply_branch_effect(state, log, branch, eff, node)


def _apply_branch_effect(state, log, branch, eff, node) -> None:
    """按分支施加长期效果（确定性修正，非守恒字段）。"""
    try:
        if branch == "govern":
            # 政务：裁汰冗费，财政减耗
            state.statistics["total_expense"] = max(
                0, state.statistics.get("total_expense", 0) - 5000)
        elif branch == "military":
            # 军事：军备增强（城防/军器）
            for line in state.defense_lines.values():
                line["fortification"] = min(100, line.get("fortification", 0) + 1)
        elif branch == "science":
            # 科学：技术积累提升
            state.tech["level"] = min(100, state.tech.get("level", 0) + 1)
        elif branch == "internal":
            # 内卫：民心微损（密探高压），但防患
            state.population_satisfaction = max(0, state.population_satisfaction - 1)
        elif branch == "tax":
            # 税务：清隐田，隐漏率下降
            state.land["hidden_rate"] = max(0.05, state.land.get("hidden_rate", 0.35) - 0.01)
    except Exception:
        pass


def focus_summary(state) -> dict:
    """返回国策树摘要（供 UI / 简报展示）。"""
    out = {}
    for branch, bspec in state.focus_tree.items():
        unlocked = [n for n in bspec.get("nodes", {}).values() if n.get("unlocked")]
        out[branch] = {
            "name": bspec["name"],
            "desc": bspec["desc"],
            "unlocked_count": len(unlocked),
            "total": len(bspec.get("nodes", {})),
            "unlocked": [n.get("name", "") for n in unlocked],
        }
    return out


__all__ = [
    "FOCUS_TREE", "MUTUAL_EXCLUSIVE", "init_focus_tree", "can_unlock",
    "start_focus", "cancel_focus", "unlock_focus", "settle_focus", "focus_summary",
]