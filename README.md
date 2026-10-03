# 《宋祚》仓库

《宋祚》是以北宋为背景的 AI 推演策略游戏。仓库包含 Python 游戏内核、Electron/React/TypeScript 客户端、开发文档与工具，以及独立的 Rust 实验实现。

## 从哪里开始

| 需要了解 | 入口 |
|---|---|
| 游戏当前结构、模块边界与运行方式 | [`game/README.md`](game/README.md) |
| 核心状态与月度结算 | [`game/core/README.md`](game/core/README.md) |
| 前端结构与命令 | [`game/frontend/README.md`](game/frontend/README.md) |
| 当前机制口径 | [`_dev_tools/game-docs/docs/README.md`](_dev_tools/game-docs/docs/README.md) |
| 规格与实施状态 | [`_dev_tools/game-docs/specs/README.md`](_dev_tools/game-docs/specs/README.md) |
| 开发与回归工具 | [`_dev_tools/game-dev/README.md`](_dev_tools/game-dev/README.md) |
| 开发约束与操作要求 | [`AGENTS.md`](AGENTS.md) |

## 顶层目录

| 路径 | 用途 |
|---|---|
| `game/` | 游戏本体：Python 核心、AI 契约、数据、资源、Electron 前端与后端服务。运行与构建产物按各层 `.gitignore` 管理。 |
| `_dev_tools/game-docs/` | 机制文档、设计分析、规格、审查与知识库工具。`docs/` 记录当前口径，`specs/` 记录目标与实施进度，归档材料不代表现状。 |
| `_dev_tools/game-dev/` | Python 回归用例及开发辅助工具；测试入口见该目录 README。 |
| `_dev_tools/game-assets-src/` | 资产生产源文件与管线，不属于运行时模块。 |
| `_dev_tools/songzuo-game-studio/` | 游戏团队角色、职责和协作资料。 |
| `songzuo_server/` | 与 Python 本体分离的 Rust 并行实验实现；功能和存档不保证与本体一致，也不作为发行版权威。 |
| `songzuo/` | Electron 安装/发行产物目录（由构建配置指定）；产物不作为源码或机制事实来源。 |
| `_scratch/`、`scratch/` | 临时工作产物；使用前确认各自忽略规则，不将其当作游戏运行依赖。 |

## 运行和验证

从仓库根启动开发版：

```powershell
.\start.bat
```

游戏运行依赖 Python 后端和 Electron 客户端。具体依赖、环境准备、打包方式及测试命令会随开发环境调整，请以 [`game/README.md`](game/README.md)、[`_dev_tools/game-dev/README.md`](_dev_tools/game-dev/README.md) 和 [`_dev_tools/game-docs/docs/开发服务器与回归测试说明.md`](_dev_tools/game-docs/docs/开发服务器与回归测试说明.md) 为准；不要把旧报告中的通过数量、性能数据或机器绝对路径当成当前基线。

## 开发约定

- **先查当前代码与文档状态**：代码是行为事实，`docs/` 是已确认机制口径，`specs/*/tasks.md` 是各项工作的状态记录。分析稿和归档报告仅供追溯。
- **状态、人口与钱粮守恒**：修改核心模拟时遵守 [`game/core/README.md`](game/core/README.md) 和权威机制文档中的 POP 挂载、账本与缺失值规则；不要从旧 README 复制过时的实现细节。
- **AI 推演与确定性结算分层**：AI 产生契约化决策和叙事，程序负责校验、状态应用及确定性结算；改变边界时同步更新机制文档、规格和受影响目录的 README。
- **文档说清状态**：明确区分已接线、部分接线、只读诊断、未接线和计划中。只有存在生产调用路径和相应证据，才写作“已生效”。
- **存档兼容**：状态结构变更需检查旧档迁移路径；持久化字段不能只在新开局初始化。
- **保护现有工作**：提交前检查工作区改动；不覆盖无关改动，不把密钥、个人凭据或运行存档写入仓库。

## 状态信息的维护

本 README 只提供仓库导航和稳定边界，不维护测试数量、某台机器的依赖版本、阶段性平衡结果或历史改动流水。上述内容应维护在对应专题文档中，并标注测量条件与日期。
