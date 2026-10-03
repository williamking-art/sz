# `game/assets/map/` · 地图数据

本目录保存地图输入、生成数据与桌面界面背景图。地图资产需区分源料、中间产物和 Electron 前端的运行副本；“本地存在”不等同于“由前端读取”或“已纳入版本管理”。

## 数据目录

| 路径 | 作用 | 当前状态说明 |
|---|---|---|
| `raw/` | 行政边界和自然地理输入 | 当前有已跟踪源文件；重建时先读生成脚本的输入说明。 |
| `web/` | 边界整理后的地图数据与治所台账 | 本地含多个可重建输出；Git 当前仍跟踪 `view.json`，其余文件遵循忽略/工作区状态。 |
| `empire_bg.png`、`desk_bg.*` | 开局/桌面背景资源 | 是否随包以 `SongZuo.spec` 为准。 |
| `game/frontend/public/map/` | Electron 客户端消费的地图运行数据 | 本地生成副本；不在本目录。读取图层见 `frontend/src/renderer/map/`。 |

忽略规则和既有跟踪文件可能不同；调整地图资源存储策略前应先核实仓库索引及 `.gitignore`，不能仅凭忽略规则宣称旧文件已从版本库移除。

## 当前前端读取链

- `circuits`、`regimes` 及对应边界由 `frontend/scripts/build-topo.ts` 转为 `public/map/regions.topojson`。
- `prefecture_borders.geojson` 单独生成 `prefecture_borders.topojson`，由 MapLibre 地图图层在启用时加载。
- `land.geojson`、`rivers.geojson`、`lakes.geojson`、`cities.geojson` 与 `view.json` 复制到前端运行目录。
- `prefectures.geojson` 由生成脚本产出，但现有前端地图消费链主要读取的是路级区域和府界线；生成数据不代表府块面已接入点击、着色或选择功能。
- 山影瓦片目录若未生成，前端 `HILL_TILES_ENABLED` 当前关闭对应图层；更改前核实本地瓦片和 `layers.ts`。

以上是前端构建/消费路径说明，不保证当前工作区每个生成文件都存在。

## 重建顺序

在 `game/` 下运行地图生成器，再进入 `frontend/` 生成前端数据：

```powershell
python .\build_map_basemap.py
python .\content\build_map_geo.py
cd .\frontend
npm run build:topo
```

山影瓦片需联网单独运行 `fetch_hillshade.py`。生成后若准备启用，检查 `layers.ts` 的开关、瓦片 zoom 范围和文件实际位置。精确依赖、回归入口和新克隆步骤见 [`../README.md`](../README.md)。

## 几何验收

调整地图数据时检查行政边界归属、省界/路界连续性、空洞、重叠、飞线、治所落点和缩放层级下的可读性。几何回归入口为 `_dev_tools/game-dev/tests/test_map_prefecture_geometry.py`；有测试不等于本次数据已运行过测试。地图可视问题还须在前端实际缩放和点选验收。
