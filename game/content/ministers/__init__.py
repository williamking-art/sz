# -*- coding: utf-8 -*-
"""大臣独立模块包。

对外导出：
- MINISTERS            大臣档案字典（含后台忠诚度、立绘文件名）
- loyalty_init()       开局忠诚度字典构造函数
- CENTRAL_ORG_INFO     中枢机构树（权限绑定在机构/职位上）
- AUTHORITY_MATTERS    事权归属表（事权归属机构，不归属个人）
- REFORM_TYPES         改制类型枚举
- get_portrait_path    按人名取立绘路径
- HISTORICAL_FIGURES   兼容别名（= MINISTERS），避免旧引用断裂
"""
from .data import (
    MINISTERS,
    loyalty_init,
    corruption_init,
    CENTRAL_ORG_INFO,
    AUTHORITY_MATTERS,
    REFORM_TYPES,
    get_portrait_path,
    org_lead,
)

# 兼容别名：旧代码 from content.data import HISTORICAL_FIGURES 已迁至此
HISTORICAL_FIGURES = MINISTERS

__all__ = [
    "MINISTERS", "HISTORICAL_FIGURES", "loyalty_init", "corruption_init",
    "CENTRAL_ORG_INFO", "AUTHORITY_MATTERS", "REFORM_TYPES",
    "get_portrait_path", "org_lead",
]
