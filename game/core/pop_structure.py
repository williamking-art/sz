# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.foundation.ledger.pop_structure
# 不复制实现；新模块不得导入本薄转发。
from core.foundation.ledger.pop_structure import (
    Dict, FARM_POSITIONS, FARM_POSITION_SHARE,
    List, Tuple, _DING_KEY,
    _KOU_KEY, _ding_ratio, _nong_of,
    adjust_farm_slices, check_farm_invariants, ding_of,
    ensure_farm_slices, kou_of, move_pop_people,
    seed_farm_slices, service_ding_of, service_ding_total,
    sync_all_farm_slices,
)

__all__ = ['Dict', 'FARM_POSITIONS', 'FARM_POSITION_SHARE', 'List', 'Tuple', '_DING_KEY', '_KOU_KEY', '_ding_ratio', '_nong_of', 'adjust_farm_slices', 'check_farm_invariants', 'ding_of', 'ensure_farm_slices', 'kou_of', 'move_pop_people', 'seed_farm_slices', 'service_ding_of', 'service_ding_total', 'sync_all_farm_slices']
