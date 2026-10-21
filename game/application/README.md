# application — 应用流程层

> 目标架构与分期见 `_dev_tools/game-docs/specs/cross-cutting/代码层机制模块化架构方案_2026-10-06.md`
> （§1 目标树、§5 回合记忆回写、§6-1 依赖方向）。本文件只记**当前事实与纪律**。
> 日期：2026-10-07（M25 落地）；2026-10-11 补记 `game_init.py`／`load_game.py`

## 职责

跨机制的**流程编排**：回合收尾该触发哪些动作、按什么顺序、失败如何处置。
本层**不拥有业务规则**、**不持有第二份账本**、**不运行月结算**。

| 模块 | 当前实现 | 说明 |
|---|---|---|
| `turn_lifecycle.py` | `finish_turn` / `check_terminal_state` / `auto_save_if_due` | 回合收尾编排：终局判定 → 记忆三步 → 自动存档 |
| `memory_lifecycle.py` | `on_turn_finished` / `compress_memory_if_needed` / `summarize_dialogue_if_due` / `persist_memory` | 记忆治理间隔：压缩 6、周期总结+归档 12、对话 3 |
| `agent_router.py` | `route_agents` / `inject_woken_agents` / `_inject_one` 等（桩面 **15** 名）| **第二十七包 DSH 2026-10-07**，`git mv` 自 `core/agent_router.py`。按需唤醒 Agent 的路由层：唤醒条件（关键词/状态触发/上轮 diff 路径），未唤醒的 Agent 不消耗任何开销。自身只 import `__future__`/`inspect`/`concurrent.futures`/`typing` ＋ 同层的 `decree_prefetch` ⇒ **零 `core` 依赖**（2026-10-20 仍成立）；唯一生产调用方 `commands.py` 已同批改指新路径。2026-10-20（全审 R-AI-1/R-AI-2/P0-4）：① `_inject_one` 按 `inspect.signature` 适配调用（state 优先）——`decree_duration_decide(state)` 不再每月假 `contract_failed`；② `_ai_failures` **每回合重建**（原跨回合累积＝面板"本月推演未成"永久假警报）；③ 天道槽 `_decree_ai`/`_decree_execute_ai` **注入前清槽**、成功时盖 `_turn` |
| `local_agent_decisions.py` | `local_agents_enabled` / `local_granary_decide` / `local_relief_decide` / `local_economy_decide` / `local_diplomacy_decide` / `local_military_decide` / `local_unrest_decide` / `local_sentiment_decide` / `local_decree_duration_decide` / `local_treasury_decide` / `local_shadow_enabled` / `local_agent_savings` / `local_decide` | **2026-10-21 P1 降 token 第一片**：仓廪 + 赈济 + 经济 + 外交 + 军事 + 民变/民情 + 诏令时效/态度/落地档 + 国库确定性档位；默认关闭（`SONGZUO_LOCAL_AGENTS=1`），缺读数/失败 ⇒ None 回落 LLM；成功时 `state.local_agent_stats` 记替代次数；**零 `core` 依赖**，只读 state |
| `shock_prefetch.py` | `detect_kinds` / `prefetch_shock_tiers` | **2026-10-20**：结算前按当前状态预判可能触发的事件（仓廪<15% ⇒ granary+famine；大策 internal ⇒ focus），让内嵌 Jev 先判「轻/中/重」写 `state._<kind>_shock_tier`；结算只读槽位（零 HTTP），失败吞掉不阻断 |
| `decree_prefetch.py` | `prefetch_decree_slots` / `clear_ai_slot` / `last_result` | **2026-10-20**：下旨成功后由玩家动作路径调用一次天道档位生产者，填 `state._decree_ai`；只在玩家路径、不在结算链；Jev 不可用只留痕不阻断下旨。**P0-4（2026-10-20 全审）**：调生产者**前先 `clear_ai_slot`** —— 原实现只在成功时写槽，失败时旧槽原样留 ⇒ 新诏沿用上一道诏的时效/态度/落地档 |
| `game_init.py` | `new_game` / `init_population` / `init_pops_seats` ＋ `GameInitError` | **M25 裁定**：新局初始化编排。顺序固定 **先注隐户（`ensure_hidden_in_pops`，因 `hidden` 属 `SPLIT_FIELDS`）→ 再下沉州府级（`sink_pops_to_seats`）**，颠倒会让路级写落进派生镜像造成分叉。**fail-fast**：失败抛 `GameInitError`（带站点＋通道），**不返回半初始化 state**。🔴 生产入口 `commands.new_game` **必须**委托本模块，否则玩家开局就缺初始化 |
| `load_game.py` | `restore_dynamic_blueprints` / `load_game` ＋ `RestoreServiceError` | **M25 裁定**：读档编排。基础层只做反序列化，**蓝图的校验与登记**在此编排。失败分级：整档级（恢复服务自身故障）**fail-fast** 不返回部分恢复的 state／单条级（蓝图内容非法）**只丢该条**并留痕／子段级（schema 过高）**只拒该子段**、整档继续 |

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
