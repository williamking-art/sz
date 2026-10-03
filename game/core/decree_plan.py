# -*- coding: utf-8 -*-
"""圣旨行动闭环 · 行动计划**校验器**（规格 `specs/decree-action-chain` 任务 0/2）。

定位（务必先读）：
  · **AI 只有提议权**。本模块是 `core/` 里的**唯一**校验与落点裁决处；
    AI 契约（`ai/contracts_decree.py::decree_action_plan`）只负责把圣旨拆成
    `actions[] / unresolved[]`，**不填最终生效数值、不写状态路径、不生成表达式**。
  · **提案 ≠ 状态变化**。本模块只做「校验 → 逐项裁决」，产出
    `status ∈ proposed / rejected / unsupported / unresolved / duplicate`，
    **不建任何工程、不改任何账**（提交工程是任务 3/4 的事）。
  · **拒绝式**：非法输入**逐项丢弃并给出原因**，绝不静默改写、绝不静默兜底
    （硬约束 #3「缺失 ≠ 0 ≠ 1.0」；规格非目标「AI 不得生成或执行代码/表达式」）。

任务 0 产物：行动状态词典 `ACTION_STATUS` ＋ 计划 `DECREE_PLAN_SCHEMA_VERSION`。
任务 2 产物：多 action schema ＋ 来源片段 ＋ 地理 entity id ＋ unresolved/unsupported
结果 ＋ operator registry ＋ 参数范围校验 ＋ 稳定 action id ＋ 重复提交防护。
"""
from __future__ import annotations

import hashlib
import math
from typing import Any, Dict, List, Optional, Tuple

from content.data_geo_tables import PREFECTURE_INFO, PREFECTURE_LIST

__all__ = [
    "DECREE_PLAN_SCHEMA_VERSION", "ACTION_STATUS", "ACTION_KINDS",
    "EFFECT_OPERATORS", "register_operator", "resolve_location",
    "action_fingerprint", "validate_action", "validate_plan",
]

# 计划 schema 版本：**显式**版本号，写入存档/读档据此迁移（规格任务 7 的前置）。
# v1：首版——多 action + 来源片段 + 路级 entity id + 逐项裁决四态。
DECREE_PLAN_SCHEMA_VERSION = 1


# ---------------------------------------------------------------- 任务 0：状态词典
# 行动状态词典（规格「前端方向」要求逐项区分，**不得混写**）：
#   拟议 → 已拨款 → 营建中 → 运行 ⇄ 降效；受阻 / 作罢为两个终态。
# 「受理 / 告成 / 效果已生效」是**另两个层级**（旨意受理、效果生效），
# 刻意**不**在本词典内，避免与工程状态混淆（规格 requirements.md:25）。
ACTION_STATUS: Dict[str, str] = {
    "proposed":   "拟议",     # 已通过校验、等待拨款/提交（尚未进入 state.projects）
    "funded":     "已拨款",   # 资源已预留（任务 3 落地）
    "building":   "营建中",   # 已进入既有工程五态状态机（任务 3 落地）
    "running":    "运行",
    "degraded":   "降效",
    "blocked":    "受阻",
    "abandoned":  "作罢",
}

# 计划层裁决四态（**校验**阶段用，与上表的工程态严格分离）
PLAN_VERDICT: Tuple[str, ...] = ("accepted", "unresolved", "unsupported", "rejected")

# 动作种类（白名单；不在表内 → rejected，不静默改写）
ACTION_KINDS: Tuple[str, ...] = (
    "营建",        # 提交既有工程状态机（任务 3）
    "军政",        # 军事/边防（军队天然参与）
    "财政",        # 钱粮调拨
    "民生",        # 赈济/减赋/招抚等民政
    "制度",        # 机构/法度变革
)

