# -*- coding: utf-8 -*-
"""宋祚 · 契约校验共享辅助（从 ai/client.py 拆出）。

存放各契约域 Mixin 共用的纯函数/常量：档位白名单、朝局摘要归一、
推演 state 脱敏注入、叙事失败分级降级。

契约内联 validate 闭包仍留在各方法体内（inspect.getsource 契约测试
要求方法源码内可见 return None / 拒绝式逻辑；且多数闭包捕获局部变量，
不宜提纯）。
"""
import json
import logging

log = logging.getLogger("ai.validators")

#: 脱敏不可用时的**粗粒度**摘要（L4，审查 P2-3）：绝不能回落原样序列化。
#: 原文案只说"摘要不可用"，不含任何精确值；`prestige.value`/`treasury.amount`/
#: 派系 `satisfaction`/`emperor_health` 等真值**一律不出现**。
_SUMMARY_DESENSITIZE_FAILED = (
    "【朝局摘要不可用】脱敏层异常，本次不注入精确读数；请按程序给出的定性档位推演。")

# 档位白名单（7 档：无/微/小/中/大/巨/极）；validator 用 normalize_tier 归一丰富表达
#
# 【缺字段处置策略（审查 B6 考证，勿再误读为「白送收益」）】本层对「缺字段/非法值」
# 分两类处理，规则一致、**从无例外**：
#   ① 类型/枚举字段（etype、agreement、target、stance、node、lineage、fund、position…）
#      → `return None` / `continue`，即**拒绝式**，整份契约作废或该项丢弃；
#   ② 强度/档位字段（tier、effect_tier、sat、inf、priority、cost_tier、probability、
#      inflow/outflow…、sui_gong/alliance）→ **向下降级**填默认值，取值一律 中/小/微
#      或「不变」，**绝无一处落到 大/巨/极**（全库反查确认）。
# 故缺字段只可能少拿、不可能多拿；且和亲/盟约/纳贡/战争等**高代价**协议在档位非法时
# 直接 `return None`（见 diplomacy_dialogue.validate），因和亲出内帑嫁妆、战争抬入侵
# 意愿，不容猜档。策略取向：宁可少给（不阻断整局），绝不因 AI 漏字段而多给。
_TIERS7 = ("无", "微", "小", "中", "大", "巨", "极")



def _summary_text(state_summary) -> str:
    """朝局摘要入参归一（审查 P0-1/P0-2 修复）：

    - str：原样（调用方已脱敏，如 state.posture / desensitize_for_ai 文本）；
    - dict（get_state_summary 全量，含国库/派系/兵力精确真值）：先经
      desensitize_state 区间化+定性化，再序列化——杜绝把精确真值直拼进 prompt
      造成脱敏四层失效，同时消灭 'dict' 拼接崩溃；
    - None/未知：返回空串。
    - **脱敏层异常（L4，审查 P2-3）**：绝不回落原样序列化，改返回粗粒度哨兵
      `_SUMMARY_DESENSITIZE_FAILED` + ERROR 日志（隐藏数值不得借故障外泄）。
    """
    if isinstance(state_summary, str):
        return state_summary
    if state_summary is None:
        return ""
    if isinstance(state_summary, dict):
        try:
            from ai.desensitize import desensitize_state
            ds = desensitize_state(state_summary)
            return json.dumps(ds, ensure_ascii=False, indent=1)
        except Exception:
            # L4（审查 P2-3）：**绝不**在脱敏失败后回落 `json.dumps(state_summary)`——
            # 那会把 prestige.value / treasury.amount / 派系 satisfaction / emperor_health
            # 等**隐藏精确值**直送 provider。异常只入日志，入参换成粗粒度哨兵。
            log.error("朝局摘要脱敏失败，已回落粗粒度摘要（不注入精确读数）", exc_info=True)
            return _SUMMARY_DESENSITIZE_FAILED
    try:
        return json.dumps(state_summary, ensure_ascii=False, sort_keys=True)
    except Exception:
        # 非 dict 且不可序列化（自定义对象）：同样不得 `str()` 出内部字段，只给粗粒度摘要
        log.error("朝局摘要不可序列化（类型 %s），已回落粗粒度摘要", type(state_summary).__name__,
                  exc_info=True)
        return _SUMMARY_DESENSITIZE_FAILED


