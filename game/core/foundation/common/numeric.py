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
| `_safe_int(v, default=None)` | **存档字段容错取整**（第八包自 `save_load_util` 原文迁入） | 返回 `default`（缺省 `None`） | 返回 `default`；**小数串也算缺省** |
| `_safe_float(v, default=None)` | 同上，浮点版 | 返回 `default`（缺省 `None`） | 返回 `default` |

⚠️ **`_safe_*` 与 `parse_number` 是刻意并存的两套口径**，别当重复代码合并：
`parse_number` 缺失回 `0.0`，`_safe_*` 缺失回 `None`（"缺失值不作 0"），且
`_safe_int("2.7")` 判为缺失而非截断。差异实测表见文件下方"近重复未合并"注记。

**未纳入**（语义不同，刻意保留在各自业务模块）：`content.data.clamp`（历史单点，本模块 re-export 保持一致）、
各模块的 `_num(v, default=50.0)` 这类"带业务默认值"的调用一律保留其默认值由调用方传入 ——
`parse_number` 只统一**实现**，不统一**默认值**。
"""
from __future__ import annotations

import math
from typing import Any, Optional

from content.data import clamp as clamp   # 与既有单点同源（re-export，避免又一份实现）

def finite_number(v: Any, default: Optional[float] = None) -> Optional[float]:
    """有限数值取数：`None`/`bool`/不可转/NaN/±inf ⇒ `default`（默认 `None`）。

    与 `parse_number` 的区别：默认**不回落 0**（缺失≠0），且 `bool` 不当数值；
    与 `_safe_float` 的区别：不做字符串 strip/容器白名单，只按 `float()` 可转性判定。
    2026-10-20 复用批：6 个模块曾各复制一份逐字节相同的 10 行 `_num`，现统一到此。
    """
    if v is None or isinstance(v, bool):
        return default
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):
        return default
    if f != f or f in (float("inf"), float("-inf")):
        return default
    return f


__all__ = ["parse_number", "finite_number", "finite_or_undefined", "clamp",
           "clamp_effect_multiplier"]


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


# ── 第八包（2026-10-07）：`_safe_int` / `_safe_float` 自 `core/save_load_util.py` 原文迁入。
# 迁到本模块的理由：这两个函数体**零存档语义**（只按值的类型/可转换性判定），属"跨域无业务归属"
# 的数值工具（架构方案 §106/§196）；而 `core/save_load.py` 是它们当前唯一调用方，
# 留在 persistence 反而会把通用件锁进专用目录。
# ⚠️ 刻意**不**并进 `__all__`：下划线名按模块私有约定处理，调用方一律显式 import，
#   避免悄悄扩大 `core.numeric` 的公开面。
# 🔴 已知**近重复未合并**（本批只搬不改）。实测三处实质差异（`default` 用各自缺省）：
#   ① 缺失回落值：`parse_number` 回 `0.0`，`_safe_*` 回 `None` —— 后者才符合"缺失值不作 0"；
#   ② 小数串：`_safe_int('2.7')` → `None`（`int('2.7')` 抛 ValueError），而 `parse_number('2.7')`
#      → `2.7`、`_safe_float('2.7')` → `2.7`。**存档里整数字段被写成小数串时会被判为缺失，不是截断**；
#   ③ 浮点入整数：`_safe_int(2.7)` → `2`（截断），`parse_number(2.7)` → `2.7`。
#   容器 / NaN / ±inf 三者行为其实等价（都回落各自 default）。
#   合并属**口径变更**（会改 ①②③ 的判定结果），须另立批次先证语义等价；
#   见 specs/cross-cutting/存档schema版本消费实况_2026-10-07.md §三之补 2。
def _safe_int(value, default=None):
    """宽松取整：空值 / 布尔 / 数字串可转则转；非法字符串、容器、NaN/inf → `default`。

    审查 P2-10：存档字段被写坏成对象/列表/乱码字符串时，`int()` 会抛未处理异常
    （经 UI/后端 → 500）。统一走此入口，把「档损坏」交给既有损坏档路径，
    而不是让异常冒泡。
    """
    if isinstance(value, bool):
        return int(value)
    if value is None or isinstance(value, (dict, list, tuple, set, bytes, bytearray)):
        return default
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return default
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _safe_float(value, default=None):
    """宽松取浮点：语义同 `_safe_int`，并剔除 NaN / ±inf。"""
    if isinstance(value, bool):
        return float(value)
    if value is None or isinstance(value, (dict, list, tuple, set, bytes, bytearray)):
        return default
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return default
    try:
        f = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return f if math.isfinite(f) else default
