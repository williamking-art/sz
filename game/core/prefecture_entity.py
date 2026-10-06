# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.foundation.ledger.prefecture_entity
# 此模块**不复制任何算法**，仅显式转发。
# 🔴 符号清单以**运行时 dir()** 枚举（AST 定义清单会漏 import 名，见迁移坑1）。
from core.foundation.ledger.prefecture_entity import (
    Any, Dict, List, Optional, annotations,
    BASIS_HISTORICAL, BASIS_AREA_ANCHOR, BASIS_AREA_ONLY, BASIS_MERGED,
    SEAT_LEVELS, ANCHOR_WEIGHTS, _SEP,
    seat_id_of, split_seat_id, duplicate_display_names, _geo, _table,
    all_seats, seats_of, circuit_of, seat_entity,
    prefecture_demog, circuit_aggregate, coverage_report,
)

__all__ = ['ANCHOR_WEIGHTS', 'Any', 'BASIS_AREA_ANCHOR', 'BASIS_AREA_ONLY', 'BASIS_HISTORICAL', 'BASIS_MERGED', 'Dict', 'List', 'Optional', 'SEAT_LEVELS', '_SEP', '_geo', '_table', 'all_seats', 'annotations', 'circuit_aggregate', 'circuit_of', 'coverage_report', 'duplicate_display_names', 'prefecture_demog', 'seat_entity', 'seat_id_of', 'seats_of', 'split_seat_id']
