# NOTICE · 交接通道变更（2026-10-09）

**给谁看**：所有接手《宋祚》的 agent（DSH / Qoder / Codex / …）。
**一句话**：CloudBase 交接 MCP **停用**，改用本目录（`_dev_tools/handover/`，仓库内、入库、本机读写）。
这是用户 2026-10-09 的裁定，登记为 `decisions/LOCAL-HANDOVER.json`。

## 为什么停（实测，不是猜测）

| 探测 | 结果 |
|---|---|
| `POST /mcp`（JSON-RPC `initialize` / `tools/call`）| **HTTP 410 空 body**，`server: tcbgw` |
| 同域其它 11 条路径（`/`、`/sse`、`/mcp-state`、`/api`、`/tools`…）| 全部结构化 `404 INVALID_PATH` |
| 带 / 不带 `CLOUDBASE_MCP_TOKEN`（本机 48 字符 bearer）| **两者都是 410**，结果一致 |
| 环境域名与网关 | 活着（能返回结构化错误）⇒ 环境没被删、没欠费冻结 |

⇒ 结论：**不是凭据问题，是 `/mcp` 这条 HTTP 路由的后端（`mcp-state` 函数或其触发器）在网关侧 Gone**。
换 key、重试、等 CDN 陈旧窗都不会自愈——所以继续把协议绑在它上面不划算。

## 已经落到本地的东西

- 存量一次性导出：`state` 8 键 → `agents.json` + `phase/*.json` + `tasks/`（7 条）+ `decisions/`（12 条），
  `worklog` 20 条 → `worklog/*.md`，context 快照 1 份 → `context/`；
  原始 JSON 逐字节留档在 `archive/cloud_2026-10-09/`。
- 本地基线之后补上的两条（它们在云端推送时 `verdict=match`，但 11:59 之后镜像再没读回过）：
  `tasks/M27-testcount-gap.json` → done（junit 定标 2446）、`tasks/M30-rebind-cache-debt.json` → 新登记；
  `phase/Qoder.json` 已换成 10-09 台账对齐批内容。

## 🔴 需要 DSH 自查的一件事（split-brain 风险）

本地基线 = **11:59 的云端镜像** + Qoder 之后自己那两次推送。
**如果 DSH 在 2026-10-09 11:59 之后还往云端写过 `tasks` / `decisions` / `phase_DSH`，那份增量我读不到，
本地因此缺它。** 请 DSH 手工核对并补进对应 `tasks/<ID>.json` / `decisions/<ID>.json`。
从现在起**只写本目录**，不要再回写云端——两边同时写必然分叉。

## 云端恢复以后怎么办

不自动恢复双写。若将来把 `mcp-state` 重新部署好，本目录仍是权威，
云端最多当**只读镜像**（由人显式执行，且方向只有 local → cloud）。
`_dev_tools/sync_mcp_state.py` 保留在原处并加了停用注释，就是留给这一步的手术刀。
