# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：实现已迁入 core.domains.politics.split（第十七包，2026-10-07）。
# 公开面上每个名字都从实现模块转发（含 `_` 开头私有名与 typing/logging 绑定名）；
# ⚠️ 打在桩上的 monkeypatch 不会再影响消费者——两处提供方 patch 已同批改指实现模块。
"""宋祚 · 派系立场占比（faction_split）（兼容入口）。实现在 `core/domains/politics/split.py`。"""
from core.domains.politics.split import (  # noqa: F401
    Any, Dict, FACTION_NAMES, FACTION_SPLIT_INIT, List, TOL, _num, annotations, blend_entrants, defect_toward_satisfaction, ensure_faction_split, exit_faction_members, faction_of_class, log, logging, normalize_split, set_split, shift_split, split_of, validate_split,
)
