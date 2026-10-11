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
