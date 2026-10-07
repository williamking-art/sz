# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：实现已迁入 core.domains.economy.hoard_settle（第十八包，2026-10-07）。
# 公开面每个名字都从实现模块转发（含私有与 typing 绑定名）。
# ⚠️ 桩不是行为开关：行为类 monkeypatch 必须打在实现模块上
#   （见 test_domains_politics_b17::test_stub_is_not_a_behavior_switch）。
"""宋祚 · 囤积与平准结算（兼容入口）。实现在 `core/domains/economy/hoard_settle.py`。"""
from core.domains.economy.hoard_settle import (  # noqa: F401
    Any, Dict, HOARD_K_GUO, HOARD_K_NEI, INVASION_CAP, INVASION_RATE, OVERFLOW_IMPERIAL_MULT, OVERFLOW_TREASURY_MULT, _drain_into_clerks, annotations, hoard_readout, random, settle_hoard,
)
