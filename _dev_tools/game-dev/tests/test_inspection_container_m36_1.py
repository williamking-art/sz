# -*- coding: utf-8 -*-
"""M36-1《察访编制与在途容器》契约回归（**监察世界接口层**；**零财政耦合**）。

架构边界（用户裁定 2026-10-11）：
  游戏系统提供**事实/约束/合法性/迁移/存档/守恒** → **AI** 决定是否派/派谁/查哪/查什么/明查密查/是否暂缓。
本批**不得**含：自动派遣算法、固定触发条件、自动监察策略、自动成案/处罚/定罪/抄没。

验收重点：① 信息权限正确（只读接口给事实、不给真账）；② 状态迁移幂等；
         ③ 存档兼容；④ 财政零耦合（不碰 POP/occupation/settlement_common/money/finance/tax/grain）。
"""
import copy
import json
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import (INSPECTION_KINDS, INSPECTION_MAX_ACTIVE_TASKS,  # noqa: E402
                          INSPECTION_WINDOW_SECRET)
from core import money  # noqa: E402
from core.commands import new_game  # noqa: E402
from core.inspection import (ensure_inspection_schema, enqueue_inspection,  # noqa: E402
                             inspection_candidates, inspection_capacity,
                             inspection_readout, inspection_task_list, inspection_tick,
                             window_for)
from core.settlement import run_monthly_settlement  # noqa: E402


def _seed(s, route, n=4):
    """测试夹具：把 `n` 名在岗官转出为**待阙**（保持 `officials` 总量不变，故 POP 不变量成立）。

    新局官员皆在岗（`on_post`），候选池为 0，须先造出待阙官才能差遣——这是"有限人力"的真实条件。
    """
    pool = s.prefectures[route]["pops"]["官僚"]
    move = min(int(n), int(pool.get("on_post", 0) or 0))
    pool["on_post"] = int(pool.get("on_post", 0) or 0) - move
    pool["waiting"] = int(pool.get("waiting", 0) or 0) + move
    return move


def _route_with_pool(s, n=4):
    """挑一条路并造出候选池（返回路名）。"""
    from core.domains.administration import officialdom as _od
    route = next(iter(s.prefectures))
    _seed(s, route, n)
    ok, bad = _od.check_invariants(s)
    assert ok, f"夹具不得破坏官员不变量：{bad}"
    assert inspection_candidates(s)[route]["candidates"] > 0
    return route


def _snapshot(s):
    return {"money": money.m_all(s),
            "prefs": copy.deepcopy(s.prefectures),
            "stats": copy.deepcopy(dict(s.statistics or {})),
            "cases": copy.deepcopy(getattr(s, "audit_cases", {}) or {}),
            "pop": getattr(s, "population", None)}


# ---------------------------------------------------------------- 容器 / 存档兼容

def test_containers_default_and_schema_idempotent():
    """新局容器默认空；`ensure_inspection_schema` 幂等（可安全重复调用）。"""
    s = new_game()
    assert s.inspection_tasks == []
    st = s.inspection_agent_state
    assert st == {"started": 0, "done": 0, "expired": 0}
    for _ in range(3):
        ensure_inspection_schema(s)
    assert s.inspection_tasks == [] and s.inspection_agent_state["started"] == 0
    # 容器被外部破坏后仍能自愈（旧档/脏档）
    s.inspection_tasks = None
    s.inspection_agent_state = None
    ensure_inspection_schema(s)
    assert s.inspection_tasks == [] and isinstance(s.inspection_agent_state, dict)


def test_legacy_save_without_inspection_keys_migrates():
    """旧档（无 `inspection_*`）加载：补默认容器，不报错、不误报在途。"""
    from core.save_load import _slot_path, load_game, save_game
    s = new_game()
    assert save_game(s, slot=71)
    p = _slot_path(71)
    with open(p, "r", encoding="utf-8") as f:
        raw = json.load(f)
    raw.pop("inspection_tasks", None)
    raw.pop("inspection_agent_state", None)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)
    s2 = load_game(71)
    assert s2 is not None
    assert s2.inspection_tasks == []
    assert s2.inspection_agent_state["started"] == 0
    if os.path.exists(p):
        os.remove(p)


