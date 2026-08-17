# -*- coding: utf-8 -*-
"""宋祚 · 平衡数据挖掘（规划性骨架）

基于固定种子做大规模策略模拟，定位支配变量、死循环、滚雪球与无效选择。
复用 core/settlement 与 core/evaluation 的真实逻辑作为评分锚点。

落地后实现要点（见 songzuo-analytics/references/project_benchmarks.md 待回填清单）：
- 固定种子 / 可注入随机源（避免随机性干扰对比）；
- 隔离外部依赖：对 AI 用假后端覆盖合法/非法响应（参照 dev/_verify_ext.py 契约）；
- 输出敏感性排名、极端场景兜底、平衡前后差异，三态报告（通过/失败/未运行）。
"""
import os
import sys

# 项目根（dev/ 上两级）
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def run_simulation(state_factory, *, seeds=range(1, 1001), policy=None):
    """对给定策略 policy 在 seeds 上跑模拟，返回逐局七维评分与结束原因聚合。

    state_factory: () -> GameState  构造初始状态（注入固定种子由调用方控制）
    policy: (state) -> list[decree]  待评估策略（占位：当前直接跑默认结算）

    注意：当前为占位实现，仅演示接驳点，不实际跑千局（避免未落地依赖）。
    """
    from core.settlement import run_monthly_settlement
    from core.evaluation import evaluate_game, check_game_over

    results = []
    for seed in seeds:
        state = state_factory(seed)
        log = run_monthly_settlement(state, seed_offset=seed)
        ev = evaluate_game(state)
        over = check_game_over(state)
        results.append({
            "seed": seed,
            "total": ev.get("total"),
            "scores": ev.get("scores"),
            "game_over": over,
            "log_len": len(log),
        })
    return results


def sensitivity_ranking(results):
    """对 results 按 total 的跨种子方差排序，给出支配变量提示（占位）。"""
    if not results:
        return []
    return sorted(results, key=lambda r: (r.get("total") or 0))
