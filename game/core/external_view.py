# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：实现已迁入 core.domains.diplomacy.external_view（第十四包，2026-10-07）。
# 显式枚举旧路径 `dir()` 的全部名字（含 content.data 绑定进来的表名与 `_` 开头的默认表）。
"""宋祚 · 外邦视图（兼容入口）。实现在 `core/domains/diplomacy/external_view.py`。"""
from core.domains.diplomacy.external_view import (  # noqa: F401
    EXTERNAL_PROVINCES, EXTERNAL_REGIMES, _EXTERNAL_PROVINCES_DEFAULT,
    external_pop_view, external_provinces,
)
