# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：实现已迁入 core.domains.production.production_chain（第十六包，2026-10-07）。
# 公开面上**每个名字都从实现模块转发**（含 `_` 开头的私有函数与 typing/`__future__` 绑定名）：
# 桩自己 import typing 会被 test_newpath_imports_b9 的"每个桩名都要有转发来源"判据抓到
# （第十五包就在本条上被抓过一次，范式统一比省两行更重要）。
"""宋祚 · 生产链（投料→产出→在途）（兼容入口）。实现在 `core/domains/production/production_chain.py`。"""
from core.domains.production.production_chain import (  # noqa: F401
    BUILDING_MATERIAL_DIMS, Dict, Optional, PRODUCTION_BUILDING_MULT, _BUILDING_LV_MAX, _DEFAULT_CAP, _building_mult, _pick_seat, _write_pending, _write_warehouse, annotations, goods_direct_production_backup, pending_total, settle_production_chain,
)
