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
| `_dev_tools/game-dev/tests/` | pytest 全量（**用例数会变，以本次实测输出为准**；最近 2026-10-19 实测 **4014 tests / 0 failed / 0 errors / 3 skipped**；唯一基线出处见 `_dev_tools/game-docs/README.md` §验证基线） |
| `_dev_tools/game-docs/docs/` | **权威机制文档**（见 §2） |
| `_dev_tools/`、`songzuo_server/` | 开发辅助（截图台、地图生成、CloudBase 检查、Rust 实验后端）——**不接游戏运行时** |

🔴 **模块级 scoped 指令（薄路由层）**：改 `game/core/` 或 `game/frontend/` 前先分别读
`game/core/AGENTS.md`、`game/frontend/AGENTS.md`——只放各自的范围/验证路径/禁区指针，
**现行事实仍以各目录 README 与本文件为准**；内容冲突以本文件为准。

## 1. 先读本机交接层（别凭猜测开工）

**2026-10-09 起交接通道换成本机文件**（用户裁定，登记 `_dev_tools/handover/decisions/LOCAL-HANDOVER.json`）。
CloudBase 交接 MCP 已停用：它的 `/mcp` 路由在网关侧返回 410（带/不带 token 一致，同域其它路径是结构化 404
⇒ 函数/触发器 Gone，不是凭据问题），换 key、重试、等陈旧窗都不会自愈。

```
sz/_dev_tools/handover/INDEX.md     ← 先读这个（各 agent 阶段 / 未完成板 / 待裁决策 / 最近日志）
sz/_dev_tools/handover/NOTICE.md    ← 通道变更说明 + 需要 DSH 自查的 split-brain 风险点
sz/_dev_tools/handover/README.md    ← 本协议细节（目录形态、命令表、为什么一条一文件）
```

| 载体 | 语义 | 约定 |
|---|---|---|
| `tasks/<ID>.json` | 任务板，含 `claimedBy` / `status` | **先认领再动手**；一条一文件 ⇒ 并发双方改的是不同文件，结构上不可能互相覆盖 |
| `decisions/<ID>.json` | 待裁定项（含 `blocks`） | **决策一律进这里，不写 phase**；`verdict` 只由裁定人写 |
| `phase/<Agent>.json` | 各 agent **独占**的当前阶段 | 只写「我现在在做什么」 |
| `worklog/<UTC>-<agent>.md` | 追加式日志（新写=新建文件） | 改共享文件前先 `log` 一行声明 |
| `agents.json` | agent 注册表 + **文件归属** | 共享，改前先读 |
| `archive/cloud_2026-10-09/` | 云端原始 JSON | **只读留档**，勿改勿删 |
| `INDEX.md` | 派生索引 | 由 `summary` 重建，**勿手改** |

工具与退出码（仓库根执行，`$py` 见 §4）：

```powershell
& $py _dev_tools\handover.py board                 # 看板
& $py _dev_tools\handover.py summary               # 重建 INDEX.md
& $py _dev_tools\handover.py check                 # 自检（含下限断言：计数为 0 = 扫描失效，不是干净）
& $py _dev_tools\handover.py claim claim <ID> --agent <名字>     # 认领（他人已占会返回 blocked）
& $py _dev_tools\handover.py claim finish <ID> --agent <名字> --commit <hash>
& $py _dev_tools\handover.py log "YYYY-MM-DD <agent> 做了什么 <验证数字>"
& $py _dev_tools\handover.py phase <Agent> --file <json>
& $py _dev_tools\handover.py decide <ID> --status <s> [--verdict "..." --ruler <裁定人>]
```
> 退出码沿用旧纪律：**0 才算已落地**（写后回读逐字比对 + 再解析一次 JSON），2=用法错，3=校验不一致/认领被拒。

**三条硬规矩**（语义与云端时代一致，只是换载体）：

