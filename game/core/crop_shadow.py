# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.domains.production.crop_shadow
# 不复制实现；新模块不得导入本薄转发。
from core.domains.production.crop_shadow import (
    CLIMATE_BANDS, CROPS, CROP_BASE_RATE,
    CROP_CLIMATE_COEF, DIM_BASE_RATE, DIM_BUILDING,
    DIM_JOBS_PER_LEVEL, Dict, FARM_EMPLOY_SHARE_MAX,
    HIDDEN_HOUSEHOLD_PROVENANCE, HIDDEN_HOUSEHOLD_RATE, JOBS_PER_LEVEL,
    List, Optional, ROUTE_CLIMATE,
    STATUS_NOT_SUITABLE, STATUS_NO_ROUTE_DATA, STATUS_OK,
    Sequence, Tuple, YIELD_ANOMALY_DIMS,
    allocate_farm_pop, annotations, climate_coef,
    corvee_base, coverage_gap, crop_output,
    crop_status, is_plantable, land_tax_base,
    run_checks,
)

__all__ = ['CLIMATE_BANDS', 'CROPS', 'CROP_BASE_RATE', 'CROP_CLIMATE_COEF', 'DIM_BASE_RATE', 'DIM_BUILDING', 'DIM_JOBS_PER_LEVEL', 'Dict', 'FARM_EMPLOY_SHARE_MAX', 'HIDDEN_HOUSEHOLD_PROVENANCE', 'HIDDEN_HOUSEHOLD_RATE', 'JOBS_PER_LEVEL', 'List', 'Optional', 'ROUTE_CLIMATE', 'STATUS_NOT_SUITABLE', 'STATUS_NO_ROUTE_DATA', 'STATUS_OK', 'Sequence', 'Tuple', 'YIELD_ANOMALY_DIMS', 'allocate_farm_pop', 'annotations', 'climate_coef', 'corvee_base', 'coverage_gap', 'crop_output', 'crop_status', 'is_plantable', 'land_tax_base', 'run_checks']
