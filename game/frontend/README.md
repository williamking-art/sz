# `game/frontend/` · 桌面客户端

Windows 桌面端使用 Electron、React、TypeScript 和 MapLibre。客户端通过本地后端接口读取状态、提交玩家操作并展示地图、HUD 与功能面板；玩法计算和权威账本仍在 Python 游戏内核。

## 目录

| 路径 | 内容 |
|---|---|
| `src/main/`、`src/preload/` | Electron 主进程、后端进程协作、窗口与受限桥接 API |
| `src/renderer/` | React 页面、地图、状态 store、HUD 和各业务面板；详见 [`src/README.md`](src/README.md) |
| `public/` | 前端运行时静态资源；地图资源由构建脚本生成/同步，见下文 |
| `scripts/` | 地图构建和界面截图/基准工具，见 [`scripts/README.md`](scripts/README.md) |
| `tests/`、`src/**/__tests__/` | Vitest 设置及组件/逻辑测试；测试数量以当前文件为准 |
| `package.json` | 前端命令、依赖及 Electron 打包配置 |
| `out/`、`dist/`、`release/`、`node_modules/` | 本机构建或依赖目录，不是源码事实；忽略规则以本目录 `.gitignore` 为准 |

## 常用命令

在本目录运行：

```powershell
npm install
npm run dev
npm run build
npm run typecheck
npm run test
npm run build:topo
npm run dist
```

命令的准确实现见 `package.json`。`dist` 还依赖 Python 后端发行构建，并可能受本机 Node/Electron 打包兼容性影响；不要仅以 `electron-vite build` 成功推断 Windows 安装包已构建成功。

## 地图资源

MapLibre 前端读取 `public/map/` 中的运行数据。该目录的地图文件为构建/本地生成产物；源料、具体生成顺序和当前 Git 跟踪状态见 [`../assets/README.md`](../assets/README.md) 与 [`../assets/map/README.md`](../assets/map/README.md)。变更地图构建逻辑时同时检查 `scripts/build-topo.ts`、`src/renderer/map/` 的读取图层以及几何回归用例。

## 界面改动约定

### 字体（2026-10-21 与官网统一）

- **单点**：字族只在 `src/renderer/styles/theme.css` 的 `--brush` / `--kai` / `--sans` 定义；
  `tailwind.config.js` 的 `fontFamily.brush/kai/sans` 全部指向这些变量（**不再**硬编码字族链），
  因此改字体只改 theme.css 一处。`font-src 'self' data:`（CSP）已放行自托管字体。
- **两款自托管字体（均 SIL OFL，授权随 `public/` 与 `src/renderer/styles/` 分发）**：
  - `--kai` / `--sans` = **LXGW ZhenKai Slab GB 霞鹜真楷**（正文，与官网正文同款）
  - `--brush` = **Ma Shan Zheng 马善政毛笔楷**（**只用于主要标题**：`.sz-panel-title` 18px、
    顶栏「宋」20px、开局「宋」30px、舆图题额「大宋天下」14px；9–13px 标签仍走真楷保证可读）
- **裁剪策略与官网不同**：官网按页面用字裁剪（几百字），游戏文本是数据驱动且动态的
  （AI 诏草、名臣档案、玩家自由输入），故取 **GB2312 全集 ∪ 仓库文本语料**：
  `zhengkai-subset.woff2` 7613 码位 / 2.56MB（**GB2312 汉字缺 0**）、
  `mashanzheng-subset.woff2` 2956 码位 / 1.22MB（缺字回退真楷）。
- **纪律**：新增或替换字体时 ① 子集脚本用 GB2312∪语料，别按「常用 N 字」盲裁；
  ② 必须同步放 OFL 授权到 `public/`；③ 改完跑双 tsconfig + vitest + `electron-vite build`，
  并用截图台复核密排面板（会计/军情/账目表）无溢出与裁字。

- 页面与共享组件索引见 [`src/renderer/panels/README.md`](src/renderer/panels/README.md) 和 [`src/renderer/components/README.md`](src/renderer/components/README.md)。
- React 层展示后端提供的状态和读数，不复制结算算法；未知或未定义数据须明确呈现。
- 面板按功能复用共享装饰组件和主题变量；视觉调整同时关注不同分辨率、地图遮挡和信息层级。
- 改变接口字段时对照后端序列化/API、TypeScript 类型和组件测试，避免仅在界面端造默认值。
- 打包协议、前后端启动与本地环境的具体细节见 `_dev_tools/game-docs/docs/开发服务器与回归测试说明.md`。
- **缺失≠0（2026-10-20 全审收口）**：可空读数（如长期案卷 `authorization`）为 `null` 时显示「未授权/未定义」，**不得**回落 0 或 1.0；金额统一「贯」，用 `utils/format.wan`。
- **案卷页数据链（R-UI-1）**：左侧局势标题传 `situations.items[].id`，该 id 必须与 `/api/readouts` 的 `longterm_cases` 键（longterm task id）同键；不得前端自造映射。
- **大臣五维（R-UI-6）**：数值只渲染 `readouts.ministers[].attrs/potential` 的真实下发值；缺失显示「未定义」，**禁止**按姓名 seed 伪随机。
- **轮询/定时器生命周期（R-UI-5）**：`subscribeRichPoll`/180s `setTimeout` 必须在 effect cleanup 中退订/清理；禁止在异步回调里调 Hook。
- **拒绝式动作（R-UI-7）**：`authorize_case` 等返回 HTTP 200 + `ok:false`，前端按 `ok` 渲染失败态，不得只看 message 猜成败。
- **展示 helper 单点（2026-10-20 复用批）**：`asNum/asStr/wan/clampPct/formatPct` 只在 `utils/format.ts` 定义并导出，面板**不得**再复制本地同名实现。`clampPct` = 0–100 钳位；`formatPct(v,digits)` = 比率→百分数（null → 「未定义」）；`EngineeringPanel` 的"效果值 delta"是特例（`|v|<2` 时按百分比、否则按原值），语义独立、保留本地实现。
