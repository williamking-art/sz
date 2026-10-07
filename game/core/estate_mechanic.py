# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.domains.administration.estate_mechanic
# MIGRATE-NOTE: M7/M9 的 monkeypatch 已改指实现模块，打在本桩上会静默失效。
from core.domains.administration.estate_mechanic import (
    BOOM_MULT, BUILDING_COST_GROWTH, BUILDING_EFFECT_CAP,
    BUILDING_LEVEL_MULT, BUILDING_STD, INVEST_BASE,
    POP_BUILDING_EFFECT, POP_BUILDING_TYPES, _GENTRY,
    _estate_income, _estate_spend, _gentry_slot,
    _hoard_leaning, _inject_slice, _mirror_total,
    _prefs, _rows_with_slice, _withdraw_slice,
    building_cost, building_level_mult, credit_estate,
    estate_persona_mod, estate_slice_total, estate_tier,
    invest, pop_building_effect, random,
    seize_estate, settle_investments, settle_minister_estate,
    sync_estate_slices,
)

__all__ = ['BOOM_MULT', 'BUILDING_COST_GROWTH', 'BUILDING_EFFECT_CAP', 'BUILDING_LEVEL_MULT', 'BUILDING_STD', 'INVEST_BASE', 'POP_BUILDING_EFFECT', 'POP_BUILDING_TYPES', '_GENTRY', '_estate_income', '_estate_spend', '_gentry_slot', '_hoard_leaning', '_inject_slice', '_mirror_total', '_prefs', '_rows_with_slice', '_withdraw_slice', 'building_cost', 'building_level_mult', 'credit_estate', 'estate_persona_mod', 'estate_slice_total', 'estate_tier', 'invest', 'pop_building_effect', 'random', 'seize_estate', 'settle_investments', 'settle_minister_estate', 'sync_estate_slices']
