# -*- coding: utf-8 -*-
"""宋祚 · 玩法数据分析（规划性骨架）

提供平衡数据挖掘与敏感性分析的占位接口。真实模拟时复用：
- core/settlement.run_monthly_settlement(state, seed_offset)  —— 12 步流水线硬约束
- core/evaluation.evaluate_game(state)  —— 七维结局评估（评分锚点）
- core/evaluation.check_game_over(state) —— 结束条件

纪律（见 README 三层隔离与单一权威源）：
- 不打包；路径引用以项目根为基准。
- 数值口径以 content/data.py 权威常量（如 TIER_RANGE、ANNUAL_TAX_BASE）为准，
  不复制魔法数字，避免漂移（已知质量债见 frontend-backend-review.md）。
"""
