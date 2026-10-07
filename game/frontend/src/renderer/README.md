# renderer — 渲染进程根

> React 渲染进程入口与目录索引。

## 入口

| 文件 | 行 | 说明 |
|---|---:|---|
| `main.tsx` | 13 | React 挂载入口 |
| `App.tsx` | 146 | 应用外壳与路由 |
| `index.html` | 23 | 渲染进程 HTML |
| `env.d.ts` | 12 | `<reference types="vite/client" />` |

## 子目录

| 目录 | 内容 |
|---|---|
| `api/` | 类型化 `/api/*` HTTP 客户端（对齐 `game/backend/server.py` 契约） |
| `store/` | 集中式状态与浮层 |
| `map/` | 舆图渲染 |
| `hud/` | 常驻 HUD |
| `panels/` | 各类面板（`__tests__/` 在此） |
| `audio/` | 音频引擎 |
| `utils/` | 展示层工具 |
| `types/` | 第三方模块类型补充 |
| `main-menu/` | 主菜单 |
| `components/` `data/` `styles/` `assets/` | 通用件 / 静态数据 / 样式 / 资源 |

## 纪律

- **前端不复制算法**（根 `AGENTS.md §3-2` 口径单点）：需要新读数就在后端加端点，不要在前端现算。
- HTTP 端点只做薄壳，读数算法在 `core/`。
