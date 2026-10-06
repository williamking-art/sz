# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.foundation.ledger.grain_bridge
# 此模块**不复制任何算法**，仅转发。
# 新模块不得导入本薄转发（避免反向边）。
# 🔴 显式重导出：`import *` 不会带下划线名（如 AFFILIATION_FIELDS），必须显式列出。
from core.foundation.ledger.grain_bridge import (
    grain_get, grain_target, _delegate, grain_set,
    grain_add, backfill_grain_to_seats,
)

__all__ = ['grain_get', 'grain_target', '_delegate', 'grain_set', 'grain_add', 'backfill_grain_to_seats']
