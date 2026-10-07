# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：实现已迁入 core.domains.production.farm_procurement（第十六包，2026-10-07）。
# 公开面上**每个名字都从实现模块转发**（含 `_` 开头的私有函数与 typing/`__future__` 绑定名）：
# 桩自己 import typing 会被 test_newpath_imports_b9 的"每个桩名都要有转发来源"判据抓到
# （第十五包就在本条上被抓过一次，范式统一比省两行更重要）。
"""宋祚 · 农户采购与余粮出售（兼容入口）。实现在 `core/domains/production/farm_procurement.py`。"""
from core.domains.production.farm_procurement import (  # noqa: F401
    Dict, FARM_PRICE_RATIO, FARM_PROCURE_DIMS, List, MERCHANT_BUY_RATIO, MERCHANT_SPEND_SHARE, Optional, PROCURE_MAX_TREASURY_SHARE, PROCURE_TARGET_MONTHS, _seat_of, _take_goods, _workshop_demand, annotations, procure_from_farmers, sell_surplus_to_merchants,
)
