# -*- coding: utf-8 -*-
"""圣旨行动闭环 · 收尾三缺口定向回归（规格任务 2/7 ＋ 运行期粮类）。

  A. **跨提交幂等**：同一 action id 第二次提交 → 拒绝重复立项（`plan_commit`）；
  B. **子 schema 版本迁移**：旧档可迁移、超版本**拒绝该段**（不猜、不降级解释）；
  C. **运行期粮类守恒落点**：籴买走 `_state_grain_trade`（太仓+粮/国库−钱/民间售粮），
     不凭空造粮，且同样按 capacity 缩放。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.blueprint_dynamic import register_dynamic_blueprint  # noqa: E402
from core.construction import propose_project  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402
from core.money import m_all  # noqa: E402
from core.plan_commit import (  # noqa: E402
    PLAN_ACTION_SCHEMA_VERSION, commit_plan, existing_action_ids,
)
from core.settlement import run_monthly_settlement  # noqa: E402


def _state():
    s = GameState("史实")
    init_legacies(s)
    s.treasury = 5_000_000_000
    return s


def _plan(route="两浙路", name="海塘", decree_id="d-1"):
    return {"decree_id": decree_id, "actions": [{
        "title": name, "source_fragment": "修海塘", "kind": "营建",
        "location_id": route, "blueprint_proposal": {
            "name": name, "category": "民生",
            "cost": {"silver": 100_000, "months": 1},
            "effects": [{"op": "仓容", "params": {"amount": 20_000}}]}}]}


# ====================================================== A. 跨提交幂等
def test_first_commit_submits_and_registers():
    s = _state()
    out = commit_plan(s, _plan())
    assert out["ok"] is True, out
    assert out["summary"]["submitted"] == 1
    r = out["results"][0]
    assert r["status"] == "submitted" and r["pid"] in s.projects
    assert r["blueprint_key"].startswith("dyn:")
    # 登记表落档结构
    reg = s.plan_actions
    assert reg[r["id"]]["pid"] == r["pid"]
    assert reg[r["id"]]["schema_version"] == PLAN_ACTION_SCHEMA_VERSION
    assert existing_action_ids(s) == {r["id"]}


def test_second_commit_is_idempotent_no_duplicate_project():
    """核心断言：同一计划重复提交**不得**建出第二份工程。"""
    s = _state()
    first = commit_plan(s, _plan())
    pid1 = first["results"][0]["pid"]
    n_proj = len(s.projects)
    second = commit_plan(s, _plan())
    r2 = second["results"][0]
    assert r2["status"] == "already_submitted", second
    assert r2["pid"] == pid1
    assert len(s.projects) == n_proj, "重复提交建出了第二份工程"
    assert second["summary"]["already_submitted"] == 1
    assert second["summary"]["submitted"] == 0
    # ok=False：本次**没有任何新动作**落地（不伪装成成功提交）
    assert second["ok"] is False


def test_idempotency_survives_reordering_and_revalidation():
    """action id 不含序号 ⇒ 重排后仍判重复（否则重复立项会漏过）。"""
    s = _state()
    p = _plan()
    p["actions"].append({"title": "疏浚", "source_fragment": "疏浚", "kind": "营建",
                         "location_id": "京畿路", "blueprint_proposal": {
                             "name": "疏浚", "cost": {"silver": 50_000, "months": 1},
                             "effects": []}})
    commit_plan(s, p)
    reordered = {"decree_id": "d-1", "actions": list(reversed(p["actions"]))}
    out = commit_plan(s, reordered)
    assert out["summary"]["already_submitted"] == 2, out
    assert out["summary"]["submitted"] == 0


def test_different_decree_is_not_blocked():
    """不同旨意 ⇒ 不同 action id ⇒ 不互相拦截（但同路同名工程仍受既有去重约束）。"""
    s = _state()
    commit_plan(s, _plan(route="两浙路", decree_id="d-1"))
    # 换一路、换名字：不受前一道旨意影响
    out = commit_plan(s, _plan(route="京畿路", name="汴堤", decree_id="d-2"))
    assert out["summary"]["submitted"] == 1, out
    assert out["summary"]["already_submitted"] == 0


def test_same_route_same_name_blocked_by_project_dedup():
    """跨旨意但同路同名：action id 不同（不算重复提交），但**蓝图/工程去重**仍拦住。"""
    s = _state()
    commit_plan(s, _plan(route="两浙路", name="海塘", decree_id="d-1"))
    out = commit_plan(s, _plan(route="两浙路", name="海塘", decree_id="d-2"))
    assert out["summary"]["submitted"] == 0
    r = out["results"][0]
    assert r["status"] == "rejected", r
    msg = " ".join(str(x) for x in (r.get("errors") or []))
    assert "海塘" in msg and ("已注册" in msg or "已有" in msg), msg


def test_rejected_plan_commits_nothing():
    s = _state()
    bad = {"decree_id": "d-x", "actions": [
        {"title": "广州建港", "source_fragment": "x", "kind": "营建", "location_id": "广州"}]}
    n0 = len(s.projects)
    out = commit_plan(s, bad)
    assert out["ok"] is False
    assert len(s.projects) == n0, "未通过校验却建了工程"
    assert not s.plan_actions, "未通过校验却写了登记表"


def test_non_building_action_registered_only():
    """非营建动作只登记（取得幂等身份），本模块不落数值。"""
    s = _state()
    p = {"decree_id": "d-nb", "actions": [
        {"title": "蠲免京西", "source_fragment": "x", "kind": "财政",
         "location_id": "京西路"}]}
    out = commit_plan(s, p)
    assert out["results"][0]["status"] == "registered_only"
    assert out["results"][0]["id"] in s.plan_actions
    assert not s.projects


def test_commit_does_not_touch_money():
    s = _state()
    before = (s.treasury, m_all(s))
    commit_plan(s, _plan())
    assert (s.treasury, m_all(s)) == before, "提交阶段不应动钱（钱在工程结算时走守恒通道）"


# ====================================================== B. schema 迁移
def test_plan_schemas_persisted_and_roundtrip():
    from core.save_load import _plan_schema_versions, load_game, save_game
    s = _state()
    commit_plan(s, _plan())
    assert save_game(s, 93) is True
    s2 = load_game(93)
    assert s2 is not None
    assert s2.plan_actions, "行动登记表未落档"
    assert len(s2.dynamic_blueprints) == 1
    # 幂等身份在读档后仍有效
    out = commit_plan(s2, _plan())
    assert out["summary"]["already_submitted"] == 1
    assert _plan_schema_versions()["plan_action"] == PLAN_ACTION_SCHEMA_VERSION


def test_old_save_without_plan_schemas_migrates():
    """旧档（无 plan_schemas 键）→ 按 v1 迁移，动态蓝图逐条重过校验器。"""
    from core.save_load import load_game, save_game
    s = _state()
    register_dynamic_blueprint(s, {
        "name": "海塘", "cost": {"silver": 100_000, "months": 1},
        "effects": [{"op": "仓容", "params": {"amount": 100}}]})
    assert save_game(s, 94) is True
    s2 = load_game(94)
    assert s2 is not None and len(s2.dynamic_blueprints) == 1


def test_higher_schema_version_section_is_refused():
    """超版本子 schema → **拒绝该段**（不猜、不降级解释），不是静默当旧档。"""
    import json
    from core.save_load import _slot_path, load_game, save_game
    s = _state()
    commit_plan(s, _plan())
    assert save_game(s, 95) is True
    p = _slot_path(95)
    with open(p, encoding="utf-8") as f:
        raw = json.load(f)
    raw["plan_schemas"] = {"dynamic_blueprint": 99, "plan_action": 99}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)
    s2 = load_game(95)
    assert s2 is not None, "拒绝子段不应导致整档拒绝"
    assert not s2.dynamic_blueprints, "超版本动态蓝图段应被拒绝"
    assert not s2.plan_actions, "超版本行动登记段应被拒绝"


# ====================================================== C. 运行期粮类落点
def _bp_grain():
    return {"name": "常平仓", "category": "财政", "cost": {"silver": 100_000, "months": 1},
            "effects": [{"op": "籴买", "params": {"amount": 5_000}}]}


def _operate(s, name="常平仓"):
    pid = propose_project(s, list(s.prefectures)[0], name)["pid"]
    s.projects[pid].update({"status": "operating", "progress": 100, "capacity": 1.0})
    return pid


def test_grain_operator_registered_and_is_runtime():
    from core.decree_plan import BUILTIN_OPERATORS
    assert "籴买" in BUILTIN_OPERATORS
    assert BUILTIN_OPERATORS["籴买"]["timing"] == "runtime"
    assert BUILTIN_OPERATORS["籴买"]["output_key"] == "grain_buy"


def test_grain_runtime_buys_into_granary_conservatively():
    """籴买：太仓得粮、国库出钱、民间售粮——钱粮两组守恒，不凭空造粮。

    注意：月度结算里太仓另有征粮/发放等步骤，**不能**用太仓净额判断本构件是否生效；
    故以 provenance（`_runtime_log` / `project_runtime_grain`）为准，并核对钱未凭空销毁。
    """
    s = _state()
    register_dynamic_blueprint(s, _bp_grain())
    pid = _operate(s)
    p = s.projects[pid]
    assert p["_runtime"] == {"grain_buy": 5_000}, p["_runtime"]
    assert p["output"] == {}, "粮类运行构件不得混进完工产出"
    m0 = m_all(s)
    run_monthly_settlement(s)
    got = float(s.statistics.get("project_runtime_grain", 0) or 0)
    assert got > 0, "运行期未籴买"
    rlog = s.projects[pid].get("_runtime_log")
    assert rlog and rlog[-1]["op"] == "grain_buy"
    assert rlog[-1]["got"] > 0 and "cost" in rlog[-1]
    # 钱粮守恒**用对照态 A/B 判定**（游戏本身每月有 ~37 贯的常态漂移，
    # 用绝对阈值会把常态漂移误判成"凭空销毁"）。
    s2 = _state()
    m2_0 = m_all(s2)
    run_monthly_settlement(s2)
    drift = m_all(s2) - m2_0
    assert abs((m_all(s) - m0) - drift) <= 200, \
        f"籴买改变了 M_ALL 轨迹：{(m_all(s) - m0)} vs 对照 {drift}"


def test_grain_runtime_scales_with_capacity():
    """按 capacity 缩放（注意维持到位时产能会回升 0.05，故以日志记录的实际产能核对）。"""
    s = _state()
    register_dynamic_blueprint(s, _bp_grain())
    pid = _operate(s)
    s.projects[pid]["capacity"] = 0.5
    run_monthly_settlement(s)
    got = float(s.statistics.get("project_runtime_grain", 0) or 0)
    cap_logged = float(s.projects[pid]["_runtime_log"][-1]["capacity"])
    assert cap_logged <= 0.56, cap_logged            # 只回升 0.05
    assert got == pytest.approx(5_000 * cap_logged, abs=2), (got, cap_logged)
    assert got < 5_000, "未按产能减产"


def test_grain_runtime_respects_pop_supply_limit():
    """民间存粮不足 → 少买（按实入账），绝不造粮。"""
    s = _state()
    register_dynamic_blueprint(s, {
        "name": "常平仓", "category": "财政",
        "cost": {"silver": 100_000, "months": 1},
        "effects": [{"op": "籴买", "params": {"amount": 200_000}}]})
    _operate(s)
    total_pop_grain = sum(float((p.get("pops") or {}).get(k, {}).get("grain", 0) or 0)
                          for p in s.prefectures.values()
                          for k in ("农", "士绅", "工匠", "商人", "官僚", "兵"))
    run_monthly_settlement(s)
    got = float(s.statistics.get("project_runtime_grain", 0) or 0)
    assert got > 0
    assert got <= total_pop_grain + 1, "买入量超过了民间存粮（凭空造粮）"