def test_save_load_roundtrip_keeps_tasks():
    """存档往返：在途任务与编制计数不丢（含密查与剩余月数）。"""
    from core.save_load import _slot_path, load_game, save_game
    s = new_game()
    rk = _route_with_pool(s)
    assert enqueue_inspection(s, rk, "查粮")["ok"]
    assert enqueue_inspection(s, rk, "查赋", secret=True)["ok"]
    s.month, s.year = 5, 990
    inspection_tick(s)                       # 推进一次，剩余月数／幂等键一并存档
    assert save_game(s, slot=72)
    s2 = load_game(72)
    assert len(s2.inspection_tasks) == 2
    assert [t["kind"] for t in s2.inspection_tasks] == ["查粮", "查赋"]
    assert s2.inspection_tasks[1]["secret"] is True
    assert s2.inspection_tasks[0]["remaining"] == 2      # M36-2：首期只出发、不扣窗口
    assert s2.inspection_tasks[0]["status"] == "active"
    assert s2.inspection_agent_state["started"] == 2
    if os.path.exists(_slot_path(72)):
        os.remove(_slot_path(72))


# ---------------------------------------------------------------- 事实：候选池 / 容量

def test_candidates_readonly_from_existing_official_pool():
    """D1 候选池＝**既有官员池**（waiting＋sinecure），**只读**且不改任何状态。"""
    s = new_game()
    rk = _route_with_pool(s, 6)
    before = _snapshot(s)
    c1 = inspection_candidates(s)
    c2 = inspection_readout(s)
    assert set(c1) == set(s.prefectures)
    for name, p in s.prefectures.items():
        pool = (p.get("pops") or {}).get("官僚") or {}
        assert c1[name]["waiting"] == int(pool.get("waiting") or 0)
        assert c1[name]["sinecure"] == int(pool.get("sinecure") or 0)
        assert c1[name]["candidates"] == (c1[name]["waiting"] + c1[name]["sinecure"])
    assert c1[rk]["candidates"] == 6, "候选口径＝waiting＋sinecure（既有官员池）"
    assert c2["candidates_total"] == sum(v["candidates"] for v in c1.values())
    assert "on_post" in c1[rk], "在岗数只作事实给出（不参与可派口径）"
    assert _snapshot(s) == before, "只读接口不得改动 POP/财政/案卷"


def test_capacity_is_fixed_config_not_finance():
    """D2 上限＝**固定配置**（小朝廷 3／正常 5／强监察 8），**不随财政/人口变化**。"""
    s = new_game()
    assert inspection_capacity(s)["max_active_tasks"] == INSPECTION_MAX_ACTIVE_TASKS["正常"]
    assert inspection_capacity(s, tier="小朝廷")["max_active_tasks"] == 3
    assert inspection_capacity(s, tier="强监察")["max_active_tasks"] == 8
    s.imperial_treasury = 0                   # 财政剧烈变化（内帑见底）
    s.granary = 0
    s.population = int(getattr(s, "population", 10 ** 8) * 0.5)
    assert inspection_capacity(s)["max_active_tasks"] == INSPECTION_MAX_ACTIVE_TASKS["正常"], \
        "编制上限不得与财政/人口耦合"
    assert inspection_capacity(s)["active"] == 0
    assert inspection_capacity(s)["free"] == INSPECTION_MAX_ACTIVE_TASKS["正常"]
    # M36-2：档位**只由调用方显式传入**，接受别名
    assert inspection_capacity(s, tier="strong")["max_active_tasks"] == 8
    assert inspection_capacity(s, tier="small")["max_active_tasks"] == 3


def test_window_rules():
    """D3/D4 窗口：普通 2 月／复杂 3 月／**密查固定 4 月**（密查非提高成功率）。"""
    assert window_for("查粮") == 2 and window_for("查吏治") == 3
    assert window_for("查粮", True) == INSPECTION_WINDOW_SECRET == 4
    assert window_for("查吏治", True) == 4


