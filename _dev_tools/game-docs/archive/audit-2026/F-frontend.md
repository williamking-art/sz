# F · 前端与 Electron 审查

审查对象：`D:\codebuddy\sz\game\frontend\`（64 源文件 / ≈17k 行 TS·TSX）
审查方式：只读逐行阅读 + 构建产物比对 + 纯函数实证脚本（**未修改 `game/` 下任何源文件**）
审查日期：2026-09（会话时间基准）

---

## 结论速览

| 编号 | 严重度 | 一句话 | 文件:行 | 证据类型 |
|------|--------|--------|---------|----------|
| F-1 | **P0** | 实际运行的 Electron 入口 `out/main/index.js` 是**过期构建产物**：`sandbox: false` + `shell.openExternal(任意协议)` + 无 `will-navigate` 白名单 → **R2-4 声称的安全修复从未生效** | `frontend/out/main/index.js:122,127` vs `frontend/src/main/index.ts:185,197` | [确认] 文件时间戳 + 构建产物反编译比对 |
| F-2 | P1 | `electron-builder.yml` 的 `files` 白名单未含 `public/**` → 打包后 13.3 MB 舆图数据与全部立绘/背景图不进 asar，成品图鉴与舆图全白 | `frontend/electron-builder.yml:6-8` vs `frontend/src/renderer/map/mapController.ts:7` | [确认] 配置静态判定 + 资产清点 |
| F-3 | P1 | MapView 的状态同步 effect 在 `MapController` 被赋值前就已跑完，且依赖数组不含它 → **开局/读档后舆图不反映真实状态**（政权显隐、标记、视角聚焦全部丢失），须等玩家再操作一次才同步 | `frontend/src/renderer/map/MapView.tsx:310-345,67-71` | [确认] 控制流静态反证 |
| F-4 | P1 | 事件选项「吉/凶」标注失真：83 条真实选项里 **30 条（36%）方向判错**，其中 7 条因不认后端权威前缀式减益档位（`"-大"`）、23 条因只数条数不看量级（`treasury` 单条 ±300 万贯 与 `prestige` 单条 ±10 同级） | `frontend/src/renderer/utils/effects.ts:89-100,136-153`；消费点 `panels/EventPanel.tsx:102-110` | [确认] 实跑脚本（`_scratch/audit-2026/verify_judge_final.py`） |
| F-5 | P2 | `index.html` 与主进程均无 CSP；`electron.vite.config.ts` 渲染层 dev server 绑 `0.0.0.0` 且 `allowedHosts: true` | `frontend/src/renderer/index.html`（无 meta）`frontend/src/main/index.ts`（无 onHeadersReceived）；`frontend/electron.vite.config.ts:35-38` | [确认] 全库检索无 CSP 设置 |
| F-6 | P2 | 鉴权契约缺口：后端 `SONGZUO_SERVER_TOKEN` 一旦设置，前端**所有** `/api/*` 恒 401 —— 前端 `ApiClient` 不发 `Authorization` 头 | `frontend/src/renderer/api/client.ts:195-199` vs `backend/server.py:80-102,830-833` | [确认] 两端代码对读 |
| F-7 | P2 | 后端子进程含 Windows 孤儿风险：`kill()` 不等待、不复查；`window-all-closed` 路径不经 `before-quit` 补偿；开发态 `python` 解析失败时「error」事件不重置 `backendUrlPromise` → 单次失败后本会话永不重试 | `frontend/src/main/index.ts:110-126,245-251,241-243,214-218` | [确认] 代码路径分析 |
| F-8 | P2 | 存储/类型欺骗：`saveDecreeDraft`（`POST /api/decree/draft`）前端**零调用**；`AiConfigResult.configured` 定义了但 `has_key` 分支可能使「密钥已配置」提示永不出现；`ReadoutsResult.granary`/`defense_lines` 声明为必填而后端可返回 `{}`；`save_slots` 的 `corrupt` 标记未被 UI 消费 | `frontend/src/renderer/api/client.ts:87-93,108,126-136,328-335`；`panels/SavePanel.tsx:17-22,76-79` | [确认] 调用点全库检索 + 后端返回体对读 |
| F-9 | P2 | 单文件 `regions.topojson` 13.3 MB，渲染进程主线程 `await res.json()` 后同步解码 8 个图层并预置 feature id，全程无 loading 态/无分片；`public/map/view.json` 与 `map/simplify.ts` 为死代码 | `frontend/src/renderer/map/MapView.tsx:93-117`；`frontend/public/map/regions.topojson` | [确认] 资产实测大小 + 引用检索 |
| F-10 | P2 | 全应用无 React 错误边界，任一浮层面板抛错即**整页白屏**（`main.tsx` 无 ErrorBoundary，`OverlayStack` 无 try/catch） | `frontend/src/renderer/main.tsx:7-12`；`panels/OverlayStack.tsx:117-186` | [确认] 全库检索无 ErrorBoundary |
| F-11 | P2 | `EFFECT_NAME` 表 65 条中仅 18 条命中后端真实维度（27.7%）；`formatEffects` 对未登记键 `continue` 静默丢弃 → 后端若新增维度，事件预览会**无声漏报**该效果 | `frontend/src/renderer/utils/effects.ts:13-86,117-119` | [确认] 实跑脚本（`verify_effect_keys.py`） |
| F-12 | P2 | 构建流水线未串联：`npm run build` 不会重新生成 `build-topo.ts` 的舆图数据；`dist` = `electron-vite build && electron-builder`，**不先 PyInstaller** → README/配置注释所述的前置步骤全靠人工 | `frontend/package.json:11-15`；`frontend/electron-builder.yml:9-16` | [确认] 脚本定义对读 |
| F-13 | P2 | `SettingsPanel.backToMenu` 静默降级：自动存档（槽位 0）失败且玩家误点两次确认后，**未存档即回主菜单**；`AudioSettingsView` 的音量/静音状态为纯装饰，不落任何持久化 | `frontend/src/renderer/panels/SettingsPanel.tsx:44-58,448-483` | [确认] 代码路径分析 |
| F-14 | P3 | 死代码/提示残留：`ActionName` 中 3 个动作零调用（`do_personal_action`/`unlock_focus`/`issue_secret_decree`，后者经 `issue_decree(is_secret)` 内部等价）；`EventPanel` 读的 `needs_confirm` 后端从不产出 | `frontend/src/renderer/api/client.ts:139-141,148`；`panels/EventPanel.tsx:41,78` | [确认] 全库检索 |

**统计：P0 × 1，P1 × 3，P2 × 9，P3 × 1。端点/字段不一致 5 条（详见「端点一致性对拍」）。**

---

## typecheck 结果

**未能执行 —— 本机不存在 Node.js 运行时。** 这是环境限制，不是命令失败。

实测取证：

```
PS D:\codebuddy\sz\game\frontend> npm --version
npm : The term 'npm' is not recognized as the name of a cmdlet, function, script file, ...
    + CategoryInfo          : ObjectNotFound: (npm:String) [], CommandNotFoundException
PS D:\codebuddy\sz\game\frontend> node --version
node : The term 'node' is not recognized ...
PS D:\codebuddy\sz\game\frontend> Test-Path "D:\codebuddy\sz\tools\nodejs\node.exe"
False
PS > where.exe node
INFO: Could not find files for the given pattern(s).
PS > reg query "HKLM\SOFTWARE\Node.js"
ERROR: The system was unable to find the specified registry key or value.
```

补充穷举（全部为空命中）：

| 检索位置 | 结果 |
|----------|------|
| `D:\codebuddy\sz\tools\nodejs\node.exe`（`start.bat:16` 的便携安装位置） | 不存在 |
| `D:\codebuddy` 全树 `node.exe` | 0 命中 |
| `D:\` 深度 5 全树 `node.exe` | 0 命中 |
| `C:\` 深度 6 全树 `node.exe` | 0 命中（仅回收站内一个已删除的 node v22 解压残留） |
| `D:\Apps\dsh\deepseek-harness-master\node_modules\.pnpm` | 无 node 运行时包（该 checkout 亦无 `node.exe`） |
| `C:\Program Files\Git\mingw64\bin` | 无 node |
| `D:\Apps\CodeBuddy CN\tools` | 仅 `inno_updater.exe`、`vcruntime140.dll` |

`frontend/node_modules/.bin/` **存在** `tsc`、`tsc.cmd`、`vite`、`electron-vite`、`tsx` 等全部 shim（用户所述「node_modules 已存在」属实），但这些 `.cmd` shim 首行即调用 `node`，无运行时无法执行。故 `npm run typecheck`（`tsc --noEmit -p tsconfig.node.json && tsc --noEmit -p tsconfig.web.json`）与 `npm run build` 均无法运行。

**错误条数：未知（无法测得）。** 本次审查的全部类型层面结论均降级为静态阅读证据，报告中不出现任何「typecheck 通过/失败」的断言。若需闭环，请在有 Node 的环境执行：

```powershell
cd D:\codebuddy\sz\game\frontend
npm run typecheck        # 期望 0 error；tsconfig.node.json + tsconfig.web.json 双配置
npm run build            # 复核构建期错误
```

**静态类型风险扫描（人工，非 tsc 结论）**：未发现结构性类型谎言的高危项 —— `pick<T>()`/`asNum`/`asStr`/`asDict` 四件套（`gameStore.tsx:197-201`、各面板头部）对未知取值做了运行时收敛；`ApiClient` 全部返回值均 `await res.json() as T`，其中 `ReadoutsResult` 存在乐观标注（见 F-8）。**唯一真正的类型谎言高风险点是 `ReadoutsResult` 的必填声明**，已单列。

---

## 详细条目

### F-1 [P0] 实际运行的 Electron 主进程是过期构建产物 —— R2-4 安全修复从未生效

- 位置：`frontend/out/main/index.js:122`、`:127`（实际运行者）对照 `frontend/src/main/index.ts:185`、`:163-168`、`:197-203`（已修但未编译）

- 证据：[确认] 三重证据。

  **(1) 时间戳证明产物早于修复**

  ```
  File                 LastWriteTime      Length
  src\main\index.ts    2026/9/18 19:53:32   9023   <-- 含 A6 安全修复
  out\main\index.js    2026/9/15 11:30:10   5615   <-- 比源码早 3 天
  src\preload\index.ts 2026/9/8  8:45:58    459
  out\preload\index.js 2026/9/15 11:30:10    389
  ```

  `out/main/index.js` 与 `src/main/index.ts` 不仅时间戳差 3 天，**体积相差 3.4 KB**（9023 → 5615），即修复代码整体不存在于产物中。

  **(2) 产物内直接可读的加固缺失**

  `out/main/index.js:120-135`（反编译所得，缩进原样）：

  ```js
      webPreferences: {
        preload: path.join(__dirname, "../preload/index.js"),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false            // <-- R2-4 声称已改 true
      }
    });
    mainWindow.on("ready-to-show", () => mainWindow?.show());
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
      electron.shell.openExternal(url);      // <-- R2-4 声称已加 http(s) 白名单
      return { action: "deny" };
    });
  ```

  同一文件内检索 `will-navigate` **0 命中**，`isSafeExternalUrl`/`openExternalIfSafe` **0 命中**。

  **(3) 源码中的修复确实存在（说明是「修了没编译」，不是「没修」）**

  `src/main/index.ts:185` `sandbox: true`；`:153-160` `isSafeExternalUrl` 仅放行 `http:`/`https:`；`:197-203` 补了 `will-navigate` 白名单。三个加固点齐全。

- 影响：**P0 —— 唯一真正被执行的 Electron 入口仍处于 R2-4 修复前的暴露状态。**

  1. `sandbox: false` 使 preload 持有完整 Node 权限（`require('fs')`/`child_process` 可用）。渲染层一旦被注入代码（例如后续任何 XSS、或 F-5 的 CSP 缺失放大的注入面），即可越出浏览器沙箱直达文件系统与进程创建。
  2. `shell.openExternal(url)` 对协议**零校验**：`file:`、`smb:`、以及任意已注册的自定义协议都会被交给 OS 处理器 → 本地命令执行面（正是 R2-4 记录的原始风险）。
  3. 无 `will-navigate` 拦截 → 页面内可被导航到任意来源/协议，进一步扩大攻击面。

  这是「源码已修、产物未修」的典型形态，比单纯的漏修更危险：静态审计源码（或看 `src/main/index.ts` 的注释）会判定「已修复」，而实际运行的是脆弱版本。

- 验证方式：

  ```powershell
  cd D:\codebuddy\sz\game\frontend
  # 1) 时间戳
  Get-Item src\main\index.ts, out\main\index.js | Select LastWriteTime, Length
  # 2) 产物内的实际取值
  Select-String -Path out\main\index.js -Pattern "sandbox|openExternal|will-navigate"
  # 3) 源码中的加固点
  Select-String -Path src\main\index.ts -Pattern "sandbox:|isSafeExternalUrl|will-navigate"
  # 4) 修复方式（重编译）
  npm run build
  # 重编译后重复 (2)，期望：sandbox: true 且不再出现裸 shell.openExternal
  ```

- 建议修复：
  1. 立即在有 Node 的环境执行 `npm run build`，把 `src/main/index.ts` 的 A6 加固编译进 `out/main/index.js`；随后重新核对 `out/main/index.js` 中 `sandbox: true` 与 `openExternalIfSafe` 均存在。
  2. 把「产物必须新鲜」变成硬约束：在 `start.bat:146` 的 `:RunDev` 分支前插入一次 `call npm run build`（或改用 `npm run dev` 并确认 electron-vite dev 会重建 main），杜绝「改源码不重编译」。
  3. 加一条产物断言测试（构建后 grep `out/main/index.js` 必须同时出现 `sandbox: true` 与 `isSafeExternalUrl`），把它纳入 CI，防止回归。

---

### F-2 [P1] 打包白名单漏掉 `public/**` —— 成品不含任何舆图数据与美术资源

- 位置：`frontend/electron-builder.yml:6-8`，受影响方 `frontend/src/renderer/map/mapController.ts:7`

- 证据：[确认]

  ```yaml
  # frontend/electron-builder.yml:6-8
  files:
    - out/**
    - package.json
  ```

  `files` 是**排他白名单**，未列出者不进 asar。而渲染层的全部运行时资产都在 `public/`，由 Vite 在 `npm run build` 时原样拷进 `out/renderer/`：

  ```ts
  // frontend/src/renderer/map/mapController.ts:7
  export const MAP_BASE_URL = import.meta.env.BASE_URL + "map";
  // frontend/electron.vite.config.ts:22
  publicDir: resolve(__dirname, "public"),
  // frontend/electron.vite.config.ts:29-30
  build: { outDir: "out/renderer", ... }
  ```

  资产实测体量与内容：

  ```
  public\map\regions.topojson   13,305.7 KB
  public\map\rivers.geojson      1,478.5 KB
  public\map\land.geojson          516.6 KB
  public\map\lakes.geojson         505.4 KB
  public\map\cities.geojson         43.4 KB
  public\map\view.json               0.2 KB
  public\map\tiles\hill\...         数百张 PNG（z=4..8）
  public\images\*                   18 个（menu_bg ×6、seal、title_calligraphy、scene_* …）
  public\portraits\*                12 + 42 张立绘
  public\events\*                   9 张事件工笔插画
  ```

  注意 `out/**` 只在 `npm run build` **之后**才包含 `out/renderer/**`；当前 `out/` 下只有 `out/main/index.js` 与 `out/preload/index.js`（`Test-Path out\renderer` → `False`），说明本机从未跑过完整 renderer 构建。

- 影响：任何基于当前 `electron-builder.yml` 产出的安装包，`MapView.loadGeoData()` 的 5 个 fetch 全部 404（`map/MapView.tsx:86-97` 的 `throw new Error(...HTTP 404)`），舆图永久空白；`MainMenu` 的 6 张背景、事件插画、群臣立绘、印章全部失效。成品只剩 HUD 骨架，**游戏不可玩**。

  唯一缓解因素是 `asar: true` 下 `file://` 读取 asar 内资源本身可行 —— 但前提是资源先进得去，而白名单把它们挡在外面。

- 验证方式：

  ```powershell
  cd D:\codebuddy\sz\game\frontend
  npm run build               # 先产出 out/renderer/**
  Test-Path out\renderer\map\regions.topojson     # 期望 True
  npx electron-builder --win nsis --dir           # 只解包不安装
  # 检查 dist/win-unpacked/resources/app.asar 内容：
  npx asar list dist\win-unpacked\resources\app.asar | Select-String "regions.topojson|menu_bg_1|title_calligraphy"
  # 期望命中；若 0 命中即复现本缺陷
  ```

- 建议修复：`files` 补上资源目录（或直接把 `public` 一并纳入）：

  ```yaml
  files:
    - out/**
    - package.json
  ```

  `out/renderer/**` 由 Vite 生成，已含 `public/` 的拷贝，因此**只要 `npm run build` 先跑过**，`out/**` 就足够；当前缺陷的本质是「从未跑过 renderer 构建 + 无前置步骤保证」。故建议同时做两件事：① 确认 `dist` 脚本顺序（见 F-12）；② 把 `npx asar list | Select-String regions.topojson` 作为打包后断言加进 CI，用非零命中数卡住漏包。

---

### F-3 [P1] MapView 状态同步在 `MapController` 就绪前完成，开局/读档后舆图不反映真实状态

- 位置：`frontend/src/renderer/map/MapView.tsx:310-315`（提前返回）、`:67-71`（就绪回调）、`:41-81`（依赖 `[]` 的初始化 effect）

- 证据：[确认] 控制流静态反证。

  ```tsx
  // MapView.tsx:310-315 —— 状态同步 effect
  useEffect(() => {
    const controller = controllerRef.current;   // 挂载首轮为 null
    const markers = markersRef.current;         // 挂载首轮为 null
    const data = dataRef.current;               // 挂载首轮为 null
    if (!controller || !markers || !data) return;   // <-- 静默早退
    ...
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);          // 依赖数组不含 controller/markers/data
  ```

  三者的赋值时机：

  ```tsx
  // MapView.tsx:67-71 —— onMapReady，由 maplibregl 'load' 事件触发（异步）
  onMapReady: () => {
    controllerRef.current = controller;
    markersRef.current = new MarkerManager(controller.getMap()!);
    loadGeoData();                     // 内部 fetch 5 个资产后才 dataRef.current = data
  }
  ```

  时序（进入游戏时 `state` 已是新开局的快照）：

  1. 挂载，渲染 `<div ref={containerRef} />`。
  2. React 执行 effect：初始化 effect（`[]`）跑 → `controller.init()` 建 `maplibregl.Map`（`MapView.tsx:73`）。**同期**状态同步 effect（`[state]`）跑 → 三个 ref 全 `null` → **提前返回**。
  3. 稍后 maplibre `load` 事件 → `onMapReady` → 三个 ref 被赋值 → `loadGeoData()` 异步 fetch。
  4. `state` 此后不再变化 → 状态同步 effect **永不重跑**（依赖数组里只有 `state`）。

  于是本应被执行的三项同步全部落空：

  - `markers.refreshRegimeLabels(regimeOn, ...)`（`:328-330`）→ 未执行，`buildLabels()` 建的政权标签沿用 `on = !!p.active` 的静态取值
  - `markers.applyCustom(ms.markers)`（`:333`）→ 未执行，事件/军队朱印标注为空
  - `ms.focus` 视角聚焦（`:336-343`）→ 未执行，镜头停在 `DEFAULT_VIEW.zoom = 4.0`，不做 `fitBounds`/`flyTo`

  必须等玩家下一次触发 `setState`（推演、下诏、读档）才会补上。同一缺陷也影响「主菜单 → 读档」路径：`SavePanel.doLoad` 里 `setState(res.state)` 之后**立即** `popOverlay()`（`SavePanel.tsx:84-88`），但 `MapView` 此时尚未挂载（`inGame` 刚被置真），挂载时同理错过。

- 影响：开局与读档后的第一屏舆图是「静态默认态」而非当前局势 —— 已灭亡/未兴政权仍显示为活跃、紧急事件无朱印提示、镜头不聚焦国策要地。玩家不做任何操作的纯观察开局完全得不到地图信息，是可见的功能缺陷。

- 验证方式：启动 `npm run dev`，新开一局后**不做任何点击**，观察 (a) 政权标签是否与实际 `active_regimes` 一致；(b) 截图 `map.getZoom()`（可在 devtools 执行 `document.querySelector('.maplibregl-canvas')` 后不便取值时，改为观察是否自动聚焦）。(c) 更直接的判据：在 `MapView.tsx:314` 的 `return` 前加临时 `console.count("[map] sync skipped")`，新开一局后应见该计数为 1 且后续无补跑。

- 建议修复：把 ref 就绪也纳入触发条件。最小改动是给状态同步 effect 增加一个显式的「地图就绪」state：

  ```tsx
  const [mapReady, setMapReady] = useState(false);
  // onMapReady 里：controllerRef.current = controller; ...; loadGeoData(); setMapReady(true);
  useEffect(() => {
    const controller = controllerRef.current;
    const markers = markersRef.current;
    const data = dataRef.current;
    if (!mapReady || !controller || !markers || !data) return;
    ...
  }, [state, mapReady]);
  ```

  注意 `dataRef.current` 也在 `loadGeoData()` 里异步赋值，故 `setMapReady(true)` 应放在 `loadGeoData()` 的 `await` 之后（即 `dataRef.current = data` 之后），否则仍会早退。更稳的做法是把「地图+数据就绪」收敛为单一 `ready` 状态位，并在其中携带当前 `state` 做一次补偿同步。

---

### F-4 [P1] 事件选项「吉/凶」标注失真 —— 36% 的真实选项方向判错

- 位置：`frontend/src/renderer/utils/effects.ts:89-100`（`effectDeltaSign`）、`:136-153`（`judgeEffects`）；消费点 `frontend/src/renderer/panels/EventPanel.tsx:102-110`

- 证据：[确认] 实跑脚本 `D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\verify_judge_final.py`（用后端权威结算函数 `core.events._resolve_effects` 求真实数值）。

  判定链：

  ```ts
  // effects.ts:89-100
  const REDUCE_WORDS = ["减", "降", "无", "停", "损", "衰", "免"];
  export function effectDeltaSign(v: unknown): number {
    if (typeof v === "number" && Number.isFinite(v)) return v > 0 ? 1 : v < 0 ? -1 : 0;
    if (typeof v === "string") return REDUCE_WORDS.some((w) => v.includes(w)) ? -1 : 1;
    return 0;                                  // boolean / null 均落此处
  }
  // effects.ts:136-153（要点）：只累加符号，不看数值
  const s = effectDeltaSign(v);
  if (s > 0) good += 1; else if (s < 0) bad += 1;
  ```

  ```tsx
  // EventPanel.tsx:102-110 —— 用条数比较定色
  const { good, bad } = judgeEffects(eff);
  const tone = good > bad ? "border-[#3f6655] bg-[#eef3ec]"   // 绿框
             : bad > good ? "border-red/50 bg-red/5"           // 红框
             : "border-gold/40";
  ...
  {good > bad ? "　吉" : bad > good ? "　凶" : ""}
  ```

  脚本输出（83 条后端真实选项 effects）：

  ```
  后端真实选项 effects: 83 条
  前端「吉/凶」标注与后端数值方向不一致: 30 条 (36%)
    其中可归因于【档位词符号错判】: 7 条
    其余归因于【量级盲（只数条数）】: 23 条
  ```

  **(a) 档位词符号错判（7 条）**：后端 `core/events.py:500-514` 规定方向用**前缀** `±`：

  ```python
  # core/events.py:507-513
  text = str(value).strip()
  direction = 1.0
  if text.startswith("+"): text = text[1:]
  elif text.startswith("-"): direction = -1.0; text = text[1:]
  ```

  全库实测：`"±X"` 前缀式档位词出现 **50 次**，`"X减"` 后缀式 **0 次**。前端 `effectDeltaSign` 只认后缀减义词，于是对 `"-大"` 返回 `+1`（增益）。实跑逐条对拍（`verify_tier_sign.py`）：

  ```
  字面量     语义              前端 sign   判定
  -大      递减-大（降）           +1      增益(+1)  **错**
  -小      递减-小（降）           +1      增益(+1)  **错**
  -微      递减-微（降）           +1      增益(+1)  **错**
  -中      递减-中（降）           +1      增益(+1)  **错**
  +大      递增+大（升）           +1      增益(+1)  OK
  ```

  真实受害选项（前缀减益被计成增益，整条被判「吉」）：

  ```
  {'tech': '中', 'faction_change': {'新党': '中', '旧党': '-大', '中立派': '中'}, 'treasury': '-小'}
       前端: good=5 bad=0 -> 【吉】     后端实际净值 -399,997 -> 【凶】
  {'prestige': '微', 'treasury': '-微', 'external_xixia': '微'}
       前端: good=3 bad=0 -> 【吉】     后端实际净值 -199,998 -> 【凶】
  ```

  **(b) 量级盲（23 条）**：`judgeEffects` 只数条数。后端各维度量级相差 6 个数量级（`content.data.TIER_VALUE_BASE`）：

  ```
  treasury 单条最大 ±3,000,000 贯   vs   prestige 单条最大 ±10   vs   art_mastery 单条最大 ±3
  ```

  于是「2 条琐碎增益 + 1 条百万贯减益」稳定被判为「吉」：

  ```
  {'prestige': 10, 'defense_bonus': 15, 'treasury': -3000000}
       前端: good=2 bad=1 -> 【吉】     后端实际净值 -2,999,975 -> 【凶】
  {'prestige': 3, 'treasury': -2000000, 'defense_bonus': 10}
       前端: good=2 bad=1 -> 【吉】     后端实际净值 -1,999,987 -> 【凶】
  {'prestige': 5, 'treasury': -1000000, 'population_satisfaction': 3}
       前端: good=2 bad=1 -> 【吉】     后端实际净值   -999,992 -> 【凶】
  {'treasury': -600000, 'army_strength': 2, 'prestige': 1}
       前端: good=2 bad=1 -> 【吉】     后端实际净值   -599,997 -> 【凶】
  ```

- 影响：事件抉择前，玩家依据「〔推演效果〕+ 吉/凶朱批色」判断利弊 —— 而 36% 的选项该判断是错的，最严重处把**净亏 300 万贯**的选项高亮成绿色「吉」。这直接诱导错误的治国决策，是本项目「数值表述绝不能误导玩家」原则的实质性破坏。（注意 `formatEffects` 输出的**文字**是对的，错的只是吉/凶定色与方向计数，因此问题很隐蔽。）

- 验证方式：

  ```powershell
  cd D:\codebuddy\sz\game
  & "D:\codebuddy\.audit-venv\Scripts\python.exe" `
    "D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\verify_judge_final.py"
  & "D:\codebuddy\.audit-venv\Scripts\python.exe" `
    "D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\verify_tier_sign.py"
  ```

- 建议修复：
  1. **补前缀方向识别**（一行级）：`effectDeltaSign` 的字符串分支先判前缀 `"-"`：
     ```ts
     if (typeof v === "string") {
       const t = v.trim();
       if (t.startsWith("-")) return -1;
       if (t.startsWith("+")) return 1;
       return REDUCE_WORDS.some((w) => t.includes(w)) ? -1 : 1;
     }
     ```
  2. **改为量级求和而非计数**。最省事且最不易漂移的做法是让后端在事件里附带归一化权重，或在前端复用后端同一张换算表（把 `content.data.TIER_VALUE_BASE`/`TIER_RANGE` 经 `export_frontend_data.py` 导到 `renderer/data/constants.json`，该文件已存在且已被 `start` 面板消费），然后：
     ```ts
     judgeEffects(effects) → { net: number, good: number, bad: number }
     // 定色改用 Math.sign(net)，good/bad 仅作为「有几项收益/几项代价」的辅助展示
     ```
     注意各维度单位不同（贯 / 点 / 0-100 刻度），直接相加前需先归一到「档位权重」，否则 `treasury` 会主导一切 —— 这正是当前用计数法想规避的问题，需一并设计。
  3. 加单测：把 `events.py` 的 83 条 effects 字面量作为 fixture，断言 `sign(judge.net) === sign(backend_net)`，即可永久锁死该缺陷（本次的 `verify_judge_final.py` 可直接改造为测试）。

---

### F-5 [P2] 无 CSP，且渲染层 dev server 对外监听 + 关闭 Host 校验

- 位置：`frontend/src/renderer/index.html`（全文 12 行，无 CSP meta）；`frontend/src/main/index.ts`（无 `session.defaultSession.webRequest.onHeadersReceived`）；`frontend/electron.vite.config.ts:35-38`

- 证据：[确认]

  ```html
  <!-- frontend/src/renderer/index.html 全文 1-12 行 -->
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>宋祚</title>
  </head>
  ```

  仅 4 个 head 子元素，无 `<meta http-equiv="Content-Security-Policy" ...>`。主进程侧同样：`src/main/index.ts` 内检索 `Content-Security-Policy`、`onHeadersReceived`、`session` 全部 0 命中（`out/main/index.js` 亦然）。

  ```ts
  // frontend/electron.vite.config.ts:35-38
  server: {
    host: "0.0.0.0",
    allowedHosts: true
  }
  ```

- 影响：
  1. 无 CSP 意味着没有第二道防线。本项目 `sandbox` 已开启（**前提是 F-1 修好后的产物**）、`contextIsolation: true`、`nodeIntegration: false`，故风险被显著削弱 —— 但 React 应用内任何一处 `javascript:` 链接、被注入的内联脚本都不会被拦住。`SettingsPanel.applyFontFamily` 已经用 `el.textContent` 写 `<style>`（`SettingsPanel.tsx:512`），是良好实践，降低了自身注入面。
  2. `host: "0.0.0.0"` + `allowedHosts: true` 仅影响 `npm run dev`。此时渲染层由 Vite 从局域网可访问的地址提供，且 Host 头校验被关闭 → 同一局域网内其他主机可访问开发中的渲染层，并为 DNS rebinding 攻击打开入口（Electron 窗口会把攻击者控制的源当作本地 dev 源加载）。

- 验证方式：

  ```powershell
  cd D:\codebuddy\sz\game\frontend
  Select-String -Path src\renderer\index.html,src\main\index.ts,out\main\index.js `
    -Pattern "Content-Security-Policy|onHeadersReceived"
  # 期望：0 命中（当前状态即复现）
  # dev 暴露面复核（需 Node）：
  npm run dev
  netstat -ano | Select-String ":5173"
  # 期望监听 0.0.0.0:5173（而非 127.0.0.1:5173）
  ```

- 建议修复：
  1. 在 `src/renderer/index.html` 加 CSP meta（Vite 构建期会原样保留）：
     ```html
     <meta http-equiv="Content-Security-Policy"
           content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';
                    img-src 'self' data: blob:; font-src 'self' data:;
                    connect-src 'self' http://127.0.0.1:8080; object-src 'none';
                    base-uri 'none'; frame-ancestors 'none'">
     ```
     `style-src` 保留 `'unsafe-inline'` 是必要的（`SettingsPanel` 动态 `<style>` 与 Tailwind 运行时注入）；`'unsafe-eval'` 与 `*` **必须避免**。注意 maplibre 需要 `worker-src blob:` / `child-src blob:`，实机验证后按需补 `worker-src 'self' blob:`。
  2. 生产环境若走 `file://` 加载，meta CSP 同样生效；另外建议在主进程加响应头兜底（`onHeadersReceived` 注入同一条 CSP），二者取交集更稳。
  3. `host` 改为 `127.0.0.1`，`allowedHosts` 改为显式允许列表（如 `["localhost", "127.0.0.1"]`）而非 `true`。

---

### F-6 [P2] 鉴权契约缺口 —— 后端配了 token 则前端全部请求恒 401

- 位置：`frontend/src/renderer/api/client.ts:195-199`（请求头只有 Content-Type）

- 证据：[确认] 两端代码对读。

  ```ts
  // frontend/src/renderer/api/client.ts:195-199
  const res = await fetch(`${this.base}${path}`, {
    headers: { "Content-Type": "application/json" },   // 无 Authorization
    ...init,
    signal: controller.signal
  });
  ```

  全库检索 `frontend/src` 的 `Authorization` / `Bearer`：**0 命中**（唯一 `token` 命中均为 token 计量语义）。

  后端对应规则：

  ```python
  # backend/server.py:93-96
  if _AUTH_TOKEN:
      if hmac.compare_digest(auth, f"Bearer {_AUTH_TOKEN}"):
          return
      raise HTTPException(status_code=401, detail="令符不合，未获授权。")
  ```

  并且 `main()` 强制：非回环 host 且无 token 直接拒绝启动（`server.py:830-833`），即**远程部署必须配 token**；一旦配了 token，前端每个 `/api/*` 都会 401。

  对照组：Python 侧 `HttpBackend` **有**完整支持（`backend/client.py:304-311` 读 `SONGZUO_SERVER_TOKEN` 或 `backend_config.json` 的 token 并加 `Authorization: Bearer`），并有 401 的明确指引（`backend/client.py:319-324`）。Electron 前端缺失这一整套。

- 影响：本机 spawn 模式（默认）不受影响。但项目的远程/局域网后端模式在此前端下**完全不可用**：表现为每一个操作都返回「此令未获准：令符不合，未获授权。」且玩家无从配置 token（`SettingsPanel` 只有 AI key，没有后端 token 字段）。属功能缺口 + 契约不一致（Python 客户端与 Electron 客户端对同一后端的能力不对等）。

- 验证方式：

  ```powershell
  # 1) 静态确认前端不发鉴权头
  Select-String -Path D:\codebuddy\sz\game\frontend\src -Pattern "Authorization|Bearer"
  # 期望 0 命中
  # 2) 实机复现（需 Node + Python）
  cd D:\codebuddy\sz\game
  $env:SONGZUO_SERVER_TOKEN="testtoken123"
  D:\codebuddy\.audit-venv\Scripts\python.exe -m backend.server
  Invoke-WebRequest http://127.0.0.1:8080/api/readouts -Method GET
  # 期望 401（无头）；前端启动后同样 401
  ```

- 建议修复：
  1. 在 `ApiClient` 增加可选 token，并在 `request()` 里注入头：
     ```ts
     constructor(base: string, token = "") { this.base = base.replace(/\/+$/, ""); this.token = token; }
     private headers(): HeadersInit {
       const h: Record<string, string> = { "Content-Type": "application/json" };
       if (this.token) h["Authorization"] = `Bearer ${this.token}`;
       return h;
     }
     ```
  2. token 来源与 Python 侧对齐：环境变量 `SONGZUO_SERVER_TOKEN` → `backend_config.json` 的 `token` 字段。注意目前 `BackendConfig` 接口（`src/main/index.ts:8-13`）也**没有** `token` 字段，需一并补上并只在主进程读取后经既有 `backend:get-url` 通道下发（或新增一个最小的 `backend:get-token`），避免把 token 硬编码进前端可读文件。
  3. 顺带补 401 的玩家可读文案（对齐 `backend/client.py:319-324` 的指引）。

---

### F-7 [P2] 后端子进程的生命周期漏洞（孤儿进程 / 失败后不重试 / 退出路径不覆盖）

- 位置：`frontend/src/main/index.ts:110-126`、`:241-243`、`:245-251`、`:214-218`

- 证据：[确认] 代码路径分析。

  **(a) 单次失败后本会话永不重试**

  ```ts
  // src/main/index.ts:214-218
  let backendUrlPromise: Promise<string> | null = null;
  function ensureBackendUrl(): Promise<string> {
    if (!backendUrlPromise) backendUrlPromise = ensureBackend();   // 一旦赋值即永久缓存
    return backendUrlPromise;
  }
  ```

  `ensureBackend()`（`:128-143`）在 spawn 失败或 `waitForBackend` 超时（40 次 × 500ms = 20s）后**仍正常 resolve** 一个 URL。该 resolved promise 被永久缓存，渲染层后续任何 `getBackendUrl()` 都拿到同一个「其实没起来」的地址，主进程也不会再尝试 spawn。`App.tsx:36-43` 的兜底轮询（20 × 700ms ≈ 14s）在首次探测失败后便放弃（`setBackend(url, false, ...)`）。**玩家唯一出路是重启整个应用。**

  **(b) spawn error 路径未复位 promise**

  ```ts
  // src/main/index.ts:117-121
  backendProc.on("error", (e) => {
    console.error(`[backend] 启动失败: ${String(e)}`);
    backendProc = null;      // 仅清进程句柄，不动 backendUrlPromise
  });
  ```

  **(c) 孤儿进程与端口占用**

  ```ts
  // src/main/index.ts:245-251
  app.on("before-quit", () => {
    if (backendProc) {
      console.log("[backend] 关闭后端子进程");
      backendProc.kill();      // Windows 上仅发终止信号，不等 exit、不复查
      backendProc = null;      // 立即置空 → 后续无二次机会
    }
  });
  ```

  两点问题：① `kill()` 后立即 `backendProc = null`，即使子进程未真正退出也没有复查手段；② `window-all-closed` 分支（`:241-243`）直接 `app.quit()`，**不经过** `before-quit` 兜底逻辑的补强（`before-quit` 会在 `quit()` 时触发，但此时 `backendProc` 可能因 (b) 的错误路径已为 `null`，或已退出）。主进程崩溃/被强杀（任务管理器结束）时完全无清理。残留的 `python -m backend.server` 继续占用 8080，且它持有**它自己那份** `_state`。

  这带来一个更隐蔽的后果：下次启动时 `ensureBackend()` 首句 `checkHealth(cfg.url)` 会对**上一个会话遗留的旧后端**返回 200（`/health` 是恒真端点：`server.py:312-314` 返回 `{"ok": True, ...}`），于是判定「已就绪」、不再 spawn 新进程 —— 玩家实际连到的是陈旧进程，其状态与本次会话无关。

  **(d) 端口占用无显式处理**：`checkHealth` 只判 HTTP 200，不校验响应体 `backend === "python-reference"`（`server.py:314` 恰好提供了这个可校验字段）。若 8080 被其它服务占用且其 `/health` 返回 200，前端会静默当作后端可用。

- 影响：后端启动失败/超时属一次性不可恢复（需重启应用）；正常关闭可能留下孤儿进程与端口占用；二次启动可能连上陈旧后端。都是真实的可复现故障态。

- 验证方式：

  ```powershell
  cd D:\codebuddy\sz\game\frontend
  # (a) 复现「不重试」：临时让后端无法启动
  #   把 src/main/index.ts:94 的 venv 探测分支指向不存在的路径，或
  #   直接以空 PATH 启动（删掉 python 可发现性）
  npm run dev
  #   观察：20s 超时后前端显示「后端未就绪」，此后无论等多久都不会再尝试 spawn
  #   控制台只出现一次 "[backend] spawn ..."（或仅一次启动失败日志）
  # (b) 复现孤儿：启动后强制结束 Electron
  taskkill /F /IM electron.exe
  Get-Process python -ErrorAction SilentlyContinue    # 期望仍存在 → 孤儿
  netstat -ano | Select-String ":8080"
  ```

- 建议修复：
  1. `ensureBackendUrl()` 的缓存改为**可失效**：失败/超时路径清空 `backendUrlPromise`（或缓存 `{url, ok}` 并允许重试），并在 `backend:get-url` handler 里给出显式失败信号，而非静默返回不可用 URL。
  2. `backendProc.on("exit")` 与 `on("error")` 均复位 `backendUrlPromise`，让下一次 `getBackendUrl()` 能重启后端。
  3. 退出清理改为「先解绑再终止、并等确认」：置 `backendProc = null` 前先 `kill()`，并在 `app.on("before-quit")` 里对 `process.platform === "win32"` 用 `taskkill /pid <pid> /T /F`（Windows 下 `ChildProcess.kill()` 对孙进程无效）；同时把清理逻辑抽成函数，在 `window-all-closed`、`before-quit`、以及 `app.on("will-quit")` 统一调用（幂等）。
  4. `checkHealth` 增加响应体校验：`res.statusCode === 200 && body.backend === "python-reference"`，避免误认他人服务。
  5. 端口占用可显式处理：健康检查失败且 `spawn` 后仍失败时，提示玩家「8080 可能被占用」。

---

### F-8 [P2] 存储槽位损坏标记未被消费；若干「定义了但用不上」的契约（类型乐观标注 / 死方法）

- 位置：`frontend/src/renderer/panels/SavePanel.tsx:17-22,76-79`；`frontend/src/renderer/api/client.ts:25-27,87-93,108,126-136,328-335`

- 证据：[确认]

  **(a) 损坏档标记被完全忽略（含数据丢失风险）**

  后端确实产出该标记：

  ```python
  # core/save_load.py:611-612
  slots.append({"slot": i, "corrupt": True, "time": "存档损坏",
                "year": 0, "month": 1, "era": "", "turn": 0})
  ```

  前端只认 `empty`：

  ```tsx
  // SavePanel.tsx:17-22
  function slotLabel(s: Dict): string {
    if (s.empty === true) return `[${asNum(s.slot)}] 空槽位`;
    return `[${asNum(s.slot)}] ${asStr(s.time)} | ${asStr(s.era)}${asNum(s.year)}年${asNum(s.month)}月`;
  }
  ```

  损坏档因此显示为 `[3] 存档损坏 | 0年1月`，与正常档外观无区别、无警示色。`doLoad` 的守卫（`:76-79`）也只拦 `empty === true`，损坏档可被选中并提交 → 后端 `load_game` 返回 `None`（`core/save_load.py:236` 已在损坏时备份 `.corrupt` 并返回 `None`）→ `_state_to_dict(None)` 抛异常 → 500 → 前端落到 `doLoad` 的 catch，提示「读档失败，存档可能已损坏：政务后端一时失序：Internal Server Error」。**不会崩溃**（这条链是安全的），但**覆盖存档风险更大**：`doSave` 对损坏槽位**无任何保护**，玩家在损坏槽位上点「保存」会直接 `POST /api/save {slot:3}` 覆盖它，而 `.corrupt` 备份虽在同一目录却不在 UI 上可见可恢复。

  **(b) 死方法：`saveDecreeDraft`**

  `client.ts:328-335` 定义了 `saveDecreeDraft` → `POST /api/decree/draft`，但全库检索（除定义处）**0 调用**。后端该端点是活的（`server.py:657-658`）。而 `DecreePanel` 的「票拟批红」模式读的是 `state.edict_drafts`（`DecreePanel.tsx:205-207`），靠后端其他路径填充。故该能力在前端不可达。

  **(c) `AiConfigResult` 字段漂移**

  ```ts
  // client.ts:126-136
  export interface AiConfigResult {
    configured: boolean;
    api_key_masked: string;
    base_url: string;
    model: string;
    has_key?: boolean;      // <-- GET /api/ai_config 从不返回
    message?: string;
    available?: boolean;    // <-- GET 也从不返回
    enable_tools?: string;
  }
  ```

  后端 `api_ai_config_get`（`server.py:729-738`）只返回 `configured / api_key_masked / base_url / model / enable_tools`；`has_key`/`available`/`message` 只有 `POST /api/ai_config` 才返回（`server.py:816-823`）。消费点信任了不存在的字段：

  ```tsx
  // SettingsPanel.tsx:296
  {cfg?.has_key ? "（已配置生效）" : "（未配置）"}
  ```

  `cfg` 来自 `getAiConfig()`（`SettingsPanel.tsx:166,168`），其 `has_key` 恒为 `undefined` → **该状态提示恒显示「（未配置）」**，即便密钥已正确保存。玩家据此以为密钥没生效。（`configured` 才是可用字段，代码里没用。）

  **(d) `ReadoutsResult` 必填声明是乐观的（类型谎言）**

  ```ts
  // client.ts:87-93（granary 声明为必填对象）
  granary: { monthly?: number; army?: number; ... };
  // client.ts:108（defense_lines 声明为必填）
  defense_lines: Record<string, { fortification: number; garrison: number }>;
  ```

  后端在任一子步骤抛异常时把整段置为空对象：

  ```python
  # server.py:471-472
  except Exception:
      granary = {}
  # server.py:461-462
  except Exception:
      flow = {}
  ```

  `granary: {}` 与 TS 声明的 `granary: {...}` 相容（成员皆可选），故不致命；但 `defense_lines` 若为 `{}` 而消费方按必填签名直接索引就会 `undefined`。实测消费点均用了 `?? {}` / `Object.entries(ro?.defense_lines ?? {})`（如 `MilitaryPanel.tsx:74`），**当前未触发**。仍应把 `granary`/`defense_lines`/`finance`/`flow` 标为 `?` 或改为可空，以免后续新增消费点时踩坑。

- 影响：(a) 是本条里唯一有真实后果的：损坏档无法在 UI 上识别，且可被静默覆盖（存档丢失）。(c) 使一个玩家可见的状态指示恒为假。(b)(d) 为可维护性负担与后续踩坑点。

- 验证方式：

  ```powershell
  # (a) 制造一个损坏档后观察 UI
  cd D:\codebuddy\sz\game
  $p="$env:USERPROFILE\...\saves\slot_3.json"   # 实际路径见 core/save_load.py::_slot_path
  Set-Content $p "{ broken json"
  # 启动前端 → 存档面板：观察槽 3 是否显示为普通档（当前：是）
  # 静态确认：
  Select-String -Path D:\codebuddy\sz\game\frontend\src\renderer\panels\SavePanel.tsx -Pattern "corrupt"
  #   期望 0 命中 → 复现
  # (b)
  Select-String -Path D:\codebuddy\sz\game\frontend\src -Pattern "saveDecreeDraft"
  #   期望仅 client.ts 定义处 1 命中 → 复现
  ```

- 建议修复：
  1. `slotLabel` 增加损坏分支（`if (s.corrupt === true) return \`[${...}] 存档损坏（不可读取）\``），并用 `text-red` 等警示样式；`doLoad` 守卫加 `|| slots[sel].corrupt === true`；`doSave` 对损坏槽位要求二次确认（`window.confirm`），避免直接覆盖。
  2. 把 `has_key` 的读取改为 `cfg?.configured`，或后端 `api_ai_config_get` 补出 `has_key: bool(key)`（后者更贴合「类型契约前后端对齐」的目标，且 Python 侧无需改动）。
  3. `saveDecreeDraft` 二选一：接入 UI（在 `DecreePanel` 加「入待签」入口），或从 `client.ts` 删除以免误认为已实现。
  4. `granary` / `defense_lines` / `finance` / `flow` 改为可选或 `Record<string, never>` 兼容，并同步后端注释说明「异常时返回空对象」的语义。

---

### F-9 [P2] 舆图数据单文件 13.3 MB 全量 JSON 解析 + 主线程同步解码；`view.json` 与 `simplify.ts` 为死代码

- 位置：`frontend/src/renderer/map/MapView.tsx:93-117`；资产 `frontend/public/map/regions.topojson`(13,305.7 KB)；`frontend/public/map/view.json`；`frontend/src/renderer/map/simplify.ts`

- 证据：[确认]

  ```tsx
  // MapView.tsx:93-107
  const loadTopo = async () => {
    const res = await fetch(`${MAP_BASE_URL}/regions.topojson`);
    if (!res.ok) throw new Error(`regions.topojson → HTTP ${res.status}`);
    return (await res.json()) as TopoJSON.Topology;      // 13.3 MB 全量 JSON.parse（主线程）
  };
  ...
  const circuits = feature(topo, topo.objects.circuits) as GeoJSON.FeatureCollection;
  const regimes = feature(topo, topo.objects.regimes) as GeoJSON.FeatureCollection;
  const borders = feature(topo, topo.objects.circuit_borders) as GeoJSON.FeatureCollection;
  const regime_borders_fc = feature(topo, topo.objects.regime_borders) as GeoJSON.FeatureCollection;
  // MapView.tsx:111-113
  for (const fc of [circuits, regimes, regime_borders_fc, cities, land, rivers, lakes, borders]) {
    fc.features.forEach((f, j) => { f.id = j; });         // 8 个图层全量遍历
  }
  ```

  该路径全部发生在渲染进程主线程；`loadGeoData` 期间无任何 loading 指示（`MapView` 只渲染一个空 `div`，`:393`），也无分片/Worker。

  死代码证据：
  - `public/map/view.json` 实际内容为 `{"bounds":[60,-44,150,56],"center":[108,31],...,"zoom":4.0}`，而 `MapView.tsx:9-17` 的 `DEFAULT_VIEW` 是它的硬编码副本，**没有任何代码读 view.json**（全库检索 `view.json` 仅 `MapView.tsx` 注释提及）。
  - `map/simplify.ts`（56 行，基于 `topojson-simplify` 的档位简化器）**无任何 import**（全库检索 `simplify` 仅命中自身）。对应地 `MapController.setLayerData`（`mapController.ts:258-262`）、`fitBounds`(`:264`)、`resetView`(`:280`)、`flyToFeature`(`:271`) 四个 public 方法零调用。

  运行期行为与注释相矛盾：`MapView.tsx:115-116` 注释写「政权几何全精度注入(不再按 zoom 分档简化)」，即简化机制已被主动放弃，但 `simplify.ts` 与三个 controller API 未随之清理。

- 影响：首屏进入游戏时，主线程需解析 13.3 MB JSON 并做 8 次全量 feature 遍历 —— 典型机器上造成数百毫秒至 1 秒以上 UI 冻结（无 loading 反馈，表现为「点了开局像卡死」）。低端机更明显。属真实体验缺陷，非纯风格问题。

- 验证方式：

  ```powershell
  cd D:\codebuddy\sz\game\frontend
  (Get-Item public\map\regions.topojson).Length / 1KB      # → 13305.7
  # 死代码确认：
  Select-String -Path src -Pattern "simplify" -Recurse | Select-String -NotMatch "simplify.ts"
  #   期望 0 命中 → simplify.ts 无人引用
  Select-String -Path src -Pattern "view\.json" -Recurse
  #   期望仅注释命中 → 未被读取
  Select-String -Path src -Pattern "setLayerData|resetView|flyToFeature|\.fitBounds\(" -Recurse
  #   期望分别仅定义处命中
  # 卡顿实测（需 Node）：npm run dev → 打开 devtools Performance 录制 → 点「承统践祚」
  #   期望在 loadGeoData 期间看到单一长任务（Long Task > 200ms）
  ```

- 建议修复：
  1. **首选**：在 `scripts/build-topo.ts` 里对 `regions.topojson` 预简化（`topojson-simplify` 的 `presimplify` + `simplify`），或对 `circuits`/`regime_borders` 用 `topoquantize` 降精度。目标是把它压到 2–4 MB 量级。
  2. **次选**：`regions.topojson` 按图层拆成多个文件，`land`/`rivers`/`lakes` 已是独立文件但同样偏大（`rivers` 1.4 MB / `land` 0.5 MB），可一并量化压缩。
  3. 解析移出主线程：`fetch(...).then(r => r.text())` 后交给 Web Worker 做 `JSON.parse` + `topojson-client.feature()`，只把解码后的 `FeatureCollection` 传回主线程（`structuredClone` 支持 GeoJSON）。这既消除冻结，也避免拆分文件的复杂度。
  4. 加载期间在 `MapView` 渲染明确 loading 态（当前只有空 div）。
  5. 清理死代码：删 `map/simplify.ts` 或把它接回 `MapController.setLayerData` 的按档位切换路径；`view.json` 要么被 `MapView` 读取（消除 `DEFAULT_VIEW` 双份真值），要么删除。

---

### F-10 [P2] 无 React 错误边界 —— 任一浮层面板抛错即整页白屏

- 位置：`frontend/src/renderer/main.tsx:7-12`；`frontend/src/renderer/panels/OverlayStack.tsx:117-186`

- 证据：[确认] 全库检索 `ErrorBoundary` / `componentDidCatch` / `getDerivedStateFromError`：**0 命中**。

  ```tsx
  // main.tsx:7-12
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <GameStoreProvider>
        <App />          // 无 ErrorBoundary 包裹
      </GameStoreProvider>
    </React.StrictMode>
  );
  ```

  ```tsx
  // OverlayStack.tsx:117-186 —— 33 个分支的裸 switch
  function PanelBody({ kind, props }: { kind: PanelKind; props?: Record<string, unknown> }) {
    switch (kind) {
      case "advance": return <AdvancePanel props={props} />;
      ...
      default: return <PlaceholderPanel kind={kind} />;
    }
  }
  ```

- 影响：React 18 中未捕获的渲染期异常会卸载整棵树 → 玩家看到全白页面，且**无法自救**（无「返回主菜单」入口，因为 UI 已消失），必须重启应用。风险并非纯理论：多个面板对后端字段做了直接索引或强制展开，例如 `DetailPanel.tsx:99-113` 对 `extProv[1].armies` 做 `Array.isArray` 判断后又直接 `as Record<string, unknown>[]` 再 `.map`；`DiplomacyPanel.tsx:197,232,239,255` 对 `currentInfo.provinces` / `cur.armies` / `cur.buildings` 做 `as` 断言后展开。后端 `/api/readouts` 与快照字段在异常时确实会返回 `{}`（见 F-8(d)），存在落到非预期形状的路径。

- 验证方式：

  ```powershell
  # 静态确认
  Select-String -Path D:\codebuddy\sz\game\frontend\src -Pattern "ErrorBoundary|componentDidCatch|getDerivedStateFromError" -Recurse
  # 期望 0 命中 → 复现
  # 动态复现（需 Node）：在任一面板内临时 throw，例如 OverlayStack.tsx 的 case "detail" 加
  #   { if (props?.forceCrash) throw new Error("x"); }
  # 然后 console 里 push 该面板 → 观察整页白屏
  ```

- 建议修复：
  1. 在 `main.tsx` 的 `<App />` 外层加一个顶层 `ErrorBoundary`，兜底 UI 提供「重载窗口」与「返回主菜单」按钮（后者可 `localStorage` + `location.reload()` 或直接调用 `window.songzuo` 暴露的最小 API）。
  2. 在 `OverlayStack` 的 `PanelBody` 外再包一层**面板级** ErrorBoundary，key 用 `ov.id`：这样单个面板崩溃只关闭该浮层并给出提示，游戏主体（舆图/HUD/存档）不受影响。这一层收益最大，因为浮层是缺陷最密集的边界。
  3. 顺手把 `DetailPanel`/`DiplomacyPanel` 里的 `as` 强转替换为运行时收敛（复用已有的 `asDict`/`asArr` 模式），降低触发概率。

---

### F-11 [P2] `EFFECT_NAME` 覆盖度 27.7%，未登记键被静默丢弃

- 位置：`frontend/src/renderer/utils/effects.ts:13-86`（65 条登记）、`:117-119`（静默跳过）

- 证据：[确认] 实跑脚本 `_scratch/audit-2026/verify_effect_keys.py`（权威源取后端 `content.data.TIER_VALUE_BASE`，即 `ai/client_utils.py:109,1153` 的 `_EFFECT_WHITELIST`）。

  ```ts
  // effects.ts:117-119
  const label = EFFECT_NAME[k];
  // 未登记键一律跳过：宁可少显示，也不把英文键名当文案直出
  if (!label) continue;
  ```

  脚本输出：

  ```
  backend TIER_VALUE_BASE keys : 18 (+faction_change)
  frontend EFFECT_NAME keys    : 65

  [A] 后端会结算、前端预览静默跳过（漏报）—— 1 键: faction_change
  [B] 前端登记、后端 tier 换算表无此维度（前端独有，疑似历史残留）—— 47 键

  覆盖度：前端 65 条登记中仅 18 条命中后端真实维度（27.7%）
  ```

  [A] 的 `faction_change` 是**误报**：`formatEffects` 在 `:108-113` 对它有专门分支（展开为 `派系名±值`），并未丢弃。故当前**不存在实际漏报**。

- 影响：**当前无功能损害**，属「待爆的隐患」而非现行缺陷。真正的问题是 [B]：65 条登记里 47 条在后端 tier 换算表中已无对应维度（属历史 Tk 键名残留）。这不影响正确性（后端不会产出它们），但意味着该表的维护者无法从表本身判断哪些是真的。风险在于：**后端未来新增一个 effect 维度时，前端不会有任何提示，事件预览会静默少显示这一项** —— 而 `formatEffects` 的注释「宁可少显示，也不把英文键名当文案直出」使这种静默成为既定行为，难以在测试中发现。

  另外 `effectDeltaSign` 对 `boolean` 返回 0（`effects.ts:120-121` 却能显示 `${label}行/止`），即布尔型效果有文案、无吉凶计数 —— 影响极小，一并记录。

- 验证方式：

  ```powershell
  cd D:\codebuddy\sz\game
  & "D:\codebuddy\.audit-venv\Scripts\python.exe" `
    "D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\verify_effect_keys.py"
  ```

- 建议修复：
  1. 把 47 条已无数据源的登记项移入 `@deprecated` 分组或直接删除，只保留后端真实维度（18 + `faction_change`），让「表 = 契约」重新成立。
  2. 对未登记键改为**开发期显式告警**而非静默跳过：
     ```ts
     if (!label) {
       if (import.meta.env.DEV) console.warn("[effects] 未登记的 effect 键（已在预览中丢弃）:", k, v);
       continue;
     }
     ```
     这样后端新增维度会在联调时立即暴露。
  3. 更彻底的做法：由 `export_frontend_data.py` 把 `TIER_VALUE_BASE` 的键导出到 `renderer/data/constants.json`（该文件已存在），前端启动时断言 `EFFECT_NAME` 覆盖了全部键，缺失即报错。这样契约漂移会在启动时被卡住。

---

### F-12 [P2] 构建流水线未串联 —— 舆图数据再生成与 PyInstaller 前置步骤全靠人工

- 位置：`frontend/package.json:11-15`；`frontend/electron-builder.yml:9-16`

- 证据：[确认]

  ```json
  // package.json:11-15
  "dev": "electron-vite dev",
  "build": "electron-vite build",
  "build:topo": "tsx scripts/build-topo.ts",
  "dist": "electron-vite build && electron-builder --win nsis",
  ```

  - `build` 与 `dist` **都不调用** `build:topo`。`scripts/build-topo.ts` 是 `public/map/*.topojson` 与 `public/map/*.geojson` 的**唯一生成者**（`build-topo.ts:35-46`），却需手动 `npm run build:topo`。
  - `electron-builder.yml:9-16` 的注释明确要求打包前先跑 PyInstaller：

    ```yaml
    # 故打包前须先执行一次 PyInstaller（工作目录 game/：pyinstaller SongZuo.spec）。
    extraResources:
      - from: ../dist/SongZuo
        to: backend
    ```

    `dist` 脚本并不包含该步骤；`../dist/SongZuo` 不存在时 electron-builder 的行为需实机确认（通常报错或产出缺后端的包）。

  这与 F-1 同源：工程没有「源 → 产物」的强制链路，导致安全修复（F-1）与数据/后端资源（本条）都可能滞后。

- 影响：`npm run dist` 在干净检出上无法产出可运行安装包；更常见的是产出「舆图数据陈旧但能启动」的包，缺陷难以察觉（舆图能显示，但国界是上一版的）。与 F-1 叠加后，工程存在系统性的「产物滞后」风险。

- 验证方式：

  ```powershell
  cd D:\codebuddy\sz\game\frontend
  Select-String -Path package.json -Pattern "build:topo"
  # 期望仅定义行命中，scripts 内无其他引用 → 复现
  Test-Path ..\dist\SongZuo          # extraResources 的来源
  # 期望 False（当前）→ dist 前置条件未满足
  ```

- 建议修复：
  1. 串联数据生成：
     ```json
     "build": "npm run build:topo && electron-vite build",
     "dist": "npm run build && electron-builder --win nsis"
     ```
     注意 `build:topo` 需要 `game/assets/map/web/*.geojson` 存在，建议在脚本内对缺失资产给出明确失败（当前 `build-topo.ts:29-31` 对缺失层是 `console.warn` 后 `continue`，会静默产出不完整数据 —— 建议改为非零退出）。
  2. 把 PyInstaller 步骤显式化：新增 `"dist:full": "cd .. && pyinstaller SongZuo.spec && cd frontend && npm run build && electron-builder --win nsis"`，或在 `dist` 前置一个存在性检查脚本，`../dist/SongZuo/SongZuo.exe` 缺失时立即报错退出。
  3. 加一条 `predev` 时效检查（见 F-1 建议 2），确保 `out/main/index.js` 不比 `src/main/index.ts` 旧。

---

### F-13 [P2] 「返回主菜单」的存档失败降级会丢进度；「视听音律」为纯装饰

- 位置：`frontend/src/renderer/panels/SettingsPanel.tsx:44-58`、`:448-483`、`:517-539`

- 证据：[确认]

  ```tsx
  // SettingsPanel.tsx:44-58
  async function backToMenu() {
    const saveFirst = window.confirm(
      "返回主菜单前是否先存档？\n\n【确定】= 先存档再回主菜单\n【取消】= 不存档，直接回主菜单"
    );
    if (saveFirst) {
      try {
        const res = await getApiClient().save(0);
        if (!res.ok && !window.confirm("自动存档失败（槽位 0）。仍要返回主菜单吗？")) return;
      } catch {
        if (!window.confirm("自动存档失败（槽位 0 写入异常）。仍要返回主菜单吗？")) return;
      }
    }
    clearOverlays();     // ← 无论存档成败，此后一律清空全部浮层并退出游戏
    setInGame(false);
  }
  ```

  存档失败时确实多了一次确认 —— 但 `window.confirm` 的默认文案是「仍要返回主菜单吗？」，玩家为回到主菜单而连点两次确认是极自然的操作，随后 `clearOverlays()` + `setInGame(false)` **无条件执行**，`Progress` 未落档即丢失。同时 `clearOverlays()` 会清掉当前所有浮层（包括可能的未提交拟旨输入）。

  另：`AudioSettingsView`（`:448-483`）的 `muted`/`vol` 是纯 `useState`，全库无任何音频消费点（无 `Audio`/`Howler`/`<audio>`），退出面板即丢；其标题「大晟府雅乐音量」对玩家暗示有实际效果。相比之下同一面板的 `UiScaleSettingsView`（`:517-539`）有真实 `localStorage` 持久化与 DOM 生效，二者并排出现加剧误导。

- 影响：玩家在存档失败时会**在不知情的情况下丢失自上次存档以来的全部进度**（含已输入未提交的拟旨内容）。音律设置是不实的功能宣称，属「伪成功 UI」，与项目在其他位置多处刻意修复的「不伪造」原则（如 `client.ts:382-390` 对 `fetchModels` 的修复、`DecreePanel.tsx:127-129` 对伪成功的修复）自相矛盾。

- 验证方式：

  ```powershell
  # 静态确认音律无消费点
  Select-String -Path D:\codebuddy\sz\game\frontend\src -Pattern "new Audio|<audio|Howler|playSound" -Recurse
  # 期望 0 命中 → 纯装饰
  # 动态复现丢档（需 Node + Python）：
  #   1. 开局并推演若干回合
  #   2. 让存档失败：把 saves 目录设为只读，或后端以只读盘启动
  #   3. 设置面板 →「返回主菜单」→ 连点两次确认
  #   期望观察：回到主菜单，重新读档后进度回到旧档（本次进度丢失）
  ```

- 建议修复：
  1. `backToMenu` 改为「存档失败则**阻止**返回」的语义，而不是「再问一次」：
     ```tsx
     if (saveFirst) {
       let ok = false;
       try { ok = (await getApiClient().save(0)).ok; } catch { ok = false; }
       if (!ok) {
         setMsg({ type: "error", text: "自动存档失败，已阻止返回主菜单以免进度丢失。" });
         return;                       // 不 clearOverlays、不 setInGame(false)
       }
     }
     ```
     若需保留「强行返回」出口，应改成明确的危险按钮（红色、独立文案「放弃进度并返回」），而不是 `confirm` 的默认路径。
  2. `AudioSettingsView` 二选一：接入真实音频（当前无音频资源，成本较高），或把该 Tab 隐藏/标注为「暂未实装」并从设置面板移除，以消除不实宣称。

---

### F-14 [P3] 死动作与虚构字段

- 位置：`frontend/src/renderer/api/client.ts:139-141,148`；`frontend/src/renderer/panels/EventPanel.tsx:41,78`

- 证据：[确认]

  **(a) 三个 `ActionName` 零调用**

  全库检索确认（除 `client.ts` 的联合类型定义处）：

  | 动作 | 前端调用 | 后端 handler | 备注 |
  |------|----------|--------------|------|
  | `do_personal_action` | 0 | `backend/client.py:176-177` 有 | 完全不可达 |
  | `unlock_focus` | 0 | `backend/client.py:195-196` 有（与 `_start_focus_action` 同体，`:238-245`） | 完全不可达 |
  | `issue_secret_decree` | 0 | `backend/client.py:165-166` 有 | 经 `issue_decree(is_secret:true)` 内部等价可达（`core/commands_decree.py:303-306`） |

  即 `ActionName`（23 项）与后端 handler 表（23 项）**逐一对齐、无缺无多**，README「逐一对齐」的声明属实 —— 但其中 3 项在前端没有触发入口，实际可达 20 项。

  **(b) `EventPanel` 读取后端从不产出的字段**

  ```tsx
  // EventPanel.tsx:41
  const needsConfirm = event?.needs_confirm === true;
  // EventPanel.tsx:78
  {(breakId || needsConfirm) && ( <span ...>军机 · 战略决策</span> )}
  ```

  全库检索 `needs_confirm`（`game/**/*.py`）：仅 `EventPanel.tsx` 自身命中，后端**从不产出**该字段。故 `needsConfirm` 恒为 `false`，角标实际只由 `breakId`（`_break_id`，由 `core/events.py:768` 正确附加）驱动。功能未受损，属冗余条件。

- 影响：无可观测故障。属可维护性噪声：`ActionName` 的 3 项死动作会让人误以为功能已接线；`needs_confirm` 会让人误以为后端有该契约。考虑到本项目以「逐一对齐」为契约纪律，这类残留会削弱该纪律的可信度。

- 验证方式：

  ```powershell
  cd D:\codebuddy\sz\game\frontend\src
  Select-String -Pattern "do_personal_action|unlock_focus|issue_secret_decree" -Path . -Recurse
  # 期望：每项仅 api\client.ts 联合类型定义处 1 命中
  Select-String -Pattern "needs_confirm" -Path D:\codebuddy\sz\game -Recurse
  # 期望：仅 EventPanel.tsx 2 处命中（后端 0 处）
  ```

- 建议修复：
  1. 三个死动作二选一：接入 UI（`do_personal_action` 对应「御躬·个人行动」，`PersonalPanel` 已存在且已接线 `choose_imperial_action`，可评估是否本应由前者承担），或从 `ActionName` 中移除并在 `client.ts` 注释中记录「后端保留但前端未接线」。**不建议**保留在联合类型里而不加注释。
  2. 删除 `EventPanel.tsx:41,78` 的 `needs_confirm` 分支，或后端在 `get_pending_break_event`（`core/events.py:753-768`）一并产出 `needs_confirm` 使契约成立。

---

## 端点一致性对拍

### A. 前端调用的端点 → 后端存在性

对拍方法：`frontend/src/renderer/api/client.ts` 的 20 个方法逐条提取 `this.request(path)` 的字面量，与 `backend/server.py` 的 20 个 `@app.<method>` 装饰器（`server.py:312-778`）逐一对齐。

| 前端调用 | 后端存在? | 字段一致? | 备注 |
|----------|-----------|-----------|------|
| `GET /health` (`client.ts:253`) | ✅ `server.py:312` | ✅ `{ok, backend, has_state}` 与 `health()` 返回类型一致 | `/health` 无 `_require_auth`（有意，供探活）。建议前端校验 `backend` 字段以排除端口被他人占用（见 F-7(d)） |
| `POST /api/new_game` (`:257`) | ✅ `server.py:317` | ✅ 请求 `{difficulty}`；响应 `{state}` | — |
| `POST /api/advance` (`:264`) | ✅ `server.py:326` | ✅ `{events, log, report, state}` 四项齐全 | 非幂等，已在 `NON_IDEMPOTENT_PATHS` |
| `POST /api/action` (`:268`) | ✅ `server.py:348` | ✅ `{action, params}` → `{message, state}` | 非幂等，已列 |
| `POST /api/resolve_event` (`:275`) | ✅ `server.py:365` | ✅ `{title, choice}`；响应 `{message, state}` | 非幂等，已列。`ResolveReq` 同时兼容 `event` 字段（`server.py:269-272`），前端只用 `title`，由 `_find_frontend_event` 反查 |
| `POST /api/save` (`:282`) | ✅ `server.py:385` | ✅ `{slot}` → `{ok, slot}` | 非幂等，已列。`SettingsPanel:50` 传 `slot=0`（自动存档），`save_slots` 遍历 1..5 不列 0，故槽 0 在 UI 不可见 —— 后端行为正确，属设计 |
| `POST /api/load` (`:289`) | ✅ `server.py:398` | ✅ `{slot}` → `{state}` | **未列入 `NON_IDEMPOTENT_PATHS`**（见下「B-4」） |
| `GET /api/save_slots` (`:296`) | ✅ `server.py:407` | ⚠️ `{slots}` 存在，但元素含 `corrupt` 标记而前端不消费 | 见 F-8(a) |
| `POST /api/conclude` (`:300`) | ✅ `server.py:551` | ✅ `{eval, ai_eval}` | **未列入非幂等**（见 B-4） |
| `GET /api/readouts` (`:304`) | ✅ `server.py:415` | ⚠️ `granary`/`defense_lines` 后端异常时可为 `{}`，TS 声明为必填 | 见 F-8(d) |
| `GET /api/meter` (`:309`) | ✅ `server.py:499` | ✅ `{rows, total, token_log}` | — |
| `POST /api/meter/reset` (`:313`) | ✅ `server.py:529` | ✅ `{ok}` | **未列入非幂等**（重置是幂等的，可接受） |
| `POST /api/decree/polish` (`:321`) | ✅ `server.py:608` | ✅ `{raw_intent, draft_id}`；响应 `{draft, state?}` | 前缀 `/api/decree/` 已覆盖，非幂等不重试 |
| `POST /api/decree/draft` (`:331`) | ✅ `server.py:657` | ✅ `{draft}` → `{draft_id, state?}` | **前端零调用**（见 F-8(b)） |
| `POST /api/decree/discard` (`:341`) | ✅ `server.py:674` | ✅ `{draft_id}` → `{ok, title?, state?}` | — |
| `POST /api/monthly_report` (`:349`) | ✅ `server.py:692` | ✅ `{report}` | — |
| `POST /api/council_review` (`:353`) | ✅ `server.py:564` | ⚠️ 后端可返回 `unavailable: true`（`server.py:600-603`），TS `CouncilReviewResult` 未声明该字段 | 消费点 `DecreePanel.tsx:226` 只取 `res.review`，值为兜底文案，功能安全；类型应补 `unavailable?: boolean` |
| `GET /api/ai_config` (`:360`) | ✅ `server.py:718` | ⚠️ 后端**不返回** `has_key`/`available`/`message`，TS 声明为可选 | 见 F-8(c)：`SettingsPanel:296` 因此恒显示「（未配置）」 |
| `POST /api/ai_config` (`:369`) | ✅ `server.py:778` | ✅ `{ok, available, message?, has_key, base_url, model}` 与 `setAiConfig` 返回类型一致 | — |
| `POST /api/fetch_models` (`:377`) | ✅ `server.py:741` | ✅ `{ok, models, error?}` | — |

**后端存在而前端未使用的端点：`POST /api/decree/draft`（1 个，见 F-8(b)）。**
**前端调用而后端不存在的端点：0 个。**
**HTTP 方法全部匹配（`GET`×6、`POST`×14）。**

### B. `ActionName` 与 `/api/action` 处理分支逐一对齐

对拍方法：`client.ts:138-161` 的 23 项联合类型 vs `backend/client.py:162-213` 的 `handlers` 字典键。

| 结果 | 数量 | 明细 |
|------|------|------|
| 完全匹配（前后端均有） | 20 | `issue_decree` `issue_secret_decree` `issue_edict_from_review` `reject_edict_draft` `issue_free_decree` `merge_drafts` `do_personal_action` `choose_imperial_action` `audience_dialogue` `allocate_payraise` `envoy_diplomacy` `start_tech_research` `approve_invention` `reject_invention` `unlock_focus` `start_focus` `cancel_focus` `approve_ai_action` `reject_ai_action` `issue_kouyu` `propose_inner_transfer` `confirm_inner_transfer` `cancel_inner_transfer` |
| 前端声明但后端无 | **0** | — |
| 后端有但前端未声明 | **0** | — |
| 前端声明但**无调用点** | 3 | `do_personal_action` `unlock_focus` `issue_secret_decree`（见 F-14(a)） |

> 上表「完全匹配」计数含 3 项无调用点者，故集合层面为 23 项全匹配。**README:100「与前端 `ActionName` 逐一对齐」的声明经核实成立。**

**参数名逐条对拍**（前端调用点 vs 后端 lambda 取值）：

| 动作 | 前端参数（调用点） | 后端取值（`backend/client.py`） | 一致? |
|------|--------------------|----------------------------------|-------|
| `issue_decree` | `{text, title, minister, is_secret}`（`DecreePanel.tsx:103-108`） | `p.get("is_direct")` → `issue_decree(s, decree=params, direct=...)`，正文读 `decree.get("desc") or decree.get("text")`（`core/commands_decree.py:357`） | ✅ 已由 P1 契约对齐修复覆盖（`commands_decree.py:298-300` 注释即记录此对齐） |
| `issue_free_decree` | `{parse_result:{category,exec_mode,title,params}, minister, is_secret}`（`DecreePanel.tsx:116-125,189-193`） | `p.get("parse_result")`, `p.get("minister")`, `p.get("is_secret")` | ✅ |
| `issue_kouyu` | `{title, body, effects}`（`DecreePanel.tsx:157-161`） | `p`（整个 params 作为 draft，读 `draft.get("effects")`） | ✅ |
| `issue_edict_from_review` | `{draft_id, decision}` | `p.get("draft_id")`, `p.get("decision","approve")` | ✅ |
| `reject_edict_draft` | `{draft_id}` | `p.get("draft_id")` | ✅ |
| `merge_drafts` | `{draft_ids}` | `p.get("draft_ids",[])` | ✅ |
| `choose_imperial_action` | `{location, mode, action, target, prepared}`（`PersonalPanel.tsx:157-163`） | `p.get("location")`,`mode`,`action`,`target`,`prepared` | ✅ |
| `audience_dialogue` | `{minister, text}`（`AudienceView.tsx:243`） | `p.get("minister")`, `p.get("text")` | ✅ |
| `propose_inner_transfer` | `{amount}`（`AudienceView.tsx:199`） | `p.get("amount",0)` | ✅ |
| `confirm/cancel_inner_transfer` | `{}`（`AudienceView.tsx:134`） | 无参 | ✅ |
| `envoy_diplomacy` | `{target, speech}`（`DiplomacyPanel.tsx:87-90`） | `p.get("target")`, `p.get("speech")` | ✅ |
| `allocate_payraise` | `{amount}`（`AccountingPanel.tsx:80`） | `p.get("amount",0)` | ✅ |
| `start_tech_research` | `{node_id, silver, fund, source, signoff?}`（`TechPanel.tsx:142`） | `params.get("node_id")`,`silver`,`fund`,`source`,`signoff`（`client.py:248-256`） | ✅ |
| `approve_invention` | `{index, fund?, signoff?}`（`TechPanel.tsx:170`） | `params.get("index",0)`,`fund`,`signoff` | ✅ |
| `reject_invention` | `{index}`（`TechPanel.tsx:190`） | `params.get("index",0)` | ✅ |
| `start_focus` | `{branch, node_key}`（`FocusPanel.tsx:49`） | `params.get("branch")`,`node_key` | ✅ |
| `cancel_focus` | `{}`（`FocusPanel.tsx:67`） | 无参 | ✅ |
| `approve/reject_ai_action` | `{action_id}`（`PendingActionsPanel.tsx:65-68`） | `p.get("action_id","")` | ✅ |

**参数名不一致：0 条。**

### C. 非幂等重试清单（R2-15 复核）

R2-15 声称「现仅对『请求未送达』重试，非幂等端点不自动重试」。实测**部分成立，存在残留**。

```ts
// frontend/src/renderer/api/client.ts:168-174
const NON_IDEMPOTENT_PATHS = [
  "/api/advance", "/api/action", "/api/resolve_event", "/api/save", "/api/decree/"
];
// client.ts:215-222
const retryable =
  res.status >= 500 && res.status < 600 && attempt < MAX_ATTEMPTS &&
  !NON_IDEMPOTENT_PATHS.some((p) => path.startsWith(p));
