# 本机交接层 · 使用协议

> **自 2026-10-09 起，这里是《宋祚》跨会话交接的唯一权威**。
> 取代 CloudBase 交接 MCP（原因与实测证据见 [`NOTICE.md`](NOTICE.md)）。
> 停用说明：**云端与本地不要并行双写**；云端那份存量已一次性归档到 `archive/cloud_2026-10-09/`。

工具：`python _dev_tools/handover.py <子命令>`（仓库根执行）。退出码沿用旧纪律：**0 才代表已落地**
（每个写操作都是"临时文件 → 原子替换 → 回读逐字比对 → 再解析一次 JSON"），3=校验不一致，2=用法错。

## 目录形态（**一条一文件**，这是设计要点不是排版偏好）

```
_dev_tools/handover/
├── INDEX.md                  # `summary` 生成，勿手改
├── agents.json               # agent 注册表 + 文件归属（共享；改前先读）
├── NOTICE.md                 # 通道变更说明 + 需自查的 split-brain 风险点
├── TO_DSH_2026-10-09.md      # 云端→本机切换时写给 DSH 的交接单（历史留档）
├── phase/<Agent>.json        # 各 agent **独占**；退役键落 `_retired.<名>.json`
├── tasks/<ID>.json           # 任务板：认领只碰自己那一条
├── decisions/<ID>.json       # 决策项：verdict 只由裁定人写
├── worklog/<UTC时间>-<agent>.md  # 追加 = 新建文件，永不重写历史
├── context/<snapshotId>.json # 快照（可选，取代云端 context_save）
└── archive/cloud_2026-10-09/ # 云端原始 JSON，只读留档
```

为什么一条一文件：云端旧协议的真丢数据事故全部来自**整份 JSON 的读-改-写**
（两个 agent 各取全量、各改、各写回 ⇒ 后写覆盖先写）。本地化如果还是单文件，
只是把竞态从 CDN 搬到磁盘上，**问题一模一样**。拆开写后并发双方改的是不同 inode，
结构上不可能互相覆盖；`INDEX.md` 是派生物，谁都能重建。

⚠️ 实测坑（本目录自己踩过一次）：`phase/Qoder.json` 与 `phase/qoder.json` 在
**Windows 大小写不敏感卷**上会互相覆盖，且写入不报错——现行状态被一个退役墓碑吃掉。
现在 `_case_clash()` 会在撞名时直接写失败；云端退役键一律落成 `phase/_retired.<名>.json`。

## 命令

| 目的 | 命令 |
|---|---|
| 看板上有什么 | `handover.py board` / 读 `INDEX.md` |
| **交接四件事（借鉴外部项目）** | 见下方 §交接四件事与三条护栏 |
| **决策台账导航** | 读 **`DECISIONS-INDEX.md`**（自动汇总 `decisions/*.json`：档案/verdict/前二概率/裁定人/问题；**权威仍是各 json**，本索引只做导航；M116 生成） |
| **认领**（先认领再动手） | `handover.py claim claim <ID> --agent <名字> [--status in_progress]` |
| 交差 | `handover.py claim finish <ID> --agent <名字> --commit <hash>` |
| 追加日志（声明/汇报） | `handover.py log "YYYY-MM-DD <agent> 做了什么 <验证数字>"` |
| 写自己的 phase | `handover.py phase <Agent> --file <json>`（JSON 须是 object） |
| 更新决策项 | `handover.py decide <ID> --status <状态> [--verdict "..." --ruler <裁定人>]` |
| 重建索引 | `handover.py summary` |
| 完整性自检 | `handover.py check`（含**下限断言**：计数出现 0 视为扫描失效而非干净）|
| 一次性导入云端存量 | `handover.py import-cloud`（幂等，已存在则跳过）|

## 三条硬规矩（本地版，语义与旧协议一致）

1. **先认领再动手** —— `claim` 会拒绝认领别人已占的条目（`verdict=blocked`），不是靠自觉。
2. **改共享文件先声明** —— 动手前 `log` 一行「我要改 X」；声明与改动在同一个 commit 里落地最稳。
3. **决策不进 phase** —— 待裁项写 `decisions/<ID>.json`；**verdict 只能由裁定人写**
   （工具会拒绝没有 `--ruler` 的 verdict 写入）。

## 与 git 的关系

