# -*- coding: utf-8 -*-
"""M36.7-B《最小原型》契约回归：**1 议题 × 3 大臣 × 单轮 × 不落库**。

裁定（2026-10-11）：Q8–Q11 全采①；D1–D9 为准。原型的验收**不是**"三段像样的奏议"，
而是：三人差异有**既有资料依据**、各类属性**没有串账**、AI **没有获得写入权**、原系统**完全不受影响**。

本文件**不调用 LLM**：以固定 fixtures 走**真实校验路径**
（`council_review.validate` → `ai/validators.validate_minister_opinions`），
故可确定性地验证"机制边界"。
"""
import copy
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from ai.validators import (OPINIONS_MAX, default_allowed_ref_keys,  # noqa: E402
                           flatten_readout_keys, validate_minister_opinions)
from core import money  # noqa: E402
from core.commands import new_game  # noqa: E402
from core.inspection import ai_decision_view  # noqa: E402

from content.ministers.data import MINISTERS  # noqa: E402

#: B 原型锁定参数（用户裁定：最出名的三人；本地核验见台账 §18）
PROTO_MINISTERS = ("韩忠彦", "曾布", "陈瓘")
ACTION_KINDS = ("inspect_dispatch", "inspect_report", "inspect_allege", "audit_route")


def _opinion(minister, refs, pos, *, role="", based=None, spec=None,
             risks=None, ex=False, ex_reason="当前无执行器", act="",
             query=None, unknowns=None, extra=None):
    """构造一条意见（fixture）。

    `speculative` 语义：**有 `based`** ⇒ 取显式值（缺省 False，表示有据）；
    **无 `based`** ⇒ 缺省 `True`（无据即须自标推测，符合 §5 硬校验）。
    """
    _based = list(based or [])
    _spec = bool(spec) if _based else (True if spec is None else bool(spec))
    op = {"minister": minister, "role": role or MINISTERS.get(minister, {}).get("role", ""),
          "facts_refs": list(refs),
          "inferences": [{"text": "由所见略可知其概略", "based_on": _based,
                          "speculative": _spec}],
          "unknowns": list(unknowns or []), "position": pos,
          "risks": list(risks or []), "executable": ex,
          "executable_reason": ex_reason, "action_kind": act, "query": query}
    if extra:
        op.update(extra)
    return op


def _three_opinions(allowed):
    """三人单轮意见：各自的职责/取向/立场不同，但**引用都取自同一可见键集合**。"""
    if not allowed:
        raise AssertionError("可见键集合为空：原型须在有效 viewer 下运行")
    # 取集合内真实存在的键（不杜撰）
    cap_free = next((k for k in allowed if k.endswith("capacity.free")), None)
    pending = next((k for k in allowed if k.endswith("suspicion_pending")), None)
    assert cap_free, "可见键集合缺 capacity.free（既有读数应提供）"

    # ① 韩忠彦（左相·旧党·调停）：中枢视角——重整体可行与执行安排
    a = _opinion("韩忠彦", [cap_free], "宜先令本路自陈，俟核实再议处置",
                 risks=[{"category": "political", "text": "遽加处置恐激地方与部院之争"}],
                 based=[cap_free], unknowns=["该路实情尚未核实"])
    # ② 曾布（右相·中立派·权谋/理财）：权衡成本与替代方案
    b = _opinion("曾布", [cap_free], "可先增差遣名额以核其账，毋须遽更其人",
                 risks=[{"category": "execution", "text": "差遣名额有限，恐分薄要务"}],
                 ex=True, act="inspect_dispatch", ex_reason="",
                 query={"target": "陈瓘", "about": "position",
                        "text": "若核而无实据，台谏是否仍主更易其人？"})
    # ③ 陈瓘（右司谏·旧党·刚直）：监察视角——责任与证据是否充分
    c = _opinion("陈瓘", [pending] if pending else [cap_free],
                 "未有实据之前，不宜以风闻议人之罪",
                 risks=[{"category": "information", "text": "所据多为风闻，未足为凭"}],
                 spec=True, unknowns=["所报失当之事，未见可核之凭"])
    return [a, b, c]


# ------------------------------------------------- 范围与结构

