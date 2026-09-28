# assets/fonts · 字体资源

> 层归属：**游戏本体**（资源层）。

## 现状
- 目录内为 `README.txt`（说明性文本）；
- 界面实际使用的书法字体放在前端工程：`game/frontend/src/renderer/styles/MaShanZheng.ttf`（随前端打包进 `app.asar`）。

## 注意
字体体积大且**每改一次就新增一份 git blob**（仓库膨胀主因之一）。
新增字体前先评估体积与授权（见根 README「体积与历史」节的 LFS 建议）。
---
最后更新：2026-09-27（补目录文档）
