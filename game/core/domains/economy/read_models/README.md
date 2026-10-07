# economy/read_models — 经济域只读读数

> 架构方案 §3.1：读数可单独放 `read_models/` 子包，**不写 `state`**。

## 模块（1 个）

| 模块 | 行 | 对外接口 |
|---|---:|---|
| `flow_summary.py` | 143 | `build_flow_summary`（国库/内帑收支悬浮栏数据，**纯派生、只读 GameState**）；含私有 `_this_month_log` / `_parse_finance_line` / `_extract_one_off` |

## 🔴 纪律

- **只读派生**，不写 `state`。
- 🔴 `_extract_one_off` 取结算日志里某一行**第一个「数字+贯」**。由此带来硬约束：**同一次支出只能写成一行**，否则会被当成第二笔、面板双计。改结算日志格式前必须先看本文件。
- 前端面板与测试共用同一读数，不要在 HTTP 端点里另写一套（口径单点）。

上级索引见 [`../README.md`](../README.md)。