# ---------------------------------------------------------------- 动作合法性（AI 提出，系统校验）

def test_enqueue_legality_checks():
    """系统只做**合法性校验**：路存在／种类在首批／未超上限／候选池 > 0。"""
    s = new_game()
    assert enqueue_inspection(s, "不存在的路", "查粮")["ok"] is False
    rk = _route_with_pool(s)
    assert enqueue_inspection(s, rk, "查军务")["ok"] is False, "D5：未开放种类必须拒绝"
    assert enqueue_inspection(s, rk, "查军务")["reason"]
    empty = next((n for n, v in inspection_candidates(s).items()
                  if v["candidates"] == 0), None)
    if empty:
        assert enqueue_inspection(s, empty, "查粮")["ok"] is False
    cap = inspection_capacity(s)["max_active_tasks"]
    for _ in range(cap):
        assert enqueue_inspection(s, rk, "查粮")["ok"]
    assert inspection_capacity(s)["free"] == 0
    assert enqueue_inspection(s, rk, "查粮")["ok"] is False
    # M36-2：受理（created）与在途（active）**同占名额**
    assert inspection_capacity(s)["occupied"] == cap
    assert inspection_capacity(s)["created"] == cap and inspection_capacity(s)["active"] == 0


def test_no_auto_dispatch_and_no_auto_case():
    """**不自动派遣、不自动成案**：空容器跑结算不得产生任务/案卷。"""
    s = new_game()
    before = _snapshot(s)
    for _ in range(6):
        s.month = 1 + (s.month % 12)
        run_monthly_settlement(s)
    assert s.inspection_tasks == [], "系统不得自动派遣（决策权归决策方：玩家／外部 AI）"
    assert s.inspection_agent_state["started"] == 0
    assert (getattr(s, "audit_cases", {}) or {}) == before["cases"], "不得自动成案"


# ---------------------------------------------------------------- 状态迁移（幂等）

def test_tick_transitions_and_idempotent_same_period():
    """状态迁移：同结算期**重复 tick 不重复处理**；`created→active→expired`；`remaining` 单调。

    🟢 **M36-2 契约升级**（2026-10-11 裁决）：生命周期为
    `created → active → completed ／ expired`——`enqueue` 只**受理**（`created`），
    首次月度推进才**出发**（`active`，出发当月不扣窗口），此后每期 `remaining −1`。
    """
    s = new_game()
    rk = _route_with_pool(s)
    assert enqueue_inspection(s, rk, "查粮")["ok"]           # 窗口 2 月
    assert s.inspection_tasks[0]["status"] == "created", "受理即为 created（待发）"
    s.year, s.month = 990, 3
    assert inspection_tick(s, []) == {"dispatched": 1, "advanced": 0, "expired": 0}
    t0 = s.inspection_tasks[0]
    assert t0["status"] == "active" and t0["dispatched_period"] == "990-3"
    assert t0["remaining"] == 2, "出发当月不扣窗口"
    assert inspection_tick(s, []) == {"dispatched": 0, "advanced": 0, "expired": 0}, \
        "同期必须幂等（不重复出发/扣减）"
    assert s.inspection_tasks[0]["remaining"] == 2
    s.month = 4
    assert inspection_tick(s) == {"dispatched": 0, "advanced": 1, "expired": 0}
    assert s.inspection_tasks[0]["remaining"] == 1
    s.month = 5
    assert inspection_tick(s) == {"dispatched": 0, "advanced": 1, "expired": 1}
    t = s.inspection_tasks[0]
    assert t["status"] == "expired" and t["remaining"] == 0
    assert t["settled_turn"] is not None and t["settled_period"] == "990-5"
    assert s.inspection_agent_state["expired"] == 1
    assert inspection_tick(s) == {"dispatched": 0, "advanced": 0, "expired": 0}, \
        "过期任务不得重复推进"
    assert inspection_capacity(s)["occupied"] == 0, "过期任务不再占名额"
    # 跨年不碰撞：新任务在新的一年推进仍生效
    assert enqueue_inspection(s, rk, "查赋")["ok"]
    s.year, s.month = 991, 3
    assert inspection_tick(s)["dispatched"] == 1


