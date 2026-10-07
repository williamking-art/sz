# administration/read_models — 官厅域只读读数

> 架构方案 §3.1：读数可单独放 `read_models/` 子包，**不写 `state`**。
> 这里的函数被 HTTP readouts 端点与测试**共用**——同一份读数两处用，避免口径分叉。

## 模块（1 个）

| 模块 | 行 | 对外接口 |
|---|---:|---|
| `minister_profile.py` | 89 | `build_minister_profiles`（群臣卡片数据，供 HTTP readouts 与测试共用）；含私有 `_portrait_url` |

## 🔴 纪律

- **只读**：不得写 `state`。要写就去业务域，不要在读数里顺手改状态。
- 🔴 **私有符号也要被外部取用**：`tests/test_portrait_*` 取 `_portrait_url`。迁移该模块时桩面**必须含私有符号**，否则 `ImportError`。
- 前端与测试**共用同一读数**，不要在 HTTP 端点里另写一套（口径单点）。

上级索引见 [`../README.md`](../README.md)。