1. **先认领再动手** —— `board` 看 `claimedBy`，非空且非自己就不碰；`claim` 会程序化拒绝抢单。
2. **改共享文件先声明** —— 动手前 `log` 一行「我要改 X」，声明与改动尽量进同一个 commit。
3. **决策不进 phase** —— 待裁项写 `decisions/<ID>.json`；phase 只写「我现在在做什么」。

🔴 **跨会话结论必须落进仓库文件**（这条在本地化后更重要）：交接层本身已入库，但
`phase` 是覆盖、`context` 是快照，**机制/口径/坑的正文必须写进 `game-docs` 或对应 README**，
交接层只做索引与认领，不做唯一存储。

**历史成因（保留，别再踩）**：云端旧协议的整份 JSON「读-改-写」真丢过数据 ——
`worklog` 旧实现是整文件 RMW，CDN 分钟级陈旧窗内顺序两次追加后者覆盖前者（丢过 2 条）；
函数 20s 超时会让平台回 HTTP 433 + `ret_code 200401`（非 JSON-RPC），响应丢了但写入可能已落地；
`tasks` 共享板两边各取全量各写回 ⇒ 后写覆盖先写。本地化若仍用单文件，只是把竞态从 CDN 搬到磁盘，
所以**一条一文件**是设计要点。另有两次同型教训：Windows 大小写不敏感卷会让 `phase/Qoder.json`
被 `phase/qoder.json`（退役墓碑）静默覆盖，现由 `_case_clash()` 直接拒绝写；
`check` 曾把正则串当 `endswith` 参数用 ⇒ 扫到 0 条还报"问题=0"，现加下限断言。

> `_dev_tools/sync_mcp_state.py` 保留在原处并加了停用注释；`tmp/mcp_sync/`（gitignored）
> 不再是权威，可留作历史缓存。云端恢复部署后也**只作单向只读镜像**，禁止双向写。

## 2. 再读权威文档（按任务挑，别全读）

| 文件 | 讲什么 |
|---|---|
| `_dev_tools/game-docs/docs/游戏机制说明.md` | **当前真实机制** + §十一「设计稿：已成文机制的状态索引」（判断"已生效/待实现"；含自相矛盾文档清单与跨文档阻断链） |
| `_dev_tools/game-docs/docs/局势系统实施规范.md` | 局势系统 v1/v2 唯一规范（注意：`<工作区根>\宋祚局势系统实施规范.md` 是**失效路径**） |
| `_dev_tools/game-docs/docs/货币口径规范_M0M1M2.md` | M0–M3 口径与月度对账恒等式 |
| `_dev_tools/game-docs/docs/开发服务器与回归测试说明.md` | 开发/测试环境 + CloudBase 接入现状（§8） |
| `game/README.md` | 游戏本体说明（含「舆图资源需重建」「后端连接」） |
| `game/游戏审查整改实施指南.md` | 2026-09 审查整改任务书（**已执行完**，留作口径参考） |
| `README.md`（sz 根） | 工具脚本清单与分工 |

## 3. 硬约束（违反即返工）

