# domains/economy — 财政与市场

> 2026-10-06 · 阶段 0（架构基线）· 本包为空骨架：未移动实现、未改 import

## 拥有的规则

财政、税务、粮政、市场、价格、需求与商品流转

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

**未开始**（阶段 0 仅建骨架与 README）。
