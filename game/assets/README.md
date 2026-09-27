# `game/assets/` —— 运行期资源（地图 / 事件图 / 立绘 / 字体 / 知识库）

> 上级规范：[`game/README.md`](../README.md) ｜ 相关：[`content/README.md`](../content/README.md)、[`frontend/README.md`](../frontend/README.md)

## 一、子目录

| 目录 | 内容 | 入库策略 |
|---|---|---|
| `map/` | 舆图资源：`web/`（**生成后供前端用的 geojson/topojson**，入库）、`raw/`（Natural Earth 等原始数据，**大文件已 gitignore**）、`web/tiles/`（瓦片切片，**gitignore**） | 生成物入库、原始大件不入库 |
| `events/` | 事件插图（`songjiang.png`、`jin_invasion.png` 等） | ✅ 入库（**大二进制，注意 LFS/历史膨胀**） |
| `portraits/` | 立绘相关资源 | ✅ 入库（同上） |
| `fonts/` | 字体 | ✅ 入库 |
| `kb/` | **游戏内知识库** `game_kb.sqlite` | ✅ **必须入库**（随游戏分发；缺失只是静默降级，不易察觉） |
| `audio/` | 音频资源（当前为空骨架，音频逻辑见 `game/audio/`） | — |

## 二、关键约定

1. `kb/game_kb.sqlite` **随分发**：不要加进 `.gitignore`，也不要删（删了 `kb_search` 会静默失效）。
   重建方式见 [`_dev_tools/game-docs/kb/build_kb.py`](../../_dev_tools/game-docs/kb/build_kb.py)。
2. `map/web/*.geojson`、`*.topojson` 是**生成物**：修改请改 `content/build_map_geo.py` 后重新生成，
   不要手改生成结果（否则下次生成会被覆盖）。
3. `raw/` 与 `web/tiles/` 是**大件且可再生**：换机后按需重新下载/生成即可，故不入库。
4. **大二进制的历史代价**（2026-09-27 实测）：地图 geojson 与事件 PNG 每改一次都会在 git 历史里
   留下完整一份 blob（PNG 不可压缩）。当时仓库历史 483 MiB 里约 270 MiB 就是这些资产的**当前版本**，
   工具已把它们的历史版本重置为单版本。**新增/替换大图前**请考虑 Git LFS 或"资产不入库"。
5. 前端另有一份导出副本（`game/frontend/public/`）由构建/导出流程同步——
   改资源后若前端没变，先检查是否需要重新导出（`export_frontend_data.py`）。
