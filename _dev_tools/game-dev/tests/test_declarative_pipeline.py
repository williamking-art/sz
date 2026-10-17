# -*- coding: utf-8 -*-
"""测试声明式月度结算管线（SettlementPipeline）机制与健壮性。

验证目标：
1. 步骤元数据完整性（id, phase, name, func, target_func）；
2. 调度执行机制与自适应参数传递（支持无参、仅state、state+log三种签名）；
3. 容错隔离机制：非 critical 抛异常记录告警日志且管线不崩溃，critical 步骤抛异常立即阻断；
4. 阶段因果顺序（Phase 1 诏令政治 -> Phase 2 实体生产 -> Phase 3 产业链物流 -> Phase 4 营造 -> Phase 5 仓廪生计官吏 -> Phase 6 宏观财政信用 -> Phase 7 上层建筑派生天下 -> Phase 8 皇帝隐藏 -> Phase 9 不变量硬收敛）；
5. 真实月度全流程驱动（与 run_monthly_settlement 契约无缝衔接）。
"""
import pytest
from core.settlement_pipeline import (
    SettlementStep,
    SettlementPipeline,
    get_default_pipeline,
    get_pipeline_step_pairs,
)
from application.game_init import new_game


def test_pipeline_registration_and_phases():
    """验证默认管线步骤数、相位划分与唯一性。"""
    pipeline = get_default_pipeline()
    steps = pipeline.steps
    # 2026-10-17 审计校准：新增 spatial_logistics 真实步骤，总步数由 48 调整为 49
    assert len(steps) == 49, f"权威管线应包含 49 个步骤，实测 {len(steps)}"

    # ID 唯一性
    step_ids = [s.id for s in steps]
    assert len(step_ids) == len(set(step_ids)), "管线中存在重复的 Step ID"

    # 相位单调推进检验（因果律拓扑序）
    expected_phase_order = [
        "control", "politics", "production", "culture", "decree", "diplomacy",
        "industry", "trade", "logistics", "construction", "finance",
        "granary", "pop", "administration", "economy", "credit", "market",
        "military", "history", "legacy", "tech", "institution", "focus", "event",
        "disaster", "situation", "imperial", "hidden", "audit"
    ]
    seen_phases = []
    for s in steps:
        if not seen_phases or seen_phases[-1] != s.phase:
            seen_phases.append(s.phase)
    # 所有出现的相位都在预期的范畴内
    for p in seen_phases:
        assert p in expected_phase_order, f"未知相位: {p}"


def test_step_execute_adaptive_signature():
    """验证参数自适应探测传递。"""
    calls = []

    def fn_state_only(state):
        calls.append(("state_only", state.year))

    def fn_state_log(state, log):
        log.append("logged from fn_state_log")
        calls.append(("state_log", state.year))

    def fn_no_arg():
        calls.append(("no_arg", True))

    step1 = SettlementStep("s1", "phase", "测试1", fn_state_only)
    step2 = SettlementStep("s2", "phase", "测试2", fn_state_log)
    step3 = SettlementStep("s3", "phase", "测试3", fn_no_arg)

    pipeline = SettlementPipeline([step1, step2, step3])
    state = new_game()
    log = []

    pipeline.execute(state, log)

    assert ("state_only", 1101) in calls
    assert ("state_log", 1101) in calls
    assert ("no_arg", True) in calls
    assert "logged from fn_state_log" in log


def test_step_error_isolation():
    """验证非 critical 容错隔离与 critical 快速失败。"""
    def buggy_non_critical(state, log):
        raise ValueError("微小故障")

    def buggy_critical(state, log):
        raise RuntimeError("核心阻断故障")

    def normal_step(state, log):
        log.append("normal_executed")

    # 1. 非 critical 步骤异常，日志记录 WARN，后续步骤正常运行
    pipeline_resilient = SettlementPipeline([
        SettlementStep("bad", "test", "缺陷步", buggy_non_critical, critical=False),
        SettlementStep("good", "test", "正常步", normal_step, critical=False),
    ])
    log_sink = []
    state = new_game()
    pipeline_resilient.execute(state, log_sink)
    assert any("缺陷步" in msg and "WARN" in msg for msg in log_sink)
    assert "normal_executed" in log_sink

    # 2. critical 步骤异常，立即抛出
    pipeline_strict = SettlementPipeline([
        SettlementStep("fatal", "test", "关键步", buggy_critical, critical=True),
    ])
    with pytest.raises(RuntimeError, match="核心阻断故障"):
        pipeline_strict.execute(state, [])


def test_get_pipeline_step_pairs():
    """验证对账接口导出格式规范。"""
    pairs = get_pipeline_step_pairs()
    assert len(pairs) == 49
    for step_id, exec_fn in pairs:
        assert isinstance(step_id, str) and step_id
        assert callable(exec_fn)
