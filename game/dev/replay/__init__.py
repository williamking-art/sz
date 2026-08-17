# -*- coding: utf-8 -*-
"""宋祚 · 策略回放（规划性骨架）

记录/重放一局决策的逐月状态，用于极端场景兜底复现与平衡前后对比。
复用 core/settlement.run_monthly_settlement 的真实流水线与 core/evaluation 评分。
"""
import os
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def record_episode(state, out_path):
    """将一局关键节点序列化到 _scratch/ 下（不参与版本管理/打包）。"""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    snap = {
        "year": getattr(state, "year", None),
        "month": getattr(state, "month", None),
        "treasury": getattr(state, "treasury", None),
        "total_score": _safe_total(state),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)


def _safe_total(state):
    try:
        from core.evaluation import evaluate_game
        return evaluate_game(state).get("total")
    except Exception:
        return None