def _decide_state_text(state) -> str:
    """任一 *_decide 的 state 直读注入统一改经此脱敏（审查 P0-2）：

    只把 GameState 变成「区间/滞后/定性」文本，绝不写精确国库/太仓/派系/流民。
    """
    if state is None:
        return ""
    try:
        from ai.desensitize import desensitize_for_ai
        return desensitize_for_ai(state)
    except Exception:
        return _summary_text(getattr(state, "get_state_summary", lambda: {})())


def _narrative_fallback(kind, minister_name=""):
    """AI 失败分级降级（落地改进 4 + T8 完整模板库）：**叙事类**失败 → 本地模板兜底
    （本地组装，非 AI 伪造，明确标注由程序代拟）；**推演类**（economy/military/
    era 等）失败仍拒绝式（AIRuntimeError/None，必须 AI）。

    模板库见 ai/narrative_fallback.py（多句式轮换 + 事件分档 + 结构化真值组装）。
    """
    from ai import narrative_fallback
    from ai.client_utils import _ai_unavailable
    if kind == "report":
        return narrative_fallback.fallback_report()
    if kind == "dialogue":
        return narrative_fallback.fallback_dialogue(minister_name)
    if kind == "narrative":
        return narrative_fallback.fallback_narrative()
    if kind == "advice":
        return narrative_fallback.fallback_advice()
    if kind == "event":
        return narrative_fallback.fallback_event()
    if kind == "eval":
        return narrative_fallback.fallback_eval()
    return _ai_unavailable(kind)


# ============================================================
# 🟢 M36.7-B（2026-10-11）：**大臣专业判断意见**的纯校验（朝议结构化意见）
#   依据 M36.7-A 台账 §5（四类内容）／§11（拒绝与降级矩阵）／§17（量纲与写入纪律）。
#   纪律：**纯函数、只读、零写入**；不新增属性真相源；不授予任何权限。
#   校验失败 ⇒ 返回 ok=False（**整单拒绝**）：绝不"删掉非法部分继续"。
# ============================================================
OPINION_TEXT_MAX = 600          # 单条文本上限（与既有契约截断纪律一致）
OPINIONS_MAX = 3                # B 原型：单轮 ≤3 人；配置只能收紧
_NUMERIC_BAN = (                # 禁**无依据精确数值**（M36.7-A §6；含中文数字）
    r"\d+(?:\.\d+)?\s*%",
    r"[零一二三四五六七八九十百千万]+(?:成|倍|贯|石|里|人|骑|级|员|顷|石)",
    r"\d+\s*(?:成|倍)",
    r"\d[\d,]*\s*(?:贯|石|万|骑|级|人)",
)
_FORBIDDEN_KEYS = ("traits", "trait_ids", "persona", "loyalty", "corruption",
                   "competence", "faction_change", "nobility", "rank")   # 防借意见写回属性
_RISK_CATS = ("finance", "execution", "military", "political", "information")


def flatten_readout_keys(obj, prefix: str = "", sep: str = ".", _depth: int = 0):
    """把只读读数**拍平成精确键集合**（如 `inspection_view.capacity.free`）。**只读**。"""
    out = set()
    if _depth > 6:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}{sep}{k}" if prefix else str(k)
            out.add(key)
            out |= flatten_readout_keys(v, key, sep, _depth + 1)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out |= flatten_readout_keys(v, f"{prefix}[{i}]", sep, _depth + 1)
    return out


