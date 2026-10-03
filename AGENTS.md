# AGENTS.md · 《宋祚》开发交接协议

> **目的**：开发阶段让**任何 agent**（DSH / CodeBuddy / Claude Code / Cursor / Codex …）都能直接接手，
> 不必重新考古。接手时按 §1 → §2 走一遍；收工按 §6 回写。
> 本文件由 2026-09-29 的审查整改会话建立，随项目演进更新。

## 0. 项目一句话

《宋祚》——北宋末年模拟/经营游戏。**Python 核心 + Electron/React 前端**。

| 目录 | 内容 |
|---|---|
| `game/core/` | 规则与结算（算法**单点**在此；`settlement*.py` 十二步流水线） |
| `game/content/` | 数据表（`data.py`、`geo_admin.py`、`ministers/`、`demography.py`） |
| `game/ai/` | AI 契约（**只出档位/叙事**，数值一律程序算） |
| `game/backend/` | FastAPI 薄壳（`/api/action` 等；`client.py` 是动作分派表） |
| `game/frontend/` | Electron + React（`src/renderer/` 地图/HUD/面板） |
| `_dev_tools/game-dev/tests/` | pytest 全量（**用例数会变，以本次实测输出为准**；最近 2026-10-03 实测 2159 passed + 1 skipped） |
| `_dev_tools/game-docs/docs/` | **权威机制文档**（见 §2） |
| `_dev_tools/`、`songzuo_server/` | 开发辅助（截图台、地图生成、CloudBase 检查、Rust 实验后端）——**不接游戏运行时** |

## 1. 先读云端交接状态（别凭猜测开工）

交接状态放在 CloudBase 上的 MCP（`cloudbase-state-mcp`），**project = `songzuo`**：

| 项 | 值 |
|---|---|
| URL | `https://william-1-d5grtya3z0b5e143d-1440445995.ap-singapore.app.tcloudbase.com/mcp` |
| Header | `Authorization: Bearer $CLOUDBASE_MCP_TOKEN`（本机已设**用户级**环境变量，token 不入库） |
| 工具 | `state_get` `state_set` `context_load` `context_save` `log_read` `log_append` `project_list` `project_create` |
| DSH | 已在 `~/.dsh/profiles/desktop/cordis.patch.yml` 配 `mcp-cloudbase` → 重启后得 `mcp__cloudbase__*` |
| 其他 agent | 通用 `mcpServers` 片段见 §7 |

**没有 MCP 的 agent** → 直接读**本地镜像**（普通文件，read 工具即可）：

```
sz/tmp/mcp_sync/SUMMARY.md      ← 先读这个（阶段/验证/待裁决/阻塞/最近日志）
sz/tmp/mcp_sync/state.json      ← 全部 state 键值
sz/tmp/mcp_sync/context.json    ← 最近上下文快照（交付明细、新文件、产物指纹）
sz/tmp/mcp_sync/worklog.json    ← 工作日志
```

刷新镜像（需 `CLOUDBASE_MCP_TOKEN`）：

```powershell
$py = "D:\codebuddy\.audit-venv\Scripts\python.exe"
cd D:\codebuddy\sz
& $py _dev_tools\sync_mcp_state.py            # 拉取并写镜像
& $py _dev_tools\sync_mcp_state.py log "…"    # 只追加一条云端日志
```

## 2. 再读权威文档（按任务挑，别全读）

| 文件 | 讲什么 |
|---|---|
| `_dev_tools/game-docs/docs/游戏机制说明.md` | **当前真实机制** + §六「落地进度」（判断"已生效/待实现"） |
| `_dev_tools/game-docs/docs/局势系统实施规范.md` | 局势系统 v1/v2 唯一规范（注意：`D:\codebuddy\宋祚局势系统实施规范.md` 是**失效路径**） |
| `_dev_tools/game-docs/docs/货币口径规范_M0M1M2.md` | M0–M3 口径与月度对账恒等式 |
| `_dev_tools/game-docs/docs/开发服务器与回归测试说明.md` | 开发/测试环境 + CloudBase 接入现状（§8） |
| `game/README.md` | 游戏本体说明（含「舆图资源需重建」「后端连接」） |
| `game/游戏审查整改实施指南.md` | 2026-09 审查整改任务书（**已执行完**，留作口径参考） |
| `README.md`（sz 根） | 工具脚本清单与分工 |

## 3. 硬约束（违反即返工）

