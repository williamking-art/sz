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
| `sources/` | **外部史料原文与派生数据集**（不入运行时）；见 [`sources/README.md`](sources/README.md) —— 现有《宋史·地理志》卷85–90 原文与 **195 条州级贡物**（`songshi/gong_prefecture.json`），是「按产地落州府桶」的数据依据 |
| `analysis-shots/` | 界面/经济等观察与截图相关辅助内容 |
| `_scratch/` | 临时审计或生成工作区；内容不保证保留 |

## 根级工具

可用脚本包括 `aliyun-check.ps1`（**阿里云侧资产 + 本机工具链一键自检**；原 `cloudbase-check.ps1` 已随 CloudBase 停用删除，历史见 `game-docs/docs/开发服务器与回归测试说明.md` §8.8）、`verify-all.ps1`、`dev-env.ps1`、`handover.py`（本机交接层，2026-10-09 起为交接唯一入口）、`sync_mcp_state.py`（**已停用**，保留作恢复参考）、`agnes_gen.py` 等。运行前先阅读脚本帮助/源码，尤其是会联网、删除或写入外部状态的工具；不要把凭据放入脚本或输出。

## 约定

- 测试放在 `game-dev/tests/`；运行入口见该目录 README 和 `game-docs/docs/开发服务器与回归测试说明.md`。
- 临时脚本放进约定的临时目录，不混入 `game/` 运行时代码。
- **新增数据资产目录（如 `sources/`）必须同时建 README**：写清来源出处、粒度、规模、用法与「只增不改」纪律 —— 否则入库后无人知道它是什么。（2026-10-03 补：`sources/` 归档《宋史》地理志与贡物数据集时立此规）
- 新增开发文件时先确认跟踪/忽略策略；目录中实际存在不表示它已提交或发行。
- 对机制改动保持开发文档、规格状态和游戏模块 README 同步。
- 🔴 **2026-10-09（历史）：交接通道从 CloudBase MCP 换成本机 `_dev_tools/handover/`（工具 `handover.py`）**。
  2026-10-22 起云侧全面转**阿里云**（ECS 自托管 MCP 只作跨设备只读快照，见 `game-docs/docs/开发服务器与回归测试说明.md` §8.1）；
  CloudBase 已停用。下面这条对 `sync_mcp_state.py` 的加固记录仍是有效教训——它正是本地层坚持「一条一文件 + 写后回读」的原因；但该脚本本身已停用
- **`sync_mcp_state.py`：失败绝不伪装成"云端为空"**（2026-10-03 加固写盘守卫；2026-10-07 R4 加固传输层）。
  历史两代病灶：① 旧 `call()` 在云端超时/HTTP 433 时返回 `None`，`or {}` 把失败伪装成「云端为空」，
  再无条件 `_write` 就**把 `tmp/mcp_sync/` 镜像清空**（实测 `worklog.json` 32.8KB→2B、`SUMMARY.md` 37.9KB→6KB；
  镜像是**没有 MCP 的 agent 的唯一入口**，`AGENTS.md` §1，清空即交接断链）；② `log` 子命令的
  `print(call(...) or "ok")` 在响应被吞后照样打印 `ok` —— 2026-10-07 补写日志时就靠这条假成功掩盖了真丢 2 条。
  **R4 现状**：非 200 / 请求收到 202 / 空 content / SSE 无有效 JSON-RPC 事件一律抛 `McpTransportError`；
  `log` 走「追加 → 轮询回读」，`push-state`/`push-context` 走「写 → 回读比对」；
  **退出码 0 才算已落地**（2=服务端称已写但回读未见，**勿重发**；3=lost/failed/mismatch；4=传输失败）。
  非 0 一律按「状态未知」处理：读不到不等于没写进去，盲目重发会造重复/覆盖。
  写盘守卫仍在，但只在**确认云端为空**时触发。
- **`log_append` 正文长度**：2026-10-07 起日志改 PG 表 `mcp_work_log` 逐行追加（R2-A），
  不再整文件重传 —— 实测 650~770ms/条，长正文不触 20s 上限（旧版写整份 263KB JSON 才会）。
  ⚠️ 但 `state_set`/`context_save` **仍走整文件 JSON 写**，长值遇冷实例依旧可能超时；
  那两条的成败以回读比对（`PUSH_STATE verdict=match`）为准，不看响应体。
