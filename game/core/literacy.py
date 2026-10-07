# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：实现已迁入 core.domains.culture.literacy（第二十包，2026-10-07）。
# 公开面上每个名字都从实现模块转发（含 `_` 开头私有名与 typing 绑定名）；
# ⚠️ 桩只保住『名字与对象』：打在桩上的 monkeypatch 不影响消费者，打在桩上的**重绑**也不改变实现侧同名绑定（第十七/十八包教训）。
"""宋祚 · literacy（兼容入口）。实现在 `core/domains/culture/literacy.py`。"""
from __future__ import annotations
from core.domains.culture.literacy import (  # noqa: F401
    Any, Dict, LITERACY_CAP, LITERACY_CONVERGE, LITERACY_FLOOR, MOD_ART_W, MOD_BASE, MOD_HI, MOD_LO, MOD_SUPPORT_W, MOD_UNREST_W, Optional, POP_LITERACY_BASE, Tuple, _CLASSES, _clamp, _num, _region_mod, annotations, init_literacy, literacy_target, log, logging, national_literacy, pop_literacy, route_literacy, settle_literacy,
)
__all__ = ["POP_LITERACY_BASE", "literacy_target", "init_literacy", "settle_literacy",
           "route_literacy", "national_literacy", "pop_literacy"]