1. **POP 挂载律**：人（官/吏/宗室/兵/编制）只落 6 类 POP 的 `size`；钱粮只落 POP `wealth`/`grain` 或国库/内帑；**禁与 POP 平行的账本**；阶层变动走既有通道且 ΣPOP 守恒。
2. **口径单点**：算法在 `core/`；HTTP 端点只做薄壳；**前端不复制算法**。
3. **缺失 ≠ 0 ≠ 1.0**：缺失一律 `None` → 界面显示"未定义"；禁止回落 0/1.0 假装无事。
4. **核心模拟**（经济/人口/税收/随机数/长期结算）任何改动：**先说明口径与影响 + 加定向回归**。
5. 禁 `git checkout -- .` / `git clean`；保留工作区里他人未提交的改动。
6. 审查类任务默认**只审不改**（用户说"执行"才落地）；每条结论给「位置 + 改法 + 验收断言」。
7. **不臆断**：材料不足就写"材料不足"；报缺陷前先对照机制文档，避免把**刻意设定**当缺陷。
8. 不把密钥/token 写进仓库；`_credentials/` 内容不外传。

## 4. 复跑命令（本机已实测）

```powershell
$py   = "D:\codebuddy\.audit-venv\Scripts\python.exe"
$node = "D:\codebuddy\tools\nodejs\node-v20.19.5-win-x64\node.exe"

# 后端全量测试（最近 2026-10-03 实测 2159 passed + 1 skipped；用例数会变，以本次输出为准；
#            先清 shim，否则 pytest tmp_path 会 PermissionError）
$env:PYTHONPATH=""; $env:CODEBUDDY_SAFE_DELETE_ENABLED="0"
cd D:\codebuddy\sz
& $py -m pytest _dev_tools/game-dev/tests -q -p no:cacheprovider

# 前端：类型检查（双配置）+ 单测（最近 2026-10-03 实测 72 passed；同上以本次输出为准）
cd D:\codebuddy\sz\game\frontend
& $node .\node_modules\typescript\bin\tsc --noEmit -p tsconfig.web.json
& $node .\node_modules\typescript\bin\tsc --noEmit -p tsconfig.node.json
& $node .\node_modules\vitest\vitest.mjs run

# 面板/HUD 截图台（Edge headless，真实组件渲染）→ PNG
$env:SHOT_PYTHON = $py
$env:SHOT_OUT = "D:\codebuddy\sz\_dev_tools\analysis-shots\panels"
& $node scripts\shot\shoot.mjs

# 舆图产物重建（改了生成器/资产后必须按序跑）
cd D:\codebuddy\sz\game
& $py build_map_basemap.py        # → assets/map/web/*.geojson + circuit_seat_ledger.json
& $py content\build_map_geo.py    # → assets/map/web/{regimes,regime_borders,regime_prefectures,cities,view.json}
cd frontend
& $node .\node_modules\tsx\dist\cli.mjs scripts/build-topo.ts   # → public/map/*.topojson
& $node .\node_modules\electron-vite\bin\electron-vite.js build  # → out/renderer（**安装包需另打包**）
```

## 5. 环境要点（踩过的坑，省你半小时）

- **无系统 node** → 用便携版 `D:\codebuddy\tools\nodejs\node-v20.19.5-win-x64\node.exe`（含 npm/npx）。
- **`frontend/node_modules/electron/dist` 缺失** → 能 build，**不能** `electron-builder` 打包（安装包当前停留在 2026-09-28）。
- **本机无 httpx** → 端点测试必须**直调端点函数 + 伪造 Request**（范例 `tests/test_readouts_endpoint.py`）。
- **PowerShell 读 UTF-8 中文会按 GBK 解码**（实测：`ConvertFrom-Json` 报错、参数退化）。要往云端/JSON 写中文，**用 Python**（`_dev_tools/sync_mcp_state.py` 与各测试即如此）。
- 截图台为何不拍舆图：**maplibre 需 WebGL**，无头浏览器不保证 → 地图用**数据级回归**（`tests/test_map_prefecture_geometry.py`），像素级验收仍需真机。
- 舆图生成物（`assets/map/web/*`、`frontend/public/map/*.topojson`）**不入库**，新克隆后须按 §4 重建，否则舆图空白。

## 6. 收工必须回写（否则下一个 agent 只能重新考古）

三件事，缺一不可：

1. **state**：`state_set project=songzuo key=phase`，值形如
   `{phase, updatedAt, agent, verification:{pytest,tsc,vitest,build}, openDecisions:[], blocked:[]}`
