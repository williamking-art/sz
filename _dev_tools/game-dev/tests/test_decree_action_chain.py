# -*- coding: utf-8 -*-
"""圣旨行动闭环 · 定向回归（规格 `specs/decree-action-chain` 任务 0/2 的验收断言）。

对应 EARS 验收：#1（AI 拆多动作）· #3（未注册构件 → 待支持/未执行）· #6（地点 → 权威 id）
· #7（稳定 action id ＋ 重试幂等）· #10（缺 decree_id 不得默认成功）。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from ai.client import AIClient  # noqa: E402
from core.decree_plan import (  # noqa: E402
    ACTION_STATUS, DECREE_PLAN_SCHEMA_VERSION, EFFECT_OPERATORS,
    action_fingerprint, register_operator, resolve_location, validate_action, validate_plan,
)
from core.game_state import GameState  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_registry():
    """每个用例跑在**干净的 operator 注册表**上（防用例间串味）。"""
    saved = dict(EFFECT_OPERATORS)
    EFFECT_OPERATORS.clear()
    yield
    EFFECT_OPERATORS.clear()
    EFFECT_OPERATORS.update(saved)


def _state():
    return GameState("史实")


def _act(**kw):
    a = {"title": "修两浙路海塘", "kind": "营建", "location_id": "两浙路"}
    a.update(kw)
    return a


# --------------------------------------------------------------- 任务 0：状态词典
def test_action_status_dictionary_is_explicit_and_complete():
    """行动状态词典必须显式存在且覆盖规格要求的 7 个工程态。"""
    assert DECREE_PLAN_SCHEMA_VERSION == 1
    for k in ("proposed", "funded", "building", "running", "degraded", "blocked", "abandoned"):
        assert k in ACTION_STATUS, f"缺状态：{k}"
        assert isinstance(ACTION_STATUS[k], str) and ACTION_STATUS[k].strip()
    # 「受理/告成/效果已生效」是另两个层级，**刻意不在**本词典内
    for forbidden in ("accepted", "告成", "effect_applied"):
        assert forbidden not in ACTION_STATUS, \
            f"工程状态词典里混入受理/生效层级：{forbidden}"


# --------------------------------------------------------------- 验收 6：地点 → 权威 id
def test_location_resolves_only_to_registered_entity():
    assert resolve_location("两浙路")[0] == "两浙路"
    assert resolve_location("两浙")[0] == "两浙路"        # 去「路」的唯一简称
    assert resolve_location("  京畿路  ")[0] == "京畿路"
    # 规格点名：广州/明州等自由文本**不得**当成已有可建位置
    for bad in ("广州", "明州", "汴京", "不存在的地方"):
        loc, err = resolve_location(bad)
        assert loc is None, f"『{bad}』不应解析为注册实体"
        assert err, f"『{bad}』必须给出原因"
    assert resolve_location("")[0] is None
    assert resolve_location(None)[0] is None
    assert resolve_location(123)[0] is None


def test_unresolved_location_marks_action_unresolved_not_proposed():
    """地点不可解析 → unresolved（待补信息），**不得**默默当成可执行。"""
    v = validate_action(_act(location_id="广州"), "d1", 0, state=_state())
    assert v["status"] == "unresolved", v
    assert v["reasons"] and "广州" in v["reasons"][0]
    assert v["location_id"] is None


# --------------------------------------------------------------- 验收 3：未注册构件
def test_unregistered_effect_operator_is_unsupported():
    """未注册构件 → 待支持/未执行，**绝不**落地、也不静默丢成 0。"""
    a = _act(effects=[{"op": "凭空造银", "params": {"amount": 999999}}])
    v = validate_action(a, "d1", 0, state=_state())
    assert v["status"] == "unsupported", v
    assert v["effects"] == []
    assert any("未注册" in r for r in v["reasons"])


def test_registered_operator_passes_and_keeps_params():
    register_operator("粮食增产", params={
        "rate": {"type": "int", "min": 0, "max": 20, "required": True}})
    v = validate_action(_act(effects=[{"op": "粮食增产", "params": {"rate": 5}}]),
                        "d1", 0, state=_state())
    assert v["status"] == "proposed", v
    assert v["effects"] == [{"op": "粮食增产", "params": {"rate": 5}}]


@pytest.mark.parametrize("params,frag", [
    ({"rate": 999}, "上限"),          # 越上界
    ({"rate": -1}, "下限"),           # 越下界
    ({}, "缺必填参数"),                # 缺必填
    ({"rate": float("nan")}, "非有限"),
    ({"rate": True}, "数值"),          # bool 不算数值
])
def test_operator_param_range_validation(params, frag):
    register_operator("粮食增产", params={
        "rate": {"type": "int", "min": 0, "max": 20, "required": True}})
    v = validate_action(_act(effects=[{"op": "粮食增产", "params": params}]),
                        "d1", 0, state=_state())
    assert v["effects"] == []
    assert any(frag in r for r in v["reasons"]), v["reasons"]


def test_duplicate_operator_registration_rejected():
    register_operator("甲", params={})
    with pytest.raises(ValueError):
        register_operator("甲", params={})


# --------------------------------------------------------------- 验收 1：多动作
def test_multi_action_plan_validated_per_action():
    """一旨多动作：逐项独立裁决，**不得**因一项坏就整单静默通过。"""
    plan = {"decree_id": "d-001", "actions": [
        _act(title="修海塘", location_id="两浙路"),
        _act(title="广州建港", location_id="广州"),                     # → unresolved
        _act(title="神秘工程", kind="法术"),                            # → rejected（种类非法）
        _act(title="修海塘", location_id="两浙路"),                     # 与第1条同指纹 → duplicate
    ]}
    out = validate_plan(plan, state=_state())
    assert out["ok"] is True                                   # 至少一条通过即可提交
    assert [a["status"] for a in out["actions"]] == \
        ["proposed", "unresolved", "rejected", "duplicate"]
    assert out["summary"]["proposed"] == 1
    assert out["summary"]["unresolved"] == 1
    assert out["summary"]["rejected"] == 1
    assert out["summary"]["duplicate"] == 1
    # 待补信息汇总里能看到「广州」这条
    assert any("广州" in (u.get("reason") or "") for u in out["unresolved"])


def test_no_legal_action_must_not_report_success():
    """零条通过 → ok=False，**不得**整道旨意伪报为成功（验收 10 的同源要求）。"""
    out = validate_plan({"decree_id": "d-2", "actions": [
        _act(location_id="广州"), _act(kind="法术")]}, state=_state())
    assert out["ok"] is False
    assert out["summary"]["proposed"] == 0
    assert "reason" in out["summary"]


# --------------------------------------------------------------- 验收 7：稳定 id ＋ 幂等
def test_action_id_is_stable_across_recompute():
    a = _act()
    v1 = validate_action(a, "d-1", 2, state=_state())
    v2 = validate_action(dict(a), "d-1", 2, state=_state())
    assert v1["id"] == v2["id"]
    assert v1["id"] == action_fingerprint("d-1", "营建", "两浙路", "修两浙路海塘")


def test_action_id_survives_action_reordering():
    """重试时 AI 重排动作顺序，id 仍跟着逻辑动作走（否则重复立项会漏过）。"""
    a = _act(title="甲工程", location_id="两浙路")
    b = _act(title="乙工程", location_id="京畿路")
    first = validate_plan({"decree_id": "d-1", "actions": [a, b]}, state=_state())
    again = validate_plan({"decree_id": "d-1", "actions": [b, a]}, state=_state())
    ids_first = {x["title"]: x["id"] for x in first["actions"]}
    ids_again = {x["title"]: x["id"] for x in again["actions"]}
    assert ids_first == ids_again


def test_action_id_differs_per_decree_and_location():
    base = validate_action(_act(), "d-1", 0, state=_state())["id"]
    assert base != validate_action(_act(), "d-2", 0, state=_state())["id"]
    assert base != validate_action(_act(location_id="京畿路"), "d-1", 0, state=_state())["id"]
    assert base != validate_action(_act(title="别的工程"), "d-1", 0, state=_state())["id"]


def test_retry_of_same_plan_is_fully_idempotent():
    """重试/重算同一条旨意：裁决结果与 action id 完全一致，无重复立项。"""
    plan = {"decree_id": "d-3", "actions": [_act(), _act(title="另修一路", location_id="京畿路")]}
    r1 = validate_plan(plan, state=_state())
    r2 = validate_plan(plan, state=_state())
    assert [a["id"] for a in r1["actions"]] == [a["id"] for a in r2["actions"]]
    assert [a["status"] for a in r1["actions"]] == [a["status"] for a in r2["actions"]]
    assert r1["summary"] == r2["summary"]


# --------------------------------------------------------------- 拒绝式与结构非法
def test_missing_decree_id_is_rejected_not_defaulted():
    """缺 decree_id → 整单不可提交（id 无法稳定 ⇒ 幂等无从保证）。"""
    out = validate_plan({"actions": [_act()]}, state=_state())
    assert out["ok"] is False
    assert "decree_id" in out["summary"]["reason"]


def test_illegal_kind_is_rejected_not_coerced():
    v = validate_action(_act(kind="修仙"), "d-1", 0, state=_state())
    assert v["status"] == "rejected"
    assert v["kind"] is None            # 不得静默改成某个合法种类
    assert "修仙" in v["reasons"][0]


def test_non_dict_action_rejected_without_raising():
    v = validate_action("我不是对象", "d-1", 0, state=_state())
    assert v["status"] == "rejected"


def test_plan_structure_violations_rejected():
    assert validate_plan(None, state=_state())["ok"] is False
    assert validate_plan({"decree_id": "d", "actions": "不是数组"}, state=_state())["ok"] is False
    over = {"decree_id": "d", "actions": [_act() for _ in range(20)]}
    assert validate_plan(over, state=_state())["ok"] is False


def test_budget_negative_or_nonnumeric_is_dropped_with_reason():
    v = validate_action(_act(budget={"treasury": -5, "granary": float("inf"), "labor": 1000}),
                        "d-1", 0, state=_state())
    assert v["budget"] == {"labor": 1000}
    assert any("treasury" in r for r in v["reasons"])
    assert any("granary" in r for r in v["reasons"])


def test_blueprint_proposal_only_allowed_for_building():
    ok = validate_action(_act(blueprint_proposal={"name": "海塘"}), "d-1", 0, state=_state())
    assert ok["blueprint_proposal"]["name"] == "海塘"
    bad = validate_action(_act(kind="财政", blueprint_proposal={"name": "海塘"}),
                          "d-1", 0, state=_state())
    assert bad["status"] == "rejected"
    assert "营建" in bad["reasons"][0]


def test_blueprint_unregistered_effects_are_stripped_with_reason():
    v = validate_action(_act(blueprint_proposal={
        "name": "海塘", "effects": [{"op": "凭空造银"}]}), "d-1", 0, state=_state())
    assert v["blueprint_proposal"]["effects"] == []
    assert any("未注册" in r for r in v["reasons"])


def test_blueprint_with_bad_effect_marks_action_unsupported():
    """反回归：蓝图提案含未注册构件 → 整条动作判**待支持**，
    不得静默缩水成"少效果"的蓝图照常通过（那等于玩家提三效果拿到两效果且不知情）。"""
    v = validate_action(_act(blueprint_proposal={
        "name": "海塘", "effects": [
            {"op": "仓容", "params": {"amount": 1000}},        # 已注册
            {"op": "凭空造银", "params": {"amount": 1}},        # 未注册
        ]}), "d-1", 0, state=_state())
    assert v["status"] == "unsupported", v
    assert v["status"] != "proposed"
    assert any("未注册" in r for r in v["reasons"]), v["reasons"]
    # 合法构件仍留在提案里（供玩家改提案时参考），但动作本身不获通过
    assert v["blueprint_proposal"]["effects"] == [
        {"op": "仓容", "params": {"amount": 1000}}]


def test_blueprint_all_effects_valid_stays_proposed():
    """反回归对照：全部构件合法时不得误判 unsupported。"""
    v = validate_action(_act(blueprint_proposal={
        "name": "海塘", "effects": [{"op": "仓容", "params": {"amount": 1000}}]}),
        "d-1", 0, state=_state())
    assert v["status"] == "proposed", v


# --------------------------------------------------------------- 副作用边界
def test_validate_plan_does_not_mutate_state():
    """校验器**只裁决**、不落工程、不改账（提案 ≠ 状态变化）。"""
    s = _state()
    before_proj = len(getattr(s, "projects", []) or [])
    before_tre = s.treasury
    before_pool = s.payraise_budget
    out = validate_plan({"decree_id": "d-9", "actions": [
        _act(), _act(title="赈济", kind="民生", location_id="京西路")]}, state=s)
    assert out["ok"] is True
    assert len(getattr(s, "projects", []) or []) == before_proj, "校验器不得建工程"
    assert s.treasury == before_tre, "校验器不得动国库"
    assert s.payraise_budget == before_pool, "校验器不得动账"


def test_location_not_in_save_is_unresolved():
    """注册表里有、但本局存档没有的路 → unresolved（不默认可建）。"""
    s = GameState("史实")
    if "两浙路" in getattr(s, "prefectures", {}):
        s.prefectures.pop("两浙路")
        v = validate_action(_act(location_id="两浙路"), "d-1", 0, state=s)
        assert v["status"] == "unresolved", v
    else:                                   # 存档根本没有该路则直接用别的验证
        v = validate_action(_act(location_id="不存在的路"), "d-1", 0, state=s)
        assert v["status"] == "unresolved"


# --------------------------------------------------------------- 契约层（不打真实 AI）
class _StubDecree(AIClient):
    """真实 `AIClient`（含真实 `_postprocess` 校验链），**只桩掉网络** `_call`。"""

    def __init__(self, reply):
        super().__init__()
        self._reply = reply
        self.last_call = None

    def _call(self, *args, **kw):
        self.last_call = (args[0] if args else kw.get("system_prompt", ""),
                          args[1] if len(args) > 1 else kw.get("user_prompt", ""), kw)
        return self._reply


import json  # noqa: E402


def _reply(obj):
    return json.dumps(obj, ensure_ascii=False)


def test_contract_accepts_multi_action_plan():
    c = _StubDecree(_reply({
        "decree_id": "d-100",
        "actions": [
            {"source_fragment": "修两浙海塘", "title": "修两浙海塘",
             "kind": "营建", "location_id": "两浙路"},
            {"source_fragment": "蠲免京西钱税", "title": "蠲免京西钱税",
             "kind": "财政", "location_id": "京西路"},
        ],
        "unresolved": [{"source_fragment": "广州设市舶司", "reason": "广州非注册路"}],
        "narrative": "两事分办",
    }))
    out = c.decree_action_plan("修两浙海塘，蠲免京西钱税，广州设市舶司",
                               routes=["两浙路", "京西路"])
    assert not out.get("_error"), out
    assert out["decree_id"] == "d-100"
    assert len(out["actions"]) == 2
    assert out["unresolved"][0]["source_fragment"] == "广州设市舶司"
    # 再过 core 校验器：广州那条只能待在 unresolved
    v = validate_plan(out, state=_state())
    assert v["ok"] is True
    assert v["summary"]["proposed"] == 2
    assert any("广州" in u["reason"] for u in v["unresolved"])


def test_contract_rejects_missing_decree_id():
    c = _StubDecree(_reply({"actions": [
        {"source_fragment": "x", "title": "x", "kind": "财政", "location_id": "京西路"}]}))
    out = c.decree_action_plan("蠲免京西钱税")
    assert out.get("_error"), f"缺 decree_id 应整单失败：{out}"


def test_contract_rejects_empty_actions():
    c = _StubDecree(_reply({"decree_id": "d-1", "actions": []}))
    assert c.decree_action_plan("空计划").get("_error")


def test_contract_drops_actions_without_fragment_or_title():
    """缺来源片段/题名的动作**逐条丢弃**，不编造，也不让整单带病通过。"""
    c = _StubDecree(_reply({"decree_id": "d-2", "actions": [
        {"source_fragment": "修两浙海塘", "title": "修两浙海塘",
         "kind": "营建", "location_id": "两浙路"},
        {"source_fragment": "", "title": "无片段"},      # 丢
        {"source_fragment": "有片段", "title": ""},        # 丢
        "不是对象",                                        # 丢
    ]}))
    out = c.decree_action_plan("修两浙海塘")
    assert not out.get("_error"), out
    assert [a["title"] for a in out["actions"]] == ["修两浙海塘"]


def test_contract_truncates_and_cleans_text():
    c = _StubDecree(_reply({"decree_id": "d-3", "actions": [
        {"source_fragment": "修" * 400, "title": "题" * 80,
         "kind": "营建", "location_id": "两浙路"}]}))
    out = c.decree_action_plan("修")
    assert len(out["actions"][0]["title"]) == 40
    assert len(out["actions"][0]["source_fragment"]) == 200


def test_contract_does_not_ask_ai_for_final_values_or_code():
    """提示词必须**显式禁止**填最终生效数值/状态路径/公式（规格硬要求）。"""
    c = _StubDecree(_reply({"decree_id": "d-4", "actions": [
        {"source_fragment": "x", "title": "x", "kind": "财政", "location_id": "京西路"}]}))
    c.decree_action_plan("蠲免京西钱税", routes=["京西路"])
    sys_p = c.last_call[0]
    # 三条硬要求必须写进提示词：不填最终数值 / 不写状态路径与代码 / 拿不准就交 unresolved
    assert "最终生效数值" in sys_p
    assert "状态字段路径" in sys_p
    assert "代码" in sys_p
    assert "unresolved" in sys_p and "不要臆造" in sys_p


def test_contract_failure_does_not_fabricate_plan():
    """模型返回垃圾 → 拒绝式降级，**不得**凭空造一份计划。"""
    c = _StubDecree("这不是 JSON")
    out = c.decree_action_plan("修两浙海塘")
    assert out.get("_error"), out
    assert "actions" not in out
