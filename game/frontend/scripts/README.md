# frontend/scripts · 前端构建/工具脚本

> 层归属：**游戏本体**（前端工程内脚本，Node 侧运行）。

## 关键内容
| 文件/目录 | 说明 |
|---|---|
| `build-topo.ts` | 舆图拓扑化：读 `game/assets/map/web/*.geojson` → 生成 `public/map/regions.topojson` 并拷贝 `*.geojson`/`view.json`（`npm run build:topo`） |
| `shot/` | **面板截图台**（无头浏览器渲染面板 → PNG，含 `shoot.mjs`、`panel.tsx`、mock、`bench-map.mjs` 舆图首帧基准）；命令 `npm run shot` / `npm run bench:map` |

## 关联
- 截图台用于**替代真机目视验收**的一层（`_dev_tools/cloudbase-check.ps1 §8` 会在 panels 改动时自动跑）；
- 舆图首帧成本实测见 `_dev_tools/game-docs/analysis/game项目审查_按功能模块_2026-09-27.md §11`。
---
最后更新：2026-09-27（补目录文档）
