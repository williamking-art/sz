# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：实现已迁入 core.domains.diplomacy.treaty（第十四包，2026-10-07）。
# 本模块**不复制任何算法**，只显式枚举转发旧路径 `dir()` 上的**全部**名字——
# 含两个私有名 `_DIPLO_ATT` / `_att_delta`（本仓有测试直取私有符号的先例，漏一个就是静默断链），
# 以及从 content.data 绑定进来的常量（它们本来就在旧路径的公开面上，不能因搬迁而缩面）。
"""宋祚 · 外交条约（兼容入口）。实现在 `core/domains/diplomacy/treaty.py`。"""
from core.domains.diplomacy.treaty import (  # noqa: F401
    DIPLO_ATT_CAP, DOWRY_BASE, SUI_GONG_MULT, TRADE_INCOME, TREATY_TYPES,
    WAR_RISK_BOOST, _DIPLO_ATT, _att_delta, apply_treaty,
)
