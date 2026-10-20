# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.foundation.common.numeric
# 此模块**不复制任何算法**，仅显式转发。
from core.foundation.common.numeric import (
    Any, Optional, annotations,
    clamp, clamp_effect_multiplier, finite_number, finite_or_undefined,
    math, parse_number,
)

__all__ = ['Any', 'Optional', 'annotations', 'clamp', 'clamp_effect_multiplier', 'finite_number', 'finite_or_undefined', 'math', 'parse_number']
