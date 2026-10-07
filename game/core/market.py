# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：实现已迁入 core.domains.economy.market（第十八包，2026-10-07）。
# 公开面每个名字都从实现模块转发（含私有与 typing 绑定名）。
# ⚠️ 桩不是行为开关：行为类 monkeypatch 必须打在实现模块上
#   （见 test_domains_politics_b17::test_stub_is_not_a_behavior_switch）。
"""宋祚 · 市集成交（trade_goods 唯一入口）（兼容入口）。实现在 `core/domains/economy/market.py`。"""
from core.domains.economy.market import (  # noqa: F401
    Any, Dict, Optional, TRADE_PURPOSES, TRADE_SCHEMA_VERSION, TradeOutcome, Tuple, _TRADE_LEDGER, _int, _ledger_key, _num, annotations, reset_trade_ledger, sellable_stock, trade_goods,
)