1. **POP 挂载律**：人（官/吏/宗室/兵/编制）只落 6 类 POP 的 `size`；钱粮只落 POP `wealth`/`grain` 或国库/内帑；**禁与 POP 平行的账本**；阶层变动走既有通道且 ΣPOP 守恒。
   - 🔴 **2026-10-04 用户裁定：POP 实体下沉到州府级（方案乙）**。真账在
     `prefectures[路]["seats"][治所]["pops"][类]`（每治所一个独立 POP）；
     **路级 `prefectures[路]["pops"]` 降为只读派生聚合（Σ 治所）**，任何写入必须落州府，
     否则即构成「与 POP 平行的账本」。这与粮迁移（`grain` → `goods[米]` 派生）是同一模式。
   - ✅ **下沉已覆盖新局与读档（2026-10-08 落地）**：`migrations.sink_pops_to_seats(state)`
     是**无条件幂等入口**（已下沉则跳过），`new_game`（`application/game_init.init_pops_seats`）与读档共用。
     **实测 `commands.new_game()`：20 路 `seats` 有值 = 20 / 20**；生产连跑 3 回合，逐字段
     （`size`/`wealth`/`grain`/`hidden`/`kou`/`ding` 等）路级 == Σ 治所，**差恒为 0**。

     ⚠️ **顺序不可调换**：`hidden` 在 `SPLIT_FIELDS` 内 ⇒ `new_game` 必须**先注隐户再下沉**，
     否则路级写会落进派生镜像造成分叉。

   - 🔴 **路级 `pops` 已下沉档里是派生镜像 ⇒ 直写 = 写丢失**。`sync_route_pops` 每次从治所真账
     **重算覆盖** `SPLIT_FIELDS`，所以直写路级会被**静默撤销**。实测：

     | 写法 | 治所真账 |
     |---|---|
     | 直写路级 `+1000` | **不变**（写进镜像，随后被 sync 刷回）|
     | 桥接 `pop_obj_add(..., "size", 1000)` | `6,217,964 → 6,218,964` ✅ |

     ⇒ **所有写点必须走桥接**（惯例：`if _pop_obj_add(state, obj, fld, d) is None: <原写法>`；
     未下沉时返回 `None` 走原路径，行为不变）。**测试构造前置同样要桥接**（直写镜像清不掉真粮）。

   - 🔴 **读路级 `pops` 是对的，写才是错**。存量读取（42 文件 / 133 处）**刻意保留**读镜像
     （镜像是 `seats` 的纯函数）。区分判据：**读镜像 / 写必须桥接**。

   - 🔴 **守卫只对已安装守卫的路生效**（`pop_bridge._GuardedPops`，`install_all_guards`）；
     **生产未启用** ⇒ 测试未覆盖的写点仍可能静默丢失。待办：装守卫跑完整结算序列 + 后端动作，
     按字段分类（`SPLIT_FIELDS` 补桥接 / 其它补 `_pops_write_exempt` 白名单）。

     🔴 `grain_bridge` 的四个函数都支持**可选 `state`**：给了就委派 `pop_bridge`（写入下沉州府），没给则沿用旧载体
     —— **改调用点时务必传 `state`，否则会继续写路级、造成分叉**。依赖它的四个函数中已有三处漏网实例。

   - ✅ **身份/家产子池已下沉（2026-10-08）**：`estate`/`estate_hoard`/`officials`/`clerks`/`on_post`/`waiting`/`sinecure`
     加入 `SPLIT_FIELDS`。此前它们**不在**该表 ⇒ `sync_route_pops` 把路级值**原样复制**到每个治所 ⇒
     **Σ治所 == 路级 × 治所数**（实测 `estate` 6.4×、`officials` 6.1×），按治所读会算错。现已相等。

     ⚠️ **均值类例外**：`literacy` 属 `MEAN_FIELDS`（比率，**不可求和**）——拆分侧「原样复制」+ 聚合侧
     「按 `size` 加权」是**成对设计**，实测 112/120 精确还原；余 8 为 `size = 0` 的良性边界
     （`aggregate_seat_pops` 有 `_den > 0` 保护）。**不是缺陷，勿按「Σ治所≠路级」判错。**
2. **口径单点**：算法在 `core/`；HTTP 端点只做薄壳；**前端不复制算法**。
3. **缺失 ≠ 0 ≠ 1.0**：缺失一律 `None` → 界面显示"未定义"；禁止回落 0/1.0 假装无事。
4. **核心模拟**（经济/人口/税收/随机数/长期结算）任何改动：**先说明口径与影响 + 加定向回归**。
5. 禁 `git checkout -- .` / `git clean`；保留工作区里他人未提交的改动。
6. 审查类任务默认**只审不改**（用户说"执行"才落地）；每条结论给「位置 + 改法 + 验收断言」。
7. **不臆断**：材料不足就写"材料不足"；报缺陷前先对照机制文档，避免把**刻意设定**当缺陷。
8. 不把密钥/token 写进仓库；`_credentials/` 内容不外传。

