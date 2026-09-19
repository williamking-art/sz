# -*- coding: utf-8 -*-
"""宋祚 · 数值工具单一权威（core/numeric.py）

**设立理由**（2026-09-19 代码质量全检 §1.2）：`_num` 在 4 个文件、`_finite` 在 2 个文件、
`_clamp` 在 5 个文件各自复制了一份**逐字相同**的实现（其中 3 份是本轮新引入的重复），
违反"口径单点"，且让"缺失值策略"散落在多处、容易各自漂移。

本模块把这组工具收敛为一处，并提供**语义明确的 API**（不是把不同业务语义强绑一起）：

| API | 语义 | 缺失（None / 非法串） | NaN / ±inf |
|---|---|---|---|
| `parse_number(v, default)` | 容错取数（原 `_num`/`_finite`） | 返回 `default` | 返回 `default` |
| `finite_or_undefined(v)` | **对外**语义（面板/AI：未定义） | `None` | `None` |
| `clamp(v, lo, hi)` | 通用钳位（与 `content.data.clamp` 同源） | — | — |
| `clamp_effect_multiplier(v, lo=0, hi=2)` | 效果系数钳位（诏令/局势推进） | 钳到下界 `lo` | 钳到边界 |

**未纳入**（语义不同，刻意保留在各自业务模块）：`content.data.clamp`（历史单点，本模块 re-export 保持一致）、
各模块的 `_num(v, default=50.0)` 这类"带业务默认值"的调用一律保留其默认值由调用方传入 ——
`parse_number` 只统一**实现**，不统一**默认值**。
"""
from __future__ import annotations

import math
from typing import Any, Optional

from content.data import clamp as clamp   # 与既有单点同源（re-export，避免又一份实现）

__all__ = ["parse_number", "finite_or_undefined", "clamp", "clamp_effect_multiplier"]


def parse_number(v: Any, default: float = 0.0) -> float:
    """容错取数：None / 字符串 / NaN / ±inf 一律回落 `default`。

    （原 `core/situations.py::_finite`、`core/decree_effect.py::_num` 等 6 份实现的统一体。）
    """
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):
        return default
    return f if math.isfinite(f) else default


def finite_or_undefined(v: Any) -> Optional[float]:
    """非有限 / 不可转换 → `None`（"未定义"语义，**不**回落 0）。

    用于对外读数（面板、AI 输入、序列化）：缺失就是缺失，禁止用 0 顶替。
    """
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    return f if math.isfinite(f) else None


def clamp_effect_multiplier(v: Any, lo: float = 0.0, hi: float = 2.0) -> float:
    """效果系数钳位（诏令实际效果 / 局势推进系数；缺省值域 0–2）。"""
    return clamp(parse_number(v, lo), lo, hi)