2. **context**：`context_save project=songzuo summary="一句话现状" data={delivered,newFiles,artifacts,next}`
3. **worklog**：`log_append project=songzuo` 消息格式
   `YYYY-MM-DD <agent> <做了什么> <验证数字>`（例：`2026-09-29 DSH 完成审查整改 5 项；pytest 1291 / tsc 0 错 / vitest 62`）
4. **文档**：**每轮结束前必须更新文档**，见 §6.1。

最后刷新本地镜像（§1），让没有 MCP 的 agent 也看得到。

### 6.1 文档回写（每轮必做 · 用户 2026-10-01 定规）

> **"每轮要更新文档"**——不论这轮是写代码、纯审查，还是只改配置。

| 改了什么 | 必须同步哪份文档 |
|---|---|
| **模块行为 / 文件增删** | 该目录 `README.md`（先读后写；新文件进索引表；过时的"只读/纯函数"之类描述要改） |
| **机制口径 / 规则** | `_dev_tools/game-docs/docs/` 对应权威文档（经济→`货币口径规范`；机制→`游戏机制说明`） |
| **新增子目录 / docs 文档 / 目录文档增删** | `_dev_tools/game-docs/README.md`（子目录表） |
| **测试规模 / 跑法变化** | `_dev_tools/game-dev/tests/README.md`（用例数**不要写死**，指向 `docs/开发服务器与回归测试说明.md`） |
| **落了新规格** | `_dev_tools/game-docs/specs/<规格>/tasks.md` 状态表 ＋ `specs/README.md` 索引 |
| **踩坑 / 立新规矩** | 写进对应 README 的"关键约定/纪律"（**比记流水账有用**） |

细则：
- **README 记"当前事实 ＋ 纪律"，不记"某天做了什么"**；日期只在文末标注一次。
- **目录文档增删要回填上级索引**，否则索引与实际脱节＝没写。
- **未实施的设计显式标"尚未实施"**，别让后人误当现状。
- **发现文档与代码不符（错名/过时描述）顺手改**——这是性价比最高的文档维护。
  （实例：engine README 原把 `NON_NEG_PREFIXES` 写成 `NON_NEGATIVE_PATHS`；core README
  说 `construction.py` 是"只读纯函数"，而它自 2026-10-01 起已是立项写入点。）

## 7. 其他 agent 的连接片段（通用 MCP 格式）

```json
{
  "mcpServers": {
    "cloudbase": {
      "type": "streamable-http",
      "url": "https://william-1-d5grtya3z0b5e143d-1440445995.ap-singapore.app.tcloudbase.com/mcp",
      "headers": { "Authorization": "Bearer ${CLOUDBASE_MCP_TOKEN}" }
    }
  }
}
```

- **DSH**：已配（`mcp-cloudbase`，token 走环境变量），重启会话后工具体现为 `mcp__cloudbase__*`。
- **Claude Code / Cursor / Codex**：写入各自的 MCP 配置（`mcpServers` 同名段），token 用环境变量引用。
- **CodeBuddy**：它走**内置 CloudBase 连接器**（`~/.codebuddy/integration/tcb.json`）；该文件 2026-09-29 已由"指向已删除环境"改为当前环境（但内置连接器给的是**官方管理面**能力，不是本交接 MCP——要用本 MCP 需按上面通用格式另配）。

## 8. CloudBase 环境现状（2026-09-29 复核）

**当前唯一有效环境**：`william-1-d5grtya3z0b5e143d`（别名 `william-1`）· 账号=国内站 · 地域=**ap-singapore**（体验版）
· PG 后端可用 · **该地域不支持云托管**（`queryCloudRun envStatus` 报
`region ap-singapore not in config support region`）。详见
`_dev_tools/game-docs/docs/开发服务器与回归测试说明.md` §8.0（环境表）与 §8.7（PG HTTP 直连备用通路）。

