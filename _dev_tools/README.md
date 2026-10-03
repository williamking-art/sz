# `_dev_tools/` · 开发辅助区

本目录存放测试、文档、团队说明、检查脚本、分析工具、未接线参考代码和临时产物，不属于游戏运行时。子目录可能按不同规则跟踪或忽略，文件是否入库以 `git status`、`git ls-files` 和 `.gitignore` 实际结果为准。

## 子目录导航

| 路径 | 用途 |
|---|---|
| `game-dev/tests/` | Python 回归用例；见 [`game-dev/tests/README.md`](game-dev/tests/README.md) |
| `game-dev/` | 测试辅助、分析、运维脚本和本地技能 |
| `game-docs/` | 机制文档、设计分析、规格与审查记录；见 [`game-docs/README.md`](game-docs/README.md) |
| `game-assets-src/` | 美术/立绘生成管线源料 |
| `songzuo-game-studio/` | 专家角色、工作流程和团队装载资料 |
| `unwired/` | 未接生产调用链的参考实现；不得误认为正在运行的游戏能力 |
| `analysis-shots/` | 界面/经济等观察与截图相关辅助内容 |
| `_scratch/` | 临时审计或生成工作区；内容不保证保留 |

## 根级工具

可用脚本包括 `cloudbase-check.ps1`、`verify-all.ps1`、`dev-env.ps1`、`sync_mcp_state.py`、`agnes_gen.py` 等。运行前先阅读脚本帮助/源码，尤其是会联网、删除或写入外部状态的工具；不要把凭据放入脚本或输出。

## 约定

- 测试放在 `game-dev/tests/`；运行入口见该目录 README 和 `game-docs/docs/开发服务器与回归测试说明.md`。
- 临时脚本放进约定的临时目录，不混入 `game/` 运行时代码。
- 新增开发文件时先确认跟踪/忽略策略；目录中实际存在不表示它已提交或发行。
- 对机制改动保持开发文档、规格状态和游戏模块 README 同步。
- **`sync_mcp_state.py` 的写盘是「云端权威、失败即放弃」**（2026-10-03 加固）：云端超时会话失效时，`call()` 返回 `None` →
  旧的 `or {}` 会把失败伪装成「云端为空」，再无条件 `_write` 就**把 `tmp/mcp_sync/` 镜像清空**。
  实测事故：`worklog.json` 32.8KB→2B、`SUMMARY.md` 37.9KB→6KB —— 镜像是**没有 MCP 的 agent 的唯一入口**（`AGENTS.md` §1），
  清空即交接断链。现在脚本会在「全空」或「云端 worklog 为空而本地已有条目」时**抛 `RuntimeError` 并放弃写盘**。
  看到这个报错 = 上游没通，**不要**手工建空文件绕过；修好网络/令牌重跑即可，云端是权威源。
- 交接回写走 MCP 时 `log_append` **正文别超约 150 字**：该端点有服务端 20s 硬限，长正文会超时（`ok:true` 也可能没落盘，
  写完务必 `log_read` 或看本地 `tmp/mcp_sync/worklog.json` 复核）。
