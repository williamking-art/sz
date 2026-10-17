# -*- coding: utf-8 -*-
"""大宋内置本地决策引擎（Embedded Jev Engine - 向下兼容转发桩）。

历史背景：
- 本模块原为临时内嵌决策模块；
- 现已全面升级为大宋世界观「天道裁决体系（TianDaoEngine）」；
- 为确保全库既有调用平稳过渡，本桩将 EmbeddedJevEngine 别名映射至 TianDaoEngine。
"""
from __future__ import annotations

from core.ai.tiandao_engine import TianDaoEngine

__all__ = ["EmbeddedJevEngine"]

# 双名兼容别名
EmbeddedJevEngine = TianDaoEngine
