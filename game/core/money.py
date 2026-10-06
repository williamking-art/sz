# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.foundation.ledger.money
# 此模块**不复制任何算法**，仅转发。
# 新模块不得导入本薄转发（避免反向边）。
# 🔴 显式重导出：`import *` 不会带下划线名（如 AFFILIATION_FIELDS），必须显式列出。
from core.foundation.ledger.money import (
    ACCOUNTS, SINK_ACCOUNTS, EXTERNAL_ACCOUNTS, _FLOW_KEY,
    _flow, register_flow, take_flow, pop_money,
    hoard_money, local_treasury_total, estate_wealth, estate_hoard,
    payraise_budget_total, invest_principal_total, effective_jiaozi, copper_share,
    _silver_stock, _bank_capital_as_guan, m0, m1,
    m2, m3, m_all, snapshot,
    reconcile, describe_residual, audit_step, _num,
    _clamp01, bank_capital_as_guan, jiaozi_issued, jiaozi_circulating,
    jiaozi_reserve, jiaozi_redeem_rate, _derived_jiaozi_discount, jiaozi_discount,
    _derived_jiaozi_run, jiaozi_run_pressure, jiaozi_view, bank_view,
    standard_rates, _unit_per_copper, exchange_quote, circulating_copper,
    circulating_jiaozi, circulating_silver, effective_money_supply, supply_breakdown,
    assert_supply_no_double_count, finance_report,
)

__all__ = ['ACCOUNTS', 'SINK_ACCOUNTS', 'EXTERNAL_ACCOUNTS', '_FLOW_KEY', '_flow', 'register_flow', 'take_flow', 'pop_money', 'hoard_money', 'local_treasury_total', 'estate_wealth', 'estate_hoard', 'payraise_budget_total', 'invest_principal_total', 'effective_jiaozi', 'copper_share', '_silver_stock', '_bank_capital_as_guan', 'm0', 'm1', 'm2', 'm3', 'm_all', 'snapshot', 'reconcile', 'describe_residual', 'audit_step', '_num', '_clamp01', 'bank_capital_as_guan', 'jiaozi_issued', 'jiaozi_circulating', 'jiaozi_reserve', 'jiaozi_redeem_rate', '_derived_jiaozi_discount', 'jiaozi_discount', '_derived_jiaozi_run', 'jiaozi_run_pressure', 'jiaozi_view', 'bank_view', 'standard_rates', '_unit_per_copper', 'exchange_quote', 'circulating_copper', 'circulating_jiaozi', 'circulating_silver', 'effective_money_supply', 'supply_breakdown', 'assert_supply_no_double_count', 'finance_report']