# ---------------------------------------------------------------- 任务 2：operator registry
# 效果构件注册表：**只接受已注册 operator**（规格设计原则 2）。
# 注册的是「参数 schema ＋ 校验器」，不是可执行代码——AI 永远不能新增 operator。
# 初始为空：任务 3/4 随效果构件一并注册。**注册表为空时**，任何带 effects 的动作
# 一律判`unsupported`（规格非目标第 2 条：未注册构件不得靠改名或叙述落地）。
EFFECT_OPERATORS: Dict[str, Dict[str, Any]] = {}


def register_operator(name: str, *, params: Optional[Dict[str, Any]] = None,
                     validator=None) -> None:
    """注册一个效果构件 operator（**仅 core 内部调用**，AI/前端不得调用）。

    `params` 声明参数名 → 规格（`{"type": "int", "min": .., "max": .., "required": bool}`）；
    `validator` 为可选的额外校验函数（`(params) -> Optional[str]`，返回错误文案）。
    重名注册**拒绝**（防止悄悄改写既有构件的语义）。
    """
    key = str(name or "").strip()
    if not key:
        raise ValueError("operator 名称不能为空")
    if key in EFFECT_OPERATORS:
        raise ValueError(f"operator 已注册，不得重注册：{key}")
    EFFECT_OPERATORS[key] = {
        "params": dict(params or {}),
        "validator": validator,
    }


# ---- 内建效果构件（规格任务 3/4）：**只映射到既有的完工/运行落点**，不另起通道 ----
# `output_key` 必须是 `_settle_projects` **已经会处理**的键
#（`granary_cap_add` / `defense_add` / `wine_coin_add`），
# 这样动态蓝图的效果复用既有、已被测试覆盖的落地路径，**不新增结算分支**。
# `limit` 为单座建筑的参数上限（防 AI 用离谱数值撑爆盘面）。
#
# `timing`（规格任务 4）区分两类效果：
#   · `"completion"` 完工**一次性**落地（仓容/厢军这类"建成即得"）；
#   · `"runtime"`    **运行期按月**落地，且**按 capacity 缩放**（降效即减产）。
# 只有走守恒通道的构件才允许 runtime（酒课经 `_collect_from_pops` 向民间守恒征收）。
BUILTIN_OPERATORS: Dict[str, Dict[str, Any]] = {
    "仓容": {"output_key": "granary_cap_add", "unit": "石", "timing": "completion",
             "params": {"amount": {"type": "int", "min": 1, "max": 2_000_000,
                                   "required": True}}},
    "厢军": {"output_key": "defense_add", "unit": "人", "timing": "completion",
             "params": {"amount": {"type": "int", "min": 1, "max": 5_000,
                                   "required": True}}},
    "酒课": {"output_key": "wine_coin_add", "unit": "贯/月", "timing": "runtime",
             "params": {"amount": {"type": "int", "min": 1, "max": 500_000,
                                   "required": True}}},
    # 粮类运行构件：经**既有守恒配对通道** `_state_grain_trade(..., "buy", ...)`
    #（太仓 +粮、国库 −钱、民间售粮得钱，钱粮两组 ΣΔ==0），
    # 故运行期粮产出**不是凭空造粮**——此前"运行期粮类无守恒落点"的缺口由它补齐。
    "籴买": {"output_key": "grain_buy", "unit": "石/月", "timing": "runtime",
             "params": {"amount": {"type": "int", "min": 1, "max": 200_000,
                                   "required": True}}},
}
_BUILTIN_READY = False


def _ensure_builtin_operators() -> None:
    """幂等注册内建构件（测试清空注册表后仍能自愈，避免"注册表被清 → 全部
    unsupported"的假阴性）。"""
    global _BUILTIN_READY
    if _BUILTIN_READY and all(k in EFFECT_OPERATORS for k in BUILTIN_OPERATORS):
        return
    for _n, _d in BUILTIN_OPERATORS.items():
        if _n not in EFFECT_OPERATORS:
            EFFECT_OPERATORS[_n] = {"params": dict(_d["params"]), "validator": None,
                                    "output_key": _d["output_key"], "unit": _d["unit"],
                                    "timing": _d.get("timing", "completion")}
    _BUILTIN_READY = True


