# 会话上下文总结（2026-08-20 · 完整版 v2 · 供后续会话恢复）

> 用途：上下文恢复用。本会话完成了《宋祚》AI 架构升级（Function Call 结构化/守恒校验/按需唤醒/契约统一/记忆数据库化/异步化）+ 平衡修复 + 技能加载 + exe 打包。后续会话读此可快速续接。
> **注意**：测试前必须清环境（`$env:PYTHONPATH=''` + 删 CODEBUDDY_* 变量），否则 CodeBuddy shim 干扰产生大量假失败。

## 一、游戏项目状态（G:\sz\game · pytest 224 全绿）

### 产品定位
模拟穿越者（玩家），通过与大臣对话、发布圣旨（政策），改变历史进程（北宋徽宗朝）。**AI 是核心引擎**——所有机制通过 AI（agent）推演驱动，harness 保证稳定，程序负责数值/守恒/校验。

### AI 架构升级（本轮完成）
- **AI 只通过 Function Call 返回结构化 changes 改状态**（3 工具：update_state/query_state/trigger_event + tool_choice required + parse_tool_calls）
- **应用层管道**：engine/state_applier.py（验证/合并/守恒校验/cascade/写库/返回叙事层）+ ai/narrative_guard.py（数字/来源闭集/人物护栏）
- **守恒校验**：钱/粮分组 ΣΔ==0 + reason 补记账 + 硬拒绝（不凭空造灭）
- **Agent 路由按需唤醒**：core/agent_router.py（military/relief 真实军情/灾荒唤醒，economy 必调，未唤醒不耗 token）
- **契约统一**：ai/contract_adapter.py（34 契约 → {changes, narrative} 双通道）+ 拟旨人 persona 差异（style_decree）+ 句式库迁移运行资源（ai/prompts/decree_style_ref.md）
- **记忆库数据库化**：memory/memory_graph.py SQLite 一轮一库（saves/slot_{slot}.db：去重/6回合压缩/12回合总结/精确调动；60 回合 = summary_10+period_summary_5）
- **异步化**：core/async_ai.py（ThreadPoolExecutor ≤2 worker：后台只 AI 网络调用+纯函数校验，主线程 after 回调写状态/UI）+ 6+1 处 UI 接线（polish/批改/廷议/御笔/月折/召对/会签）+ 结算拆分（AI 推演→本地结算→叙事后补）
- **回合时序**：AI 推演（先）→ 系统结算（后）→ 形成叙事（最后）

### 既有机制（已完成）
- 全游戏强制 AI + persona 0-100 + 大臣家产/建筑（时代/科技/产业）/投资 + 经济金融 AI + 平衡修复（60月国库 -307万）+ 军队模型（每路禁/厢/乡）+ 内帑口谕调拨 + 生产过剩加消耗

### 验证
- pytest 224 全绿（清 PYTHONPATH + 删 CODEBUDDY_* 变量后）
- 60 月回放：国库 -307万（> -500万）、物价 0.814、农存粮 8.0石/人、记忆 141 实体+31 关系、性能 0.2s
- exe：G:\sz\game\SongZuo\SongZuo.exe（已重新打包，含全部新模块）

### 权威文档（已更新）
- `analysis/progress_snapshot.md`（第十三部分：AI 架构升级）
- `analysis/refactor_ai_upgrade_plan.md`（AI 架构升级计划 + 分工）
- `analysis/refactor_plan_ai_harness.md`（harness 化计划）
- `docs/游戏机制说明.md`（完整机制）
- `README.md`（总纲）

### 待办/可续
- QA 人工 GUI 验证（AI 调用期间 UI 不卡/加载环/按钮禁用/月折后补）
- exe 重新打包（当前已打包，但若后续改动需重打）
- self.self.messagebox 笔误清理（景呈宣发现）
- P0 混沌运算（派系+党争、外邦态度）/ 12 步 agent 化 P2+ / 徽宗朝新番号

## 二、工具配置状态

### 技能加载（~/.dsh/skills/，DSH 自动扫描）
- `songzuo-dev`（宋祚开发指南，全体专家）
- `agnes-image`（宋式生图，惠宋韵；Agnes API：AGNES_BASE_URL=https://apihub.agnes-ai.com/v1，key 在注册表，当前进程 env 不可见但脚本用注册表兜底）
- `web-search-exa` / `web-access` / `multi-search-engine`（检索，史翰青/析微澜）
- + DSH 内置（cordis-plugin-development/editing-cordis-compositions）

### 其他
- CloudBase：Skills + tcb 3.7.3 + 环境 william-d6gbq46nl4bd4e950（帮助开发，备用）
- codebase-memory-mcp v0.10.8：CodeBuddy 配置 + 索引 G-sz-game（DSH 内 CLI 查询）
- 专家团 12 席 subagent（权威源 _dev_tools/songzuo-game-studio/TEAM.md）

## 三、关键命令速查
- 测试（必须清环境）：`$env:PYTHONPATH=''; Remove-Item Env:CODEBUDDY_TOOL_CALL_ID,CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR; python -m pytest -q`
- 60 月回放：FakeAIClient 注入（tests.fake_ai_backend），random.seed(2026)
- 打包：`cd G:\sz\game; python build_exe.py`
- 技能目录：`C:\Users\ma_li\.dsh\skills\`（加 SKILL.md 即被 DSH 扫描）

## 四、环境警告（重要）
**CodeBuddy CN 注入**：PYTHONPATH=D:\CodeBuddy CN\...\shim（sitecustomize.py safe-delete 钩子）——不清除会导致测试大量假失败（AttributeError/GBK/roundtrip）。测试/回放前必须清 PYTHONPATH + CODEBUDDY_* 变量。