def default_allowed_ref_keys(state, viewer: str = "official", oversight=None,
                             secret: bool = False):
    """引擎侧**可见键集合**（B 原型的权威来源）：按 viewer 取**既有只读读数**并拍平。

    - `inspection_view`：`core.inspection.ai_decision_view(viewer=…)`（D11 已在入口过滤）；
    - `finance`：`state.finance_readout()`（账面聚合）；
    - `discovery`：既有发现链只读读数。
    越权键不在集合内 ⇒ 任何引用必被拒（白名单＋可见性＋禁任意属性路径一次达成）。
    **只读**：调用不改变任何状态（由测试逐位比对）。
    """
    keys = set()
    try:
        from core.inspection import ai_decision_view
        keys |= flatten_readout_keys(
            ai_decision_view(state, viewer=viewer, oversight=oversight, secret=secret),
            "inspection_view")
    except Exception:                      # noqa: BLE001 — 读数不可用不阻断构建
        pass
    try:
        keys |= flatten_readout_keys(state.finance_readout(), "finance")
    except Exception:                      # noqa: BLE001
        pass
    try:
        from core.audit_case import discovery_readout
        keys |= flatten_readout_keys(discovery_readout(state), "discovery")
    except Exception:                      # noqa: BLE001
        pass
    return keys


def _op_txt(v, limit: int = OPINION_TEXT_MAX) -> str:
    return str(v or "").strip()[:limit]


def _has_unfounded_number(text: str) -> bool:
    import re as _re
    return any(_re.search(p, text) for p in _NUMERIC_BAN)


def to_proposal_payload(decision_record, *, title: str = "", summary: str = ""):
    """🟢 M36.6 收口第 2 项：`decision_record` → **既有 `payload.proposal` 契约**（**仅五项**）。

    映射（严格按 M36.7-A §10 表）：
      `rationale ← position`｜`evidence_refs ← facts_refs`｜`risks ← risks`｜
      `authorization ← authorization_required`｜`expected ← expected`。

    **表达层适配，不是新增执行载荷**：其余字段（`inferences／unknowns／alternatives／
    executable…`）**不映射**（要进提案须另裁）；**不**改变 P1–P3 批红规则、权限校验与圣旨入口。
    缺失字段**不编造**：值缺 ⇒ 省略该键，并在 `missing` 中列出。
    """
    rec = decision_record if isinstance(decision_record, dict) else {}
    out: Dict[str, Any] = {}
    missing: List[str] = []
    pairs = (("rationale", rec.get("position")),
             ("evidence_refs", rec.get("facts_refs")),
             ("risks", rec.get("risks")),
             ("authorization", rec.get("authorization_required")),
             ("expected", rec.get("expected")))
    for key, val in pairs:
        if val is None or val == "" or val == []:
            missing.append(key)
            continue
        out[key] = val
    payload: Dict[str, Any] = {"proposal": out}
    if title:
        payload["proposal"]["title"] = str(title)[:80]
    if summary:
        payload["proposal"]["summary"] = str(summary)[:200]
    return {"payload": payload, "missing": missing,
            "note": ("仅五项映射；不得借映射扩张执行载荷；缺项列 missing（不编造）")}