def test_prototype_scope_is_one_issue_three_ministers_one_round():
    """范围门槛：恰 3 人、每人 1 意见（至多 1 质询）、不超上限。"""
    s = new_game()
    allowed = default_allowed_ref_keys(s)
    ops = _three_opinions(allowed)
    assert [o["minister"] for o in ops] == list(PROTO_MINISTERS)
    ok, cleaned, why = validate_minister_opinions(ops, allowed_ref_keys=allowed,
                                                 action_kinds=ACTION_KINDS)
    assert ok, why
    assert len(cleaned) == 3 and len(cleaned) <= OPINIONS_MAX
    assert all(o["position"] for o in cleaned), "每人须有主张"
    assert sum(1 for o in cleaned if o["query"]) <= 3, "每人至多 1 条质询"


def test_opinions_structure_channel_passes_contract_validate():
    """走**真实契约校验路径**（council_review.validate 内的同一校验器）⇒ 合法意见通过。"""
    s = new_game()
    allowed = default_allowed_ref_keys(s)
    ops = _three_opinions(allowed)
    ok, cleaned, why = validate_minister_opinions(ops, allowed_ref_keys=allowed,
                                                 action_kinds=ACTION_KINDS)
    assert ok and cleaned, why
    for o in cleaned:
        assert set(o) == {"minister", "role", "facts_refs", "inferences", "unknowns",
                          "position", "risks", "executable", "executable_reason",
                          "action_kind", "query"}, "意见字段集须固定（不外扩）"


def test_ministers_differ_with_evidenced_basis():
    """独立性门槛：三人主张不同、且各自依据/取向不同（**有既有资料依据**，非模板化雷同）。"""
    s = new_game()
    allowed = default_allowed_ref_keys(s)
    ok, cleaned, _ = validate_minister_opinions(_three_opinions(allowed),
                                               allowed_ref_keys=allowed,
                                               action_kinds=ACTION_KINDS)
    assert ok
    positions = {o["minister"]: o["position"] for o in cleaned}
    assert len(set(positions.values())) == 3, "三人主张不得雷同"
    # 取向/归属来自既有资料（只读）：旧党·调停 / 中立派·权谋+理财 / 旧党·刚直
    assert MINISTERS["韩忠彦"]["faction"] == "旧党" and "调停" in MINISTERS["韩忠彦"]["trait_ids"]
    assert MINISTERS["曾布"]["faction"] == "中立派" and "理财" in MINISTERS["曾布"]["trait_ids"]
    assert MINISTERS["陈瓘"]["faction"] == "旧党" and "刚直" in MINISTERS["陈瓘"]["trait_ids"]
    # 风险类别各自不同（职责视角差异的可核验痕迹）
    cats = {o["minister"]: {r["category"] for r in o["risks"]} for o in cleaned}
    assert cats["韩忠彦"] == {"political"} and cats["曾布"] == {"execution"}
    assert cats["陈瓘"] == {"information"}


# ------------------------------------------------- 守卫（逐条对应 D1–D9）

def test_guard_rejects_unverifiable_refs_and_path_probing():
    """D1/D6＋Q3：引用越权／不存在／任意属性路径 ⇒ **整单拒绝**（不得删引用后继续）。"""
    s = new_game()
    allowed = default_allowed_ref_keys(s)
    good = next(k for k in allowed if k.endswith("capacity.free"))
    for bad_ref in ("state.prefectures.河南路.pops.官僚.waiting",     # 任意路径
                    "finance.real.total",                              # 未授权真账
                    "inspection_view.capacity.free.DEEP",              # 杜撰键
                    ""):
        ops = [_opinion("韩忠彦", [good, bad_ref], "宜核实")]
        ok, cleaned, why = validate_minister_opinions(ops, allowed_ref_keys=allowed)
        if bad_ref == "":
            assert ok, "空引用应被忽略而非视为非法"
        else:
            assert not ok and cleaned is None, f"应整单拒绝：{bad_ref}"
            assert "不可核对" in why


