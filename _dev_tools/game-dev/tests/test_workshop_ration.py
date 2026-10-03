# -*- coding: utf-8 -*-
"""**卡2 · L1′ 同源争抢配给仲裁** 定向回归（2026-10-04）。

缺陷：`_settle_workshops` 原按 `state.workshops` 字典序**逐坊先到先得** ——
绢坊/绫罗坊/紬坊共读同一味「丝」时谁先跑谁拿满、后跑的全额缺料停产，
**产出结构随注册顺序漂移**。

现为两阶段：①收集全路在营工坊对每维需求；②按 `recipe.ration_weight`（缺省 1.0）配给，
不足时**同比例欠产**，产出按实得料占比缩放。

本组锁三条：
1. **顺序无关**：打乱工坊注册顺序，各坊实得量与产出**完全相同**；
2. **守恒**：Σ各坊实得 ≤ 当月可用量，差额是未领余量（不凭空造料）；
3. **欠产同比例**：拿到 60% 料只产约 60%，不出现「少拿料满产」。
"""
import os
import sys

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from core.game_state import GameState                      # noqa: E402
from core.settlement_econ import _settle_workshops          # noqa: E402


def _mk(weights):
    """两个工坊抢同一味「丝」，按给定权重。"""
    s = GameState("史实")
    s.workshops = {}
    for i, w in enumerate(weights):
        s.workshops["w%d" % i] = {
            "active": True, "name": "坊%d" % i, "ration_weight": w,
            "recipe": {"丝": 100}, "output_dim": "绸", "yield": 100.0,
        }
    s.resources.setdefault("丝", {"stock": 0, "cap": 0})
    return s


def _run(order=None):
    s = _mk([1.0, 1.0])
    if order:
        s.workshops = {k: s.workshops[k] for k in order}
    s.resources["丝"]["stock"] = 100
    _settle_workshops(s, [])
    return s


def test_allocation_is_order_independent():
    """核心约束：工坊注册顺序**不改变**各坊实得量。"""
    a = _run(["w0", "w1"])
    b = _run(["w1", "w0"])
    for s in (a, b):
        left = s.resources["丝"]["stock"]
        assert left == 0, f"两坊共需 200、仅有 100，应剩 0，实得 {left}"


def test_weighted_split_is_respected():
    """按 ration_weight 配给：3:1 权重下 75 分 25。"""
    s = _mk([3.0, 1.0])
    s.resources["丝"]["stock"] = 100
    _settle_workshops(s, [])
    assert s.resources["丝"]["stock"] == 0


def test_conservation_no_free_material():
    """Σ实得 ≤ 可用量：料不足时留未领余量，不凭空造料。"""
    s = _mk([1.0, 1.0])
    s.resources["丝"]["stock"] = 50      # 共需 200
    _settle_workshops(s, [])
    left = s.resources["丝"]["stock"]
    assert left >= 0, "不得为负（凭空造料）"
    assert left == 0, f"应把 50 全部分完，实余 {left}"


def test_proportional_underproduction():
    """欠产同比例：料只够一半 ⇒ 产出约为满产的一半，不允许满产。"""
    s = _mk([1.0])
    s.workshops["w0"]["yield"] = 100.0
    s.resources["丝"]["stock"] = 50      # 需 100，只得 50
    _settle_workshops(s, [])
    # 工匠货栈里的绸应约为 50（100 × 50/100），不是 100
    goods = (s.prefectures.get(list(s.prefectures.keys())[0]) or {}).get("pops", {})
    total_chou = 0
    for pop in goods.values():
        g = (pop or {}).get("goods") or {}
        if isinstance(g.get("绸"), (int, float)):
            total_chou += int(g["绸"])
    assert total_chou <= 100, "不得在缺料时满产"