## 4. 复跑命令（本机已实测）

```powershell
$repo = git rev-parse --show-toplevel
$ws   = Split-Path $repo -Parent
$py   = Join-Path $ws ".audit-venv\Scripts\python.exe"
$node = Join-Path $ws "tools\nodejs\node-v20.19.5-win-x64\node.exe"

# 后端全量测试（最近 2026-10-19 实测 4014 tests / 0 failed / 0 errors / 3 skipped；干净 clone 3535 / 0 failed / 12 skipped（舆图产物未重建）；用例数会变，以本次输出为准；
#            唯一基线出处见 _dev_tools/game-docs/README.md §验证基线（各文档内的用例数多为历史快照）；
#            先清 shim，否则 pytest tmp_path 会 PermissionError）
$env:PYTHONPATH=""; $env:CODEBUDDY_SAFE_DELETE_ENABLED="0"
cd $repo
& $py -m pytest _dev_tools/game-dev/tests -q -p no:cacheprovider

# 前端：类型检查（双配置）+ 单测（最近 2026-10-17 实测 17 files / 98 passed；同上以本次输出为准）
cd (Join-Path $repo "game\frontend")
& $node .\node_modules\typescript\bin\tsc --noEmit -p tsconfig.web.json
& $node .\node_modules\typescript\bin\tsc --noEmit -p tsconfig.node.json
& $node .\node_modules\vitest\vitest.mjs run

# 面板/HUD 截图台（Edge headless，真实组件渲染）→ PNG
$env:SHOT_PYTHON = $py
$env:SHOT_OUT = Join-Path $repo "_dev_tools\analysis-shots\panels"
& $node scripts\shot\shoot.mjs

# 舆图产物重建（改了生成器/资产后必须按序跑）
cd (Join-Path $repo "game")
& $py build_map_basemap.py        # → assets/map/web/*.geojson + circuit_seat_ledger.json
& $py content\build_map_geo.py    # → assets/map/web/{regimes,regime_borders,regime_prefectures,cities,view.json}
cd frontend
& $node .\node_modules\tsx\dist\cli.mjs scripts/build-topo.ts   # → public/map/*.topojson
& $node .\node_modules\electron-vite\bin\electron-vite.js build  # → out/renderer

# 发布打包（PyInstaller 后端 one-dir → electron-vite → electron-builder NSIS → 产物校验）
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo "_dev_tools\build-release.ps1")
```

## 5. 环境要点（踩过的坑，省你半小时）

- **无系统 node** → 用便携版 `<工作区>\tools\nodejs\node-v20.19.5-win-x64\node.exe`（含 npm/npx）。
- **`frontend/node_modules/electron/dist`**：2026-10-18 已从本机
  `%LOCALAPPDATA%\electron\Cache\electron-v33.0.0-win32-x64.zip` 解压恢复，并写
  `node_modules/electron/path.txt = electron.exe`；现可 `electron-builder` 打包。
  安装包 2026-10-18 已重出：`sz/songzuo/SongZuo Setup 0.1.0.exe`（约 302 MB），
  `win-unpacked/SongZuo.exe` 约 180 MB，`resources/backend` 内含 PyInstaller one-dir。
- **本机无 httpx** → 端点测试必须**直调端点函数 + 伪造 Request**（范例 `tests/test_readouts_endpoint.py`）。
- **PowerShell 读 UTF-8 中文会按 GBK 解码**（实测：`ConvertFrom-Json` 报错、参数退化）。要往云端/JSON 写中文，**用 Python**（`_dev_tools/sync_mcp_state.py` 与各测试即如此）。
- 截图台为何不拍舆图：**maplibre 需 WebGL**，无头浏览器不保证 → 地图用**数据级回归**（`tests/test_map_prefecture_geometry.py`），像素级验收仍需真机。
- 舆图生成物（`assets/map/web/*`、`frontend/public/map/*.topojson`）**不入库**，新克隆后须按 §4 重建，否则舆图空白。

## 6. 收工必须回写（否则下一个 agent 只能重新考古）