def test_guard_rejects_unfounded_inference_and_numbers():
    """D1/§5/§6：`based_on ⊄ facts_refs`、无依据未标 speculative、无依据数值 ⇒ 整单拒绝。"""
    s = new_game()
    allowed = default_allowed_ref_keys(s)
    good = next(k for k in allowed if k.endswith("capacity.free"))
    other = next((k for k in allowed if k != good), good)
    # 依据不在 facts_refs 内
    ops = [_opinion("曾布", [good], "宜行", based=[other])]
    ok, _, why = validate_minister_opinions(ops, allowed_ref_keys=allowed)
    assert not ok and "依据不在" in why
    # 无依据且未标 speculative（显式 spec=False）
    ops = [_opinion("曾布", [good], "宜行", spec=False)]
    ok, _, why = validate_minister_opinions(ops, allowed_ref_keys=allowed)
    assert not ok and "speculative" in why
    # 无依据精确数值（主张/推断/风险三处各试一次）
    for pos, inf, risk in (("可省三成", None, None), (None, "或省三成", None),
                           (None, None, "恐耗万贯")):
        op = _opinion("曾布", [good], pos or "宜行",
                      risks=[{"category": "finance", "text": risk}] if risk else [],
                      spec=True)
        if inf:
            op["inferences"] = [{"text": inf, "based_on": [], "speculative": True}]
        ok, _, why = validate_minister_opinions([op], allowed_ref_keys=allowed)
        assert not ok and "无依据数值" in why, (pos, inf, risk, why)


def test_guard_rejects_attribute_writes_and_self_assessment():
    """D4/Q1：借意见写回属性（trait/persona/loyalty/competence…）⇒ 整单拒绝。"""
    s = new_game()
    allowed = default_allowed_ref_keys(s)
    good = next(k for k in allowed if k.endswith("capacity.free"))
    for badkey in ("traits", "persona", "loyalty", "competence", "faction_change"):
        ops = [_opinion("陈瓘", [good], "宜核实", spec=True,
                        extra={badkey: {"level": 3}})]
        ok, _, why = validate_minister_opinions(ops, allowed_ref_keys=allowed)
        assert not ok and "禁止字段" in why, badkey


def test_guard_executable_and_query_boundaries():
    """Q7：executable=true 须有执行器；false 须说明原因。规则4：质询不得索取未公开事实。"""
    s = new_game()
    allowed = default_allowed_ref_keys(s)
    good = next(k for k in allowed if k.endswith("capacity.free"))
    # executable=true 但无执行器
    ops = [_opinion("曾布", [good], "宜遣官察访", ex=True, act="modern_audit_office",
                    ex_reason="")]
    ok, _, why = validate_minister_opinions(ops, allowed_ref_keys=allowed,
                                            action_kinds=ACTION_KINDS)
    assert not ok and "无对应执行器" in why
    # executable=false 未说明原因
    ops = [_opinion("曾布", [good], "宜行", ex=False, ex_reason="")]
    ok, _, why = validate_minister_opinions(ops, allowed_ref_keys=allowed)
    assert not ok and "未说明原因" in why
    # 质询索取未公开事实
    ops = [_opinion("曾布", [good], "宜行", spec=True,
                    query={"target": "韩忠彦", "about": "position",
                           "text": "请出示户部真账", "facts_refs": ["finance.real.total"]})]
    ok, _, why = validate_minister_opinions(ops, allowed_ref_keys=allowed)
    assert not ok and "未公开事实" in why
    # 质询对象非法
    ops = [_opinion("曾布", [good], "宜行", spec=True,
                    query={"target": "韩忠彦", "about": "secret_file", "text": "?"})]
    ok, _, why = validate_minister_opinions(ops, allowed_ref_keys=allowed)
    assert not ok and "质询对象非法" in why


def test_guard_scope_and_count_limits():
    """Q5/D8：条数超限拒绝；`None` ⇒ 不产出（向后兼容）。"""
    s = new_game()
    allowed = default_allowed_ref_keys(s)
    good = next(k for k in allowed if k.endswith("capacity.free"))
    four = [_opinion(n, [good], "宜行", spec=True) for n in ("甲", "乙", "丙", "丁")]
    ok, _, why = validate_minister_opinions(four, allowed_ref_keys=allowed)
    assert not ok and "超限" in why
    assert validate_minister_opinions(None, allowed_ref_keys=allowed) == (True, None, "")


# ------------------------------------------------- 零持久化 / 缺值 / 三处同步

