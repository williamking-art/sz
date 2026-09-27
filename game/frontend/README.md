# `game/frontend/` —— Electron + React 前端

> 上级规范：[`game/README.md`](../README.md) ｜ 资源：[`game/assets/`](../assets/README.md)、[`game/content/`](../content/README.md)

## 一、结构（Electron 三进程）

| 路径 | 职责 |
|---|---|
| `src/main/` | **主进程**（`index.ts`）：窗口、生命周期、与后端（进程内直连或 HTTP）通信 |
| `src/preload/` | **预加载**（`index.ts`）：`contextBridge` 暴露给渲染进程的安全 API |
| `src/renderer/` | **渲染进程**（React SPA）：`App.tsx`、`main.tsx`、`index.html` |
| `src/types/` | 共享 TS 类型（含 `topojson-server.d.ts` 等三方补丁） |
| `public/` | **已入库的前端资源**（立绘/地图/事件图导出，2279 个跟踪文件）——改资源后需同步重新导出 |
| `scripts/` | 构建脚本（如 `build-topo.ts`：topojson 生成） |
| `tests/` | 前端测试（vitest + @testing-library） |
| `out/`、`node_modules/`、`dist/`、`release/` | 构建产物与依赖：**均不入库**，`out/` 可删（重新 build 即再生）、`node_modules/` 可删（需 `npm install` 重装） |

`src/renderer/` 内部：`api/`（后端调用封装）· `store/`（状态管理）· `panels/`（各类面板浮层）·
`map/`（舆图：maplibre + topojson）· `hud/`（顶栏/底栏）· `main-menu/` · `audio/` · `data/` · `styles/` · `types/` · `utils/`

## 二、命令（`package.json` scripts）

```bash
npm run dev        # electron-vite dev（开发热更）
npm run build      # electron-vite build → out/（main/preload/renderer）
npm run typecheck  # tsc --noEmit（node + web 两个 tsconfig）
npm run test       # vitest run（前端单测）
npm run build:topo # tsx scripts/build-topo.ts（舆图 topojson 生成）
npm run dist       # build + electron-builder --win nsis（打包安装包）
```

**本机环境注意**（无系统 node/npm 时的实测结论，见 `sz/README.md`）：

- 可用 **Electron 内置 Node**：设 `ELECTRON_RUN_AS_NODE=1` 后调用 `node_modules/electron/dist/electron.exe`，
  等价于 node（可跑 `tsc`、`electron-vite`）；
- 也可用便携 Node：`D:\codebuddy\tools\nodejs\node-v20.19.5-win-x64`（含 npm/npx）；
- **`electron-builder` 在该 shim 下打包会失败**（写 app.asar 报 `Invalid package`）——完整打包需真正的 Node，
  且要先产出 PyInstaller 本体（`extraResources.from` 指向 `../dist/SongZuo`）。

## 三、约定

1. **真值不下发**：渲染层只应拿到后端给的**档位词/已脱敏数据**；要展示新数值时先确认后端快照是否已脱敏。
2. `public/` 里的资源是**导出产物**：源头在 `game/content/ministers/`、`game/assets/` →
   改原图后要重新导出（`game/export_frontend_data.py` / `scripts/`），否则前端看到的还是旧图。
3. **不要把大图直接塞进 git**（历史会膨胀，见 [sz/README.md](../README.md) §五）：新增/替换大资源前先想 LFS 或"资源不入库"。
4. 前端目前**没有 CI 门禁**（`npm run test` 需手动跑）；涉及会话/竞态的改动请同时跑 Electron 自测。
