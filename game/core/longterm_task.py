# -*- coding: utf-8 -*-
"""宋祚 · 长期事务支持模型（core/longterm_task.py）—— **唯一权威**

审查任务书（`game/游戏审查整改实施指南.md` P1-1）要求：
> 事务需要相关官员、机构或派系支持，圣旨影响支持与阻力，
> 最终结果由这些因素和执行过程决定；**禁止继续使用无因果关系的固定进度条**。

## 三条口径（本模块只做组装，不重算任何算法）

| 项 | 来源（唯一权威） |
|---|---|
| 执行能力（吏治强 / 民心·识字率弱 / 军队加成） | `core/decree_effect.effect_channels`（含 `core/clerks`、`core/literacy`、`core/army_models`） |
| 支持方 / 阻力方 | 既有**声明表**：`FACTION_POP_BASIS`（集团 ⊆ POP 阶级）＋ `REFORM_POP_BASIS`（改革 → POP 得失）＋ `YAMEN_INFO`（衙署主责派系） |
| 承办大臣 → 派系 | `core.officialdom.minister_faction`（查 `content.ministers.data.MINISTERS`，查不到 = None，不编造） |

## POP 挂载律（本模块不得违反）

本模块**不新开任何人口账本或钱粮账本**：只维护
`support_bonus`（一道已施行圣旨带来的政治支持标量，有上限、逐月衰减）与
`progress`（0–100 的成效度）。支持方/阻力方的"势力"一律**从既有 POP 基本盘与集团影响力现读**，
不复制、不另立存量。**不写 treasury / granary / POP.size / POP.wealth。**

## 缺失值口径

`effect_mult` 为 `None`（吏治读数缺失）时，本月**不推进**并在读数里标
`defined=False`、文案写"未定义"——**禁止回落 1.0 假装吏治完美**（见审查基准 §6）。
无任何声明立场时 `declared=False`，面板写"未声明立场"，**不编造支持者**。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from content.data import FACTION_POP_BASIS, REFORM_POP_BASIS, YAMEN_INFO
from core.numeric import clamp as _clamp, parse_number as _num

log = logging.getLogger("longterm_task")

__all__ = [
    "SUPPORT_PER_DECREE", "SUPPORT_BONUS_CAP", "SUPPORT_DECAY_PER_MONTH",
    "STANCE_MULT_MIN", "STANCE_MULT_MAX", "STALL_MONTHS_FAIL",
    "TASK_DECREE_KINDS", "ensure_task_schema", "normalize_tasks",
    "task_topic", "stance_of", "build_readout", "monthly_advance",
    "apply_decree_to_task", "issue_task_decree", "find_task", "task_queue",
    "TASK_HANDLERS", "handler_of", "task_is_supported",
]

# ------------------------------------------------------------
# 常量（单点；只在测试里 monkeypatch，面板/AI 只读）
# ------------------------------------------------------------
SUPPORT_PER_DECREE = 0.12        # 一道**已施行**圣旨给该事务的政治支持（受阻 = 0）
SUPPORT_BONUS_CAP = 0.30         # 圣旨支持累计上限（继续颁诏不再叠加，防"越颁越强"）
SUPPORT_DECAY_PER_MONTH = 0.02   # 支持逐月衰减：圣意须持续，否则惯性与阻力重新占上风
STANCE_MULT_MIN = 0.25           # 立场系数下界（阻力极大 → 事倍功半，但不归零）
STANCE_MULT_MAX = 1.75           # 立场系数上界
NET_SUPPORT_WEIGHT = 0.5         # 净立场对推进速度的权重
STALL_MONTHS_FAIL = 6            # 连续 6 个月无实质推进 → 罢废（失败条件，可解释）
MIN_MEANINGFUL_ADVANCE = 0.05    # %/月；低于此视为"无实质推进"
DECREE_HISTORY_KEEP = 5
SUPPORT_LOG_KEEP = 8

#: 圣旨三通道（对同一事务，三者**成本与效果确有差异**；均不保证成功）
#:   · 督行诏 —— 常规督责：成本最低（皇威 −1），支持增量 ×1.0
#:   · 调兵督行 —— 民政事务调兵强制施行：成本较高（皇威 −2），支持增量 ×1.2，
#:     且本回合军队通道参与（**加成**，绝不比不调兵差；用户定稿口径）
#:   · 御笔中旨 —— 绕过会签：成本最高（皇威 −3），支持增量 ×0.8（不公开，官场不买账），
#:     执行率按机构归属另算（`ZHONGZHI_AFFILIATION_RATE`，见 `calc_decree_execution_rate`）
TASK_DECREE_KINDS: Dict[str, Dict[str, Any]] = {
    "督行": {"label": "督行诏", "prestige_cost": 1, "support_mult": 1.0,
             "enforce_troops": False, "zhongzhi": False,
             "desc": "明诏督责有司奉行"},
    "调兵督行": {"label": "调兵督行", "prestige_cost": 2, "support_mult": 1.2,
                 "enforce_troops": True, "zhongzhi": False,
                 "desc": "调兵强制施行（民政事务的杠杆）"},
    "御笔中旨": {"label": "御笔中旨", "prestige_cost": 3, "support_mult": 0.8,
                 "enforce_troops": False, "zhongzhi": True,
                 "desc": "御笔直发、绕过会签"},
}

# ------------------------------------------------------------
# 议题桥：事务 → `REFORM_POP_BASIS` 的**已声明**改革键
# ------------------------------------------------------------
# 说明（诚实标注其性质）：`REFORM_POP_BASIS` 的键是「诏令效果键 / 国策 node_key」，
# 而长期事务只带标题与摘要文本，两者之间没有现成的机器可读映射，故此处用**关键词桥**
# 把事务文本对到已声明的改革得失上。它是启发式、单一处声明、可审计：
#   · 命中 → 面板 reason 明写"按《<该改革 label>》POP 得失声明"；
#   · 未命中 → `declared=False`，面板写"未声明立场"，**不编造支持者**。
_TOPIC_BRIDGE: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("land_survey", ("清丈", "方田", "均税", "隐田", "田亩", "手实", "推排")),
    ("curtail_waste", ("省浮费", "浮费", "冗费", "节流", "省费")),
    ("reduce_office", ("裁汰冗员", "裁冗", "冗官", "省官", "并职", "并省")),
    ("reform", ("官制", "改制", "更张", "新制", "法度")),
    # 注意：键须是 `REFORM_POP_BASIS` 的**真实主键**（`m1_garrison` 与 `m3_war_machine`
    # 同指「整军经武」声明；此处取前者为规范键，`task_topic` 会校验存在性）。
    ("m1_garrison", ("整军", "经武", "军备", "军器", "练军", "整练", "置将", "边备", "武备")),
)

#: 议题键（`REFORM_POP_BASIS` 的主键）→ 中文议题名（面板/AI 文案用；找不到则用表内 label）
_TOPIC_LABEL = {
    "land_survey": "方田均税（清丈隐田）",
    "curtail_waste": "裁汰冗费（省浮节流）",
    "reduce_office": "省官并职（裁并机构）",
    "reform": "更张法度（官制改革）",
    "m1_garrison": "整军经武（边备与军器）",
}

# ============================================================
# 事务 **handler 注册表**（规格 decree-action-chain 任务 4）
# ============================================================
# 规格要求（`design.md:47`）：**未绑定 handler 的事务应标为"未执行/待支持"，
# 不能只累进度就宣称告成**。
#
# 这里登记的是"该议题在**程序侧**到底把哪些数值改了、在哪段代码里改的"——
# 只登记**能在代码里指出落点**的议题；指不出来的**一律不登记**，
# 从而在满进度时被判「待支持」而不是「告成」（拒绝式，符合硬约束 #3）。
#
# `applied_at` 语义（重要，勿误读）：
#   · `"issue"`          效果在**下诏当时**即落地（`_apply_decree_effect`），
#                        事务进度是**政治推进轨道**，不是效果的开关；
#   · `"issue+monthly"`  下诏时建立制度，之后**逐月**持续生效（如省浮费）。
# 面板/文书据此如实表述"数字何时动过"，不得把政治轨道说成数值开关。
TASK_HANDLERS: Dict[str, Dict[str, Any]] = {
    "land_survey": {
        "applied_at": "issue",
        "landing": "state.land['hidden_rate'] 下降 + 隐田转正/士绅退田/士绅吐粮（钱粮守恒）",
        "code": "core/settlement_decree.py::_apply_decree_effect（land_survey 分支）",
    },
    "curtail_waste": {
        "applied_at": "issue+monthly",
        "landing": "state.waste_reform（target/months_left）→ settlement_finance 逐月省浮费",
        "code": "core/settlement_decree.py::_apply_decree_effect + core/settlement_finance.py（waste_reform）",
    },
    "reduce_office": {
        "applied_at": "issue+monthly",
        "landing": "state.waste_reform ＋ 官僚 POP 裁 5% 转士绅（ΣPOP 守恒）",
        "code": "core/settlement_decree.py::_apply_decree_effect + core/officialdom.remove_officials",
    },
    "reform": {
        "applied_at": "issue",
        "landing": "state.central_orgs 机构改制落地",
        "code": "core/settlement_decree.py::_apply_decree_effect（reform_org 分支）",
    },
    # 注意：**`m1_garrison` 刻意不登记** —— 它只参与 `REFORM_POP_BASIS` 的立场计算，
    # 全库没有任何数值落点（无消费方）。故「整军经武」类事务满进度时判**待支持**。
}


def handler_of(task: dict) -> Optional[Dict[str, Any]]:
    """该事务绑定的程序侧落点；**没有则返回 None**（不是空 dict，也不是默认值）。"""
    topic = task_topic(task) if isinstance(task, dict) else None
    if not topic:
        return None
    h = TASK_HANDLERS.get(topic)
    return dict(h, topic=topic) if isinstance(h, dict) else None


def task_is_supported(task: dict) -> bool:
    """该事务是否绑定程序侧落点（供面板/AI/结算**单点**查询）。"""
    return handler_of(task) is not None


#: 旧公式的难度成长因子同源常量（保持难度曲线连续：原 `0.8 + 0.4 * external_growth`）
_GROWTH_BASE, _GROWTH_W = 0.8, 0.4

_SCHEMA_FIELDS = ("id", "progress", "months", "support_log", "support_bonus",
                  "stall_months", "outcome", "decree_count", "decree_history",
                  "troops_enforced_turn", "readout")


# ============================================================
# 存档兼容：幂等补齐 + 坏条目隔离
# ============================================================
def task_queue(state, is_secret: bool) -> list:
    """该事务所属队列（公开 / 密令）。"""
    return state.longterm_secret if is_secret else state.longterm_public


def find_task(state, task_id: str) -> Optional[dict]:
    """按 id 在两队列中找事务；找不到返回 None（不编造）。"""
    if not task_id:
        return None
    for queue in (getattr(state, "longterm_public", None) or [],
                  getattr(state, "longterm_secret", None) or []):
        for t in queue:
            if isinstance(t, dict) and t.get("id") == task_id:
                return t
    return None


def _stable_id(task: dict, index: int, is_secret: bool) -> str:
    """旧档事务**无 id** → 按队列位置派生稳定 id（落档后即固定，不再漂移）。"""
    return f"lt{'s' if is_secret else 'p'}{index + 1}"


def _infer_org(task: dict) -> str:
    """推断主责衙署（启发式、保守）：显式 org_hint → 六部 acts 关键词 → 文本含部名 → "政府"。"""
    hint = str(task.get("org_hint") or "").strip()
    if hint:
        return hint
    text = "".join(str(task.get(k) or "") for k in ("task_name", "title", "summary", "desc"))
    for yamen, info in YAMEN_INFO.items():
        for act in (info.get("acts") or []):
            if act and str(act) in text:
                return yamen
    for yamen in YAMEN_INFO:
        if yamen in text:
            return yamen
    return "政府"


def ensure_task_schema(state, task: dict, *, index: int = 0, is_secret: bool = False) -> bool:
    """**幂等**补齐事务字段（旧档安全默认值）；返回是否发生过补齐。"""
    if not isinstance(task, dict):                      # 坏条目由 normalize_tasks 隔离
        return False
    before = len(task)
    name = task.get("task_name") or task.get("title") or "政务"
    task.setdefault("id", _stable_id(task, index, is_secret))
    task.setdefault("progress", 0)
    if task.get("months") is None and isinstance(task.get("task"), dict):
        task["months"] = task["task"].get("months")
    task.setdefault("months", 18)
    task.setdefault("org_hint", _infer_org(task))
    task.setdefault("goal", str(task.get("summary") or f"办成「{name}」并见实效"))
    task.setdefault("success_condition",
                    "成效满 100%（按月由支持方/阻力方与执行能力推进，非按时间自动完成）")
    task.setdefault("support_log", [])
    task.setdefault("support_bonus", 0.0)
    task.setdefault("stall_months", 0)
    task.setdefault("outcome", "在办")
    task.setdefault("decree_count", 0)
    task.setdefault("decree_history", [])
    task.setdefault("troops_enforced_turn", -1)
    task.setdefault("last_change", "已立案，待下月奉行。")
    # 坏值归一（旧档可能被写坏）——不抛异常，不放行非法值。
    # 注意 `progress` 保留小数（月度推进量为亚百分点级，取整会丢掉推进）。
    task["progress"] = round(_clamp(_num(task.get("progress"), 0.0), 0.0, 100.0), 4)
    for key in ("months", "stall_months", "decree_count"):
        task[key] = int(_clamp(_num(task.get(key), 0), 0, 240))
    task["support_bonus"] = round(_clamp(_num(task.get("support_bonus"), 0.0),
                                         0.0, SUPPORT_BONUS_CAP), 4)
    if not isinstance(task.get("support_log"), list):
        task["support_log"] = []
    if not isinstance(task.get("decree_history"), list):
        task["decree_history"] = []
    for key in ("last_change", "outcome", "goal", "success_condition", "org_hint"):
        if not isinstance(task.get(key), str):
            task[key] = str(task.get(key) or "")
    if not isinstance(task.get("readout"), dict):
        task["readout"] = None
    return len(task) != before


def normalize_tasks(state, log_list: Optional[list] = None) -> Dict[str, Any]:
    """两队列全量迁移：非 dict 条目**隔离**（记 warning，不拒档）＋逐条幂等补齐。

    返回 `{"migrated": n, "isolated": n, "ids": [...]}`（供测试与诊断）。
    """
    migrated = isolated = 0
    ids: List[str] = []
    for is_secret, attr in ((False, "longterm_public"), (True, "longterm_secret")):
        queue = getattr(state, attr, None)
        if not isinstance(queue, list):
            setattr(state, attr, [])
            continue
        keep = []
        for i, t in enumerate(list(queue)):
            if not isinstance(t, dict):
                isolated += 1
                log.warning("[事务] 坏条目已隔离（%s[%d] 类型 %s）", attr, i, type(t).__name__)
                if log_list is not None:
                    log_list.append(f"[事务] 存档坏条目已隔离（{attr}[{i}]），未影响其余事务。")
                continue
            if ensure_task_schema(state, t, index=len(keep), is_secret=is_secret):
                migrated += 1
            ids.append(str(t.get("id")))
            keep.append(t)
        queue[:] = keep
        # id 重复（旧档手工编辑/迁移残留）→ 重新编号，避免"圣旨打到别的事务"
        seen = set()
        for i, t in enumerate(queue):
            if t.get("id") in seen:
                t["id"] = f"{_stable_id(t, i, is_secret)}x"
            seen.add(t.get("id"))
    return {"migrated": migrated, "isolated": isolated, "ids": ids}


# ============================================================
# 支持方 / 阻力方（全部来自既有声明表）
# ============================================================
def task_topic(task: dict) -> Optional[str]:
    """事务 → 已声明改革键（`REFORM_POP_BASIS` 主键）；无命中返回 None（不猜）。"""
    text = "".join(str(task.get(k) or "") for k in
                   ("task_name", "title", "summary", "desc", "goal"))
    for key, kws in _TOPIC_BRIDGE:
        if key not in REFORM_POP_BASIS:
            continue
        if any(kw in text for kw in kws):
            return key
    return None


def _redline_hit(text: str, spec: dict) -> Optional[str]:
    """红线命中（保守启发式）：红线的**首二字动宾头 + 末二字对象**同时出现才算命中。

    取「头+尾」而不是任意 2-gram，是为了避免把「推行**新法**」误判成新党的红线
    「废署新法」（该红线要求同时出现「废署」）。命中即公开反对（阻力）。
    """
    for rl in (spec.get("red_lines") or []):
        rl = str(rl or "")
        if len(rl) < 4:
            if rl and rl in text:
                return rl
            continue
        if rl[:2] in text and rl[-2:] in text:
            return rl
    return None


def _faction_classes(fn: str) -> List[str]:
    spec = FACTION_POP_BASIS.get(fn) or {}
    return [c for c in (spec.get("pop_classes") or []) if c]


def stance_of(state, task: dict) -> Dict[str, Any]:
    """事务的支持方/阻力方读数（只读；缺声明即 `declared=False`，不编造）。"""
    factions = getattr(state, "factions", None) or {}
    supporters: List[Dict[str, Any]] = []
    opposers: List[Dict[str, Any]] = []
    declared = False

    topic = task_topic(task)
    spec = REFORM_POP_BASIS.get(topic) if topic else None
    topic_label = _TOPIC_LABEL.get(topic or "", (spec or {}).get("label") if spec else None)
    gain_classes = {str(g.get("class")) for g in ((spec or {}).get("gain") or [])}
    lose_classes = {str(l.get("class")) for l in ((spec or {}).get("lose") or [])}
    gain_why = {str(g.get("class")): str(g.get("why") or "") for g in ((spec or {}).get("gain") or [])}
    lose_why = {str(l.get("class")): str(l.get("why") or "") for l in ((spec or {}).get("lose") or [])}

    if spec:
        declared = True
        for fn, f in factions.items():
            if not isinstance(f, dict):
                continue
            inf = _num(f.get("influence"), 0.0)
            classes = _faction_classes(fn)
            gain_hit = [c for c in classes if c in gain_classes]
            lose_hit = [c for c in classes if c in lose_classes]
            # 红线命中 → 公开反对（阻力），优先级高于"基本盘受益"
            rl = _redline_hit("".join(str(task.get(k) or "") for k in
                                      ("task_name", "title", "summary", "desc")),
                              FACTION_POP_BASIS.get(fn) or {})
            if rl:
                declared = True
                opposers.append({
                    "name": fn, "influence": round(inf, 2),
                    "reason": f"触其红线「{rl}」，公开反对（按 {fn} 声明）",
                })
                continue
            if len(gain_hit) > len(lose_hit):
                why = "；".join(gain_why.get(c, "") for c in gain_hit if gain_why.get(c))
                supporters.append({
                    "name": fn, "influence": round(inf, 2),
                    "reason": f"基本盘 {'/'.join(gain_hit)} 受益"
                              + (f"（{why}）" if why else "")
                              + f"——按《{topic_label}》POP 得失声明",
                })
            elif len(lose_hit) > len(gain_hit):
                why = "；".join(lose_why.get(c, "") for c in lose_hit if lose_why.get(c))
                opposers.append({
                    "name": fn, "influence": round(inf, 2),
                    "reason": f"基本盘 {'/'.join(lose_hit)} 受损"
                              + (f"（{why}）" if why else "")
                              + f"——按《{topic_label}》POP 得失声明",
                })

    # 衙署主责派系（YAMEN_INFO 声明）→ 支持方
    org = str(task.get("org_hint") or "")
    yamen_faction = ((YAMEN_INFO.get(org) or {}).get("faction") if org else None)
    if yamen_faction:
        declared = True
        sup = next((s for s in supporters if s["name"] == yamen_faction), None)
        _inf = _num(((factions.get(yamen_faction) or {}) if isinstance(
            factions.get(yamen_faction), dict) else {}).get("influence"), 0.0)
        if sup:
            sup["reason"] += f"；且{org}主责"
        else:
            supporters.append({
                "name": yamen_faction, "influence": round(_inf, 2),
                "reason": f"{org}主责，本派（按 YAMEN_INFO 声明）力主",
            })

    # 承办大臣所属派系 → 支持方
    minister = str(task.get("minister") or "").strip()
    if minister:
        try:
            from core.officialdom import minister_faction
            mf = minister_faction(minister)
        except Exception as e:  # noqa: BLE001  派系查不到不得阻断事务结算
            log.debug("[事务] 承办大臣派系解析失败：%s", e)
            mf = None
        if mf:
            declared = True
            if not any(s["name"] == mf for s in supporters):
                _inf = _num(((factions.get(mf) or {}) if isinstance(
                    factions.get(mf), dict) else {}).get("influence"), 0.0)
                supporters.append({
                    "name": mf, "influence": round(_inf, 2),
                    "reason": f"承办大臣 {minister} 出身该派（按 MINISTERS 声明）",
                })

    sup_names = {s["name"] for s in supporters}
    opposers = [o for o in opposers if o["name"] not in sup_names]   # 同一派不得两面都算
    sup_inf = sum(_num(s.get("influence"), 0.0) for s in supporters)
    opp_inf = sum(_num(o.get("influence"), 0.0) for o in opposers)
    net = _clamp((sup_inf - opp_inf) / 100.0, -1.0, 1.0)
    supporters.sort(key=lambda s: -_num(s.get("influence"), 0.0))
    opposers.sort(key=lambda o: -_num(o.get("influence"), 0.0))
    return {
        "topic": topic, "topic_label": topic_label,
        "declared": declared,
        "supporters": supporters, "opposers": opposers,
        "support_influence": round(sup_inf, 2), "oppose_influence": round(opp_inf, 2),
        "net": round(net, 4),
        "note": ("支持/阻力取自既有声明表（FACTION_POP_BASIS / REFORM_POP_BASIS / YAMEN_INFO）"
                 if declared else
                 "未声明立场：本事务未命中任何既有 POP 得失声明（不编造支持者），"
                 "仅按官场配合度与执行能力推进"),
    }


# ============================================================
# 推进公式（与旧公式同源的难度因子；缺失即"未定义"）
# ============================================================
def _channels(state, task: dict) -> Dict[str, Any]:
    """执行能力三通道读数（委托 `core/decree_effect` 单一权威）。"""
    from core.decree_effect import effect_channels, decree_kind
    org = str(task.get("org_hint") or "")
    text = "".join(str(task.get(k) or "") for k in ("task_name", "title", "summary", "desc"))
    route = str(task.get("route") or "") or None
    enforce = task.get("troops_enforced_turn") == getattr(state, "turn", -1)
    kind = decree_kind(org, text)
    return effect_channels(state, org_hint=org, text=text, route=route, kind=kind,
                           enforce_troops=bool(enforce))


def _advance_amount(state, task: dict, channels: Dict[str, Any], stance: Dict[str, Any]
                    ) -> Tuple[Optional[float], Dict[str, Any]]:
    """本月推进量（%）。`data["defined"]=False` 表示吏治读数缺失 → 返回 None（不推进）。"""
    months = max(1, int(_num(task.get("months"), 18)))
    growth = ((getattr(state, "difficulty_presets", None) or {})
              .get(getattr(state, "difficulty", "史实"), {}) or {}).get("external_growth", 1.0)
    growth_mult = _GROWTH_BASE + _GROWTH_W * _num(growth, 1.0)
    base = 100.0 / months
    eff = channels.get("effect_mult")
    support_bonus = _num(task.get("support_bonus"), 0.0)
    stance_mult = _clamp(1.0 + NET_SUPPORT_WEIGHT * _num(stance.get("net"), 0.0) + support_bonus,
                         STANCE_MULT_MIN, STANCE_MULT_MAX)
    data = {"base_pct": round(base, 4), "growth_mult": round(growth_mult, 4),
            "effect_mult": eff, "stance_mult": round(stance_mult, 4),
            "support_bonus": round(support_bonus, 4),
            "net_support": round(_num(stance.get("net"), 0.0), 4)}
    if eff is None:
        data["defined"] = False
        return None, data
    data["defined"] = True
    return round(base * growth_mult * _num(eff, 0.0) * stance_mult, 4), data


def _stage(progress: float) -> str:
    if progress >= 100:
        return "告成"
    if progress >= 75:
        return "将成"
    if progress >= 40:
        return "成效渐著"
    if progress > 0:
        return "推行中"
    return "立案待行"


def _obstruction(state, task: dict, channels: Dict[str, Any], stance: Dict[str, Any]) -> Dict[str, Any]:
    """当前阻碍（可诊断：吏治折扣 / 民心·识字率 / 军队是否参与 / 阻力方）。"""
    blockers: List[str] = []
    mil = channels.get("military") or {}
    clerks_mult = channels.get("clerks_mult")
    if not channels.get("defined") or clerks_mult is None:
        blockers.append("吏治读数缺失（未定义）→ 政令无法评估执行能力")
    else:
        blockers.append(f"吏治（强关联）折扣 ×{_num(clerks_mult, 1.0):.2f}"
                        f"（{(channels.get('clerks') or {}).get('quality') or '—'}）")
    civil = channels.get("civil_mult")
    if civil is not None:
        blockers.append(f"民心/识字率（弱关联）×{_num(civil, 1.0):.2f}")
    if mil.get("applies"):
        if mil.get("mult") is None:
            blockers.append("军队本应参与，但无驻军读数（未计入）")
        else:
            blockers.append(f"军队督行加成 ×{_num(mil.get('mult'), 1.0):.2f}"
                            f"（{'军政类天然参与' if channels.get('kind') == '军政' else '本回合调兵强制施行'}）")
    else:
        blockers.append("军队不参与（民政事务，未调兵）")
    for o in (stance.get("opposers") or [])[:3]:
        blockers.append(f"{o['name']} 反对（影响力 {o['influence']}）：{o['reason']}")
    return {
        "defined": bool(channels.get("defined")),
        "clerks_mult": clerks_mult, "clerks_quality": (channels.get("clerks") or {}).get("quality"),
        "civil_mult": civil, "literacy": channels.get("literacy"),
        "kind": channels.get("kind"),
        "military_applies": bool(mil.get("applies")), "army_mult": mil.get("mult"),
        "blockers": blockers,
        "note": channels.get("note"),
    }


def build_readout(state, task: dict, *, channels: Optional[Dict[str, Any]] = None,
                  stance: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """面板/AI 只读读数（全部由本模块算好，**前端不复制算法**）。"""
    channels = channels if channels is not None else _channels(state, task)
    stance = stance if stance is not None else stance_of(state, task)
    advance, data = _advance_amount(state, task, channels, stance)
    progress = _num(task.get("progress"), 0.0)
    if data["defined"] and advance is not None:
        forecast = {
            "advance_pct": advance,
            "text": (f"按本月读数，下月约推进 {advance:.2f}%"
                     f"（基数 {data['base_pct']:.2f}% × 难度 {data['growth_mult']:.2f}"
                     f" × 执行 {_num(data['effect_mult'], 0.0):.2f}"
                     f" × 立场 {data['stance_mult']:.2f}）"),
        }
    else:
        forecast = {"advance_pct": None,
                    "text": "吏治读数缺失（未定义）→ 无法预判，本月不推进（不伪造）"}
    goal = str(task.get("goal") or "")
    return {
        "id": task.get("id"), "name": str(task.get("task_name") or task.get("title") or "政务"),
        "goal": goal, "success_condition": str(task.get("success_condition") or ""),
        "org_hint": task.get("org_hint"), "minister": task.get("minister") or "—",
        "topic": stance.get("topic"), "topic_label": stance.get("topic_label"),
        "kind": channels.get("kind"),
        "stage": _stage(progress), "progress": round(progress, 2),
        "months": int(_num(task.get("months"), 18)),
        "supporters": stance.get("supporters") or [],
        "opposers": stance.get("opposers") or [],
        "stance_declared": bool(stance.get("declared")), "stance_note": stance.get("note"),
        "support_net": stance.get("net"), "support_bonus": data["support_bonus"],
        "stance_mult": data["stance_mult"],
        "obstruction": _obstruction(state, task, channels, stance),
        "forecast": forecast,
        "last_change": str(task.get("last_change") or ""),
        "support_log": list(task.get("support_log") or [])[-SUPPORT_LOG_KEEP:],
        "decree_history": list(task.get("decree_history") or [])[-DECREE_HISTORY_KEEP:],
        "decree_count": int(_num(task.get("decree_count"), 0)),
        "stall_months": int(_num(task.get("stall_months"), 0)),
        "outcome": str(task.get("outcome") or "在办"),
    }


# ============================================================
# 月度推进（替换"固定进度条"）
# ============================================================
def monthly_advance(state, task: dict, log_list: list, *, is_secret: bool = False,
                    index: int = 0) -> Dict[str, Any]:
    """按「支持 − 阻力 × 执行能力」推进一个月；返回 `{status, name, advance, ...}`。

    `status`：`"ongoing"` 在办 / `"done"` 告成（进度满 100）/ `"failed"` 受阻罢废
    （连续 `STALL_MONTHS_FAIL` 个月无实质推进）。**两者都会写明原因。**
    """
    ensure_task_schema(state, task, index=index, is_secret=is_secret)
    name = str(task.get("task_name") or task.get("title") or "政务")
    channels = _channels(state, task)
    stance = stance_of(state, task)
    advance, data = _advance_amount(state, task, channels, stance)

    # 圣旨支持逐月衰减（有下限 0）；本回合调兵标记只对本月有效
    task["support_bonus"] = round(max(0.0, _num(task.get("support_bonus"), 0.0)
                                      - SUPPORT_DECAY_PER_MONTH), 4)
    if task.get("troops_enforced_turn") != getattr(state, "turn", -1):
        task["troops_enforced_turn"] = -1

    if advance is None:
        # **缺失 ≠ 完美**：吏治读数缺失 → 本月不推进，明确写"未定义"，不伪造推进
        task["stall_months"] = int(_num(task.get("stall_months"), 0)) + 1
        task["last_change"] = "吏治读数缺失（未定义）→ 本月不推进，成效未变（不伪造）"
        _append_support_log(task, {"turn": getattr(state, "turn", 0), "kind": "未定义",
                                   "cause": "吏治读数缺失", "delta": 0.0,
                                   "note": task["last_change"]})
        # 缺失也必须**在月志里可见**（不得静默不推进）
        log_list.append(f"[事务] {name}：{task['last_change']}")
        task["readout"] = build_readout(state, task, channels=channels, stance=stance)
        _maybe_fail(task, log_list, name)
        return {"status": task.get("outcome") == "受阻罢废" and "failed" or "ongoing",
                "name": name, "advance": 0.0, "defined": False}

    old = _num(task.get("progress"), 0.0)
    task["progress"] = round(_clamp(old + advance, 0.0, 100.0), 4)
    if advance <= MIN_MEANINGFUL_ADVANCE:
        task["stall_months"] = int(_num(task.get("stall_months"), 0)) + 1
    else:
        task["stall_months"] = 0

    sup_txt = "、".join(s["name"] for s in (stance.get("supporters") or [])[:2]) or "无声明支持方"
    opp_txt = "、".join(o["name"] for o in (stance.get("opposers") or [])[:2]) or "无声明阻力方"
    cause = (f"执行 ×{_num(data['effect_mult'], 0.0):.2f}"
             f"（吏治 ×{_num(channels.get('clerks_mult'), 1.0):.2f}"
             f" · 民心/识字率 ×{_num(channels.get('civil_mult'), 1.0):.2f}"
             f"{' · 军队督行 ×%.2f' % _num((channels.get('military') or {}).get('mult'), 1.0) if (channels.get('military') or {}).get('mult') is not None else ''}）"
             f" × 立场 ×{_num(data['stance_mult'], 1.0):.2f}"
             f"（净支持 {_num(data['net_support'], 0.0):+.2f}；支持方 {sup_txt}，阻力方 {opp_txt}）")
    task["last_change"] = (f"本月推进 {advance:.2f}%（{old:.1f}% → {task['progress']:.1f}%）：{cause}"
                           if advance > 0 else
                           f"本月无实质推进（{task['progress']:.1f}%）：{cause}")
    _append_support_log(task, {"turn": getattr(state, "turn", 0), "kind": "月度",
                               "cause": "支持−阻力×执行能力", "delta": round(advance, 3),
                               "note": task["last_change"]})
    task["readout"] = build_readout(state, task, channels=channels, stance=stance)
    log_list.append(f"[事务] {name}：{task['last_change']}")

    if task["progress"] >= 100.0:
        # 规格任务 4：**满进度 ≠ 效果落地**。只有绑定了程序侧落点（handler）的事务
        # 才能宣称「告成」；未绑定的据实标为「待支持」（不执行、不伪报）。
        _h = handler_of(task)
        if _h is None:
            task["outcome"] = "待支持"
            task["unsupported_reason"] = (
                "该事务未绑定程序侧落点（无 handler）：进度已满，但没有任何数值随之改变，"
                "故**不计为告成**，标为待支持/未执行")
            task["readout"] = build_readout(state, task, channels=channels, stance=stance)
            log_list.append(f"[事务] {name}：议毕（进度 {task['progress']:.0f}%），"
                            f"但**未绑定程序侧落点 → 待支持**（不宣告成、不改数值）")
            return {"status": "unsupported", "name": name, "advance": advance,
                    "defined": True, "handler": None,
                    "reason": task["unsupported_reason"]}
        task["outcome"] = "告成"
        task["handler"] = _h
        return {"status": "done", "name": name, "advance": advance, "defined": True,
                "handler": _h}
    if _maybe_fail(task, log_list, name):
        return {"status": "failed", "name": name, "advance": advance, "defined": True}
    return {"status": "ongoing", "name": name, "advance": advance, "defined": True}


def _maybe_fail(task: dict, log_list: list, name: str) -> bool:
    """失败条件：连续 `STALL_MONTHS_FAIL` 月无实质推进 → 罢废（写明原因，不静默丢弃）。"""
    if int(_num(task.get("stall_months"), 0)) < STALL_MONTHS_FAIL:
        return False
    task["outcome"] = "受阻罢废"
    note = (f"[事务] {name} 连月无实质推进（{STALL_MONTHS_FAIL} 个月），"
            f"事遂中辍、罢废销案。原因：{task.get('last_change', '')}")
    task["last_change"] = note
    log_list.append(note)
    return True


def _append_support_log(task: dict, entry: dict) -> None:
    rows = task.get("support_log")
    if not isinstance(rows, list):
        rows = []
    rows.append(entry)
    task["support_log"] = rows[-SUPPORT_LOG_KEEP:]


# ============================================================
# 圣旨 → 事务（因果留痕；颁旨 ≠ 成功）
# ============================================================
def apply_decree_to_task(state, decree: dict, executed: bool, log_list: list,
                         rate: float = 0.0) -> None:
    """把一道**已结算**的诏令结果落到其关联事务：支持增减 + 因果留痕。

    只有事务关联诏令（`decree["task_id"]`）才生效；普通诏令不受影响。
    **`executed=False`（执行受阻）→ 支持增量为 0**——这正是"颁旨不等于成功"。
    """
    tid = decree.get("task_id")
    if not tid:
        return
    task = find_task(state, str(tid))
    if task is None:
        log_list.append(f"[事务] 圣旨「{decree.get('title', '')}」所指事务已结案/不存在，未计入支持。")
        return
    ensure_task_schema(state, task)
    meta = decree.get("task_decree") if isinstance(decree.get("task_decree"), dict) else {}
    kind = str(meta.get("kind") or "督行")
    spec = TASK_DECREE_KINDS.get(kind) or TASK_DECREE_KINDS["督行"]
    name = str(task.get("task_name") or task.get("title") or "政务")
    delta = round(SUPPORT_PER_DECREE * _num(spec.get("support_mult"), 1.0) * (1.0 if executed else 0.0), 4)
    before = _num(task.get("support_bonus"), 0.0)
    task["support_bonus"] = round(min(SUPPORT_BONUS_CAP, before + delta), 4)
    capped = (before + delta) > SUPPORT_BONUS_CAP + 1e-9
    if spec.get("enforce_troops") and executed:
        task["troops_enforced_turn"] = getattr(state, "turn", -1)
    task["decree_count"] = int(_num(task.get("decree_count"), 0)) + 1
    entry = {
        "turn": getattr(state, "turn", 0),
        "title": str(decree.get("title") or spec.get("label") or "圣旨"),
        "kind": kind, "target": str(meta.get("target") or "有司"),
        "executed": bool(executed), "rate": round(_num(rate, 0.0), 3),
        "support_delta": delta,
        "note": (f"{spec.get('label')}已施行（执行率 {_num(rate, 0.0):.0%}），支持 +{delta:.2f}"
                 if executed else
                 f"{spec.get('label')}执行受阻（执行率 {_num(rate, 0.0):.0%}），支持未增"),
    }
    rows = task.get("decree_history")
    if not isinstance(rows, list):
        rows = []
    rows.append(entry)
    task["decree_history"] = rows[-DECREE_HISTORY_KEEP:]
    task["last_change"] = (f"〔圣旨〕{entry['title']}（{spec.get('label')}）"
                           f"{'已施行' if executed else '受阻'}：支持 "
                           f"{before:.2f} → {task['support_bonus']:.2f}"
                           + ("（已至支持上限，不再叠加）" if capped and delta > 0 else "")
                           + f"，本月军队{'督行' if entry['kind'] == '调兵督行' and executed else '未参与'}")
    log_list.append(f"[事务] {name}：{task['last_change']}")
    task["readout"] = build_readout(state, task)


def issue_task_decree(state, task_id: str, kind: str = "督行",
                      target: str = "", title: str = "") -> str:
    """针对某在办事务颁旨（走**既有诏令通道**：占带宽、经会签、受吏治折扣、随月结算）。

    三通道成本与效果确有差异（`TASK_DECREE_KINDS`）；**不保证成功**——
    执行率仍由 `calc_decree_execution_rate`（会签/机构归属）× 吏治折扣决定。
    """
    task = find_task(state, task_id)
    if task is None:
        return "无此在办事务（可能已结案）。"
    spec = TASK_DECREE_KINDS.get(kind)
    if spec is None:
        return f"未知颁旨方式：{kind}（可选：{'、'.join(TASK_DECREE_KINDS)}）。"
    # 未决呈请守卫（与 `issue_decree` / `issue_free_decree` 同款契约）
    _pending = [a for a in (getattr(state, "ai_pending_actions", None) or [])
                if isinstance(a, dict) and a.get("status") == "pending"]
    if _pending:
        return (f"⚠ 409 未决呈请：尚有 {len(_pending)} 件大臣呈请待朱批。"
                f"请先至「朱批待阅」处置后再颁旨。")
    ensure_task_schema(state, task)
    is_secret_task = any(t is task for t in (getattr(state, "longterm_secret", None) or []))
    if spec.get("enforce_troops") and is_secret_task:
        return "密令不可调兵督行（会暴露事机），请改用「督行」或「御笔中旨」。"
    name = str(task.get("task_name") or task.get("title") or "政务")
    _t = str(title or f"{spec.get('label')}「{name}」")
    meta = {"kind": kind, "target": target or "有司"}
    # 密令事务的"督行"走密旨通道（不占公开带宽，但有密旨上限）
    use_secret = bool(is_secret_task) or bool(spec.get("zhongzhi"))
    if use_secret:
        if len(state.pending_secret_decrees) >= 3:
            return "密旨（含中旨）已满，暂不能发。"
        decree = {
            "title": _t, "category": "中旨" if spec.get("zhongzhi") else "密旨",
            "is_secret": True, "is_direct": bool(spec.get("zhongzhi")),
            "is_zhongzhi": bool(spec.get("zhongzhi")),
            "turn_issued": state.turn, "org_hint": task.get("org_hint") or "政府",
            "faction_stances": _task_faction_stances(state),
            "secret_loyalty": 0.6, "effects": {}, "duration": 1,
            "desc": f"{spec.get('desc')}：{name}", "target": meta["target"],
            "task_id": task.get("id"), "task_decree": meta,
        }
        state.pending_secret_decrees.append(decree)
    else:
        if len(state.pending_decrees) >= state.decree_bandwidth:
            return "诏令带宽已满！"
        decree = {
            "title": _t, "category": "诏令", "is_secret": False, "is_direct": False,
            "turn_issued": state.turn, "org_hint": task.get("org_hint") or "政府",
            "faction_stances": _task_faction_stances(state),
            "effects": {}, "duration": 1,
            "desc": f"{spec.get('desc')}：{name}", "targets": [meta["target"]],
            "task_id": task.get("id"), "task_decree": meta,
        }
        state.pending_decrees.append(decree)
    state.statistics["total_decrees"] = int(state.statistics.get("total_decrees", 0)) + 1
    cost = int(spec.get("prestige_cost") or 0)
    _p0 = _num(getattr(state, "prestige", 0.0), 0.0)
    if cost:
        state.change_prestige(-cost, f"{spec.get('label')}督责{name}")
    # 如实报**实际**扣减额（皇威有月度上限，宣称 −N 而实扣更少就是伪报）
    _paid = round(_num(getattr(state, "prestige", 0.0), 0.0) - _p0, 2)
    task["readout"] = build_readout(state, task)
    return (f"已下{spec.get('label')}：「{_t}」，督责{meta['target']}奉行"
            f"（皇威 {_paid:+.0f}）。施行与否由会签与吏治决定，本诏不保其必成。")


def _task_faction_stances(state) -> dict:
    """事务诏令的派系立场——委托单一权威 `commands_decree._random_faction_stances`（不复制）。"""
    from core.commands_decree import _random_faction_stances
    return _random_faction_stances(state)
