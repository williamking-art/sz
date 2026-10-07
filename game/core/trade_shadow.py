# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.domains.economy.trade_shadow
# 不复制实现；新模块不得导入本薄转发。
# 影子模块：刻意不接入正式结算，生产调用方为 0属正常。
from core.domains.economy.trade_shadow import (
    ABSTRACT_TRADERS, COND_MULT_BEST, COND_MULT_WORST,
    DISTANCE_BAND, Dict, LOGISTICS_FEE,
    OVER_TAX_SHARE, Optional, REGIME_IMPORTS,
    ROUTE_WATERWAY, SEA_FREIGHT, SEA_TRADERS,
    STAY_TAX_SHARE, TERRAIN_MULT, Tuple,
    WAR_MULT, WATERWAY_TIER_MULT, WATER_FREIGHT,
    annotations, canal_condition, condition_mult,
    export_quote, import_quote, land_freight,
    road_condition, run_checks, run_checks2,
    run_checks3, sea_freight, tax_cost,
    tax_split, trade_net, trade_total_cost,
    water_freight, water_freight_tiered, waterway_tier,
)

__all__ = ['ABSTRACT_TRADERS', 'COND_MULT_BEST', 'COND_MULT_WORST', 'DISTANCE_BAND', 'Dict', 'LOGISTICS_FEE', 'OVER_TAX_SHARE', 'Optional', 'REGIME_IMPORTS', 'ROUTE_WATERWAY', 'SEA_FREIGHT', 'SEA_TRADERS', 'STAY_TAX_SHARE', 'TERRAIN_MULT', 'Tuple', 'WAR_MULT', 'WATERWAY_TIER_MULT', 'WATER_FREIGHT', 'annotations', 'canal_condition', 'condition_mult', 'export_quote', 'import_quote', 'land_freight', 'road_condition', 'run_checks', 'run_checks2', 'run_checks3', 'sea_freight', 'tax_cost', 'tax_split', 'trade_net', 'trade_total_cost', 'water_freight', 'water_freight_tiered', 'waterway_tier']
