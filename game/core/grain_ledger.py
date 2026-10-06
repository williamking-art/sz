# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.foundation.ledger.grain_ledger
# 此模块**不复制任何算法**，仅显式转发。
# 🔴 符号清单以**运行时 dir()** 枚举（AST 定义清单会漏 import 名，见迁移坑1）。
from core.foundation.ledger.grain_ledger import (
    Dict, List, Optional,
    GRAIN_MIGRATION_DIM, grain_of, has_grain_bucket, survey_grain,
)

__all__ = ['Dict', 'GRAIN_MIGRATION_DIM', 'List', 'Optional', 'grain_of', 'has_grain_bucket', 'survey_grain']
