# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.foundation.ledger.grain_ledger
# 此模块**不复制任何算法**，仅显式转发。
# 🔴 符号清单以**运行时 dir()** 枚举（AST 定义清单会漏 import 名，见迁移坑1）。
from core.foundation.ledger.grain_ledger import (
    Dict, List, Optional,
    GRAIN_MIGRATION_DIM, STORAGE_LOSS_TIERS, assert_loss_tiers_sane,
    grain_of, has_grain_bucket, storage_loss_rate, survey_grain, survey_grain_seats,
    project_grain_migration,
)

__all__ = ['Dict', 'GRAIN_MIGRATION_DIM', 'List', 'Optional',
           'STORAGE_LOSS_TIERS', 'assert_loss_tiers_sane', 'grain_of',
           'has_grain_bucket', 'storage_loss_rate', 'survey_grain', 'survey_grain_seats',
           'project_grain_migration']
