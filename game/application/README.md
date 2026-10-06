# application — 应用流程层

> 目标架构与分期见 `_dev_tools/game-docs/specs/cross-cutting/代码层机制模块化架构方案_2026-10-06.md`
> （§1 目标树、§5 回合记忆回写、§6-1 依赖方向）。本文件只记**当前事实与纪律**。
> 日期：2026-10-07

## 职责

跨机制的**流程编排**：回合收尾该触发哪些动作、按什么顺序、失败如何处置。
本层**不拥有业务规则**、**不持有第二份账本**、**不运行月结算**。

| 模块 | 当前实现 | 说明 |
|---|---|---|
| `turn_lifecycle.py` | `finish_turn` / `check_terminal_state` / `auto_save_if_due` | 回合收尾编排：终局判定 → 记忆三步 → 自动存档 |
| `memory_lifecycle.py` | `on_turn_finished` / `compress_memory_if_needed` / `summarize_dialogue_if_due` / `persist_memory` | 记忆治理间隔：压缩 6、周期总结+归档 12、对话 3 |

## 已知的既有语义（抽取时原样保留，勿"顺手修正"）

- **对话记忆一支没有 `turn > 0` 前置**：`turn=0` 时 `0 % 3 == 0` 也会触发一次总结。
  主记忆库两支（6/12）都有 `turn > 0` 前置。这个不对称是抽取前就存在的行为，
  是否该修属玩法口径，未定案前保持原样（`test_turn_lifecycle.py` 有锁）。
- **`game_over` 只会被置 True，不会被冲回 False**（存档读回的真值优先于一次判定）。
- **自动存档条件**：`month == 1` 或 `game_over`；固定写**槽 0**。成功要清 `state.save_error`
  陈旧提示；`save_game` 返回 `False` 与抛异常**都算失败**，各记 ERROR 并置可读文案。

## 依赖纪律（两条禁令）

允许的方向：`backend/UI → application → core.evaluation / core.save_load / memory`。

1. 🔴 `application` **不得 import `core.commands`**。入口门面是
   `core/commands.py::finish_turn` 薄代理**到本层**（§5.2），反向 import 会成新环。
2. 🔴 `core/` 下除该门面外的业务模块**不得 import `application`**（§6-2：跨域流程归应用编排，
   不由业务域暗中兼管）。

## 失败语义

沿用既有明确口径：**记日志、不阻断主流程**，但**不得静默 `pass`**。
logger 名固定 `"finish_turn"`——M2 可观测性用例
（`_dev_tools/game-dev/tests/test_error_observability_settle.py`）按该 logger 名过滤，改名即丢可见面。

## 验证

- 本层专项：`_dev_tools/game-dev/tests/test_turn_lifecycle.py`（触发条件 + 失败路径逐条）。
- 入口不变性：`core.commands.finish_turn` 与应用层入口对同一 state 产生**相同调用序列**；
  代理仍返回 `None`、不抛错。