| 项 | 状态 |
|---|---|
| 旧环境 `william-1-d6genf4wb9988a74a` + 云托管 `songzuo-server` + 其域名 | **已删除**——任何引用都别照抄（2026-09-29 已修 2 处，见下） |
| `.cloudbase/project.json`（sz 根 与 `D:\codebuddy\.cloudbase`） | `site: domestic` + `region: ap-singapore` 是**实测可用的组合**（国内账号 + 新加坡地域体验版），**不是**冲突；此前把它当"site/region 冲突"是误判，**不要改** |
| `~/.codebuddy/integration/tcb.json` | CodeBuddy 内置连接器：`projectId` 已由死环境改为当前环境、失效 `previewUrl` 置空、加 `_note`（变更前副本：`%TEMP%\tcb.integration.json.bak`） |
| `songzuo_server/cloudbaserc.json` | `envId` 已改为当前环境并加 `_note`（提示该地域不支持云托管）。注意**该文件被 `.gitignore:59 cloudbaserc.json` 全局忽略**，改动只在本机生效 |
| `tcb` CLI | **未登录**（`.cloudbase/login.out`：设备码过期；官方建议 `tcb login --key`）。要用 CLI 管环境/PG 需先登录 |
| CloudBase 官方管理面 MCP | 本项目**未接**；当前接的是自定义 `cloudbase-state-mcp`（交接状态库，见 §1）。要管环境/PG 走 `tcb` CLI，或按 §7 另配官方远端 MCP |

> **交接协议「解封规则已就位，但文件尚未入库」（2026-10-03 复核更正）**：
> 2026-09-29 用户决定让协议随仓库分发，`.gitignore` **末尾**的 `!/AGENTS.md` 覆盖了上方
> "根文件忽略"块里的 `/AGENTS.md`（git 以最后匹配为准，**该行必须留在文件末尾**），
> `_dev_tools/sync_mcp_state.py` 同理经 `!_dev_tools/...` 白名单放行（`.gitignore:102`）。
> **规则层面完好**（`git check-ignore -v AGENTS.md` 命中末尾否定规则）。
>
> ⚠️ **但截至 2026-10-03，这两个文件仍是未跟踪状态**：`git ls-files --error-unmatch AGENTS.md` 与
> `... sync_mcp_state.py` 均返回 rc=1，`git status` 显示 `??`。**即规则备好了、文件没 `git add`**，
> 干净 clone 仍然拿不到协议与同步脚本——「已入库」的原记载与事实不符，此处更正。
> 另：`sz/README.md`（`.gitignore:264`）与 `game/frontend/README.md`（`:268`）也被排除，
> 而入库的 `game/README.md:16` 恰恰外链后者，构成**断链**。
>
> **落地方式**：`git add AGENTS.md _dev_tools/sync_mcp_state.py .gitignore` 并与 `.gitignore` **同一次提交**；
> 验收：干净 clone 后 `test -f AGENTS.md` 为真，且 `git check-ignore -v AGENTS.md` 仍输出末尾否定规则。

## 9. 共享记忆（跨项目，2026-10-01 接入）

本项目接入了一套**跨 agent 共享记忆**。**本文件仍是《宋祚》的唯一权威项目记忆**，共享记忆只提供索引。

**记忆版本：v4**（权威值：`C:\Users\william\AI-Memory\MEMORY-VERSION`）

| 读什么 | 路径 | 作用 |
|---|---|---|
| 共享记忆索引 | `C:\Users\william\AI-Memory\README.md` | 全局/项目记忆边界、各 agent 接入方式、更新规则 |
| 变更日志 | `C:\Users\william\AI-Memory\CHANGELOG.md` | 记忆最近改了什么 |
| 全局偏好 | `C:\Users\william\AI-Memory\GLOBAL.md` | 跨项目通用约定与本机环境要点 |
| 本项目指针 | `C:\Users\william\AI-Memory\projects\songzuo.md` | 指向本文件，不复制内容 |

**开工第一件事**：读 `MEMORY-VERSION` 并与上面的版本标记比对；**不一致就重读** `GLOBAL.md` 与本文件再开工，
并告知用户"记忆已过期，已重读"——本机所有 agent 都只在会话首轮读一次记忆，**不会自动刷新**。

**改记忆后必须同步**：递增 `MEMORY-VERSION`、在 `CHANGELOG.md` 末尾追加一行、更新所有入口文件的版本标记，
并告知用户"已开着的其他 agent 会话需新开一轮"（详见 `README.md` §4.1）。

**冲突时以本文件为准。** §3 的硬约束、§6 的回写协议、§1 的交接状态入口**均不因共享记忆而改变**。

§5 已记录的环境要点与 `GLOBAL.md` §3 有意重叠（无系统 node、PowerShell 中文 GBK 等）——**这是刻意冗余**：本项目可能被不带共享记忆目录的 agent 接手，`AGENTS.md` 必须自足。
