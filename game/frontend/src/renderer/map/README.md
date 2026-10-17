# renderer/map — 舆图渲染

> 全屏舆图组件与图层方案。对齐既有 `map_app.js` 的图层方案与状态推导。

## 文件（6 个）

| 文件 | 行 | 职责 |
|---|---:|---|
| `MapView.tsx` | 539 | 舆图主组件 |
| `mapController.ts` | 301 | **舆图数据资产基址**（构建期从 `game/assets/map/web/` 平移） |
| `markers.ts` | 263 | 标签记录：HTML Marker + 显隐档位 + 数据侧可见性 |
| `layers.ts` | 192 | 图层定义：政区/边界/城市/河流/湖泊/势力 |
| `state.ts` | 75 | 从游戏快照推导舆图状态（对齐 `map_app.js` 的 `applyStateInner`） |
| `MapModesControl.tsx` | ~120 | 舆图模式切换控件（政区/水系/地貌/商贸等图层模式切换） |
| `avoid.ts` | 73 | 标签避让：屏幕空间碰撞剔除（`d3-delaunay` 加速近邻查询） |

## 纪律

- **舆图产物不入库**。`game/assets/map/web/`、`topo-simplified.json`、`viewport.json` 必须**按序重建**（见根 `AGENTS.md §4`），否则新 clone 打开舆图是空白。
- `mapController.ts` 的基址是**构建期平移**来的，不是运行时读 `game/` —— 改了基址要同步核对 `electron-vite` 配置，两处不一致就是白屏。
- 标签显隐是**分档**的（`markers.ts`），不要按单条硬编码可见性。