def _check_operator(op_name: str, params: Any) -> Optional[str]:
    """单个 operator 的参数校验；返回错误文案（None = 通过）。"""
    _ensure_builtin_operators()
    spec = EFFECT_OPERATORS.get(op_name)
    if spec is None:
        return f"未注册的 effects 构件：{op_name}"
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return f"effects[{op_name}] 的 params 必须是对象"
    declared = spec.get("params") or {}
    for pname, pspec in declared.items():
        if pname not in params:
            if pspec.get("required"):
                return f"effects[{op_name}] 缺必填参数 {pname}"
            continue
        val = params[pname]
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            return f"effects[{op_name}].{pname} 必须是数值"
        if not math.isfinite(float(val)):
            return f"effects[{op_name}].{pname} 为非有限值"
        lo, hi = pspec.get("min"), pspec.get("max")
        if lo is not None and val < lo:
            return f"effects[{op_name}].{pname}={val} 低于下限 {lo}"
        if hi is not None and val > hi:
            return f"effects[{op_name}].{pname}={val} 高于上限 {hi}"
    vfn = spec.get("validator")
    if callable(vfn):
        err = vfn(params)
        if err:
            return f"effects[{op_name}]: {err}"
    return None


# ---------------------------------------------------------------- 地理 entity id
def resolve_location(raw: Any, state=None) -> Tuple[Optional[str], str]:
    """AI 给的地点文本 → **权威 entity id**（当前仅「路」一级）。

    规格要求（`requirements.md` 待核实第 2 条 / `design.md` 原则 4）：
    「计划里的地点必须映射到注册实体，不能把『广州』『明州』等自由文本
    直接当成已有可建位置」。

    返回 `(entity_id, "")` 成功；`(None, 原因)` 失败（**不猜、不就近匹配**）。
    容许的写法：注册路名本身（「两浙路」），或去掉「路」后的简称（「两浙」）——
    简称也必须能**唯一**命中注册表，否则判 unresolved。
    """
    if not isinstance(raw, str):
        return None, f"地点必须是字符串（得到 {type(raw).__name__}）"
    txt = raw.strip()
    if not txt:
        return None, "地点为空"
    if txt in PREFECTURE_INFO:
        return txt, ""
    # 唯一简称匹配（广州/明州这类**非注册**地名在此落空 → unresolved）
    stripped = txt[:-1] if txt.endswith("路") else txt
    hits = [r for r in PREFECTURE_LIST if r[:-1] == stripped or r == stripped]
    if len(hits) == 1:
        return hits[0], ""
    if len(hits) > 1:
        return None, f"地点『{txt}』匹配到多条注册路，需写全称（{'/'.join(hits)}）"
    return None, f"地点『{txt}』不是已注册实体（当前仅路一级：{'/'.join(PREFECTURE_LIST[:3])}…）"


# ---------------------------------------------------------------- 稳定 action id
def action_fingerprint(decree_id: str, kind: str, location_id: str, title: str) -> str:
    """稳定 action id：同一道旨意里同一个动作**重算必同**（规格要求 2 / 设计原则 6）。

    用 `(decree_id, 动作种类, 落点, 题名)` 的 sha1 前 12 位——**不含序号、时间戳
    与任何随机量**。

    ⚠️ 刻意**不含 index**：若把序号掺进指纹，
      ① 同一计划里两个内容相同的动作会拿到不同 id → 计划内重复检测形同虚设；
      ② AI 重试时只要重排动作顺序，同一个逻辑动作就会换id → 重复立项直接漏过。
    幂等要的是「同一逻辑动作 ＝ 同一 id」，与它在数组里的位置无关。
    """
    raw = "\x1f".join([str(decree_id or ""), str(kind or ""),
                       str(location_id or ""), str(title or "").strip()])
    return "act_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------- 单动作校验