本目录**入库**（`.gitignore` 里 `!_dev_tools/handover/**`）。同一台机器上的多个 agent 共用同一个
工作树，所以写完即刻对彼此可见，不必先提交；但**收工应当把交接文件与代码一起提交**，
这样换工作树/新克隆也拿得到状态。`tmp/mcp_sync/` 仍是 gitignored 的历史缓存目录，
**不再是权威**，可以不管它或删除，不影响交接。

## 交接四件事与三条护栏（2026-10-13 · 借鉴 jidekaixin2dian/handoff）

> 参照外部项目 [handoff](https://github.com/jidekaixin2dian/handoff)（MIT；"换个对话，项目接着做"）
> 的四件事模板与保留边界原则，落到本项目既有载体上。**载体不变，只是把要求写明。**

### 四件事（接手时按此读，缺一件就是交接不完整）

| 要素 | 本项目载体 |
|---|---|
| **当前状态**：哪个版本有效、哪些结果**已验证** | `INDEX.md`（自动重建）· `phase/<Agent>.json` · 各批 `tasks/<ID>.json` 的 `verified` |
| **下一步**：什么未完成、**什么需要人决定** | `tasks/*`（`status`）· `decisions/*`（`status=待裁定`，见 `DECISIONS-INDEX.md`） |
| **关键约束**：数据/接口/历史材料要保留什么 | 仓库根 `AGENTS.md` §3 硬约束；`specs/**` 的口径与"尚未实施"标注 |
| **证据入口**：按任务链到**权威文件** | 各批提交 hash（`claim finish --commit`）· `worklog/*` 的实测数字 · `_scratch/*.log` |

### 三条护栏（**违反即视为交接失效**）

1. **不得混淆验证层级**：**"离线检查通过" ≠ "人工已经接受"**；**"全量回归 EXIT=0" ≠ "功能已被用户验收"**。
   写状态时如实分层（本会话做法：正文写"EXIT=0 / X passed"，并把"需你拍板"单列）。
2. **授权不继承**：**旧交接里的发布/实施计划，不得当作新一轮的授权**。凡涉及改数值、改 state、
   对外发布，必须当轮重新取得裁定或用户确认（本项目：由 `decisions/<ID>.json` 或用户当场指令承载）。
3. **保留边界**：原始数据、冻结评估、人工评分、**哈希**、独有决策、**他人未提交改动**
   一律保留；**没有明确清理请求就不删文件**；**"还能重新下载/重新生成"不是删除理由**。
   （与本仓库 §3-5「保留工作区他人未提交改动」同源，此处扩展到**交接材料**本身。）

### 只读审查入口（可选）

只想检查、不改文件时说一句「**只读审查当前交接**」：本目录支持——读 `INDEX.md` + `check` +
`DECISIONS-INDEX.md`，指出**过期状态、断链、遗漏**，**不写任何文件**（`log` 也不写）。

### 提交前门禁（2026-10-13 起 · 逐条不可省）

> 借鉴外部项目 [handoff](https://github.com/jidekaixin2dian/handoff) 工作流第 9 条
> （`git diff --check`）与本仓库既有纪律，固化为**每次提交前**的检查清单：

```powershell
$py = "D:\codebuddy\.audit-venv\Scripts\python.exe"
cd D:\codebuddy\sz
& $py _dev_tools\handover.py check                       # 交接层自检（问题必须为 0）
git diff --cached --check                                # 🔴 尾随空白 / 冲突标记 / 空行 EOF ⇒ 非 0 即阻止提交
& $py -m pytest _dev_tools/game-dev/tests/test_readme_sync.py -q -p no:cacheprovider   # 索引纪律
& $py -m pytest _dev_tools/game-dev/tests -q -p no:cacheprovider > $env:TEMP\full.log 2>&1
"FULL EXIT=$LASTEXITCODE"                                # 🔴 只看退出码，别只看 tail
```
- **JSON 文件**（`decisions/`、`tasks/`）写完**立刻解析一次**（内层引号用「」；`None` 要写 `null`）。
- **碰了 `game/` 下任何代码或数据** ⇒ 全量回归**不可省**；
  「纯文档批是否免全量」**待用户裁定**（见 `specs/cross-cutting/对照借鉴_外部交接项目handoff_2026-10-13.md` 第三节）。
- 提交正文写明 **Jev 概率 + 实测数字 + 纪律声明**（只写正文不算留痕 ⇒ 裁定必须同时落 `decisions/`）。