```

| 检查项 | 结论 |
|--------|------|
| 5xx 是否重试非幂等端点 | ✅ 不重试。`advance`/`action`/`resolve_event`/`save`/`decree/*` 全覆盖（`/api/decree/` 前缀覆盖 polish/draft/discard） |
| 超时/网络失败是否重试 | ✅ **完全不重试** —— `AbortError` 与 `TypeError` 分支（`:229-236`）直接 `throw`，不经重试循环。R2-15 声称的「请求未送达才重试」在前端**实际未实现任何该类重试**（比声称更保守，无重复副作用风险） |
| 残留：`POST /api/load` 未列入 | ⚠️ **未列入**。5xx 时最多重试 3 次。`load` 只把后端磁盘档读回内存（`server.py:402-404`），本身幂等，重试无副作用 —— 但 `api_load` 之后紧跟 `_state_to_dict`，若首次 5xx 发生在「已替换 `_state` 之后」，重试会再替换一次（结果相同）。**判为可接受，建议仍加入清单以保持语义清晰** |
| 残留：`POST /api/new_game` 未列入 | ⚠️ **未列入**。5xx 重试会**重建一局全新游戏**（丢弃当前进度）。`MainMenu`/`StartPanel` 的调用点都在开局前，实际影响窗口窄；但若在游戏中途被调用（当前无此调用点），重复开局即为真实数据丢失。**建议加入清单** |
| 残留：`POST /api/conclude` 未列入 | ⚠️ **未列入**。`conclude` 会调用 AI（`commands.py:635-643`），5xx 重试意味着**重复消耗 token**。副作用非破坏性但真实。建议加入 |
| 残留：`POST /api/meter/reset` 未列入 | ✅ 可接受（重置幂等） |

**结论：R2-15 的核心目标（advance/action/save/decree 不因 5xx 重复副作用）已达成。残留缺陷为 `new_game` / `conclude` / `load` 三个端点未列入清单，其中 `new_game` 的重复开局属真实数据风险。** 建议将清单扩为 `["/api/advance","/api/action","/api/resolve_event","/api/save","/api/decree/","/api/new_game","/api/conclude"]`。

### D. R2-4 / R2-18 修复状态复核

| 历史项 | 源码状态 | 实际生效状态 | 判定 |
|--------|----------|--------------|------|
| R2-4 `sandbox:false → true` | ✅ `src/main/index.ts:185` 为 `true` | ❌ `out/main/index.js:122` 仍为 `false` | **未生效**（回归）→ F-1 |
| R2-4 `shell.openExternal` 任意协议 → 仅 http(s) | ✅ `src/main/index.ts:153-168` 已实现白名单 | ❌ `out/main/index.js:127` 仍为裸 `shell.openExternal(url)` | **未生效**（回归）→ F-1 |
| R2-4 补 `will-navigate` 白名单 | ✅ `src/main/index.ts:197-203` 已实现 | ❌ `out/main/index.js` 内 0 命中 | **未生效**（回归）→ F-1 |
| R2-15 非幂等端点不自动重试 | ✅ 清单 5 条已覆盖核心端点 | ✅ 生效 | **已修**（残留 3 端点，见 C） |
| R2-18 `frontend/` → `game/frontend/` 路径校正 | ✅ `src/main/index.ts:27` 为 `../../../../game/backend_config.json`；`scripts/build-topo.ts:14` 为 `../../../game/assets/map/web` | ⚠️ 产物 `out/main/index.js:15` 含**第三个**候选 `../../../backend_config.json`（源码无此项），属旧版残留 | **已修**（产物待重编译） |

---

## 附：本次实际执行的验证命令

```powershell
# 环境探测（确认 Node 缺失，typecheck 无法执行）
cd D:\codebuddy\sz\game\frontend
npm --version                                    # → CommandNotFoundException
node --version                                   # → CommandNotFoundException
Test-Path "D:\codebuddy\sz\tools\nodejs\node.exe"  # → False
Get-ChildItem D:\ -Filter "node.exe" -Recurse -Depth 5 -Force -ErrorAction SilentlyContinue
Get-ChildItem C:\ -Filter "node.exe" -Recurse -Depth 6 -Force -ErrorAction SilentlyContinue
where.exe node ; reg query "HKLM\SOFTWARE\Node.js"

# 构建产物 vs 源码（F-1 核心证据）
Get-Item src\main\index.ts, src\preload\index.ts, out\main\index.js, out\preload\index.js |
  Select-Object @{n='File';e={$_.FullName.Replace('D:\codebuddy\sz\game\frontend\','')}}, LastWriteTime, Length
Select-String -Path out\main\index.js -Pattern "sandbox|openExternal|will-navigate|isSafeExternalUrl"
Select-String -Path src\main\index.ts -Pattern "sandbox:|isSafeExternalUrl|will-navigate|openExternalIfSafe"
Test-Path out\renderer                                        # → False

# 资产清点（F-2 / F-9）
Get-ChildItem public\map -File | Select-Object Name, @{n='KB';e={[math]::Round($_.Length/1KB,1)}}
Get-ChildItem public -Recurse -File | Group-Object { $_.Directory.Name } | Select Name, Count

# 纯函数 / 契约实证（Python，脚本落在 _scratch，未触碰 game/ 源文件）
cd D:\codebuddy\sz\game
$py = "D:\codebuddy\.audit-venv\Scripts\python.exe"
& $py "D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\verify_format.py"
& $py "D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\verify_effect_keys.py"
& $py "D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\verify_effect_gap.py"
& $py "D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\verify_judge_effects.py"
& $py "D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\verify_judge_magnitude.py"
& $py "D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\verify_judge_vs_events.py"
& $py "D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\verify_tier_sign.py"
& $py "D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\verify_judge_final.py"

# 端点 / ActionName 对拍（静态检索）
Select-String -Path D:\codebuddy\sz\game\backend\server.py -Pattern "@app\.(get|post|put|delete)" -AllMatches
Select-String -Path D:\codebuddy\sz\game\frontend\src\renderer -Pattern "getApiClient\(\)\.\w+" -Recurse
Select-String -Path D:\codebuddy\sz\game\frontend\src -Pattern "saveDecreeDraft|councilReview|needs_confirm|ErrorBoundary|Authorization|Bearer|simplify|view\.json" -Recurse
```

脚本清单（全部位于 `D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\`）：

| 脚本 | 用途 | 支撑条目 |
|------|------|----------|
| `verify_format.py` | 移译 `wan`/`humanizeCoin`/`seasonName` 用真实数量级对拍 | 结论：数值格式化**无缺陷**（否决了一条误报） |
| `verify_effect_keys.py` | `EFFECT_NAME` vs 后端 `TIER_VALUE_BASE` | F-11 |
| `verify_effect_gap.py` | 静默跳过语义 + 覆盖度 | F-11 |
| `verify_judge_effects.py` | `judgeEffects` 初版语义探针 | F-4（含一条被后续否决的 `unrest` 假设） |
| `verify_judge_magnitude.py` | 量级盲 + 档位符号 | F-4 |
| `verify_judge_vs_events.py` | 用 98 条真实 effects 字面量批量对拍 | F-4 |
| `verify_tier_sign.py` | 前缀式档位符号逐条对拍 | F-4(a) |
| `verify_judge_final.py` | **定稿**：用 `_resolve_effects` 求真实数值，分类归因 | F-4（36% / 7 + 23） |

---

## 说明与局限

1. **未能执行 `npm run typecheck` / `npm run build`** —— 本机无 Node.js 运行时（证据见「typecheck 结果」段）。所有类型层面判断均为静态阅读，已在相应条目注明。E-1 项（`out/` 产物陈旧）本身即是构建产物与源码不一致的实证，间接说明该工程的构建流程未被执行过一轮。
2. **未修改 `game/` 下任何源文件**，符合只读要求。全部临时脚本置于 `D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\`。
3. 报告中有一条假设被后续实证**自行否决**：曾据 `registries.py:80` 怀疑 `unrest`/`flood_risk`/`epidemic_risk` 会作为「越高越糟」的维度被 `judgeEffects` 判成增益。实测后端 effect 白名单（`content.data.TIER_VALUE_BASE`，18 维）**不含这三个键**，故该推理不成立，已在 F-4 中改以量级盲与档位符号两条真实缺陷替代。
4. `verify_format.py` 的结论是**未发现缺陷**（`humanizeCoin` 的万/千分位边界、负数、`null` 处理均正确，`effectDeltaSign` 对 `"大减"`/`"停"`/`"无"` 的减义识别正确）—— 一并记录，以免后续复查重复投入。
5. 以下项经检查**未发现问题**，不作为条目报告：`contextIsolation: true` 与 `nodeIntegration: false`（源码与产物一致，均正确）；preload 暴露面（仅 4 个具名方法，无 `ipcRenderer` 整体透出、无通用 invoke 桥，参数无自由度）；`shell: false` 的 spawn（无命令注入面）；`SettingsPanel.applyFontFamily`（用 `textContent` 而非 `innerHTML`，且 `FONT_TABLE` 白名单化，无 CSS 注入）；`MainMenu` 的 interval+timeout 双层清理（`:41-56`，正确）；`AdvancePanel` 的 Space 键监听清理（`:29-40`，正确）；`HoverDetailCapsule` 的定时器卸载清理（`TopBar.tsx:155-157`，正确）；`MapView`/`MapController.destroy` 的 `map.remove()`（`:295-298`，正确）；`SavePanel` 以 `slots[sel].slot` 而非数组下标作为槽号（`doSave:59`/`doLoad:83`，正确）；`humanizeCoin(null)` 的 `?? 0` 兜底（`format.ts:24`，正确）；`EventPanel` 的 `resolveEvent(title, idx)` 契约（后端 `_find_frontend_event` 已按 title 反查完整事件，`server.py:239-256`，正确）；`/api/advance` 返回的 events 为完整事件对象（`server.py:344` → `OverlayStack` → `EventPanel`，链路正确）；`is_secret` 密谕通道（`issue_decree` → `issue_secret_decree`，`core/commands_decree.py:303-306`，正确）；`res.slots[sel].slot` 与后端 `save_slots` 遍历 1..5 的对应关系（正确）。
