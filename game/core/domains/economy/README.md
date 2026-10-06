# domains/economy — 财政与市场

> 2026-10-06 · 丙批二起**已有首个实现**（`material_trade_ops.py`）；其余仍为候选归属，未移动。

## 拥有的规则

财政、税务、粮政、市场、价格、需求与商品流转

## 已迁入实现

| 模块 | 来源 | 符号 | 说明 |
|---|---|---|---|
| `material_trade_ops.py` | `core/material_holding.py` 交易侧（丙批二 2026-10-06）| `commodity_dims` `supply_merchant_materials` `trade_material` | 搬运/成交规则，非账本接口；向下依赖 `foundation/ledger/material_holding`；`trade_material` 复用 `core.market.trade_goods`（函数内延迟导入）；`supply_merchant_materials` **生产零调用但测试依赖、不得删**（甲批 §五 实测）|

✅ **已销账（第十包，2026-10-07）**：`material_trade_ops` 改用 ledger 显式接口
`attribute_to_seats` / `route_of`（旧私有名在 ledger 内仅作兼容别名保留，供 `core/material_holding.py`
薄桩守恒其公开面）。跨包借用私有符号已由 `test_ledger_interface_b10.py` 常驻拦截，
同包内已知欠账 `grain_bridge → pop_bridge._split_int` 单列登记、只减不增。

## 现有代码候选（**候选归属，迁移前须以符号调用图核实**）

```
market*.py
demand.py
material_market.py
settlement_finance.py
settlement_granary.py
dynamic_price.py
```

## 边界

- 向下依赖 foundation（账本/状态）与 game/content（数据）；**不得反向导入 workflows 或上层**。
- 机制间协作**经显式接口**，不得跨域读写私有内部结构。
- 读数是只读投影，**不得成为结算算法权威**。

## 迁移状态

**已开始**：丙批二（2026-10-06）迁入 `material_trade_ops.py`（交易 3 项）；
其余候选文件（market/demand/settlement_* 等）**未开始**，结算域受阶段 3 前置（12 条反向边）约束。
