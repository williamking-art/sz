# assets/map · 舆图资源

> 层归属：**游戏本体**（资源层）；本目录同时是**构建期输入**与**生成物**的所在。

## 结构
| 路径 | 类型 | 入库 | 说明 |
|---|---|---|---|
| `raw/` | **源料** | 部分（大件忽略） | DataV 省级/地级 JSON、Natural Earth 河流湖泊等 |
| `web/` | **构建期输入 + 生成物** | 生成物忽略 | `circuits/circuit_borders/regimes/regime_borders/prefectures/land/lakes/rivers/cities/view.json` |
| `empire_bg.png` / `desk_bg.jpg` / `desk_bg.png` | 背景图 | ✅ | 运行期真要读的（随打包白名单） |

## 再生成（新克隆后舆图能显示的关键）
```powershell
cd D:\codebuddy\sz\game
& <venv>\python.exe build_map_basemap.py        # → web/{circuits,circuit_borders,prefectures,prefecture_borders,land,lakes,rivers}
& <venv>\python.exe content\build_map_geo.py    # → web/{regimes,regime_borders,regime_prefectures,cities,view.json}
cd frontend; npm run build:topo                   # → public/map/regions.topojson + 拷贝 geojson/view.json
& <venv>\python.exe ..\fetch_hillshade.py        # 可选：地形晕渲瓦片（需联网）
```
> 完整速查表见上一级 `game/assets/README.md §四`。
> 缺 `public/map/**` 时，打包版舆图会**空白**（页面取不到 `regions.topojson`）。
---
最后更新：2026-09-27（补目录文档）