四件事，缺一不可（载体见 §1，全部走 `_dev_tools/handover.py`）：

1. **phase（独占）**：把值写成一份 JSON 文件后执行
   `& $py _dev_tools\handover.py phase <你的agent名> --file <json>`
   → 落到 `_dev_tools/handover/phase/<Agent>.json`。值形如
   `{phase, updatedAt, agent, verification:{pytest,tsc,vitest,build}, next}`。
   ⚠️ **不要写共享的 `phase`**（云端时代就多 agent 互相覆盖，本地同理）；
   待裁定项**另登记** `decisions/<ID>.json`（`decide`），任务状态**另登记** `tasks/<ID>.json`（`claim`）。
2. **context（可选快照）**：`_dev_tools/handover/context/<snapshotId>.json`，
   形如 `{summary, data:{delivered,newFiles,artifacts,next}}`。只作快照，**结论正文必须进文档**（§6.1）。
3. **worklog**：`& $py _dev_tools\handover.py log "YYYY-MM-DD <agent> <做了什么> <验证数字>"`
   （例：`2026-09-29 DSH 完成审查整改 5 项；pytest 1291 / tsc 0 错 / vitest 62`）。
   改共享文件前也要用同一命令**先声明**（§1 硬规矩 2）。
4. **文档**：**每轮结束前必须更新文档**，见 §6.1。

收尾两步：`& $py _dev_tools\handover.py summary`（重建 `INDEX.md`，别手改）
+ `& $py _dev_tools\handover.py check`（自检；计数为 0 会被判成扫描失效而非干净）。
交接层与代码**一起提交**最稳——同一台机器上共用工作树时不提交也立刻可见，但换工作树就取不到了。

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

## 7. 交接 MCP 连接片段（**已停用，仅留作恢复参考**）

> 2026-10-09 起交接走本机文件（§1）。下面这段**不要再接**——它的 URL 现在对 `/mcp`
> 返回 HTTP 410（函数/触发器 Gone）。保留只为将来真要恢复云端通道时不必重新考古。

