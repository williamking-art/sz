# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：实现已迁入 core.workflows.evaluation（第二十二包，2026-10-09）。
# 公开面上每个名字都从实现模块转发（含 `_` 开头私有名与常量绑定）；
# ⚠️ 桩只保住『名字与对象』：打在桩上的 monkeypatch 不影响消费者，打在桩上的**重绑**也不改变实现侧同名绑定（第十七/十八包教训）。
"""宋祚 · evaluation（兼容入口）。实现在 `core/workflows/evaluation.py`。"""
from core.workflows.evaluation import (  # noqa: F401
    END_YEAR, EVAL_OUTCOMES, EVAL_WEIGHTS, _DEF_GARRISON_SCORE_BASE, _garrison_breached, _get_outcome_desc, check_abdication, check_game_over, check_reach_end_year, evaluate_game,
)
