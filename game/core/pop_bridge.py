# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.foundation.ledger.pop_bridge
# 此模块**不复制任何算法**，仅转发。
# 新模块不得导入本薄转发（避免反向边）。
# 🔴 显式重导出：`import *` 不会带下划线名（如 AFFILIATION_FIELDS），必须显式列出。
from core.foundation.ledger.pop_bridge import (
    POP_CLASSES, MEAN_FIELDS, SPLIT_FIELDS, seat_pop_weights,
    _split_int, AFFILIATION_FIELDS, split_affiliation_to_seats, aggregate_affiliation,
    split_pops_to_seats, aggregate_seat_pops, survey_pops, _NUM_FIELDS,
    sync_route_pops, pop_get, _field_weights, pop_set,
    pop_add, assert_pops_consistent, _VIOLATIONS, _GUARD_INSTALLED,
    _EXEMPT, _pops_write_exempt, _charging, _GuardedPops,
    _GuardedRow, install_pops_guard, install_all_guards, pops_guard_violations,
    reset_pops_guard, locate_pops, pop_obj_set, pop_obj_add,
    pop_seat_set, pop_seat_add,
)

__all__ = ['POP_CLASSES', 'MEAN_FIELDS', 'SPLIT_FIELDS', 'seat_pop_weights', '_split_int', 'AFFILIATION_FIELDS', 'split_affiliation_to_seats', 'aggregate_affiliation', 'split_pops_to_seats', 'aggregate_seat_pops', 'survey_pops', '_NUM_FIELDS', 'sync_route_pops', 'pop_get', '_field_weights', 'pop_set', 'pop_add', 'assert_pops_consistent', '_VIOLATIONS', '_GUARD_INSTALLED', '_EXEMPT', '_pops_write_exempt', '_charging', '_GuardedPops', '_GuardedRow', 'install_pops_guard', 'install_all_guards', 'pops_guard_violations', 'reset_pops_guard', 'locate_pops', 'pop_obj_set', 'pop_obj_add', 'pop_seat_set', 'pop_seat_add']
