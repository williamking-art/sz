# -*- coding: utf-8 -*-
"""作坊岗位/工价表（G-4 影子口径，2026-10-21 Jev A 0.536）。

⚠️ **玩法设定数据，非史料**：仅用于 G-4「工坊营运资金」影子预算，
不接正式结算、不直接改钱；用户/标定后可逐项校准。
- 作坊不在建筑 `JOBS_PER_LEVEL` 内，**不得**拿建筑岗位硬套；
- 当前实测仅 4 类作坊（酒坊/畜栏/麻坊/丝坊），按"每级岗位数"显式登记；
- 月工价取既有 `WAGE_RATE` default 档的 1.5 贯/岗/月（不另造价格体系）。
"""
from __future__ import annotations

from typing import Dict, Optional

#: 每级岗位数（玩法设定；缺失 ⇒ None，不臆造）
WORKSHOP_JOBS_PER_LEVEL: Dict[str, int] = {
    "酒坊": 80_000,
    "畜栏": 20_000,
    "麻坊": 60_000,
    "丝坊": 100_000,
}

#: 月工价（贯/岗/月）：沿用既有 WAGE_RATE default 档
WORKSHOP_WAGE_PER_JOB: float = 1.5

#: 口径标注（面板/报告可直接展示）
PROVENANCE = "玩法设定，非史料；G-4 影子预算用，未接正式结算"


def jobs_of(name: str, level: int = 1) -> Optional[int]:
    """该作坊类型×等级的岗位数；未知类型/非法等级 ⇒ `None`（不回落 0）。"""
    try:
        lv = int(level)
    except (TypeError, ValueError):
        return None
    base = WORKSHOP_JOBS_PER_LEVEL.get(str(name or ""))
    if base is None or lv <= 0:
        return None
    return int(base * lv)


def wage_of(name: str, level: int = 1,
            rate: Optional[float] = WORKSHOP_WAGE_PER_JOB) -> Optional[float]:
    """该作坊类型×等级的月工资义务；岗位/工价不可读 ⇒ `None`。"""
    jobs = jobs_of(name, level)
    if jobs is None or rate is None:
        return None
    return float(jobs) * float(rate)
