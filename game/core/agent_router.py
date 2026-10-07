# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 application.agent_router
# 不复制实现；新模块不得导入本薄转发。
from application.agent_router import (
    AGENT_DEFS, Dict, List,
    Optional, PENDING_CONTRACTS, _inject_one,
    _path_matches, _wake_by_diff, _wake_by_keywords,
    _wake_by_state, annotations, inject_woken_agents,
    log, logging, route_agents,
)

__all__ = ['AGENT_DEFS', 'Dict', 'List', 'Optional', 'PENDING_CONTRACTS', '_inject_one', '_path_matches', '_wake_by_diff', '_wake_by_keywords', '_wake_by_state', 'annotations', 'inject_woken_agents', 'log', 'logging', 'route_agents']
