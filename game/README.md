# `game/` · 游戏本体

《宋祚》的运行时代码与资源。游戏以 AI 契约驱动决策和叙事，并由程序校验状态变更、执行月度结算和维护账本。AI 输出不会绕过校验直接写入游戏状态。

## 结构导航

| 目录/文件 | 职责 | 说明入口 |
|---|---|---|
| `core/` | 游戏状态、命令、人口/财政/市场/营造/外交、月度结算、存档 | [`core/README.md`](core/README.md) |
| `application/` | 应用流程层：回合生命周期与记忆协调的编排（不含业务规则、不运行月结算） | [`application/README.md`](application/README.md) |
| `engine/` | AI 结构化变更的校验、应用与状态写入边界 | [`engine/README.md`](engine/README.md) |
| `ai/` | 模型客户端、角色契约、提示词、输出校验和叙事护栏 | [`ai/README.md`](ai/README.md) |
| `backend/` | 本地/HTTP 后端适配和 FastAPI 服务 | [`backend/README.md`](backend/README.md) |
| `memory/` | 对话与长期游戏记忆 | [`memory/README.md`](memory/README.md) |
| `content/` | 开局数据、规则常量、地图/人口派生数据和大臣内容 | [`content/README.md`](content/README.md) |
| `assets/` | 地图、美术、字体、音频等运行资源 | [`assets/README.md`](assets/README.md) |
| `frontend/` | Electron + React + TypeScript + MapLibre 客户端 | [`frontend/README.md`](frontend/README.md) |
| `audio/`、`telemetry/` | 音频能力与运行观测的独立模块 | 各自目录 README |
| `saves/` | 本地运行存档位置 | [`saves/README.md`](saves/README.md) |
| `backend_server_entry.py`、`SongZuo.spec` | 冻结后端的入口与 PyInstaller 配置 | 发行构建的具体要求见下文链接文档 |
| `pytest.ini`、`requirements.txt`、`requirements-extras.txt` | `game/` 下的 pytest 配置与依赖清单 | ⚠️ 仓库根与 `game/` **各有一份 pytest 配置**，从不同目录启动会选中不同配置；见 [`_dev_tools/game-dev/tests/README.md`](../_dev_tools/game-dev/tests/README.md) |
| `build_map_basemap.py`、`content/build_map_geo.py`、`export_constants.py`、`export_frontend_data.py`、`fetch_basemap.py`、`fetch_hillshade.py` | 舆图/常量/前端数据的**生成与导出脚本** | 生成物**不入库**，新克隆须按序重建；顺序见仓库根 `AGENTS.md` §4 与 [`assets/map/README.md`](assets/map/README.md) |
| `ai_config.example.json`、`backend_config.example.json` | 本机配置**样例**（真实配置 git-ignored） | 勿把真实密钥写入仓库 |

开发工具、回归用例、机制文档和规格在仓库根 `_dev_tools/` 下，不属于游戏模块。Rust 并行实现位于仓库根 `songzuo_server/`，不是 Python 后端的替代入口。

## 主要运行链

1. 前端经本地服务接口读取游戏快照、提交操作并展示结果。
2. `core/commands.py` 编排玩家命令、AI 推演和回合推进；结算流程由 `core/settlement.py` 与 `core/settlement_steps.py` 组织，具体步骤分散在相应 `settlement_*.py` 模块。
3. `ai/` 的契约和校验约束模型输出；`engine/state_applier.py` 是结构化 AI 变更进入游戏状态的受控应用路径。确定性规则仍由核心程序结算。
4. 圣旨行动、长期事务和营造相关实现分布在 `decree_plan.py`、`longterm_task.py`、`blueprint_dynamic.py`、`construction.py`、`plan_commit.py`、`settlement_tech.py` 等模块。具体接线和遗留事项以 [`decree-action-chain/tasks.md`](../_dev_tools/game-docs/specs/cross-cutting/decree-action-chain/tasks.md) 及代码调用链为准。
5. 民间交易、需求、价格、人口与营造等实现正在分模块演进。存在代码文件或只读读数，不等于它已经进入月结算生产链；按 [`market-civilian-economy/tasks.md`](../_dev_tools/game-docs/specs/economy/market-civilian-economy/tasks.md) 的逐项状态核实，不把计划态写成已生效。
6. 底层经济闭环与全息真账机制已全面接驳主链：
   - 治所物理四仓位确权与四大物权流转原子操作（`game/core/foundation/ledger/spatial_warehouse_bridge.py`），挂载于开局初始化、读档与全域仓储结算；
   - 政府采购订单引擎（`game/core/domains/economy/procurement.py`），切除硬编码比例，实现实物料场入库与差役/雇役动态工役博弈（`settlement_finance.py`）；
   - 三维交通沈括途耗模型与客运时空流动（Step 4.46b），在途批次按沈括《梦溪笔谈》民夫日食六升口粮递减，运抵物理入库；
   - 双层智能协同架构：宏观叙事与复杂行动由大模型承担，微观高频即时决策收敛至内嵌 0 Token 决策引擎与领域门面（`game/core/ai/embedded_jev.py`、`decision_facade.py`）。

## 开发入口

从仓库根运行启动脚本：

```powershell
.\start.bat
```

前端包位于 `frontend/`。可用命令以 `frontend/package.json` 的 scripts 为准：`dev`、`build`、`typecheck`、`test`、`build:topo`、`dist`。依赖准备、地图重建、打包前置条件见 [`frontend/README.md`](frontend/README.md) 和 [`assets/README.md`](assets/README.md)。

Python 回归用例在仓库根 `_dev_tools/game-dev/tests/`，运行入口和环境限制见 [`_dev_tools/game-dev/README.md`](../_dev_tools/game-dev/README.md) 与 [`_dev_tools/game-docs/docs/开发服务器与回归测试说明.md`](../_dev_tools/game-docs/docs/开发服务器与回归测试说明.md)。本 README 不固定测试数量、机器路径或“最近一次通过”结果。

## 机制与状态来源

- 已确认的当前机制口径：[`_dev_tools/game-docs/docs/`](../_dev_tools/game-docs/docs/README.md)（含 [`底层经济闭环与全息真账机制规范_2026-10-17.md`](../_dev_tools/game-docs/docs/底层经济闭环与全息真账机制规范_2026-10-17.md)、财政供需、POP 等规范）。
- 目标设计及实施状态：[`_dev_tools/game-docs/specs/`](../_dev_tools/game-docs/specs/README.md) 和各规格 `tasks.md`。
- 代码调用路径决定能力是否实际生效。标记为“只读”“预留”“未接线”或“计划中”的实现不得描述为已改变游戏行为。

## 改动纪律

- 改动状态字段时同时检查开局构建、结算读写、存档迁移、API/前端展示以及对应守恒规则。
- 人口、财富、钱粮与商品须挂在既有 POP、机构账户、库存持有人或明确登记的在途/工程槽位；任何新库存和转移都要明确来源、去向及唯一权威记录，不能靠重复镜像补数。
- 对 AI 输入输出坚持契约校验；缺失值与数值零分开处理。失败、拒绝、待支持与已完成须能从状态或读数中区分。
- 机制改动同步权威机制文档、相关规格状态和受影响目录 README；不要在导航文档固化易过期的回归数、平衡快照或绝对路径。
- 修改前后检查现有工作区改动，保留不相关的用户改动和新增文件。
