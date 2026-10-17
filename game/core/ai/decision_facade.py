# -*- coding: utf-8 -*-
"""大宋全域内嵌微观决策统一门面（EmbeddedDecisionFacade - 向下兼容转发桩）。

历史背景：
- 本门面现已全面升级为「天道业务门面（TianDaoFacade）」；
- 为确保全库既有调用平稳过渡，本桩将 EmbeddedDecisionFacade 别名映射至 TianDaoFacade。
"""
from __future__ import annotations

from core.ai.tiandao_facade import TianDaoFacade

__all__ = ["EmbeddedDecisionFacade"]

# 双名兼容别名
EmbeddedDecisionFacade = TianDaoFacade