def _clean_num(v: Any) -> Optional[float]:
    """非有限/非数值 → None（缺失就报缺失，**不回落 0**）。"""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def validate_action(action: Any, decree_id: str, index: int, *,
                    state=None, seen_ids: Optional[Dict[str, int]] = None,
                    ) -> Dict[str, Any]:
    """校验单个动作 → 裁决记录（**不抛异常、不改 state**）。

    返回 dict：`{id, index, kind, title, location_id, status, reasons, ...}`。
    `status` ∈ `proposed / unresolved / unsupported / rejected / duplicate`。
    """
    seen_ids = seen_ids if seen_ids is not None else {}
    verdict: Dict[str, Any] = {
        "index": int(index),
        "status": "proposed",
        "reasons": [],
        "source_fragment": "",
        "kind": None,
        "title": "",
        "location_id": None,
        "org": "",
        "prereq": None,
        "budget": None,
        "deadline": None,
        "effects": [],
        "blueprint_proposal": None,
    }
    if not isinstance(action, dict):
        verdict.update(status="rejected", reasons=["动作必须是对象"])
        return verdict

    # ---- 题名（来源片段另存，两者不可混为一谈）
    title = action.get("title")
    if isinstance(title, str) and title.strip():
        verdict["title"] = title.strip()[:40]
    frag = action.get("source_fragment") or action.get("fragment")
    if isinstance(frag, str):
        verdict["source_fragment"] = frag.strip()[:200]
    if not verdict["title"]:
        verdict["status"] = "rejected"
        verdict["reasons"].append("缺题名（title）")
        return verdict

    # ---- 动作种类（白名单；不静默改写）
    kind = action.get("kind")
    if kind not in ACTION_KINDS:
        verdict["status"] = "rejected"
        verdict["reasons"].append(f"动作种类非法：{kind!r}（允许：{'/'.join(ACTION_KINDS)}）")
        return verdict
    verdict["kind"] = kind

    # ---- 地点：必须映射到注册实体
    loc_raw = action.get("location_id") or action.get("location") or action.get("route")
    loc_id, loc_err = resolve_location(loc_raw, state)
    if loc_id is None:
        # 地点不可解析 → **unresolved（待补信息）**，不是 rejected：
        # 规格要求「地点歧义 → 返回待补信息/未支持项」，由玩家/后续补全。
        verdict["status"] = "unresolved"
        verdict["reasons"].append(loc_err)
    else:
        if state is not None and isinstance(getattr(state, "prefectures", None), dict):
            if loc_id not in state.prefectures:
                verdict["status"] = "unresolved"
                verdict["reasons"].append(f"地点『{loc_id}』不在本局存档的路表中")
        verdict["location_id"] = loc_id

    # ---- 执行机构（只存字符串，不改 state.orgs）
    org = action.get("org")
    verdict["org"] = org.strip()[:20] if isinstance(org, str) else ""

    # ---- 前置 / 资源预算 / 时限（逐项校验，缺失即缺失，不填默认值）
    prereq = action.get("prereq")
    verdict["prereq"] = prereq if isinstance(prereq, (dict, list)) else None
    budget = action.get("budget")
    if isinstance(budget, dict):
        clean_b: Dict[str, int] = {}
        for k in ("treasury", "granary", "labor", "materials"):
            if k not in budget:
                continue
            n = _clean_num(budget.get(k))
            if n is None:
                verdict["reasons"].append(f"budget.{k} 非数值或非有限，已丢弃该键")
                continue
            if n < 0:
                verdict["reasons"].append(f"budget.{k} 为负，已丢弃该键")
                continue
            clean_b[k] = int(n)
        verdict["budget"] = clean_b or None
    elif budget is not None:
        verdict["reasons"].append("budget 必须是对象")
    dl = _clean_num(action.get("deadline"))
    if dl is not None:
        verdict["deadline"] = int(dl) if dl > 0 else None

    # ---- effects：只接受**已注册 operator**
    raw_effects = action.get("effects")
    if raw_effects is None:
        raw_effects = []
    if not isinstance(raw_effects, list):
        verdict["reasons"].append("effects 必须是数组")
        raw_effects = []
    kept: List[Dict[str, Any]] = []
    for eff in raw_effects:
        if not isinstance(eff, dict):
            verdict["reasons"].append("effects 元素必须是对象")
            continue
        op_name = str(eff.get("op") or eff.get("operator") or "").strip()
        if not op_name:
            verdict["reasons"].append("effects 元素缺 op")
            continue
        err = _check_operator(op_name, eff.get("params"))
        if err:
            verdict["reasons"].append(err)
            continue
        kept.append({"op": op_name, "params": dict(eff.get("params") or {})})
    verdict["effects"] = kept
    if raw_effects and not kept and verdict["status"] == "proposed":
        # 有 effects 但**全部**未通过 → unsupported（规格：未注册构件 = 待支持/未执行）
        verdict["status"] = "unsupported"
        verdict["reasons"].append("effects 全部未通过校验（未注册或参数越界）→ 待支持/未执行")

    # ---- 蓝图提案（仅「营建」类允许；只存数据，不注册、不落库）
    bp = action.get("blueprint_proposal")
    if bp is not None:
        if kind != "营建":
            verdict["status"] = "rejected"
            verdict["reasons"].append("只有『营建』动作可带 blueprint_proposal")
            return verdict
        if not isinstance(bp, dict):
            verdict["status"] = "rejected"
            verdict["reasons"].append("blueprint_proposal 必须是对象")
            return verdict
        bp_name = bp.get("name")
        if not isinstance(bp_name, str) or not bp_name.strip():
            verdict["status"] = "rejected"
            verdict["reasons"].append("blueprint_proposal 缺 name")
            return verdict
        clean_bp = {
            "name": bp_name.strip()[:40],
            # 未给分类就**不写该键**（不补空串——空串在下游会被当成"给了非法值"）
            **({"category": str(bp["category"])[:20]}
               if str(bp.get("category") or "").strip() else {}),
            "cost": bp.get("cost") if isinstance(bp.get("cost"), dict) else {},
            "months": bp.get("months"),
            "materials": bp.get("materials") if isinstance(bp.get("materials"), dict) else {},
            "maintenance": bp.get("maintenance"),
            # 构件白名单：逐个过 operator registry（未注册 → 不保留）
            "effects": [],
        }
        _bp_bad: List[str] = []
        for eff in (bp.get("effects") if isinstance(bp.get("effects"), list) else []):
            if not isinstance(eff, dict):
                continue
            op_name = str(eff.get("op") or "").strip()
            if not op_name:
                continue
            err = _check_operator(op_name, eff.get("params"))
            if err:
                # ⚠️ 不能**静默丢弃**坏构件后照常注册蓝图——那等于玩家提出"三效果建筑"
                # 却拿到"两效果建筑"且无从知晓，恰是本规格要治的"叙事说办了、数值没动"。
                # 故整条动作判 unsupported（待支持），由玩家/AI 改提案后再来。
                _bp_bad.append(f"blueprint_proposal：{err}")
                continue
            clean_bp["effects"].append({"op": op_name, "params": dict(eff.get("params") or {})})
        verdict["blueprint_proposal"] = clean_bp
        if _bp_bad:
            # 坏构件已进 `_bp_bad` → 整条动作判**待支持**（不静默缩水成"少效果"蓝图）
            verdict["reasons"].extend(_bp_bad)
            if verdict["status"] == "proposed":
                verdict["status"] = "unsupported"

    # ---- 稳定 id + 重复提交防护
    verdict["id"] = action_fingerprint(decree_id, verdict["kind"] or "",
                                       verdict["location_id"] or "", verdict["title"])
    if verdict["id"] in seen_ids:
        verdict["status"] = "duplicate"
        verdict["reasons"].append(
            f"与第 {seen_ids[verdict['id']]} 号动作重复（同指纹），本条不重复立项")
    else:
        seen_ids[verdict["id"]] = index

    # ---- 未定级/未定点的动作不得声称"已就绪"
    if verdict["status"] == "proposed" and verdict["location_id"] is None:
        verdict["status"] = "unresolved"
    if verdict["status"] == "proposed" and verdict["reasons"]:
        # 有非致命告警但仍可提交 → 保留 proposed，并显式带出 reasons（可诊断）
        pass
    return verdict


