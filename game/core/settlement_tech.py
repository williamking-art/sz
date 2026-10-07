# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.domains.construction.settlement_tech
# 阶段 3 主体：科技攻关与工程归属 construction 域。
from core.domains.construction.settlement_tech import (
    _collect_from_pops, _log, _research_rate_mult,
    _settle_projects, _settle_tech_research, annotations,
    logging, math, transfer_public_funds_to_pops,
)

__all__ = ['_collect_from_pops', '_log', '_research_rate_mult', '_settle_projects', '_settle_tech_research', 'annotations', 'logging', 'math', 'transfer_public_funds_to_pops']
