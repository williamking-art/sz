# 会话上下文总结（2026-08-20 · 工具配置 + 项目状态）

> 用途：上下文恢复用。本会话从「专家团加载」开始，完成了 CloudBase 与 codebase-memory-mcp 的接入配置，并推进了游戏经济/军队重构。后续会话读此可快速续接。

## 一、游戏项目状态（G:\sz\game）

- **pytest：96/96 全绿**（最后验证状态）。
- **本轮（专家团执行）已完成**：
  - 消费端校准 + POP 流动 AI 化（口粮按职业、粮市净头寸撮合、消费率、城市化/回乡/科举 AI 档位）
  - 生产过剩「加消耗」（酿酒扩容+酒课税改造、种粮、饲料、农储粮上限霉耗、常平扩容、官户免役钱）；加工消耗依托建筑（酒坊/畜栏）
  - **军队模型重构**：每路 1 支混合军队（12 支）、兵种「军籍:兵种」复合键、粮饷按兵种（BRANCH_STD = BRANCH_BASE × ARMY_RATE）、装备按人头（EQUIP_STD × EQUIP_RATE）、宋制番号（ARMY_ORG：禁军「神勇左厢第X军」、厢军「路+役种」、乡兵史实名）
  - **内帑口谕调拨**（商量确认式）：召对中口谕「发内帑 X 万入国库」→ 记 pending → 点「准」守恒划账（propose/confirm/cancel_inner_transfer）
- **权威文档**：`analysis/progress_snapshot.md`（第十一部分为 POP 经济收尾）、`analysis/pop_economy_system.md`。
- **残留/另派单**：生产过剩（P0-#7，农存粮 12.5 石/人收敛但仍有结构性过剩）、税基/窖藏链路（物价 0.85、国库 -1052 万）；主理人审计出的 P0 混沌运算（派系+党争、外邦态度）未启动；特质×事件联动未落地。

## 二、工具配置状态（本会话新增）

### 1. CloudBase（腾讯云开发）
- **定位（用户确认）**：帮助开发用，**不接入游戏运行时**。
- Skills：`G:\sz\.agents\skills\cloudbase`（已入技能目录）。
- tcb CLI：3.7.3（全局，`tcb login` 已登录）。
- 环境：`william-d6gbq46nl4bd4e950`（个人版 · ap-shanghai · 到期 09-20）。
- 用途候选：平衡/遥测数据入云库、云函数批处理（未深入，备用）。

### 2. codebase-memory-mcp（代码知识图谱）
- 二进制：v0.10.8
  - `C:\Users\ma_li\AppData\Local\Programs\codebase-memory-mcp\codebase-memory-mcp.exe`
  - `C:\Users\ma_li\.local\bin\codebase-memory-mcp.exe`
- **CodeBuddy 配置已完整**（`C:\Users\ma_li\.codebuddy\`）：
  - `mcp.json`：含 `codebase-memory-mcp`（指向 %LOCALAPPDATA% 二进制）+ `CloudBase AI ToolKit`（npx @cloudbase/cloudbase-mcp）
  - `CODEBUDDY.md`（指示优先用 MCP 图谱工具代替 grep）
  - `agents\codebase-memory[-scout|-auditor].md`（3 个）
  - `skills\codebase-memory\SKILL.md`（完整）
- 索引：**G-sz-game（4009 节点 / 17985 边）** + G-sz（2 个项目）。
- 使用：
  - **CodeBuddy** 重启后 → MCP 15 工具可用（search_graph / trace_path / get_architecture / query_graph 等）。
  - **DSH 环境**（无 MCP 工具槽）→ CLI 模式：`codebase-memory-mcp cli <tool> <flags>`（已验证 search_code / list_projects）。
- install 报错均为无害：`mcp_foreign`（mcp.json 已含 CBM 不覆盖）、Copilot hook 冲突（与 CodeBuddy 无关）。

### 3. 专家团（12 席 subagent 已加载）
主理人邹运筹 + 史翰青/蔡权衡/谷承构/言枢密/景呈宣/惠宋韵/严归正/封致远/吕清商/析微澜/沈舶司。权威源 `G:\sz\_dev_tools\songzuo-game-studio\`（TEAM.md + agents/）。

## 三、挂起 / 待办
1. 游戏：经济/军队重构基本收官；残留（生产过剩、税基/窖藏、P0 混沌运算）按需另派单。
2. CloudBase：备用（帮助开发，如平衡数据入云库）。
3. CBM：已配好 CodeBuddy + 索引完成；DSH 内用 CLI 查询。
4. 队列清理：无进行中的专家任务（谷承构军队收尾已完）。

## 四、关键命令速查
- CBM CLI：`codebase-memory-mcp cli search_code --pattern <pat> --project G-sz-game`；`cli trace_path --help` 等。
- CloudBase：`tcb env list`、`tcb fn deploy`（云函数）。
- 游戏验证：`cd G:\sz\game; python -m pytest -q`。
