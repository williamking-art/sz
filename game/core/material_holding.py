# -*- coding: utf-8 -*-
"""`core.material_holding` —— 迁移期兼容入口（丙批二 · 2026-10-06 收敛为**纯转发桩**）。

实现唯一位置（本模块**不复制任何算法**）：
- **账本侧 42 符号** → `core.foundation.ledger.material_holding`（丙批一）
- **交易侧 3 项**（`trade_material`/`supply_merchant_materials`/`commodity_dims`）
  → `core.domains.economy.material_trade_ops`（丙批二；归属判据与
  「生产零调用但测试依赖、不得删」实测见 `specs/cross-cutting/甲批_符号归属与新旧路径表.md` §一/§五/§六）

对外 dir() 保持 **52 名不变**（42+3 实现名 + typing/future 7 名）。
⚠️ 勿在此新增实现；新代码请 import 对应新路径。
"""
from __future__ import annotations

from core.foundation.ledger.material_holding import (
    Any, Dict, List, Optional, Sequence, Tuple, annotations,
    HOLDER_IMPERIAL, HOLDER_MAP, HOLDER_PROVENANCE, HOLDER_TREASURY,
    MATERIAL_DIMS, SEAT_SEP, SEAT_SLOT, SEAT_W, TRIBUTE_WEIGHT_BONUS,
    _TRIBUTE_BY_CIRCUIT, _TRIBUTE_BY_SEAT, _attribute_by_weights,
    _attribute_to_seats, _build_tribute_index, _num, _route_of,
    _seat_name_of, circuit_seats, circuit_tribute_dims, consume_for_circuit,
    consume_for_seat, goods_add, goods_amount, goods_bucket, goods_set,
    holder_pops_of_circuit, holding_report, is_seat_bucket_key,
    material_holding_for_circuit, material_holding_for_seat, merchant_goods,
    merchant_of, resolve_holder, seat_holding_report, seat_slot,
    seat_tribute_dims, seat_weights_for, seat_weights_of_circuit,
    seat_yield_weights_of_circuit, supply_goods_to_seats, to_material_dim,
    tribute_circuits,
)

from core.domains.economy.material_trade_ops import (
    commodity_dims, supply_merchant_materials, trade_material,
)

__all__ = ['MATERIAL_DIMS', 'to_material_dim', 'seat_yield_weights_of_circuit', 'seat_weights_for', 'supply_goods_to_seats', 'circuit_seats', 'merchant_of', 'merchant_goods', 'material_holding_for_circuit', 'consume_for_circuit', 'supply_merchant_materials', 'trade_material', 'holding_report', 'SEAT_SEP', 'is_seat_bucket_key', 'goods_bucket', 'goods_amount', 'goods_set', 'goods_add', 'commodity_dims', 'seat_slot', 'seat_weights_of_circuit', 'holder_pops_of_circuit', 'material_holding_for_seat', 'consume_for_seat', 'seat_holding_report']
