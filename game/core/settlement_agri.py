# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.domains.production.settlement_agri
from core.domains.production.settlement_agri import (
    AGRI_HARVEST_MONTHS, AGRI_HARVEST_SHARE, AGRI_LEVEL_CAP,
    AGRI_LOSS_REDUCTION_CAP, AGRI_MAINTENANCE_MODES, AGRI_STAT_KEYS,
    AGRI_TRANSPORT_RELIEF_CAP, AGRI_UPGRADE_EFFECTS, AgriUpgradeError,
    Any, Dict, List,
    Optional, WIRING_HINT, _AGRI_LOOKALIKE_NAMES,
    _ALIAS_INDEX, _READOUT_KEYS, _build_alias_index,
    _collect_sources, _coverage, _finite_or_none,
    _grain_add, _invalidate_alias_index, _num,
    _pay_upkeep, _stat_add, _undefined,
    _validate_entry, annotations, apply_agri_effects,
    effective_canal_block, effective_spoil_rate, math,
    register_agri_upgrade, resolve_agri_upgrade, route_agri_effect,
)

__all__ = ['AGRI_HARVEST_MONTHS', 'AGRI_HARVEST_SHARE', 'AGRI_LEVEL_CAP', 'AGRI_LOSS_REDUCTION_CAP', 'AGRI_MAINTENANCE_MODES', 'AGRI_STAT_KEYS', 'AGRI_TRANSPORT_RELIEF_CAP', 'AGRI_UPGRADE_EFFECTS', 'AgriUpgradeError', 'Any', 'Dict', 'List', 'Optional', 'WIRING_HINT', '_AGRI_LOOKALIKE_NAMES', '_ALIAS_INDEX', '_READOUT_KEYS', '_build_alias_index', '_collect_sources', '_coverage', '_finite_or_none', '_grain_add', '_invalidate_alias_index', '_num', '_pay_upkeep', '_stat_add', '_undefined', '_validate_entry', 'annotations', 'apply_agri_effects', 'effective_canal_block', 'effective_spoil_rate', 'math', 'register_agri_upgrade', 'resolve_agri_upgrade', 'route_agri_effect']
