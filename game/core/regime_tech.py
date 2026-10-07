# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.domains.economy.regime_tech
# 不复制实现；新模块不得导入本薄转发。
# game_state.py 取私有名 _starter_node_ids，档面必须含之。
from core.domains.economy.regime_tech import (
    Any, Dict, List,
    Optional, TECH_NODES, Tuple,
    _TECH_IDX, _starter_node_ids, _tech_nodes_index,
    advance_regime_tech, blueprint_of, charge_maintenance,
    deploy_cost, deploy_regime_building, deployable_nodes,
    is_starter, monthly_maintenance, next_researchable,
)

__all__ = ['Any', 'Dict', 'List', 'Optional', 'TECH_NODES', 'Tuple', '_TECH_IDX', '_starter_node_ids', '_tech_nodes_index', 'advance_regime_tech', 'blueprint_of', 'charge_maintenance', 'deploy_cost', 'deploy_regime_building', 'deployable_nodes', 'is_starter', 'monthly_maintenance', 'next_researchable']