```json
{
  "mcpServers": {
    "cloudbase": {
      "type": "streamable-http",
      "url": "https://william-1-d5grtya3z0b5e143d-1440445995.ap-singapore.app.tcloudbase.com/mcp",
      "headers": { "Authorization": "Bearer ${CLOUDBASE_MCP_TOKEN}" },
      "_status": "DEPRECATED 2026-10-09：交接改走 _dev_tools/handover/，本端点 /mcp 返回 410"
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
| `.cloudbase/project.json`（sz 根 与 `<工作区>\.cloudbase`） | `site: domestic` + `region: ap-singapore` 是**实测可用的组合**（国内账号 + 新加坡地域体验版），**不是**冲突；此前把它当"site/region 冲突"是误判，**不要改** |
| `~/.codebuddy/integration/tcb.json` | 🔴 **2026-10-09 实测：该文件已不存在**（本行原记 2026-09-29 的改法，已随文件删除而失效）。要用 CodeBuddy 内置连接器得重新配置，别照抄本行 |
| `songzuo_server/cloudbaserc.json` | `envId` 已改为当前环境并加 `_note`（提示该地域不支持云托管）。注意**该文件被 `.gitignore:59 cloudbaserc.json` 全局忽略**，改动只在本机生效 |
| `tcb` CLI | **未登录**，且 2026-10-09 实测 **本机连 `~/.tcb` 目录都不存在**（= 从未在这台机器登录过，不只是设备码过期）。要管环境/PG 需 `tcb login --key` 或给 william-1 建环境级 API Key |
| CloudBase 官方管理面 MCP | 本项目**未接入可用登录**：2026-10-09 实测插件为账号级 device 登录，但 `queryEnv(list, region=ap-singapore)` 返回 `EnvList: []`（该登录账号看不到 william-1），且 william-1 的环境级 key 未在本机任何凭据位出现（`settings.json` 里只有 cloud1 环境的 AI provider key）。管环境/PG 需先补 william-1 凭据 |
| **交接状态库 `cloudbase-state-mcp`** | 🔴 **2026-10-09 停用**：`/mcp` 网关侧 410（带/不带 token 一致，同域其他路径为结构化 404 ⇒ 不是凭据问题）。存量已导出到 `_dev_tools/handover/`（含 `archive/cloud_2026-10-09/` 原始 JSON），现行协议见 §1 与 `_dev_tools/handover/NOTICE.md` |

> **交接协议「解封规则已就位，但文件尚未入库」（2026-10-03 复核更正）**：
> 2026-09-29 用户决定让协议随仓库分发，`.gitignore` **末尾**的 `!/AGENTS.md` 覆盖了上方
> "根文件忽略"块里的 `/AGENTS.md`（git 以最后匹配为准，**该行必须留在文件末尾**），
> `_dev_tools/sync_mcp_state.py` 同理经 `!_dev_tools/...` 白名单放行（现已加停用注释，保留作恢复用）；
> 2026-10-09 起本机交接层同样放行入库：`!_dev_tools/handover/` + `!_dev_tools/handover/**` +
> `!_dev_tools/handover.py`（规则必须排在 `_dev_tools/*` 之后，git 以最后匹配为准）。
> **规则层面完好**（`git check-ignore -v AGENTS.md` 命中末尾否定规则）。
>
> ✅ **已入库（2026-10-03 实测更正）**：`AGENTS.md` 与 `_dev_tools/sync_mcp_state.py` **现已 `git add` 入库**
> （`git ls-files --error-unmatch` 返回 rc=0），干净 clone 可取得协议与同步脚本。
> ⚠️ 前一版本此处曾记「两文件仍是未跟踪状态」——那是 2026-09-29 的事实，**已于同日提交中解决，此处更正以免误导**。
>
> 另注：`README.md` 与 `game/*/README.md` 现已入库（`.gitignore:317/321` 的否定规则）；
> `game/README.md` 外链 `game/frontend/README.md` 不再构成干净 clone 断链。

## 9. 共享记忆（跨项目，2026-10-01 接入）

本项目接入了一套**跨 agent 共享记忆**。**本文件仍是《宋祚》的唯一权威项目记忆**，共享记忆只提供索引。

**记忆版本：v5**（权威值：`$env:USERPROFILE\AI-Memory\MEMORY-VERSION`）

| 读什么 | 路径 | 作用 |
|---|---|---|
| 共享记忆索引 | `$env:USERPROFILE\AI-Memory\README.md` | 全局/项目记忆边界、各 agent 接入方式、更新规则 |
| 变更日志 | `$env:USERPROFILE\AI-Memory\CHANGELOG.md` | 记忆最近改了什么 |
| 全局偏好 | `$env:USERPROFILE\AI-Memory\GLOBAL.md` | 跨项目通用约定与本机环境要点 |
| 本项目指针 | `$env:USERPROFILE\AI-Memory\projects\songzuo.md` | 指向本文件，不复制内容 |

**开工第一件事**：读 `MEMORY-VERSION` 并与上面的版本标记比对；**不一致就重读** `GLOBAL.md` 与本文件再开工，
并告知用户"记忆已过期，已重读"——本机所有 agent 都只在会话首轮读一次记忆，**不会自动刷新**。

**改记忆后必须同步**：递增 `MEMORY-VERSION`、在 `CHANGELOG.md` 末尾追加一行、更新所有入口文件的版本标记，
并告知用户"已开着的其他 agent 会话需新开一轮"（详见 `README.md` §4.1）。

**冲突时以本文件为准。** §3 的硬约束、§6 的回写协议、§1 的交接状态入口**均不因共享记忆而改变**。

§5 已记录的环境要点与 `GLOBAL.md` §3 有意重叠（无系统 node、PowerShell 中文 GBK 等）——**这是刻意冗余**：本项目可能被不带共享记忆目录的 agent 接手，`AGENTS.md` 必须自足。
