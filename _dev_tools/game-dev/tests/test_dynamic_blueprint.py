# -*- coding: utf-8 -*-
"""圣旨行动闭环 · **动态蓝图与多地点立项**定向回归（规格任务 3 的验收断言）。

要证明的四件事：
  1. 动态蓝图只能是**声明式数据**：未注册构件 / 非法字段 / 表达式一律拒绝；
  2. 注册后与静态蓝图**同路**：走同一 `can_build` / `propose_project` / 五态状态机；
  3. **地利前置不得被绕过**（静态用的 `blueprint_region_ok` 查不到动态 key 会返回 True）；
  4. **完工必须真落成**（原实现只认静态表 ⇒ 动态建筑完工后不登记，即"完工无产出"）；
  5. 一旨多址：逐路独立立项、一路失败不影响其余、同一台账、部分成功如实回报。
  6. 存档 round-trip：不落档则读档后动态蓝图全消失（孤儿工程）。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.blueprint_dynamic import (  # noqa: E402
    MAX_DYNAMIC_BLUEPRINTS, blueprint_key, dynamic_blueprint_output,
    register_dynamic_blueprint, resolve_dynamic_blueprint, validate_dynamic_blueprint,
)
from core.construction import (  # noqa: E402
    blueprint_cost, can_build, propose_project, propose_projects, resolve_blueprint,
)
from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402
from core.settlement import run_monthly_settlement  # noqa: E402


def _state():
    s = GameState("史实")
    init_legacies(s)
    s.treasury = 5_000_000_000
    return s


def _bp(**kw):
    b = {"name": "海塘", "category": "民生",
         "cost": {"silver": 120_000, "months": 2},
         "effects": [{"op": "仓容", "params": {"amount": 50_000}}]}
    b.update(kw)
    return b


# ============================================================ 1. 声明式数据边界
def test_valid_dynamic_blueprint_accepted_normalized():
    clean, errs = validate_dynamic_blueprint(_bp())
    assert clean is not None, errs
    assert clean["name"] == "海塘"
    assert clean["_dynamic"] is True
    # `cost.silver` 是**货币银两**（造价），与物料维「银」无关
    assert clean["cost"] == {"silver": 120000, "months": 2}
    assert clean["effects"] == [{"op": "仓容", "params": {"amount": 50000}}]
    assert clean["schema_version"] == 1


@pytest.mark.parametrize("bad,frag", [
    ({"name": ""}, "缺 name"),                                   # 无名
    ({"name": "X", "category": "修仙"}, "分类非法"),              # 分类白名单
    ({"name": "X", "cost": {"silver": -1}}, "silver"),     # 负造价（货币）
    ({"name": "X", "cost": {"months": 99}}, "months"),           # 工期越界
    ({"name": "X", "maintenance": 5}, "maintenance"),            # 维护费非 0-1
    ({"name": "X", "requires_region": "沿海"}, "requires_region"),  # 非数组
    ({"name": "X", "materials": {"木材": -5}}, "木材"),            # 负材料
])
def test_illegal_dynamic_blueprint_rejected(bad, frag):
    clean, errs = validate_dynamic_blueprint(bad)
    assert clean is None, f"应拒绝：{bad}"
    assert any(frag in e for e in errs), errs


def test_unregistered_effect_operator_rejects_whole_blueprint():
    """蓝图是**要落档的资产**：带未注册构件 → 整份拒绝（不是部分接受）。"""
    clean, errs = validate_dynamic_blueprint(_bp(effects=[
        {"op": "仓容", "params": {"amount": 1000}},
        {"op": "凭空造银", "params": {"amount": 9_999_999}},
    ]))
    assert clean is None
    assert any("未注册" in e for e in errs)


def test_effect_param_range_enforced_via_shared_registry():
    clean, errs = validate_dynamic_blueprint(_bp(effects=[
        {"op": "仓容", "params": {"amount": 99_999_999}}]))
    assert clean is None
    assert any("上限" in e for e in errs)


def test_blueprint_rejects_code_like_payload():
    """非声明式字段不得进入净蓝图（防夹带代码/路径）。"""
    clean, _ = validate_dynamic_blueprint(_bp(
        **{"script": "import os; os.system('rm -rf /')",
           "path": "treasury", "expr": "__import__('os')"}))
    assert clean is not None
    for k in ("script", "path", "expr"):
        assert k not in clean, f"净蓝图夹带了 {k}"


def test_extra_effect_params_are_dropped():
    clean, _ = validate_dynamic_blueprint(_bp(effects=[
        {"op": "仓容", "params": {"amount": 1000, "evil": 1}}]))
    assert clean is not None
    assert clean["effects"][0]["params"] == {"amount": 1000}


def test_empty_effects_warns_but_registers():
    clean, errs = validate_dynamic_blueprint(_bp(effects=[]))
    assert clean is not None
    assert any("无产出" in e for e in errs)


def test_blueprint_key_is_stable_and_name_derived():
    assert blueprint_key(_bp()) == blueprint_key(_bp())
    assert blueprint_key(_bp()) == blueprint_key(_bp(name="海塘"))
    assert blueprint_key(_bp(name="另一工程")) != blueprint_key(_bp())


# ============================================================ 2. 注册与解析
def test_register_then_resolve_by_name_and_key():
    s = _state()
    r = register_dynamic_blueprint(s, _bp())
    assert r["ok"] is True, r
    key = r["key"]
    assert key.startswith("dyn:")
    assert resolve_dynamic_blueprint(s, name="海塘")["name"] == "海塘"
    assert resolve_dynamic_blueprint(s, key=key)["name"] == "海塘"
    # 统一入口：resolve_blueprint 优先命中动态表
    got = resolve_blueprint("海塘", None, s)
    assert got and got["_dynamic"] is True
    # state=None 时**不**查动态表（保持既有调用方语义）
    assert resolve_blueprint("海塘", None, None) is None


def test_duplicate_registration_rejected():
    s = _state()
    assert register_dynamic_blueprint(s, _bp())["ok"] is True
    r2 = register_dynamic_blueprint(s, _bp())
    assert r2["ok"] is False
    assert any("已注册" in e for e in r2["errors"])


def test_blueprint_count_cap_enforced():
    s = _state()
    for i in range(MAX_DYNAMIC_BLUEPRINTS):
        assert register_dynamic_blueprint(s, _bp(name=f"工程{i}"))["ok"] is True
    r = register_dynamic_blueprint(s, _bp(name="超额"))
    assert r["ok"] is False
    assert any("上限" in e for e in r["errors"])


def test_registration_does_not_touch_money_or_projects():
    s = _state()
    tre, projs = s.treasury, len(s.projects)
    register_dynamic_blueprint(s, _bp())
    assert s.treasury == tre, "注册蓝图不得动钱"
    assert len(s.projects) == projs, "注册蓝图不得立项"


# ============================================================ 3. 地利前置（防绕过）
def test_dynamic_region_requirement_is_not_bypassed():
    """坑：`blueprint_region_ok` 查不到动态 key 会返回 True。必须按蓝图自身声明判。"""
    s = _state()
    register_dynamic_blueprint(s, _bp(name="海塘", requires_region=["沿海"]))
    # 找一个**非**沿海路与一个沿海路（按存档实际路型）
    sea = [r for r, p in s.prefectures.items() if "沿海" in str(p.get("type") or "")]
    inland = [r for r, p in s.prefectures.items() if "沿海" not in str(p.get("type") or "")]
    assert inland, "本局应有内陆路"
    ok_bad, errs_bad = can_build(s, inland[0], "海塘")
    assert ok_bad is False, f"{inland[0]} 不是沿海却可建 ⇒ 地利前置被绕过"
    assert any("地利不合" in e for e in errs_bad), errs_bad
    if sea:
        ok_sea, errs_sea = can_build(s, sea[0], "海塘")
        assert ok_sea is True, f"沿海路 {sea[0]} 应可建：{errs_sea}"


def test_dynamic_no_region_requirement_builds_anywhere():
    s = _state()
    register_dynamic_blueprint(s, _bp(name="普适工程", requires_region=[]))
    for r in list(s.prefectures)[:3]:
        ok, errs = can_build(s, r, "普适工程")
        assert ok is True, f"{r}: {errs}"


# ============================================================ 4. 立项 / 多址
def test_propose_project_for_dynamic_blueprint_carries_effects():
    s = _state()
    register_dynamic_blueprint(s, _bp(name="海塘", requires_region=["沿海"]))
    route = next(p for p, v in s.prefectures.items() if "沿海" in str(v.get("type") or ""))
    res = propose_project(s, route, "海塘")
    assert res["ok"] is True, res
    proj = s.projects[res["pid"]]
    assert proj["name"] == "海塘"
    assert proj["status"] == "proposed"
    assert proj["output"] == {"granary_cap_add": 50_000}, proj["output"]
    assert proj["_dynamic"] is True
    assert proj["blueprint_key"].startswith("dyn:")


def test_dynamic_cost_uses_same_growth_caliber_as_static():
    """动态与静态蓝图造价必须同口径（都按 BUILDING_COST_GROWTH 分级）。"""
    s = _state()
    register_dynamic_blueprint(s, _bp(name="海塘", cost={"silver": 100_000, "months": 2}))
    bp = resolve_blueprint("海塘", None, s)
    lv1, lv2 = blueprint_cost(bp, 1), blueprint_cost(bp, 2)
    assert lv1 == 100_000
    assert lv2 == 100_000 + int(100_000 * 1.8)


def test_propose_projects_multi_location_independent():
    """一旨多址：逐路独立立项；一路不合法不影响其余；结果逐项可诊断。"""
    s = _state()
    register_dynamic_blueprint(s, _bp(name="海塘", requires_region=["沿海"]))
    sea = [r for r, p in s.prefectures.items() if "沿海" in str(p.get("type") or "")]
    inland = [r for r, p in s.prefectures.items() if "沿海" not in str(p.get("type") or "")]
    if len(sea) < 2:
        pytest.skip("本局沿海路不足两条")
    routes = [sea[0], sea[1], inland[0], "不存在的路"]
    out = propose_projects(s, routes, "海塘")
    by = {x["route"]: x for x in out["results"]}
    assert by[sea[0]]["ok"] is True
    assert by[sea[1]]["ok"] is True
    assert by[inland[0]]["ok"] is False and any("地利不合" in e for e in by[inland[0]]["errors"])
    assert by["不存在的路"]["ok"] is False
    assert out["summary"] == {"total": 4, "succeeded": 2, "failed": 2,
                             "cost_total": 2 * 120_000}
    # 独立 project、**同一**台账
    pids = [x["pid"] for x in out["results"] if x["ok"]]
    assert len(set(pids)) == 2
    for pid in pids:
        assert pid in s.projects


def test_propose_projects_duplicate_route_in_batch_rejected():
    s = _state()
    register_dynamic_blueprint(s, _bp(name="海塘"))
    r = list(s.prefectures)[0]
    out = propose_projects(s, [r, r], "海塘")
    assert out["results"][0]["ok"] is True
    assert out["results"][1]["ok"] is False
    assert any("重复" in e for e in out["results"][1]["errors"])


def test_propose_projects_existing_project_not_duplicated():
    """已在案的同路同名工程不得因多址立项再建一份。"""
    s = _state()
    register_dynamic_blueprint(s, _bp(name="海塘"))
    r = list(s.prefectures)[0]
    assert propose_projects(s, [r], "海塘")["ok"] is True
    again = propose_projects(s, [r], "海塘")
    assert again["ok"] is False
    assert any("已有" in e for e in again["results"][0]["errors"])


def test_propose_projects_empty_routes_rejected():
    s = _state()
    register_dynamic_blueprint(s, _bp(name="海塘"))
    assert propose_projects(s, [], "海塘")["ok"] is False
    assert propose_projects(s, [""], "海塘")["ok"] is False


# ============================================================ 5. 完工落成（防"完工无产出"）
def test_dynamic_building_registers_on_completion():
    """原实现只认静态表 ⇒ 动态建筑完工后 `buildings` 不登记（完工无产出）。"""
    s = _state()
    register_dynamic_blueprint(s, _bp(name="海塘"))
    route = list(s.prefectures)[0]
    res = propose_project(s, route, "海塘")
    assert res["ok"] is True
    pid = res["pid"]
    # 直接推到完工前一刻，再跑一月结算让它落成（走真实五态状态机）
    s.projects[pid]["status"] = "funded"
    s.projects[pid]["progress"] = 99
    s.projects[pid]["speed"] = 50
    for _ in range(3):
        run_monthly_settlement(s)
        if s.projects[pid].get("status") == "operating":
            break
    proj = s.projects[pid]
    assert proj.get("status") == "operating", f"未完工：{proj.get('status')} 进度 {proj.get('progress')}"
    b = s.prefectures[route].get("buildings") or {}
    assert "海塘" in b, f"动态建筑完工但未登记（完工无产出）：{b}"
    assert b["海塘"] >= 1


def test_dynamic_completion_defense_add_actually_raises_troops():
    """【2026-10-03 修】厢军构件完工后**真的加兵**。

    原实现读 `out["defense_routes"]`，而该键**全库无生产者**（全仓只有那一行读它）
    ⇒ 循环体永不执行：厢军构件完工后 Σtroops Δ=0，而面板按 plan_readout 把
    `output={"defense_add":N}` 报成「效果生效」——机制建好却没落地。
    现改用**项目自带的地点**（`propose_project` 已落档 `proj["route"]`）。
    """
    s = _state()
    register_dynamic_blueprint(s, _bp(name="厢军营", effects=[
        {"op": "厢军", "params": {"amount": 1000}}]))
    route = list(s.prefectures)[0]
    pid = propose_project(s, route, "厢军营")["pid"]
    s.projects[pid]["status"] = "funded"
    s.projects[pid]["progress"] = 99
    s.projects[pid]["speed"] = 50

    def _troops():
        return sum(int(getattr(u, "troops", 0) or 0) for u in s.army_units
                   if u.station == route and u.tier == "厢军")

    before = _troops()
    for _ in range(3):
        run_monthly_settlement(s)
        if s.projects[pid].get("status") == "operating":
            break
    assert s.projects[pid].get("status") == "operating"
    delta = _troops() - before
    assert delta == 1000, (
        f"厢军构件完工后该路厢军 Σtroops Δ={delta}，应 +1000 —— "
        f"若为 0 则 `defense_routes` 无人生产的旧缺陷复发")


def test_dynamic_completion_applies_registered_output():
    """完工效果走**既有** output 键（仓容），不新增结算分支。"""
    s = _state()
    register_dynamic_blueprint(s, _bp(name="海塘"))
    route = list(s.prefectures)[0]
    pid = propose_project(s, route, "海塘")["pid"]
    s.projects[pid]["status"] = "funded"
    s.projects[pid]["progress"] = 99
    s.projects[pid]["speed"] = 50
    cap0 = s.granary_cap
    for _ in range(3):
        run_monthly_settlement(s)
        if s.projects[pid].get("status") == "operating":
            break
    assert s.projects[pid].get("status") == "operating"
    assert s.granary_cap == cap0 + 50_000, f"仓容未按构件落地：{cap0} → {s.granary_cap}"


def test_output_translation_only_uses_registered_output_keys():
    out = dynamic_blueprint_output(_bp(effects=[
        {"op": "仓容", "params": {"amount": 10}}, {"op": "厢军", "params": {"amount": 5}}]))
    assert out == {"granary_cap_add": 10, "defense_add": 5}
    # 未注册构件即使混进来也不产生落点（绝不凭空发明落地方式）
    assert dynamic_blueprint_output(
        {"effects": [{"op": "未知构件", "params": {"amount": 1}}]}) == {}


# ============================================================ 6. 存档 round-trip
def test_dynamic_blueprints_survive_save_load():
    from core.save_load import load_game, save_game
    s = _state()
    register_dynamic_blueprint(s, _bp(name="海塘"))
    route = list(s.prefectures)[0]
    pid = propose_project(s, route, "海塘")["pid"]
    assert save_game(s, 91) is True
    s2 = load_game(91)
    assert s2 is not None, "读档失败"
    assert isinstance(s2.dynamic_blueprints, dict)
    assert len(s2.dynamic_blueprints) == 1, "动态蓝图未随存档持久化"
    assert resolve_blueprint("海塘", None, s2) is not None, "读档后无法解析动态蓝图"
    assert pid in s2.projects, "在办工程随动态蓝图一起应保留"


def test_tampered_dynamic_blueprint_dropped_on_load():
    """读档不信任存档：塞入未注册构件的蓝图必须被丢弃（不整档失败）。"""
    from core.save_load import load_game, save_game
    s = _state()
    # 直接伪造一条非法蓝图（绕过注册校验，模拟改档/旧档）
    s.dynamic_blueprints["dyn:evil"] = {
        "schema_version": 1, "name": "邪法", "category": "民生",
        "cost": {"silver": 1, "months": 1}, "materials": {}, "maintenance": 0.005,
        "effects": [{"op": "凭空造银", "params": {"amount": 1}}], "_dynamic": True}
    assert save_game(s, 92) is True
    s2 = load_game(92)
    assert s2 is not None
    assert "dyn:evil" not in (s2.dynamic_blueprints or {}), \
        "含未注册构件的动态蓝图应被读档迁移丢弃"