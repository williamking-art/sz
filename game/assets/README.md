# `game/assets/` · 游戏资源

本目录含运行期资源、游戏内知识库以及地图构建输入。目录中“存在文件”“被 Git 跟踪”“被打包”“被前端读取”是不同状态，改资源时分别核对，不能由路径或旧文档推断。

## 资源目录

| 路径 | 主要用途 | 说明 |
|---|---|---|
| `map/` | 地图源料、边界/地形构建数据和背景图 | 数据输入、生成物及前端输出的关系见 [`map/README.md`](map/README.md)。当前 Git 跟踪范围不完全等同于忽略规则：部分 raw 文件及一个 web 文件仍已跟踪。 |
| `kb/game_kb.sqlite` | 游戏运行期本地知识库 | 运行期内容；改动前核实检索代码、构建源和发行清单。 |
| `fonts/` | 字体说明/资源 | 当前界面字体还可能由前端源码资源提供，见 [`fonts/README.md`](fonts/README.md)。 |
| `audio/` | 音频资源位置 | 当前资源与逻辑接线见 [`audio/README.md`](audio/README.md) 和 `game/audio/`。 |
| `icon.ico` | 桌面应用图标 | 构建配置引用时须保持路径一致。 |

事件插图、立绘与 UI 纹样也存在于 `game/frontend/public/` 和前端源码资源中；修改前先确认实际消费者，避免重复放置两份同源文件。

## 地图数据流

地图大致经过三层：

1. `map/raw/` 保存边界等输入材料。
2. `map/web/` 存放构建中间数据；`game/build_map_basemap.py`、`game/content/build_map_geo.py` 等负责生成或整理。
3. `game/frontend/scripts/build-topo.ts` 从 web 数据生成前端运行资源，输出到 `game/frontend/public/map/`；前端由 `renderer/map/` 加载。

地图目录的跟踪状态：目前 `map/raw/` 中存在 Git 跟踪文件，`map/web/` 也有已跟踪文件；前端 `public/map/` 则包含本地产物。`.gitignore` 规则不会自动取消已跟踪文件。新增、移除跟踪文件或改变生成策略时，应先核对 `git ls-files` 和 `git check-ignore`，并同步工作区地图数据的重建步骤；不要静默改变仓库策略。

缺几何数据时，按 [`map/README.md`](map/README.md) 中的实际生成顺序重建，再运行前端 `build:topo`。地形瓦片需要额外生成，是否启用以 `renderer/map/layers.ts` 当前开关为准。

## 打包与修改

- PyInstaller 资源白名单见 [`../SongZuo.spec`](../SongZuo.spec)；Electron 前端资源规则见 [`../frontend/README.md`](../frontend/README.md)。两套发行链的输入不同。
- 新增资源前核实格式、授权、消费者、是否可重建及其体积；不要把生成物、源料和运行时文件混为一类。
- 调整地图几何时检查路/府边界连续性、省界归属、几何空洞/重叠，以及界面缩放和点选使用的图层；对应回归入口见 `_dev_tools/game-dev/tests/test_map_prefecture_geometry.py`。
