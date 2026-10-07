# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：实现已迁入 core.domains.economy.dynamic_price（第十五包，2026-10-07）。
# 本模块**不复制任何算法**，也**不自己 import typing/`__future__`**——
# 旧路径公开面上的每个名字（含 `Dict`/`Optional`/`annotations` 这类绑定名与私有
# `_clamp`/`_num`/`_cfg`）都从**实现模块**转发，与 `core/numeric.py` 等既有桩同构；
# 差别会被 test_newpath_imports_b9 的"桩面每个名字都要有转发来源"判据抓到（本批就被抓到了）。
"""宋祚 · 动态物价与运费（兼容入口）。实现在 `core/domains/economy/dynamic_price.py`。"""
from core.domains.economy.dynamic_price import (  # noqa: F401
    Dict, LOGISTICS_TIERS, Optional, Tuple, _clamp, annotations, civil_logistics, gov_logistics, logistics_rate, update_goods_prices,
)
