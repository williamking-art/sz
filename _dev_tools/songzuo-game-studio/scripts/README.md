# scripts · 专家团脚本

> 层归属：**开发工具**。

## 关键内容
| 文件 | 说明 |
|---|---|
| `load_team.py` | 读取 `../agents/*.md` 与 `TEAM.md`，把席位/技能装载成团队定义（供编排器使用） |

## 纪律
- 角色卡的**权威来源是 Markdown**（`TEAM.md` + `agents/*.md`），脚本只是读取方，不在脚本里复制席位定义。
- `load_team.py` 的关键词路由是**候选专家提示**，不是完整团队编排；圣旨因果链、官员 Agent、民间经济/营造跨模块任务须按 `TEAM.md` W5–W7 选齐主责与验收成员。
- 前端关键词映射到 Electron/React/MapLibre 角色（保留 `tkinter-ui` 作为旧注册 ID）；不得根据 agent id 推断 Tkinter 技术栈。
---
最后更新：2026-10-02（同步现行团队路由基线）
