# 专家团加载索引（Team 模式）

> 本索引供主理人以 Team 模式一键加载全部成员。每个成员的 `subagent_type`
> 即下方文件名去掉 `.md`。加载时 `Agent` 工具的 `name` 与 `subagent_type`
> 均传该值（如 `name="song-narrative-designer"`、`subagent_type="song-narrative-designer"`）。
> 完整角色卡与实勘基准见各 `.md` 文件及包根 `TEAM.md`。

## 主理人（先 TeamCreate，再 spawn 成员）

| subagent_type | 文件 | 花名 | 角色 |
|---|---|---|---|
| `songzuo-game-studio-team-lead` | songzuo-game-studio-team-lead.md | 邹运筹 | 总制作人与技术统筹：任务路由、最少专家集合、冲突裁决、交付验收 |

## 成员列表（11 名专家）

| # | subagent_type | 文件 | 花名 | Skill | 主责触发 |
|---|---|---|---|---|---|
| 02 | `song-narrative-designer` | song-narrative-designer.md | 史翰青 | `$songzuo-historical-narrative` | content/ 数据、史实事件、角色口吻、诏书、AI 叙事事实核查 |
| 03 | `strategy-systems` | strategy-systems.md | 蔡权衡 | `$songzuo-strategy-systems` | core/ 规则、content/ 数值、平衡、极端回归 |
| 04 | `core-engineering` | core-engineering.md | 谷承构 | `$songzuo-core-engineering` | core/ 状态、存档、迁移、循环依赖、权威常量 |
| 05 | `ai-pipeline` | ai-pipeline.md | 言枢密 | `$songzuo-ai-pipeline` | ai/、backend/、ai_config、模型切换、叙事安全 |
| 06 | `tkinter-ui` | tkinter-ui.md | 景呈宣 | `$songzuo-tkinter-ui` | gui_main.py、ui/、玩家可见交互 |
| 07 | `art-assets` | art-assets.md | 惠宋韵 | `$songzuo-art-assets` | assets/、水墨舆图、资源命名、授权 |
| 08 | `regression-qa` | regression-qa.md | 严归正 | `$songzuo-regression-qa` | dev/verify_*、缺陷复现、发布质量门 |
| 09 | `release-engineering` | release-engineering.md | 封致远 | `$songzuo-release-engineering` | requirements.txt、PyInstaller、EXE、发布边界 |
| 10 | `sound-music-designer` | sound-music-designer.md | 吕清商 | `$songzuo-audio-music` | audio/、音效规格、配乐、静音控制 |
| 11 | `data-analytics` | data-analytics.md | 析微澜 | `$songzuo-analytics` | dev/analytics/、dev/replay/、平衡模拟、诊断 |
| 12 | `ai-integration` | ai-integration.md | 沈舶司 | `$songzuo-ai-integration` | ai/client.py 连通性、json_mode/能力探测、契约自检、推演不动点回归、AI 输出正确性落地验证 |

## 文件主责映射（路由依据）

- `ai/`、`backend/` → 05 ai-pipeline
  - `ai/client.py` 连通性 / 能力探测 / 契约自检 / 推演不动点回归 → 12 ai-integration（与 05 协同，落地验证主责）
- `core/` → 04 core-engineering（03 strategy-systems 复核规则与数值）
- `ui/`、`gui_main.py` → 06 tkinter-ui（07 art-assets 复核视觉资源）
- `content/` → 02 与 03 共同约束，对应主责落地
- `assets/` → 07 art-assets（06 复核加载显示）
- `audio/`（规划） → 10 sound-music-designer（06 复核播放时机）
- `dev/analytics/`、`dev/replay/`（规划） → 11 data-analytics（03/08 复核）
- `dev/verify_*`、交互测试 → 08 regression-qa
- `requirements.txt`、PyInstaller、发布 → 09 release-engineering
- `_scratch/` → 各专家临时产物，禁止游戏本体依赖

## 主理人标准启动剧本（Team 模式）

```
1. 主理人读取本 INDEX.md + 包根 TEAM.md 第一部分（总提示词/DoD）。
2. 用 Agent 工具的 team 模式 TeamCreate（name="songzuo-game-studio"）。
3. 按任务路由结果，逐个 spawn 所需最少成员：
     Agent(name=<subagent_type>, subagent_type=<subagent_type>, team_name="songzuo-game-studio", prompt=<任务卡+对应角色卡摘要+约束>)
   —— 先 spawn 主责专家，再按需 spawn 复核/协作专家。
4. 成员产出经 SendMessage 回传主理人；主理人中转，成员互不直连。
5. 跨模块功能：主责出唯一实施方案 → 复核专家回传约束 → 主理人汇总。
6. 验证阶段 spawn 08 regression-qa 做回归；发布 spawn 09 release-engineering。
7. 主理人按 TEAM.md 第七部分 DoD 验收并交付综合报告。
```

## 预设工作流 → 成员组合

- `W1` 跨模块新功能：主理人路由 → 主责设计 → 复核成员 → 08 验证 → 主理人验收
- `W2` 史实事件+AI 叙事：02 → 05 → 主理人汇编
- `W3` 发布验收：09 → 08 → 主理人确认边界（不含 dev/_scratch/密钥）

## 依赖与边界

- 权威根目录：`G:/sz/game/`（游戏本体）。改动须符合 TEAM.md 的 9 条工程约束与分层规则。
- 数值权威 `content/data.py`；状态权威 `core/game_state.py`；地图仅 `assets/map/empire_bg.png`、`desk_bg.png`。
- 差异以 `TEAM.md` / 各 `.md` 角色卡为准；结构变更以游戏 `README.md` 同步。

## CodeBuddy 子 agent 注册（2026-08-15）

专家团 12 名成员已注册为 CodeBuddy 子 agent（subagent），注册位置：

```
G:/sz/.codebuddy/agents/<subagent_type>.md
```

- 注册文件由本目录角色卡转换而来（frontmatter 换为 CodeBuddy 格式：`name` / `description` / `tools`），正文保留角色卡完整内容，并在开头标注权威源路径。
- **单一权威源不变**：修改角色内容仍以 `songzuo-game-studio/agents/` 与 `TEAM.md` 为准；改后需同步 `G:/sz/.codebuddy/agents/` 下对应副本。
- 调用方式：任意对话中由主 Agent 按 `description` 自动路由，或以 `Task(subagent_type=<subagent_type>)` 显式调用；`subagent_type` 即下方文件名去掉 `.md`。
- 若需全局可用（所有项目），把 `G:/sz/.codebuddy/agents/` 下文件复制到 `C:/Users/Administrator/.codebuddy/agents/`。