# ---------------------------------------------------------------- 整份计划校验
def validate_plan(plan: Any, *, state=None, decree_id: Optional[str] = None,
                  max_actions: int = 12) -> Dict[str, Any]:
    """校验一份行动计划（版本化 ＋ 逐项裁决 ＋ 幂等）。

    返回：
      `{ok, schema_version, decree_id, actions[], unresolved[], narrative, summary}`
    `ok=False` 表示**整份不可提交**（结构非法/decree_id 缺失/零个可提交动作）；
    此时 `actions[]` 仍逐项给出裁决与原因，便于 UI 逐条显示（规格验收 3）。
    **本函数不提交工程、不改任何状态**（那是任务 3/4 的职责）。
    """
    out: Dict[str, Any] = {
        "ok": False,
        "schema_version": DECREE_PLAN_SCHEMA_VERSION,
        "decree_id": decree_id or "",
        "actions": [],
        "unresolved": [],
        "narrative": "",
        "summary": {},
    }
    if not isinstance(plan, dict):
        out["summary"] = {"reason": "计划必须是对象"}
        return out

    did = decree_id or plan.get("decree_id") or ""
    did = str(did).strip()[:64]
    if not did:
        out["summary"] = {"reason": "缺 decree_id（无法保证 action id 稳定与幂等）"}
        return out
    out["decree_id"] = did

    raw_actions = plan.get("actions")
    if not isinstance(raw_actions, list):
        out["summary"] = {"reason": "actions 必须是数组"}
        return out
    if len(raw_actions) > max_actions:
        out["summary"] = {"reason": f"动作数 {len(raw_actions)} 超过上限 {max_actions}"}
        return out

    seen: Dict[str, int] = {}
    verdicts: List[Dict[str, Any]] = []
    for i, act in enumerate(raw_actions):
        verdicts.append(validate_action(act, did, i, state=state, seen_ids=seen))

    raw_unres = plan.get("unresolved")
    unres: List[Dict[str, Any]] = []
    for u in (raw_unres if isinstance(raw_unres, list) else []):
        if isinstance(u, dict):
            frag = str(u.get("source_fragment") or u.get("fragment") or "").strip()[:200]
            why = str(u.get("reason") or "").strip()[:200]
            if frag or why:
                unres.append({"source_fragment": frag, "reason": why})
    # 校验器自身判出的 unresolved 也进汇总（玩家只看一处）
    for v in verdicts:
        if v["status"] == "unresolved":
            unres.append({"source_fragment": v["source_fragment"],
                          "reason": "；".join(v["reasons"])[:200]})

    out["actions"] = verdicts
    out["unresolved"] = unres
    nar = plan.get("narrative")
    out["narrative"] = nar.strip()[:400] if isinstance(nar, str) else ""
    out["summary"] = {
        "total": len(verdicts),
        "proposed": sum(1 for v in verdicts if v["status"] == "proposed"),
        "rejected": sum(1 for v in verdicts if v["status"] == "rejected"),
        "unsupported": sum(1 for v in verdicts if v["status"] == "unsupported"),
        "unresolved": sum(1 for v in verdicts if v["status"] == "unresolved"),
        "duplicate": sum(1 for v in verdicts if v["status"] == "duplicate"),
    }
    # 整份可提交：至少一条 proposed，且**没有**结构级问题
    out["ok"] = out["summary"]["proposed"] > 0
    if not out["ok"] and "reason" not in out["summary"]:
        out["summary"]["reason"] = "没有任何动作通过校验（不得整道旨意伪报为成功）"
    return out