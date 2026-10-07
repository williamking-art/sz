# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：实现已迁入 core.domains.economy.regime_fiscal（第十八包，2026-10-07）。
# 公开面每个名字都从实现模块转发（含私有与 typing 绑定名）。
# ⚠️ 桩不是行为开关：行为类 monkeypatch 必须打在实现模块上
#   （见 test_domains_politics_b17::test_stub_is_not_a_behavior_switch）。
"""宋祚 · 政权财政（加征/削减裁定）（兼容入口）。实现在 `core/domains/economy/regime_fiscal.py`。"""
from core.domains.economy.regime_fiscal import (  # noqa: F401
    Any, CUT_ARMY_RATIO, CUT_OFFICIAL_RATIO, DEFICIT_STREAK_TRIGGER, Dict, List, TAX_SURCHARGE_MAX_STEPS, TAX_SURCHARGE_STEP, _cut, apply_fiscal_response, move_pop_people,
)
