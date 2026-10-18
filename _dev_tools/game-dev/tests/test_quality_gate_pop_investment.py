# -*- coding: utf-8 -*-
"""质量放行门 · P8 商人自主投资（2026-10-18；Jev：默认关 0.676）。

三层：天道档位 → 规则表 → 守恒执行。
本门钉住：
1. 档位缺失/非法 ⇒ 回落「稳健」（不伪造进取）；
2. 进取的投资比例 > 稳健 > 保守；
3. `plan_investments` 是**纯函数**（不改 state）；
4. 执行**守恒**：商人 wealth↓ + 工匠 wealth↑ 与成本相等，国库不变；
5. 资产落 `state.carriage["private"]`（不另开账本）；
6. 资本不足 ⇒ 失败并给 reason；
7. 开关关闭时结算日志无 `[商投]`（零行为变更）；
8. 边际成本按规模档递增（不因存量 5 万件爆溢出）。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

import content.data_constants as dc  # noqa: E402
from core.domains.economy import pop_investment as PI  # noqa: E402


def _state():
    from core.commands import new_game

    return new_game()


def _first_merchant(state):
    for route, pdata in state.prefectures.items():
        for seat_id, srow in (pdata.get("seats") or {}).items():
            pop = (srow.get("pops") or {}).get("商人")
            if isinstance(pop, dict):
                return route, seat_id, pop
    raise AssertionError("找不到商人 POP")


def test_posture_fallback_to_neutral():
    s = _state()
    assert PI.merchant_posture(s) == "稳健", "无槽位必须回落中性"
    s._economy_ai = {"posture": "乱码"}
    assert PI.merchant_posture(s) == "稳健", "非法档位必须回落中性"
    s._economy_ai = {"posture": "进取"}
    assert PI.merchant_posture(s) == "进取"


def test_rules_ordering():
    a = PI.posture_rules("进取")["invest_ratio"]
    b = PI.posture_rules("稳健")["invest_ratio"]
    c = PI.posture_rules("保守")["invest_ratio"]
    assert a > b > c, (a, b, c)


def test_plan_is_pure():
    s = _state()
    snap = copy.deepcopy(s.carriage), copy.deepcopy(s.prefectures["京畿路"]["seats"])