def test_zero_persistence_and_no_writes():
    """D8：校验与视图构建**不得**改动任何持久化状态（含会签缓存不被写）。"""
    s = new_game()
    before = (copy.deepcopy(s.prefectures), money.m_all(s),
              copy.deepcopy(dict(s.statistics or {})),
              copy.deepcopy(getattr(s, "council_reviews", {})),
              copy.deepcopy(getattr(s, "ai_pending_actions", [])),
              copy.deepcopy(s.inspection_tasks), len(getattr(s, "discovery_suspicions", []) or []))
    allowed = default_allowed_ref_keys(s)          # 构建可见键集合（只读）
    ai_decision_view(s, viewer="official")         # 视图（只读）
    ok, cleaned, _ = validate_minister_opinions(_three_opinions(allowed),
                                               allowed_ref_keys=allowed,
                                               action_kinds=ACTION_KINDS)
    assert ok and cleaned
    after = (s.prefectures, money.m_all(s), dict(s.statistics or {}),
             getattr(s, "council_reviews", {}), getattr(s, "ai_pending_actions", []),
             s.inspection_tasks, len(getattr(s, "discovery_suspicions", []) or []))
    assert before[0] == after[0] and before[1] == after[1] and before[2] == after[2]
    assert before[3] == after[3], "会签缓存不得被写"
    assert before[4] == after[4], "提案容器不得被写"
    assert before[5] == after[5] and before[6] == after[6]


def test_unknown_is_not_zero_or_negative():
    """D6：缺值＝`unknown`，不得推成 0／无能力／负面；不在册名字亦同。"""
    s = new_game()
    allowed = default_allowed_ref_keys(s)
    ok, cleaned, _ = validate_minister_opinions(_three_opinions(allowed),
                                               allowed_ref_keys=allowed,
                                               action_kinds=ACTION_KINDS)
    assert ok
    # 陈瓘 nobility 为空 ⇒ 只能表现为"未见记载"，不得据此推断门第
    assert MINISTERS["陈瓘"]["nobility"] == "", "本地数据实况：陈瓘封爵字段为空"
    ch = [o for o in cleaned if o["minister"] == "陈瓘"][0]
    joined = str(ch)
    for bad in ("门第低", "无出身", "寒门"):
        assert bad not in joined, "不得由空值推断负面出身"
    assert ch["unknowns"], "须显式保留未知项"
    # 不在册名字：不得凭 minister_status() 判为在朝
    assert "章惇" not in MINISTERS, "本地实测：章惇不在 MINISTERS 档案内"
    assert MINISTERS.get("章惇", {}).get("in_office") is None, "不在册 ⇒ unknown，不是 False/True"


def test_three_place_sync_prompt_validator_and_token_group():
    """§13：三处同步＝提示词＋输出校验（+token 组已覆盖，无需第四处）。"""
    import ai.token_meter as tm
    base = os.path.join(_GAME_ROOT, "ai")
    with open(os.path.join(base, "prompts", "council_review.md"), encoding="utf-8") as f:
        prompt = f.read()
    assert "opinions" in prompt and "speculative" in prompt, "提示词须含结构化意见规范"
    with open(os.path.join(base, "validators.py"), encoding="utf-8") as f:
        val = f.read()
    assert "def validate_minister_opinions" in val
    assert {"council_review"} <= set(tm.TOKEN_GROUPS.get("会签", set())), \
        "会签 token 组须覆盖 council_review（既有组，未新增第四处同步点）"
    # 契约层确实接线（可选字段，向后兼容）
    with open(os.path.join(base, "contracts_court.py"), encoding="utf-8") as f:
        court = f.read()
    assert "validate_minister_opinions" in court and 'o.get("opinions")' in court


def test_contract_fallback_on_invalid_opinions():
    """§11：意见非法 ⇒ 会签**整单失败**（拒绝式），并交既有 `_ai_unavailable` 降级。"""
    court_src = open(os.path.join(_GAME_ROOT, "ai", "contracts_court.py"), encoding="utf-8").read()
    assert "return None" in court_src, "校验失败必须整单拒绝"
    # 直接验证：非法 opinions ⇒ 校验器返回 (False, None, reason)
    s = new_game()
    allowed = default_allowed_ref_keys(s)
    bad = [_opinion("曾布", ["杜撰的键"], "宜行", spec=True)]
    ok, cleaned, why = validate_minister_opinions(bad, allowed_ref_keys=allowed)
    assert (ok, cleaned) == (False, None) and why



