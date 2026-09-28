# frontend/public · 前端静态资源

> 层归属：**游戏本体**（前端资源）。构建时**原样拷贝**到 `out/renderer/`，最终进 `app.asar`。

## 子目录
| 目录 | 内容 | 入库 |
|---|---|---|
| `events/` | 事件插图（黄河决口、花石纲、靖康…） | ✅ |
| `images/` | 背景/纹样/官印/卷轴纸等界面素材 | ✅ |
| `portraits/` | 人物立绘（皇帝各年龄段、文臣武将、内侍…） | ✅（`ministers/*.png` 为生成物，忽略） |
| `map/` | **舆图数据**：`regions.topojson`、`*.geojson`、`view.json`、`tiles/` | ❌（生成物，见下） |

## 舆图数据怎么来
```powershell
cd D:\codebuddy\sz\game\frontend
npm run build:topo        # 读 game/assets/map/web/ → 生成 public/map/regions.topojson 等
```
> 缺 `public/map/**` → 打包版舆图空白（`fetch('./map/regions.topojson')` 404）。
> 生成链的起点（`assets/map/web/*.geojson`）见 `game/assets/README.md §四`。
---
最后更新：2026-09-27（补目录文档）
