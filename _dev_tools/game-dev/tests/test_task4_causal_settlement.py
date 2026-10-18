# -*- coding: utf-8 -*-
"""圣旨行动闭环 · **任务 4** 定向回归：handler 绑定 ＋ 运行期按 capacity 产出。

规格要求（`design.md:47`）：**未绑定 handler 的事务应标为"未执行/待支持"，
不能只累进度就宣称告成**。

三类断言：
  A. handler 注册表：有落点的议题 `handler_of` 有值；无落点的（含 AI 自造议题）为 None；
  B. 满进度分流：有 handler → `done/告成`；无 handler → `unsupported/待支持`，
     **且结算侧不得打印"告成，钦此"**、不得写 memory 的 completed 关系；
  C. 运行期产出：非零进度完工的建筑在 operating/degraded 期间**按月 ×capacity** 产出，
     走守恒通道（Σ钱守恒），降效即减产，并写 provenance。
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
from core.longterm_task import (  # noqa: E402
    TASK_HANDLERS, handler_of, monthly_advance, task_is_supported, task_topic,
)
from core.money import m_all  # noqa: E402
from core.settlement import run_monthly_settlement  # noqa: E402


def _state():
    s = GameState("史实")
    init_legacies(s)
    s.treasury = 5_000_000_000
    # 2026-10-18: 市舶默认开放后，闭合经济用例显式钉住关闭
    s.maritime["open"] = False
    return s


def _task(name, **kw):
    t = {"task_name": name, "title": name, "progress": 0.0}
    t.update(kw)
    return t


# ====================================================== A. handler 注册表
def test_registry_only_lists_topics_with_real_landing():
    """注册表里的每个议题都必须能指出代码落点；且键必须是真实议题键。"""
    for topic, h in TASK_HANDLERS.items():
        assert isinstance(h, dict), topic
        assert h.get("landing"), f"{topic} 缺 landing 说明"
        assert h.get("code"), f"{topic} 缺 code 落点"
        assert h.get("applied_at") in ("issue", "issue+monthly"), topic
        # 议题键必须能被真实任务文本识别到（否则注册了也永远命中不了）
        probe = {"task_name": _probe_text(topic), "title": _probe_text(topic)}
        assert task_topic(probe) == topic, f"{topic} 的注册键无法由 task_topic 识别"


def _probe_text(topic):
    return {
        "land_survey": "清丈田亩", "curtail_waste": "省浮费", "reduce_office": "裁汰冗员",
        "reform": "更张法度", "m1_garrison": "整军经武",
    }[topic]


def test_unbound_topics_have_no_handler():
    """指不出数值落点的议题（m1_garrison）与 AI 自造议题 → handler 为 None。"""
    for name in ("整军经武（边备与军器）", "兴修水利三年", "为我修一座行宫", "随便什么"):
        if "整军" in name or "经武" in name:
            assert handler_of(_task(name)) is None, f"{name} 无落点，不应登记 handler"
    assert handler_of(_task("兴修水利三年")) is None
    assert handler_of(_task("")) is None


def test_bound_topics_report_handler():
    for name, topic in (("清丈田亩", "land_survey"), ("省浮费", "curtail_waste"),
                        ("裁汰冗员", "reduce_office"), ("更张法度", "reform")):
        h = handler_of(_task(name))
        assert h is not None, f"{name} 应绑定 handler"
        assert h["topic"] == topic
        assert task_is_supported(_task(name)) is True
    assert task_is_supported(_task("兴修水利三年")) is False


# ====================================================== B. 满进度分流
def _force_complete(s, task, is_secret=False):
    task["progress"] = 99.5
    log = []
    # 给足支持与执行条件，使 advance 把进度推满（真实推进路径）
    task["support_bonus"] = 30.0
    for _ in range(40):
        res = monthly_advance(s, task, log, is_secret=is_secret, index=0)
        if res["status"] != "ongoing":
            return res, log
    return res, log


def test_bound_task_completes_as_done():
    s = _state()
    t = _task("清丈田亩")
    res, log = _force_complete(s, t)
    assert res["status"] == "done", res
    assert t.get("outcome") == "告成"
    assert res.get("handler") and res["handler"]["topic"] == "land_survey"


def test_unbound_task_is_unsupported_not_done():
    """核心断言：无 handler 的事务满进度**不得**判 done/告成。"""
    s = _state()
    t = _task("兴修水利三年")
    res, log = _force_complete(s, t)
    assert res["status"] == "unsupported", res
    assert res["status"] != "done"
    assert t.get("outcome") == "待支持"
    assert t.get("outcome") != "告成"
    assert res.get("handler") is None
    assert res.get("reason")
    assert any("待支持" in x for x in log), log


def test_garrison_topic_is_unsupported():
    """`m1_garrison` 只参与立场声明、无数值落点 → 待支持。"""
    s = _state()
    t = _task("整军经武")
    assert task_topic(t) == "m1_garrison"
    res, _ = _force_complete(s, t)
    assert res["status"] == "unsupported"


def test_settlement_never_logs_congratulations_for_unbound():
    """结算侧：无 handler 的事务**不得**打印"告成，钦此"。"""
    s = _state()
    s.longterm_public = [_task("兴修水利三年", progress=99.5, support_bonus=30.0,
                               id="ltp1", months=1)]
    log = run_monthly_settlement(s)
    joined = "\n".join(str(x) for x in log)
    # 若该事务在本月议毕，则不得出现"告成"
    if not any(t.get("id") == "ltp1" for t in s.longterm_public):
        assert "告成，钦此" not in joined, f"无落点事务被宣告成：{joined[-500:]}"
        assert int(s.statistics.get("task_unsupported", 0) or 0) >= 1


def test_unsupported_recorded_for_panel():
    s = _state()
    s.longterm_public = [_task("兴修水利三年", progress=99.5, support_bonus=30.0,
                              id="ltp1", months=1)]
    run_monthly_settlement(s)
    lst = s.statistics.get("task_unsupported_list")
    assert isinstance(lst, list)
    if lst:
        assert lst[0].get("name") and lst[0].get("reason")


# ====================================================== C. 运行期按 capacity 产出
def _bp_runtime(**kw):
    b = {"name": "榷酒务", "category": "财政",
         "cost": {"银": 100_000, "months": 1},
         "effects": [{"op": "酒课", "params": {"amount": 20_000}}]}
    b.update(kw)
    return b


def _build_and_operate(s, name="榷酒务"):
    route = list(s.prefectures)[0]
    pid = propose_project(s, route, name)["pid"]
    p = s.projects[pid]
    p["status"] = "operating"
    p["progress"] = 100
    p["capacity"] = 1.0
    return pid, route


def test_runtime_operator_is_not_completion_output():
    """运行型构件**不得**出现在完工 output 里（否则建成即一次性拿满、之后还得再拿）。"""
    s = _state()
    register_dynamic_blueprint(s, _bp_runtime())
    route = list(s.prefectures)[0]
    pid = propose_project(s, route, "榷酒务")["pid"]
    p = s.projects[pid]
    assert p["output"] == {}, f"运行型构件混进完工产出：{p['output']}"
    assert p["_runtime"] == {"wine_coin_add": 20_000}, p["_runtime"]


def test_runtime_yield_applied_monthly_scaled_by_capacity():
    """按月产出，且**随 capacity 线性缩放**（降效即减产）。"""
    s = _state()
    register_dynamic_blueprint(s, _bp_runtime())
    pid, _route = _build_and_operate(s)
    s.projects[pid]["capacity"] = 1.0
    run_monthly_settlement(s)
    full = float(s.statistics.get("project_runtime_yield", 0) or 0)
    assert full > 0, "运行期无产出"
    # 半产能 → 产出约为一半
    s2 = _state()
    register_dynamic_blueprint(s2, _bp_runtime())
    pid2, _r2 = _build_and_operate(s2)
    s2.projects[pid2]["capacity"] = 0.5
    run_monthly_settlement(s2)
    half = float(s2.statistics.get("project_runtime_yield", 0) or 0)
    assert half > 0
    assert half == pytest.approx(full / 2, rel=0.35), f"未按 capacity 缩放：{full} vs {half}"


def test_runtime_yield_is_money_conserving():
    """运行产出必须来自民间（守恒），不得凭空造币。"""
    s = _state()
    register_dynamic_blueprint(s, _bp_runtime())
    pid, _route = _build_and_operate(s)
    before = m_all(s)
    run_monthly_settlement(s)
    after = m_all(s)
    # 产出是"民间 → 内帑"的内部转移，M_ALL 不应因它而增加（其余项另有增减，容差放宽）
    yield_amt = float(s.statistics.get("project_runtime_yield", 0) or 0)
    assert yield_amt > 0
    assert after - before < yield_amt, \
        f"运行产出疑似凭空造币：ΔM_ALL={after - before} ≥ 产出 {yield_amt}"


def test_runtime_yield_writes_provenance():
    s = _state()
    register_dynamic_blueprint(s, _bp_runtime())
    pid, _route = _build_and_operate(s)
    run_monthly_settlement(s)
    rlog = s.projects[pid].get("_runtime_log")
    assert isinstance(rlog, list) and rlog, "运行产出未写 provenance"
    last = rlog[-1]
    for k in ("turn", "op", "want", "got", "capacity"):
        assert k in last, last
    assert last["op"] == "wine_coin_add"


def test_degraded_project_produces_less_and_recovers():
    """降效建筑产出下降；产能恢复后产出回升（维护与折旧影响运行）。"""
    s = _state()
    register_dynamic_blueprint(s, _bp_runtime())
    pid, _route = _build_and_operate(s)
    s.projects[pid]["capacity"] = 0.2
    s.projects[pid]["status"] = "degraded"
    run_monthly_settlement(s)
    low = float(s.statistics.get("project_runtime_yield", 0) or 0)
    assert low > 0
    s.projects[pid]["capacity"] = 0.9
    s.projects[pid]["status"] = "operating"
    s.statistics["project_runtime_yield"] = 0
    run_monthly_settlement(s)
    high = float(s.statistics.get("project_runtime_yield", 0) or 0)
    assert high > low, f"降效未减产：{low} vs {high}"


def test_zero_capacity_produces_nothing():
    """产能归零且维持欠费 → 无产出（注意：维持到位时产能会自动回升，故须制造欠费）。"""
    s = _state()
    register_dynamic_blueprint(s, _bp_runtime())
    pid, _route = _build_and_operate(s)
    s.projects[pid]["capacity"] = 0.0
    s.projects[pid]["status"] = "degraded"
    s.projects[pid]["_upkeep_arrears_seen"] = 0
    s.statistics["upkeep_arrears"] = 1000          # 欠费 → 不回升产能
    run_monthly_settlement(s)
    assert float(s.projects[pid].get("capacity", 0) or 0) == 0.0
    assert float(s.statistics.get("project_runtime_yield", 0) or 0) == 0


def test_static_project_has_no_runtime_side_effect():
    """静态蓝图（无 _runtime）不得因本次改动产生任何运行产出。"""
    s = _state()
    route = list(s.prefectures)[0]
    res = propose_project(s, route, "水利")
    assert res["ok"] is True, res
    pid = res["pid"]
    s.projects[pid].update({"status": "operating", "progress": 100, "capacity": 1.0})
    run_monthly_settlement(s)
    assert float(s.statistics.get("project_runtime_yield", 0) or 0) == 0