def validate_minister_opinions(payload, *, allowed_ref_keys, action_kinds=(),
                               max_items: int = OPINIONS_MAX):
    """校验朝议「结构化意见」（M36.7-A §5／§11／§17）。**纯函数、只读、零写入**。

    返回 `(ok, cleaned, reason)`：
    - `payload is None` ⇒ `(True, None, "")`（可选扩展，未提供即不产出）；
    - 任何一条不合法 ⇒ `(False, None, 原因)` —— **整单拒绝**，不得部分接受，
      也不得"删掉非法引用后继续"（安全失败不得降级为成功）。
    """
    allowed = set(allowed_ref_keys or ())
    kinds = set(action_kinds or ())
    if payload is None:
        return True, None, ""
    if not isinstance(payload, list):
        return False, None, "opinions 须为数组"
    if len(payload) > int(max_items):
        return False, None, f"意见条数超限（{len(payload)} > {max_items}）"
    cleaned = []
    for idx, op in enumerate(payload, 1):
        if not isinstance(op, dict):
            return False, None, f"第 {idx} 条意见须为对象"
        for bad in _FORBIDDEN_KEYS:
            if bad in op:
                return False, None, f"第 {idx} 条含禁止字段：{bad}（不得借意见写回属性）"
        refs = op.get("facts_refs") or []
        if not isinstance(refs, list):
            return False, None, f"第 {idx} 条 facts_refs 须为数组"
        refs_clean = []
        for r in refs:
            r = str(r or "").strip()
            if not r:
                continue
            if r not in allowed:
                return False, None, f"第 {idx} 条引用不可核对：{r}"
            refs_clean.append(r)
        ref_set = set(refs_clean)
        infs = op.get("inferences") or []
        if not isinstance(infs, list):
            return False, None, f"第 {idx} 条 inferences 须为数组"
        inf_clean = []
        for it in infs:
            if isinstance(it, str):
                it = {"text": it}
            if not isinstance(it, dict):
                return False, None, f"第 {idx} 条推断须为对象或字符串"
            text = _op_txt(it.get("text"))
            if not text:
                return False, None, f"第 {idx} 条推断缺 text"
            based = [str(b).strip() for b in (it.get("based_on") or [])
                     if str(b or "").strip()]
            spec = bool(it.get("speculative"))
            if based:
                if not set(based) <= ref_set:
                    return False, None, f"第 {idx} 条推断依据不在 facts_refs 内"
            elif not spec:
                return False, None, f"第 {idx} 条推断无依据且未标 speculative"
            if _has_unfounded_number(text):
                return False, None, f"第 {idx} 条推断含无依据数值"
            inf_clean.append({"text": text, "based_on": based, "speculative": spec})
        pos = _op_txt(op.get("position"))
        if not pos:
            return False, None, f"第 {idx} 条缺 position"
        if _has_unfounded_number(pos):
            return False, None, f"第 {idx} 条主张含无依据数值"
        unknowns = [_op_txt(x, 200) for x in (op.get("unknowns") or []) if _op_txt(x, 200)]
        risks = []
        for rk in (op.get("risks") or []):
            if not isinstance(rk, dict):
                return False, None, f"第 {idx} 条风险须为对象"
            cat = str(rk.get("category") or "")
            if cat not in _RISK_CATS:
                return False, None, f"第 {idx} 条风险类别非法：{cat}"
            rtext = _op_txt(rk.get("text"), 200)
            if not rtext:
                return False, None, f"第 {idx} 条风险缺 text"
            if _has_unfounded_number(rtext):
                return False, None, f"第 {idx} 条风险含无依据数值"
            risks.append({"category": cat, "text": rtext})
        ex = bool(op.get("executable"))
        ex_reason = _op_txt(op.get("executable_reason"), 200)
        act = str(op.get("action_kind") or "")
        if ex and act not in kinds:
            return False, None, f"第 {idx} 条 executable=true 但无对应执行器：{act or '（空）'}"
        if not ex and not ex_reason:
            return False, None, f"第 {idx} 条 executable=false 未说明原因"
        q = op.get("query")
        q_clean = None
        if q is not None:
            if not isinstance(q, dict):
                return False, None, f"第 {idx} 条质询须为对象"
            about = str(q.get("about") or "")
            if about not in ("position", "inference", "risk"):
                return False, None, f"第 {idx} 条质询对象非法：{about}"
            if q.get("facts_refs") or q.get("ask_for_refs"):
                return False, None, f"第 {idx} 条质询试图索取未公开事实"
            q_clean = {"target": _op_txt(q.get("target"), 60), "about": about,
                       "text": _op_txt(q.get("text"), 200)}
        cleaned.append({"minister": _op_txt(op.get("minister"), 40),
                        "role": _op_txt(op.get("role"), 60),
                        "facts_refs": refs_clean, "inferences": inf_clean,
                        "unknowns": unknowns, "position": pos, "risks": risks,
                        "executable": ex, "executable_reason": ex_reason,
                        "action_kind": act, "query": q_clean})
    return True, cleaned, ""

