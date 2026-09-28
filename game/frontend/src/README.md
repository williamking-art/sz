# frontend/src · 前端源码（Electron 三进程）

> 层归属：**游戏本体**（前端工程）。`electron-vite` 分别构建三份产物到 `out/{main,preload,renderer}`。

## 结构
| 目录 | 进程/职责 | 关键点 |
|---|---|---|
| `main/` | **Electron 主进程**（Node） | 拉起 Python 后端、健康检查与复用、CSP 注入、**`app://` 特权协议**（打包态静态资源与 `fetch` 可用）、导航白名单、窗口生命周期 |
| `preload/` | 预加载（桥） | `contextBridge` 只暴露必要能力（如 `getBackendUrl`）；**token 不进渲染进程** |
| `renderer/` | React UI | HUD、舆图（MapLibre）、38 个面板/浮层、状态 store、`api/client.ts`（与后端对话） |
| `types/` | 类型补充 | 第三方库缺声明时的 `.d.ts` | 

## 打包态注意（踩过的坑）
- 渲染层由 **`app://songzuo/`** 提供，不再用 `file://`：`file://` 下 `fetch()` 本地文件被 Chromium 禁止（舆图空白）；
- 协议处理器用 **`fs.readFile`**（asar 感知），不能用 `net.fetch(file://…)`（读不了 asar 内文件）；
- 因此后端 CORS 白名单需放行 **`app://songzuo`**（见 `game/backend/server.py`）。
---
最后更新：2026-09-27（补目录文档）
