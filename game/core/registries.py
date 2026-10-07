# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.foundation.registries
# 注意：M14 用例的 monkeypatch 打在本桩上会失效，该用例已改指实现模块。
from core.foundation.registries import (
    ARMY_RATE, BRANCH_BASE, BRANCH_PAY_CAP,
    BRANCH_TECH_GATE, EQUIP_PRICE, EQUIP_RATE,
    EQUIP_STD, RECRUIT_MONTHS, SPECIALIZATION_TIERS,
    TECH_EFFECT_WHITELIST, TECH_REGISTRY_MAX, _pay_equip_and_grain,
    _pay_of, _recruit_cost, build_branch_std,
    deactivate_branch, deactivate_node, dup_name_ok,
    node_entry, register_branch, register_node,
    sanity_effect, soft_cost_mult, spec_tier_index,
    tech_gate_ok,
)

__all__ = ['ARMY_RATE', 'BRANCH_BASE', 'BRANCH_PAY_CAP', 'BRANCH_TECH_GATE', 'EQUIP_PRICE', 'EQUIP_RATE', 'EQUIP_STD', 'RECRUIT_MONTHS', 'SPECIALIZATION_TIERS', 'TECH_EFFECT_WHITELIST', 'TECH_REGISTRY_MAX', '_pay_equip_and_grain', '_pay_of', '_recruit_cost', 'build_branch_std', 'deactivate_branch', 'deactivate_node', 'dup_name_ok', 'node_entry', 'register_branch', 'register_node', 'sanity_effect', 'soft_cost_mult', 'spec_tier_index', 'tech_gate_ok']