def test_monthly_settlement_advances_tasks_monthly():
    """接线：月度结算推进任务；**无任务时完全无操作**（月报逐字不变）。"""
    s = new_game()
    log = ["一", "二", "三"]
    assert inspection_tick(s, log) == {"dispatched": 0, "advanced": 0, "expired": 0}
    assert log == ["一", "二", "三"], "无任务不得写日志"
    rk = _route_with_pool(s)
    enqueue_inspection(s, rk, "查粮")
    s.month = 1 + (s.month % 12)
    run_monthly_settlement(s)                             # 第 1 期：出发
    assert s.inspection_tasks[0]["status"] == "active"
    assert s.inspection_tasks[0]["remaining"] == 2
    s.month = 1 + (s.month % 12)
    run_monthly_settlement(s)                             # 第 2 期：推进
    assert s.inspection_tasks[0]["remaining"] == 1


# ---------------------------------------------------------------- 冻结边界（财政/人口零耦合）

def test_zero_fiscal_and_population_coupling():
    """入列＋推进：**不改** money／prefectures／POP／statistics；只动监察容器。"""
    s = new_game()
    rk = _route_with_pool(s)
    before = _snapshot(s)
    assert enqueue_inspection(s, rk, "查赋", secret=True)["ok"]
    s.month = 1 + (s.month % 12)
    inspection_tick(s)
    assert money.m_all(s) == before["money"], "监察不得改财政"
    assert s.prefectures == before["prefs"], "监察不得改 POP/逐路状态"
    assert dict(s.statistics or {}) == before["stats"], "监察不得写统计"
    assert getattr(s, "population", None) == before["pop"], "监察不得改人口"
    assert inspection_task_list(s)[0]["kind"] == "查赋"
    after = _snapshot(s)
    inspection_readout(s)
    inspection_capacity(s)
    inspection_candidates(s)
    assert _snapshot(s) == after, "只读接口不得有副作用"


def test_source_boundary_no_finance_layers_touched():
    """源码边界：监察模块不依赖财政/POP 层；结算**唯一**接线点是 tick（不得自动派遣）。"""
    with open(os.path.join(_GAME_ROOT, "core", "inspection.py"), "r", encoding="utf-8") as f:
        src = f.read()
    for forbidden in ("settlement_common", "settlement_finance", "pop_bridge",
                      "pop_structure", "money", "audit_case"):
        assert f"from core.{forbidden}" not in src and f"import {forbidden}" not in src, \
            f"监察模块不得依赖 {forbidden}（零财政耦合 / 不成案）"
    assert "resolve_audit(" not in src, "到期不得自动成案（证据/审理属后续阶段）"
    with open(os.path.join(_GAME_ROOT, "core", "settlement.py"), "r", encoding="utf-8") as f:
        settle = f.read()
    assert "enqueue_inspection" not in settle, "结算**不得**自动派遣（决策权归 AI）"
    assert "inspection_tick" in settle, "结算需推进在途任务（状态迁移）"


def test_readout_exposed_for_ai():
    """AI 读数：`finance_readout()[\"inspection\"]` 给容量＋在途（事实与约束，无建议）。"""
    s = new_game()
    ro = s.finance_readout()["inspection"]
    assert set(ro) == {"capacity", "candidates_total", "candidates_by_route",
                       "status_counts", "identity", "tasks"}
    assert ro["capacity"]["max_active_tasks"] == INSPECTION_MAX_ACTIVE_TASKS["正常"]
    assert ro["capacity"]["tiers"] == dict(INSPECTION_MAX_ACTIVE_TASKS)
    assert set(ro["status_counts"]) == {"created", "active", "completed", "expired"}
    # M36-称谓契约升级：内容层称谓按朝代映射（宋＝察访/差遣）
    assert ro["identity"]["term"] == "察访" and ro["identity"]["dispatch"] == "差遣"
    assert len(INSPECTION_KINDS) == 3, "D5 首批仅三类（查民情/查军务暂缓）"



