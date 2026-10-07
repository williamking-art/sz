# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.domains.construction.material_tech
# 不复制实现；新模块不得导入本薄转发。
from core.domains.construction.material_tech import (
    Any, Dict, List,
    MATERIALS_RECORD_KEY, MATERIAL_TECH_UNLOCKS, MaterialTechError,
    Optional, STATUS_LOCKED, STATUS_UNKNOWN,
    STATUS_UNLOCKED, STATUS_UNRECORDED, Tuple,
    UNLOCK_SOURCES, WIRING_HINT, _ALIAS_INDEX,
    _PREREQ_FIELDS, _SITES_KEYS, _STATUS_KEYS,
    _build_alias_index, _fin, _fmt,
    _int_in, _int_or_none, _num,
    _prereq_check, _status_stub, _str_tuple,
    _tech_dict, _tech_node_unlocked, _validate_entry,
    _validate_prereq, _validate_registry, annotations,
    check_material_prereq, effective_material_price, invalidate_material_tech_cache,
    is_material_unlocked, material_availability, material_sites,
    material_tradable, material_unlock_status, material_unlocked_by,
    math, register_material_tech, resolve_material_tech,
    unlock_material, unlock_materials_for_node,
)

__all__ = ['Any', 'Dict', 'List', 'MATERIALS_RECORD_KEY', 'MATERIAL_TECH_UNLOCKS', 'MaterialTechError', 'Optional', 'STATUS_LOCKED', 'STATUS_UNKNOWN', 'STATUS_UNLOCKED', 'STATUS_UNRECORDED', 'Tuple', 'UNLOCK_SOURCES', 'WIRING_HINT', '_ALIAS_INDEX', '_PREREQ_FIELDS', '_SITES_KEYS', '_STATUS_KEYS', '_build_alias_index', '_fin', '_fmt', '_int_in', '_int_or_none', '_num', '_prereq_check', '_status_stub', '_str_tuple', '_tech_dict', '_tech_node_unlocked', '_validate_entry', '_validate_prereq', '_validate_registry', 'annotations', 'check_material_prereq', 'effective_material_price', 'invalidate_material_tech_cache', 'is_material_unlocked', 'material_availability', 'material_sites', 'material_tradable', 'material_unlock_status', 'material_unlocked_by', 'math', 'register_material_tech', 'resolve_material_tech', 'unlock_material', 'unlock_materials_for_node']
