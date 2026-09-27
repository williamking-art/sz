# I · 启动 / 打包 / 实跑链路审查

- 审查对象：`D:\codebuddy\sz`（仓库）、`D:\codebuddy\sz\game`（游戏本体）
- 审查员席位：I（发布工程 + 端到端冒烟）
- 日期：2026-09-18
- 解释器：`D:\codebuddy\.audit-venv\Scripts\python.exe`（Python 3.12，已装 requirements.txt + fastapi + uvicorn + shapely 2.1.2 + Pillow 12.3.0）
- 临时产物：`D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\`（未改动 `game/` 下任何源文件）
- **限制声明**：本机 PATH 上无 `python`、无 `node`/`npm`，`songzuo_server`（Rust）不在本次范围；PyInstaller **未安装**，故 `SongZuo.spec` 只能做静态审查 + 分项实证，**无法实际产出 exe**。所有无法实跑的项目已显式标 `[疑似]`。

---

## 结论速览

| 编号 | 严重度 | 一句话 | 文件:行 | 证据类型 |
|---|---|---|---|---|
| I-1 | **P0** | 干净机器上启动器必然失败：`game\.venv` 从不生成，回落裸 `python`（PATH 无），9009 → 走 `:DepsFail` → **Electron 永不启动**，且报错文案误导为"依赖安装失败" | `start.bat:15,32-33,36-37,40-45,68-73` | [确认] 实测复刻 |
| I-2 | **P1** | 未配 AI 时 `/api/advance` 抛 `AIRuntimeError` 无人接管 → HTTP 500 裸 `Internal Server Error`，无错误码；与 `server.py` 自身 docstring「无 key 时叙事自动走本地降级」矛盾 | `backend/server.py:326-345`、`core/commands.py:258-259` | [确认] 实跑 |
| I-3 | **P1** | `npm run dist` 无法独立完成分发：`extraResources.from: ../dist/SongZuo` 依赖手工先跑 PyInstaller，而 `dist` 脚本里没有该步骤，也无前置校验 | `frontend/package.json:15`、`frontend/electron-builder.yml:14-16` | [确认] 代码 + `game/dist` 实测不存在 |
| I-4 | **P1** | 舆图重建失败只 `pause` 后**继续启动 Electron**；`build_map_basemap` 逐文件原地覆写无 temp+rename，失败留下"新旧混合"的 `assets/map/web` | `start.bat:52-66`、`build_map_basemap.py:100-103` | [确认] 代码 + 实跑 |
| I-5 | P2 | `PYTHONIOENCODING=utf-8` 但无 `chcp 65001`：CP936 控制台下 Python 中文输出/报错全乱码，恰好毁掉 `:RebuildFail` 让玩家自查的那条路径 | `start.bat:24,50-54,58-63` | [确认] 字节实测 |
| I-6 | P2 | 遥测只接线 1/3：`record_ai_call` 有调用方，`record_monthly` / `record_event` 全库零调用 → `monthly` / `events` 两张表永远为空 | `telemetry/store.py:98,113`、`ai/client.py:225-234` | [确认] 全库检索 |
| I-7 | P2 | `audio/manifest.py` 完全无消费方（`AUDIO_SLOTS` / `audio_class_for` / `register_slot` 仅在本文件出现），8 槽位 `file` 全空；前端设置面板"大晟府雅乐音量/静音"仅本地 state，**死 UI** | `audio/manifest.py:51-69`、`SettingsPanel.tsx:447-483` | [确认] 实跑 + 代码 |
| I-8 | P2 | `fetch_hillshade.py` 输出到 `game/assets/map/web/tiles/hill/`，前端实际读 `frontend/public/map/tiles/hill/`，且 `build-topo.ts` 明写"不拷贝" → **脚本产物无消费方**，接线断裂 | `fetch_hillshade.py:13-14`、`mapController.ts:92`、`build-topo.ts:52` | [确认] 代码 |
| I-9 | P2 | `content/build_map_geo.py` 强依赖 `assets/map/raw/ne_admin1_ext.json`（23 处），但 `fetch_basemap.py` 从不下载它 → raw 目录**无法由 fetch_* 脚本重建** | `content/geo_admin.py:517+`、`fetch_basemap.py:22-46` | [确认] 代码 |
| I-10 | P2 | 每次启动都重建 ~38MB 却**从未被前端消费**的产物：`prefectures.geojson` / `prefecture_borders.geojson` / `regime_prefectures.geojson`；而 `build_map_basemap` docstring 声称"州/府可单独选中" | `MapView.tsx:99-107`、`build-topo.ts:18-20`、`build_map_basemap.py:15-17` | [确认] 代码 |
| I-11 | P2 | 目录分层与 VCS：`game/.coverage`（审计期新生成）落进本体且 `.gitignore` 未覆盖；`game/ui/__pycache__/*.pyc` 残留；`layers/_src/` 内开发脚本在 game/ 本体；**仓库无 `.git`** → 无法 `git status`/`check-ignore`/`bisect`，README 引用的提交号无法复核 | `.gitignore`、`game/.coverage`、`game/ui/__pycache__/` | [确认] 实测 |

**统计：P0 = 1，P1 = 3，P2 = 7，合计 11 条。**

### 已核实「真的修好 / 无问题」的项（不重复报告）

| 项 | 结论 | 证据 |
|---|---|---|
| R2-3 未配 token 全放行 | **真修好**：设 `SONGZUO_SERVER_TOKEN` 后，**回环来源**不携带/携带错 token 均 401；未设 token 时回环放行 | 8089 实例实测，见冒烟表 |
| R2-17 状态判空移入锁内 | **真修好**：`/api/advance` `/api/action` `/api/save` `/api/readouts` `/api/meter` 均 `with _lock:` 内首行 `_require_state()` | `backend/server.py:334-335, 356-357, 392-393, 429-430, 512-513` |
| 隐藏数值脱敏 | **真生效**：`new_game` 快照 `loyalty`/`corruption`/`minister_estate` 全为档位词，无任何数值；全文无 `secret_loyalty` | 实跑，见 §端到端冒烟 |
| `start.bat` 批处理中文乱码 | **不存在**：文件 6128 字节，**非 ASCII 字节数 = 0**，注释/echo 全英文 | 字节统计实测 |
| `if errorlevel 1` / `if not errorlevel 1` 混用 | **用法正确**：`where node` 后用 `if not errorlevel 1`（成功语义），其余 `if errorlevel 1` 均为失败语义 | `start.bat:37,43,52,54,79,120,125,150,159,181` |
| `enabledelayedexpansion` 未展开陷阱 | **不存在**：脚本声明了 delayedexpansion 但**从未使用 `!VAR!`**；`start.bat:127-130` 括号块内 `%NODE_DIR%` 在块解析前已赋值，无陷阱 | `start.bat:12,127-130` |
| 舆图构建链可重复性 | **离线可跑且字节级幂等**：raw 数据齐备时不联网即可完成；两次构建 12 个文件 SHA 全同 | 实跑，见 §构建链 |
| `content/build_map_geo` 幂等声明 | **真幂等**：同目录二次运行 5 个文件全 `unchanged`，mtime 全部未变 | 实跑 |
| 重复启动后端 | **不会静默起第二个**：8080 被占用时第二次启动 uvicorn 报 `[Errno 10048]` 并以退出码 3 结束 | 实跑 |

---

## 端到端冒烟结果

### A. 主实例 `python -m backend.server`（127.0.0.1:8080，cwd=`game/`，无 `SONGZUO_SERVER_TOKEN`，无 `ai_config.json`）

启动方式（后台作业 `pwsh-7`）：
```powershell
$env:PYTHONPATH=''; $env:PYTHONIOENCODING='utf-8'
& "D:\codebuddy\.audit-venv\Scripts\python.exe" -m backend.server
```
启动日志 `server-8080.log`：`Uvicorn running on http://127.0.0.1:8080`，PID 8112。

| 端点/步骤 | 命令 | 结果 | 状态码 | 是否符合预期 |
|---|---|---|---|---|
| `/health` | `GET /health` | `{"ok":true,"backend":"python-reference","has_state":false}` | 200 | ✅ |
| `/api/new_game` | `POST /api/new_game {"difficulty":"normal"}` | 115,735 字节完整快照 | 200 | ✅ |
| `/api/readouts` | `GET /api/readouts` | army/arsenal/finance/flow/granary/briefing/ministers/defense_lines 齐全 | 200 | ✅ |
| `/api/save_slots` | `GET /api/save_slots` | `{"slots":[{slot:1..5,empty:true}]}` | 200 | ✅ |
| `/api/meter` | `GET /api/meter` | 8 行分桶表 + total + token_log | 200 | ✅ |
| `/api/ai_config` (GET) | `GET /api/ai_config` | `{"configured":false,"api_key_masked":"",...}` | 200 | ✅ 无 `ai_config.json` → `configured:false` |
| `/api/monthly_report` | `POST /api/monthly_report` | `{"report":"（本月初报缺漏，暂由有司补录：朝局平稳，诸司奉行如仪。）"}` | 200 | ✅ 走**显式标注**的本地兜底模板，非伪造 AI 结果（`commands.py:263-269`） |
| `/api/council_review` | `POST {"topic":...}` | Pydantic 校验：`Field required: draft_id` | 422 | ✅ schema 校验生效 |
| `/api/decree/draft` | `POST {"instruction":...}` | `{"detail":"诏草不可为空"}` | 400 | ✅ 业务校验生效 |
| `/api/advance` | `POST /api/advance` | 裸 `Internal Server Error`（服务端 `AIRuntimeError` 未接管） | **500** | ❌ **缺陷 I-2** |
| 幂等复跑 | 同上全量重跑 | 结果一致 | — | ✅ |

### B. 未设 token 时的鉴权行为（8080，无 token 配置）

回环来源（127.0.0.1）调用 `/api/*` **全部放行**（200）——符合 R2-3 设计（"无 token 时仅放行回环来源"）。

### C. 设 token 实例 `SONGZUO_SERVER_TOKEN=secret-tok`（127.0.0.1:8089，后台作业 `pwsh-9`）

| 端点 | 不带 token | 带正确 token | 带错误 token | 符合预期 |
|---|---|---|---|---|
| `/health` | 200 | 200 | 200 | ✅ 健康检查免鉴权（设计） |
| `/api/new_game` | **401** `令符不合，未获授权。` | 200 | — | ✅ |
| `/api/readouts` | **401** | 200 | **401** | ✅ |
| `/api/save_slots` | **401** | 200 | — | ✅ |
| `/api/meter` | **401** | 200 | — | ✅ |
| `/api/ai_config`(GET) | **401** | — | — | ✅ 补鉴权生效 |
| `/api/advance` | **401** | — | — | ✅ |
| `/api/council_review` | **401** | — | — | ✅ |
| `/api/fetch_models` | **401** | — | — | ✅ |
| `/api/fetch_models` `base_url=file:///etc/passwd` | — | **400** `Base URL 必须是含主机名的 http(s) 地址` | — | ✅ 协议校验生效 |
| `/api/ai_config`(POST) `base_url=file:///etc/passwd` | — | **400** 同上 | — | ✅ 落盘前协议校验生效 |

> 非回环来源无法从本机伪造（`request.client.host` 取 TCP 对端），该分支为**代码确认**：`backend/server.py:97-102`。

### D. 脱敏抽查（`/api/new_game` 快照，实跑）

| 字段 | 实测样本 | 判定 |
|---|---|---|
| `loyalty` | `韩忠彦:"怨望" 曾布:"怨望" 蔡京:"怨望" 李清臣:"怨望"` | ✅ 全档位词 |
| `corruption` | `韩忠彦:"尚廉" 曾布:"尚廉" 蔡京:"贪墨"` | ✅ 全档位词 |
| `minister_estate` | `蔡京:"殷实" 童贯:"小康" 王黼:"清贫"` | ✅ 全档位词 |
| 数值型隐藏量 | 三个 block 中数值条目数 = **0** | ✅ |
| `secret_loyalty` | `"secret_loyalty" in json.dumps(snapshot)` → **False** | ✅ 已剔除 |

### E. 端口占用 / 重复实例

| 步骤 | 结果 | 符合预期 |
|---|---|---|
| 8080 已监听时再次 `python -m backend.server` | `ERROR: [Errno 10048] ... 只允许使用一次` + 退出码 **3** | ✅ 不静默起第二实例（`start.bat:181` 会 `pause`） |

### F. 进程清理

| 项 | 状态 |
|---|---|
| 我启动的 PID 8112（8080）、PID 18652（8089） | **已 `Stop-Process -Force` 精确关闭** |
| 8080 / 8089 端口 | **均已释放**（`Get-NetTCPConnection` 复检为空） |
| 其它审计员的后端进程 | **未触碰**（仅按 PID 8112/18652 精确关闭） |
| 后台作业 `pwsh-7` / `pwsh-9` | 均已 settled |

**✅ 已清理。**

---

## 详细条目

### I-1 [P0] 干净机器上启动器必然失败：venv 不存在 + 裸 python 回落 + 误导性错误分支

- 位置：`start.bat:15`、`start.bat:32-33`、`start.bat:36-37`、`start.bat:40-45`、`start.bat:68-73`
- 证据：**[确认]** 代码 + 本机实测复刻

```bat
15: set "VENV_PY=%~dp0game\.venv\Scripts\python.exe"
32: set "PY_CMD=python"
33: if exist "%VENV_PY%" set "PY_CMD=%VENV_PY%"
36: %PY_CMD% -c "import fastapi, uvicorn, requests, rich, shapely" >nul 2>nul
37: if errorlevel 1 goto InstallDeps
```
```bat
40: :InstallDeps
42: %PY_CMD% -m pip install -r "%~dp0game\requirements.txt"
43: if errorlevel 1 goto DepsFail
...
68: :DepsFail
70: echo [Songzuo] Dependency install failed (network or proxy?). Install manually:
72: pause
73: goto Finished
```

实测（`_dev_tools\_scratch\audit-2026\repro_start_python.bat`，忠实复刻 12-45 + 68-73 行）：
```
[repro] VENV_PY=D:\codebuddy\sz\game\.venv\Scripts\python.exe
[repro] venv MISSING - PY_CMD falls back to bare python
[repro] PY_CMD=python
[repro] self-check errorlevel=9009
[repro] self-check FAIL - goto InstallDeps
[repro] pip errorlevel=9009
[repro] pip FAIL - goto DepsFail
[repro] then goto Finished - Electron NEVER starts
```
`cmd /c where python` → `INFO: Could not find files for the given pattern(s).`
`Get-ChildItem D:\codebuddy\sz\tools` → **不存在**；`Test-Path game\.venv\Scripts\python.exe` → **False**。

补充：`.venv` 在 `.gitignore:26` 被忽略，且全库检索 `.venv` 只命中 `start.bat:15,83,87`（**无任何脚本会创建它**）。即 venv 对该仓库而言永远不存在，本机 PATH 又无 `python`，故启动链条在**第一跳**就断。

- 影响：任何"未预装 Python 且未手工建 venv"的机器（正是 README 面向的玩家机）双击 `start.bat` → 停在 `pause` → 按任意键 → `:Finished` 退出。**地图重建、Node 探测、Electron 全部不会执行**。更糟的是提示写的是"依赖安装失败（网络或代理？）"，把玩家引向错误方向（真因是根本没有解释器）。
- 验证方式：
  ```powershell
  cmd /c "D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\repro_start_python.bat"
  cmd /c "where python"
  Test-Path "D:\codebuddy\sz\game\.venv\Scripts\python.exe"
  ```
- 建议修复：`start.bat` 增加解释器解析阶梯（按序：`game\.venv` → `py -3` 启动器 → `where python` → 便携 Python 自动下载，与 Node 分支同构），全部失败时给出**准确**文案（"未检测到 Python 3.10+"）并**中止**而非继续；同时补一个 `setup_venv.bat` / `python -m venv game\.venv` 引导，或在 README 首次运行章节显式给出建 venv 命令。

---

### I-2 [P1] 未配 AI 时 `/api/advance` 返回裸 500，无结构化错误码，且与自身 docstring 矛盾

- 位置：`game/backend/server.py:326-345`、`game/core/commands.py:256-259`
- 证据：**[确认]** 实跑

实测：
```
--- advance: POST /api/advance -> HTTP 500 len=21
body: Internal Server Error
```
服务端 traceback（`server-8080.log`）：
```
File "D:\codebuddy\sz\game\backend\server.py", line 336, in api_advance
    events, log, report, _state = _backend.advance(_state, _get_ai())
File "D:\codebuddy\sz\game\backend\client.py", line 138, in advance
    events, log, report = cmd.advance_and_settle(state, ai_client)
File "D:\codebuddy\sz\game\core\commands.py", line 259, in settle_turn
    raise AIRuntimeError(AI_ERROR_CODES.get("AI_NOT_CONFIGURED", "AI 未接入"))
core.errors.AIRuntimeError: 未接入 AI：请配置 OpenAI 兼容 API（base_url/api_key/model）
```
关键矛盾 —— `backend/server.py` 自己的模块 docstring（第 13-14 行）写：
> `AI 可选：服务端按 ai_config.json 构建 AIClient；无 key 时用禁用客户端，叙事自动走本地降级模板（绝不伪造在线结果）；`

而实际结算路径是 `commands.py:251-252` 定稿的**拒绝式**：
> `全游戏级强制 AI（用户定稿）：AI 缺失/推演失败 → **拒绝式**（抛 AIRuntimeError...）`

两者对"advance 能不能在无 AI 下跑"给出相反承诺，且 `server.py` 未注册 `AIRuntimeError` → HTTP 的异常处理器，导致：
1. 玩家/前端只看到 `Internal Server Error`（21 字节），拿不到 `AI_NOT_CONFIGURED` 这个可编程识别的错误码；
2. 前端无法区分"AI 未配置，请去设置面板填 Key"和"服务端崩了"；
3. 网关/监控会把一次**预期内**的配置缺失记为 5xx 服务端故障。

- 影响：**无 AI 配置时整个游戏无法推进回合**（只能开局、看面板、存档），且失败原因是不可解释的 500。这直接决定"玩家第一次上手能不能玩下去"。同时 5xx 掩盖了它其实是 4xx/503 级别的可预期状态。
- 验证方式：
  ```powershell
  # 确保无 ai_config.json，起后端后：
  Invoke-WebRequest -Uri http://127.0.0.1:8080/api/advance -Method POST -UseBasicParsing
  # 观察 500 + body "Internal Server Error"；服务端日志可见未捕获的 AIRuntimeError
  ```
- 建议修复：在 `backend/server.py` 注册 `@app.exception_handler(AIRuntimeError)`，返回 `503`（或 `409`）+ `{"code":"AI_NOT_CONFIGURED","detail":"..."}`；同步改掉 `server.py:13-14` 与 `commands.py:251-252` 中矛盾的那一半 docstring；Rust 端 `songzuo_server` 需返回同一 code（跨后端契约一致性）。

---

### I-3 [P1] `npm run dist` 无法独立完成分发：extraResources 依赖手工前置的 PyInstaller 产物

- 位置：`game/frontend/package.json:15`、`game/frontend/electron-builder.yml:6-17,25`
- 证据：**[确认]** 代码 + 实测目录缺失

```json
15: "dist": "electron-vite build && electron-builder --win nsis"
```
```yaml
 6: files:
 7:   - out/**
 8:   - package.json
14: extraResources:
15:   - from: ../dist/SongZuo
16:     to: backend
...
25:   icon: ../assets/icon.ico
```
实测：`Test-Path D:\codebuddy\sz\game\dist` → **False**；`Test-Path game\frontend\build` → **False**（`directories.buildResources: build` 指向不存在的目录）；`Test-Path game\assets\icon.ico` → **True**（图标 OK）。

`electron-builder.yml:9-13` 的注释自己承认了这个前置条件：
> `故打包前须先执行一次 PyInstaller（工作目录 game/：pyinstaller SongZuo.spec）。`

但 `package.json` 的 `dist` 脚本没有这一步，仓库里也没有 `build.bat` / CI 把它们串起来。且本环境 `pip list` 无 `pyinstaller`（`import PyInstaller` → `ModuleNotFoundError`），即"跑一次 PyInstaller"本身还需要额外装包。

- 影响：`npm run dist` 在干净检出上**必然失败**（extraResources 源目录不存在，electron-builder 直接报 file not found）。分发流程是隐式知识，只存在于 yml 注释里。另外 `buildResources: build` 不存在时，后续若有人按 electron-builder 惯例往 `build/` 放资源会静默失效。
- 验证方式：
  ```powershell
  Test-Path D:\codebuddy\sz\game\dist            # False
  Select-String -Path D:\codebuddy\sz\game\frontend\package.json -Pattern '"dist"'
  & "D:\codebuddy\.audit-venv\Scripts\python.exe" -c "import PyInstaller"   # ModuleNotFoundError
  ```
- 建议修复：把 `dist` 改成 `pyinstaller ../SongZuo.spec && electron-vite build && electron-builder --win nsis`（或新增 `dist:backend` / `dist:all`），并在脚本开头校验 `../dist/SongZuo/SongZuo.exe` 存在、不存在则 fail-fast；`directories.buildResources` 改为实际存在的目录或删除；README 增补"打包三步"。

---

### I-4 [P1] 舆图重建失败静默继续 + 原地覆写无事务，可能留下新旧混合数据

- 位置：`start.bat:52-66`、`game/build_map_basemap.py:100-103`、`game/content/build_map_geo.py:649-656`
- 证据：**[确认]** 代码 + 实跑

```bat
51: %PY_CMD% build_map_basemap.py
52: if errorlevel 1 goto RebuildFail
53: %PY_CMD% -m content.build_map_geo
54: if errorlevel 1 goto RebuildFail
55: cd /d "%~dp0"
56: goto CheckNode
58: :RebuildFail
60: echo [Songzuo] ERROR: map data rebuild FAILED - the map may show stale data.
64: pause
66: goto CheckNode          <-- 仍然启动 Electron
```
```python
100: def _save_web(name: str, obj) -> None:
101:     with open(os.path.join(WEB, name), "w", encoding="utf-8") as fh:
102:         json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"))
```
`build_map_basemap.main()`（`:400-406`）按 `land → rivers → lakes → circuits → circuit_borders → prefectures → prefecture_borders` **顺序逐个写盘**，中途任一异常（如 shapely 缺失、raw 文件缺失）都不会回滚已写入的前几个文件。

实测失败路径（用 PYTHONPATH 遮蔽 `shapely`）：
```
$env:PYTHONPATH='...\_scratch\audit-2026\noshapely'
& python.exe build_map_basemap.py
Traceback (most recent call last):
  File "D:\codebuddy\sz\game\build_map_basemap.py", line 33, in <module>
    from shapely.geometry import Point, box, mapping, shape
ImportError: No module named shapely (simulated)
LASTEXITCODE=1
```
→ `start.bat:52` 捕获 → `:RebuildFail` → `pause` → `:CheckNode` → 继续启动 Electron。

对比：`content/build_map_geo.py:649-656` 的 `_write_if_changed` 有内容比对（实测真幂等），`build_map_basemap.py` 没有这层保护。

- 影响：
  1. **玩家侧**：地图数据损坏/半成品时，游戏照常起来，玩家只会看到错乱舆图，唯一的线索是一行英文警告 + 一次 `pause`；
  2. **仓库侧**：若构建失败发生在 `build_circuits()` 之后，`circuits.geojson` 已是新一代，而 `prefectures.geojson` 仍是旧一代——两级行政区划几何**不再自洽**（而 `build_map_basemap` 的文档恰恰强调两级"天然自洽、无缝隙、无重叠"）；
  3. 因为 `assets/map/web/*.geojson` 是入库产物，一次失败的本地构建会**污染待提交内容**，且无 VCS 可回退（见 I-11）。

- 验证方式：见上（遮蔽 shapely 的 PYTHONPATH 命令），或直接看 `:RebuildFail` 的 `goto CheckNode`。
- 建议修复：
  - 构建改为"先写临时目录 → 全部成功后原子替换 / 失败则不落盘"（与 `content/build_map_geo` 的 `_write_if_changed` 对齐，补 compare-then-write）；
  - `start.bat` 的重建失败应视为**致命**：要么 `goto Finished` 中止，要么用 `choice` 让玩家显式选择"忽略并继续（可能显示陈旧舆图）"；
  - 若舆图数据已入库且是权威产物，更应默认**跳过重建**，改为"仅在显式传参/数据缺失时重建"，避免每次启动 20~30s 写 64MB。

---

### I-5 [P2] `PYTHONIOENCODING=utf-8` + CP936 控制台 → 重建输出与报错全乱码

- 位置：`start.bat:24`（设置编码）、`start.bat:50-54`（执行重建）、`start.bat:58-63`（让玩家手工复现）
- 证据：**[确认]** 字节实测

`start.bat` 全文 **无 `chcp`**（6128 字节，非 ASCII = 0，故 bat 自身无乱码）。本机控制台：
```
> chcp
Active code page: 936
```
实测同一句 `print('[basemap] 地图数据重建完成')` 的**原始字节**：
```
PYTHONIOENCODING=utf-8 : b'[basemap] \xe5\x9c\xb0\xe5\x9b\xbe\xe6\x95\xb0\xe6\x8d\xae\xe9\x87\x8d\xe5\xbb\xba\xe5\xae\x8c\xe6\x88\x90'
   as utf-8 -> [basemap] 地图数据重建完成
   as gbk   -> [basemap] 鍦板浘鏁版嵁閲嶅缓瀹屾垚     <-- 控制台按 936 解码 = 玩家看到的样子
默认(不设 PYTHONIOENCODING) : b'[basemap] \xb5\xd8\xcd\xbc\xca\xfd\xbe\xdd\xd6\xd8\xbd\xa8\xcd\xea\xb3\xc9'
   as gbk   -> [basemap] 地图数据重建完成            <-- 正确
```
即 `start.bat:24` 强制 UTF-8 输出，而控制台是 936，**中文必然乱码**；`[Songzuo] Rebuilding map data ...` 之后由 Python 打印的 `[basemap] xxx features=N`、以及任何 traceback 中文文案（如 `[build_map_geo] 校验未通过，拒绝生成：`）都会花屏。

- 影响：不致命，但**恰好摧毁 `:RebuildFail` 引导的自查路径**——脚本让玩家"从 game\ 目录重跑这两条命令看错误"，而玩家看到的正是乱码。对一个有 `:RebuildFail` 分支的启动器来说这是真实缺陷，不是纯风格问题。
- 验证方式：
  ```powershell
  cmd /c chcp
  cmd /c "set PYTHONIOENCODING=utf-8&& D:\codebuddy\.audit-venv\Scripts\python.exe build_map_basemap.py"
  # 观察中文输出为 "鍦板浘..." 形态
  ```
- 建议修复：在 `start.bat` 顶部加 `chcp 65001 >nul`（或去掉 `set PYTHONIOENCODING=utf-8`，让 Python 走控制台 CP）；若保留 `chcp 65001`，需同时确认 `%PY_CMD%` 与 `npm` 输出均不受影响，并注意 Win7/旧 conhost 的字体缺字问题（可退化为 `chcp 936` + 不设 PYTHONIOENCODING）。

---

### I-6 [P2] 遥测只接线 1/3：`monthly` / `events` 两张表永远为空

- 位置：`game/telemetry/store.py:81-126`、`game/ai/client.py:225-234`
- 证据：**[确认]** 全库检索 + 代码

全库（`game/**/*.py`，排除 `node_modules`/`__pycache__`）检索结果：
```
[get_store]      -> ['ai\\client.py', 'telemetry\\store.py', 'telemetry\\__init__.py']
[telemetry]      -> ['ai\\client.py', 'telemetry\\store.py', 'telemetry\\__init__.py']
[record_monthly] -> ['telemetry\\store.py']                      <-- 只有定义，无调用方
[record_event]   -> ['core\\settlement_steps.py', 'memory\\memory_graph.py', 'telemetry\\store.py']
                     ^^ 前两处是 GameState.memory.record_event / MemoryGraph.record_event，与 TelemetryStore 无关
```
`ai/client.py:225-234` 是唯一真实接线点：
```python
225: if os.environ.get("SONGZUO_TELEMETRY") == "1":
227:     from telemetry.store import get_store
228:     st = get_store()
230:     st.record_ai_call(method=key, prompt_tokens=_p, ...)
```
`store.py:98 record_monthly` 与 `:113 record_event` 的 `INSERT INTO monthly/events` 永远不会被执行；`store.py:154 monthly_series()` 因此恒返回 `[]`，`summary()["monthly_records"]/["event_records"]` 恒为 0。

- 影响：A2 遥测能力的 2/3 是死代码。任何基于"月度快照序列/事件流水"的平衡分析、回放、复盘（`monthly_series` 的设计意图）拿不到数据。默认关闭（`SONGZUO_TELEMETRY=1` 才开）掩盖了这一点——即使开发者开了开关，也只有 AI 调用被记录。
- 验证方式：
  ```powershell
  $env:SONGZUO_TELEMETRY='1'
  # 跑一局并 advance（需先配 AI）后：
  & python.exe -c "import sys;sys.path.insert(0,r'D:\codebuddy\sz\game');from telemetry.store import TelemetryStore;print(TelemetryStore().summary())"
  # monthly_records / event_records 恒为 0
  ```
- 建议修复：在 `core/commands.py::settle_turn`（月度）与事件派发点补 `get_store().record_monthly(turn, metrics)` / `record_event(turn, name, payload)`，并补一条最小校验用例；或明确把这两个 API 标为 `@unused` 并在 README 的"可选件接线情况"里登记为**未接线**（当前 README:82 未提及遥测接线状态）。

---

### I-7 [P2] `audio/manifest.py` 完全无消费方；前端音量/静音是死 UI

- 位置：`game/audio/manifest.py:51-69`、`game/frontend/src/renderer/panels/SettingsPanel.tsx:447-483`
- 证据：**[确认]** 实跑 + 代码

实跑输出：
```
slots = 8
  bgm_court      category=bgm   file='' loop=True  ready=False
  bgm_battle     category=bgm   file='' loop=True  ready=False
  sfx_disaster   category=sfx   file='' loop=False ready=False
  sfx_omen       category=sfx   file='' loop=False ready=False
  sfx_decree     category=sfx   file='' loop=False ready=False
  sfx_click      category=sfx   file='' loop=False ready=False
  voice_minister category=voice file='' loop=False ready=False
  voice_narrator category=voice file='' loop=False ready=False
all file empty: True
```
全库检索（`.py/.ts/.tsx`，排除 node_modules）：
```
[AUDIO_SLOTS]    -> ['audio\\manifest.py']     # 仅本文件
[audio_class_for]-> ['audio\\manifest.py']     # 仅本文件
[register_slot]  -> ['audio\\manifest.py']     # 仅本文件
[from audio]     -> []
[import audio]   -> []
```
→ 没有任何模块导入 `audio`，`EVENT_AUDIO_CLASS` 这个自称"单一权威源"的映射表**没有任何读者**。

前端（`SettingsPanel.tsx:448-483`）：
```tsx
448: function AudioSettingsView() {
449:   const [muted, setMuted] = useState(false);
450:   const [vol, setVol] = useState(75);
...
459:  <input type="range" ... onChange={(e) => { setVol(Number(e.target.value)); setMuted(false); }} />
472:  <label>... <input type="checkbox" checked={muted} onChange={(e) => setMuted(e.target.checked)} />
479:    <span>静音（关闭全盘背景古乐与音效）</span>
```
全组件无 `<audio>`、无 `Audio()`、无 IPC、无 `localStorage`、无任何副作用——对比同文件 `UiScaleSettingsView`（`:485-514`）确实写了 `localStorage.setItem` 并注入 `<style>`。`assets/audio/` 只有 `.gitkeep`。

- 影响：玩家在设置面板调整"大晟府雅乐音量"、勾选"静音"，**重启后全部丢失且对游戏没有任何影响**——一个明确向玩家撒谎的控件。README:82 已如实承认"播放未接线"，但**未说明 manifest 本身也没有消费方**，容易让后续开发者误以为"接上播放器即可用"。
- 验证方式：
  ```powershell
  & python.exe -c "import sys;sys.path.insert(0,r'D:\codebuddy\sz\game');from audio.manifest import AUDIO_SLOTS;print(len(AUDIO_SLOTS), all(not s.file for s in AUDIO_SLOTS))"
  # 8 True
  Select-String -Path D:\codebuddy\sz\game -Include *.py,*.ts,*.tsx -Pattern "AUDIO_SLOTS|audio_class_for" -Recurse
  ```
- 建议修复：要么接线（`register_slot` 有实际调用方 + 前端 `AudioSettingsView` 落 `localStorage` 并驱动 `HTMLAudioElement`），要么把该面板整块隐藏/标注"未启用"，并把 manifest 标记为 `# UNWIRED`；README 补一句"manifest 目前无消费方"。

---

### I-8 [P2] `fetch_hillshade.py` 输出目录与前端实际读取目录不一致，产物无消费方

- 位置：`game/fetch_hillshade.py:13-14`、`game/frontend/src/renderer/map/mapController.ts:89-92`、`game/frontend/scripts/build-topo.ts:52`
- 证据：**[确认]** 代码

```python
# fetch_hillshade.py
12: BASE = os.path.dirname(os.path.abspath(__file__))
13: WEB = os.path.join(BASE, "assets", "map", "web")
14: OUT = os.path.join(WEB, "tiles", "hill")          # -> game/assets/map/web/tiles/hill/
```
```ts
// mapController.ts
89: // 地形晕渲（山脉立体感）：ESRI World Hillshade，构建期平移至 map/tiles/hill
92:   tiles: [`${MAP_BASE_URL}/tiles/hill/{z}/{x}/{y}.png`],   // MAP_BASE_URL = public/map
```
```ts
// build-topo.ts
52: // 4) 地形瓦片已直接常驻 frontend/public/map/tiles/，无需从后端重复拷贝
```
实测：`game/assets/map/web/` 下**没有 `tiles/` 目录**；瓦片实际在 `game/frontend/public/map/tiles/hill/{5,6,7}/{x}/{y}.png`（数千个 PNG）。`.gitignore:50-51` 忽略 `game/assets/map/web/tiles/` 与 `assets/map/web/tiles/`，这两条规则现在指向**不存在的路径**；而真正入库的 `frontend/public/map/tiles/**` **没有任何 ignore 规则**。

- 影响：重跑 `fetch_hillshade.py`（README:19 列为舆图抓取入口之一）会把几百 MB 瓦片写到一个**无人读取**的目录：既不会被 `build-topo.ts` 平移，也不会在 `git status` 中提示（被 ignore），徒增困惑与磁盘占用。地形晕渲的实际数据来源不可追溯（谁在何时把瓦片放到 `frontend/public` 的，脚本链里没有体现）。
- 验证方式：
  ```powershell
  Test-Path D:\codebuddy\sz\game\assets\map\web\tiles      # False
  Get-ChildItem D:\codebuddy\sz\game\frontend\public\map\tiles\hill -Directory   # 5,6,7
  ```
- 建议修复：把 `fetch_hillshade.py` 的 `OUT` 改为 `game/frontend/public/map/tiles/hill`（或让 `build-topo.ts` 真正执行拷贝并删掉那句"无需重复拷贝"注释）；同步清理 `.gitignore:50-51` 的失效规则，并为 `frontend/public/map/tiles/**` 明确入库/忽略策略。

---

### I-9 [P2] `ne_admin1_ext.json` 无法由 `fetch_*.py` 再生，raw 数据链有缺口

- 位置：`game/content/geo_admin.py:517,528,...`（23 处）、`game/fetch_basemap.py:22-46`
- 证据：**[确认]** 代码

`content/build_map_geo.py::regime_part_features`（`:192`）与 `_regime_sub_union`（`:541+`）都要读 `raw_dir/ext["file"]`：
```python
# content/geo_admin.py
517: "union_external": {"file": "ne_admin1_ext.json", "target_regime": "吐蕃_藏南"},
528: "union_external": {"file": "ne_admin1_ext.json", ...}
... （共 23 处，全部指向 ne_admin1_ext.json）
```
但 `fetch_basemap.py` 的下载清单里**没有它**：
```python
22: FILES = { "ne_50m_land.geojson": [...], "ne_50m_rivers...": [...], "ne_50m_lakes...": [...],
30:           "ne_10m_rivers_lake_centerlines.geojson": [...], "ne_10m_lakes.geojson": [...],
35:           "datav_100000_full.json": [...] }
40: PROVINCES = [ ... 34 个省级 adcode ... ]
```
实测 `assets/map/raw/ne_admin1_ext.json`（6,837,676 字节）**已入库**，所以当前构建能跑通（见 §构建链）；`.gitignore:188` 只忽略 `ne_10m_admin_1.geojson`（另一个文件），并留有注释"仅入库裁剪后的 kr_jp 子集"——说明这个 6.8MB 文件是**手工裁剪产物，没有生成脚本**。

- 影响：README:19 把 `fetch_basemap.py` 列为"舆图底图抓取"入口，但仅靠它**无法从零重建 `assets/map/raw/`**——`content/build_map_geo.py` 会以 `FileNotFoundError` 崩在 `open(prov_path/ne_admin1_ext.json)`。任何需要重建 raw 的场景（换数据源、清缓存、新环境）都会卡在这里，且失败信息只是一句 `FileNotFoundError`，没有指向"该文件需手工生成"。
- 验证方式：
  ```powershell
  Select-String -Path D:\codebuddy\sz\game\fetch_basemap.py -Pattern "ne_admin1_ext"    # 无匹配
  Select-String -Path D:\codebuddy\sz\game\content\geo_admin.py -Pattern "ne_admin1_ext" # 23 处
  ```
- 建议修复：`fetch_basemap.py` 增加 `ne_admin1_ext.json` 的下载或裁剪步骤（含来源 URL 与裁剪规则），或在 `content/build_map_geo.py` 中把该文件缺失转为**带指引的错误信息**（"请先运行 … 生成 ne_admin1_ext.json"）；同时在 README 的目录说明里标注该文件是手工产物。

---

### I-10 [P2] 每次启动重建 ~38MB 却从未被前端消费的舆图产物；docstring 与实现不符

- 位置：`game/content/build_map_basemap.py:15-17,337-397`、`game/frontend/src/renderer/map/MapView.tsx:99-107`、`game/frontend/scripts/build-topo.ts:18-20`
- 证据：**[确认]** 代码 + 实跑产物

前端**实际加载**的全部舆图数据（`MapView.tsx:99-107`）：
```ts
 99: const [land, lakes, rivers, cities, topo] = await Promise.all([
100:   loadGeo("land"), loadGeo("lakes"), loadGeo("rivers"),
101:   loadGeo("cities"), loadTopo()
102: ]);
104: const circuits = feature(topo, topo.objects.circuits) ...
105: const regimes  = feature(topo, topo.objects.regimes) ...
106: const borders  = feature(topo, topo.objects.circuit_borders) ...
107: const regime_borders_fc = feature(topo, topo.objects.regime_borders) ...
```
`build-topo.ts:18-20` 的清单与之一致：
```ts
18: const TOPO_LAYERS = ["circuits", "regimes", "circuit_borders", "regime_borders"];
20: const COPY_LAYERS = ["land", "rivers", "lakes", "cities"];
```
→ `prefectures` / `prefecture_borders` / `regime_prefectures` **两级都不在**。全 renderer 检索 `prefecture`：`src/renderer/map/**` **零匹配**（面板里的 `state.prefectures` 是数值字典，不是几何）。

而 `build_map_basemap.py` docstring 写：
```
15:     prefectures.geojson       州/府级实界：同一归属再按治所切一刀，州/府独立成块
16:                               （可单独选中、可由圣旨改名；并集恒等于所在路）
```
实测产物（每次 `start.bat` 都会重建）：
```
prefectures.geojson          19,196,237 字节
prefecture_borders.geojson   19,158,292 字节
regime_prefectures.geojson    2,575,606 字节
```
`frontend/public/map/` 下这三个文件**都不存在**。

- 影响：
  1. **文档-实现不符**（README 规范 #3）：docstring/README 承诺的"州/府可单独选中、可改名"在前端舆图上不可达；实际只有路级。
  2. **启动开销**：`start.bat` 每次启动都跑这两个脚本（`start.bat:51-54`），实测 `build_map_basemap` 17.6~28.3s + `build_map_geo` 84.2~113.0s（本机冷/热），其中约 40MB 的写盘是纯浪费。玩家每次开局前多等 1.5~2.5 分钟。
  3. **入库与分发体积**：这 38MB 在 `game/assets/map/web/` 入库，并被 `SongZuo.spec:13`（`datas` 含整个 `assets`）打进每份 PyInstaller 分发物。
- 验证方式：
  ```powershell
  Get-ChildItem D:\codebuddy\sz\game\frontend\public\map            # 无 prefectures.geojson
  Select-String -Path D:\codebuddy\sz\game\frontend\src\renderer\map\*.ts* -Pattern "prefecture"   # 无匹配
  Get-ChildItem D:\codebuddy\sz\game\assets\map\web -Filter "prefecture*"
  ```
- 建议修复：二选一——(a) 让前端真正消费（`TOPO_LAYERS` 加 `prefectures`/`regime_prefectures`，MapView 增加选择/改名交互），兑现 docstring 承诺；(b) 若不打算实现，把这两个产出降级为**可选/仅校验**（加 `--with-prefectures`），从 `start.bat` 默认路径移除，并把 `prefectures*.geojson` 从入库产物与 `SongZuo.spec` 的 `datas` 中排除，同步修 README:15-17 的描述。

---

### I-11 [P2] 目录分层纪律与版本控制元数据：审计产物落进 `game/`、`ui/` 残留、无 `.git`

- 位置：`game/.coverage`、`game/ui/__pycache__/`、`game/content/ministers/layers/_src/`、`.gitignore`、仓库根（无 `.git`）
- 证据：**[确认]** 实测

**(a) `game/.coverage` 落进游戏本体**（README:171「专家团/工具产出的临时文件默认落 `_dev_tools/_scratch/`，不污染 `game/` 本体」）：
```
Name                          Length  LastWriteTime
D:\codebuddy\sz\game\.coverage 53248  2026/9/18 20:51:34    <-- 本次审计期间由 pytest-cov 生成
D:\codebuddy\sz\game\.pytest_cache  (目录)
```
`.gitignore` 覆盖了 `.pytest_cache/`（:24）但**没有** `.coverage`（实测静态核对：`NOT-CVD .coverage`）。`game/pytest.ini` 的 testpaths 指向 `_dev_tools/game-dev/tests`，但 pytest 的 rootdir/cov 输出落在调用者 cwd —— 从 `game/` 跑测试就会污染本体。

**(b) `game/ui/` 未真正移除**（README:127「Tk 界面与 Web 舆图桥均已删除（`ui/` 包**整体移除**）」、README:223「连带 `game/ui/` 包」）：
```
D:\codebuddy\sz\game\ui\__pycache__\map_web.cpython-312.pyc   35578
D:\codebuddy\sz\game\ui\__pycache__\__init__.cpython-312.pyc    122
```
无 `.py` 源文件，只剩 `__pycache__`。且 `SongZuo.spec:17` 仍然 `(os.path.join(_ROOT, 'ui'), 'ui')` —— **把这两个过期 .pyc 打进每份分发物**。

**(c) `game/assets/map/web/` 内仍有已删"独立预览链"的产物**（README:222-223 声称 `preview_map.py` / `map_web_main.py` / `ui/map_web.py` 及预览页已删除）：
```
index.html            9741   2026/9/8   <-- 预览页面（内嵌 CSS 注释仍引用已删除的 ui/theme.py）
map_app.js           36897   2026/9/18 14:26
maplibre-gl.js      803145
maplibre-gl.css      65534
```
全库检索无任何代码引用 `assets/map/web/index.html`；`map_app.js` 仅在 `state.ts:4`、`layers.ts:1`、`mapController.ts:6` 的**注释**里被当作参考提到。这 ~890KB 被 `SongZuo.spec:13` 打进分发物。`index.html` 的 CSS 注释写着"色彩权威与 `ui/theme.py` 一致"——**引用了已删除的资源**（README 规范 #3 要求文档字符串与代码一致）。

**(d) 开发脚本/原始素材留在 `game/` 本体**（未被 `.gitignore` 覆盖）：
```
game/content/ministers/layers/_src/_gen2.py          (PIL 合成脚本)
game/content/ministers/layers/_src/_headcut.py
game/content/ministers/layers/_src/_ly2.py
game/content/ministers/layers/_src/_verify_layers.py
game/content/ministers/layers/_src/_i2i.py / _bodyclean.py
game/content/ministers/layers/_lay2.py
+ ~30MB 的 _base_*.png / _pose_*.png 源图
```
`.gitignore` 只忽略了 `content/ministers/portraits/_composed/`（:191），没有覆盖 `layers/_src/`。这些是**开发期素材与脚本**，按 README:171 应在 `_dev_tools/`。

**(e) 无 `.git`，README 引用的提交号无法复核**：
```
Test-Path D:\codebuddy\sz\.git   -> False
```
仓库根只有 `.gitattributes` / `.gitignore` / `start.bat`。README:58-59 引用迁移历史（"原先误置于 `game/_scratch/` 的 30 个脚本已迁至 `_dev_tools/_scratch/game-audit/`"），README 其他处引用提交号 `（旧提交·2026-09-27 历史重写后失效）`。

- 影响：
  1. **本次审查最实质的工程风险**：没有 `.git` 意味着无法 `git status` 判断哪些改动是本次审计引入的、无法 `git check-ignore` 验证 `.gitignore` 规则、无法 `diff`/`bisect` 定位回归。I-4 里"半成品污染入库产物"之所以危险，正是因为没有回退手段。README 引用的提交号**无法复核**，历史结论只能凭文档自证。
  2. `game/.coverage` 是**本次审计期间（20:51）新生成**的，证明"审计产物污染 game/ 本体"是**正在发生的、可复现的**问题，不是历史遗留。
  3. `.gitignore` 中多条规则已失效（`game/assets/map/web/tiles/`、`assets/map/web/tiles/` 指向不存在路径；`game/SongZuo/`、`game/_scratch/` 同理），而真正需要规则的 `.coverage`、`frontend/public/map/tiles/`、`content/ministers/layers/_src/` 没有规则——说明规则集长期未随目录演进同步。
- 验证方式：
  ```powershell
  Get-Item D:\codebuddy\sz\game\.coverage
  Get-ChildItem D:\codebuddy\sz\game\ui -Recurse -Force
  Test-Path D:\codebuddy\sz\.git
  Select-String -Path D:\codebuddy\sz\.gitignore -Pattern "coverage|layers/_src|public/map/tiles"
  ```
- 建议修复：
  - `.gitignore` 增补 `.coverage`、`htmlcov/`、`game/content/ministers/layers/_src/`（若确为开发素材）并清理失效规则；
  - 删除 `game/ui/`（连同 `SongZuo.spec:17` 的 `ui` datas 条目）与 `game/assets/map/web/{index.html,map_app.js,maplibre-gl.js,maplibre-gl.css}`，使实际状态与 README:127/223 一致；
  - 把 `_src/` 开发脚本迁往 `_dev_tools/`，原始图层素材若需随包请移到 `assets/` 下并明确声明；
  - **恢复 `.git`（或至少提供可追溯的版本快照）**，并在 README 中把引用的提交号替换成可对外核验的标识；审计/测试流程统一在 `_dev_tools/_scratch/` 下运行（`pytest --cov-report=… -o cache_dir=…`）以免再次污染 `game/`。

---

## 附：本次实际执行的验证命令清单

```powershell
# ---- 环境事实 ----
Get-ChildItem D:\codebuddy\sz -Force
Get-ChildItem D:\codebuddy\sz\game -Force
Test-Path D:\codebuddy\sz\game\.venv\Scripts\python.exe          # False
Test-Path D:\codebuddy\sz\tools                                   # False
Get-Command python / node / npm                                   # 全部 NOT FOUND
cmd /c "where python" ; cmd /c "where node"                       # 均无
Test-Path D:\codebuddy\sz\.git                                    # False
cmd /c chcp                                                       # Active code page: 936

# ---- start.bat 干净机器路径复刻（I-1）----
cmd /c "D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\repro_start_python.bat"
# -> venv MISSING / errorlevel=9009 / DepsFail / Electron NEVER starts

# ---- 编码实证（I-5）----
cmd /c "set PYTHONIOENCODING=utf-8&& D:\codebuddy\.audit-venv\Scripts\python.exe tmp_cjk.py > cjk_utf8.bin"
cmd /c "D:\codebuddy\.audit-venv\Scripts\python.exe tmp_cjk.py > cjk_default.bin"

# ---- 后端冒烟 A（主实例，8080）----
$env:PYTHONPATH=''; $env:PYTHONIOENCODING='utf-8'
& "D:\codebuddy\.audit-venv\Scripts\python.exe" -m backend.server      # cwd=game, 后台
& "D:\codebuddy\.audit-venv\Scripts\python.exe" smoke_i.py http://127.0.0.1:8080

# ---- 后端冒烟 B（token 实例，8089）----
$env:SONGZUO_SERVER_TOKEN='secret-tok'; $env:SONGZUO_SERVER_PORT='8089'
& "D:\codebuddy\.audit-venv\Scripts\python.exe" -m backend.server      # 后台
& "D:\codebuddy\.audit-venv\Scripts\python.exe" smoke_i_auth.py

# ---- 重复实例 / 端口占用 ----
$env:SONGZUO_SERVER_PORT='8080'; & python.exe -m backend.server        # exit=3, Errno 10048

# ---- 舆图构建链（输出重定向到 scratch，未动 game/assets）----
& python.exe probe_map_build.py        # run1 + run2 -> 12 文件 SHA 全同（幂等）
& python.exe probe_idem_wiring.py      # 二次同目录 -> 5 文件 unchanged, mtime 未变

# ---- shapely 缺失路径（I-4）----
$env:PYTHONPATH='...\_scratch\audit-2026\noshapely'
& python.exe build_map_basemap.py      # ImportError @ line 33, LASTEXITCODE=1

# ---- 接线核查 ----
& python.exe -c "from audio.manifest import AUDIO_SLOTS; print(len(AUDIO_SLOTS), all(not s.file for s in AUDIO_SLOTS))"
# 全库检索 AUDIO_SLOTS / audio_class_for / register_slot / get_store / record_monthly / record_event

# ---- 清理（仅按 PID 精确关闭，未触碰他人进程）----
Get-NetTCPConnection -LocalPort 8080 -State Listen   # PID 8112  (我)
Get-NetTCPConnection -LocalPort 8089 -State Listen   # PID 18652 (我)
Stop-Process -Id 8112 -Force ; Stop-Process -Id 18652 -Force
Get-NetTCPConnection -LocalPort 8080,8089 -State Listen   # 均为空 —— 已清理
```

### 本次产生的证据文件（均在 `_dev_tools\_scratch\audit-2026\`）

| 文件 | 内容 |
|---|---|
| `repro_start_python.bat` | 忠实复刻 `start.bat:12-45,68-73` 的干净机器路径 |
| `smoke_i.py` / `smoke_i.out.json` | 主实例 11 端点冒烟 + 脱敏抽查 |
| `smoke_i_auth.py` / `smoke_i_auth.out.txt` | token 鉴权矩阵 16 用例 |
| `server-8080.log` / `server-8089-token.log` / `server-8080-dup.log` | 三次后端启动日志（含 `/api/advance` 的 AIRuntimeError traceback、10048 绑定失败） |
| `probe_map_build.py` / `mapbuild.out.txt` | 舆图构建链两次运行 + 逐文件 SHA 幂等比对 |
| `probe_idem_wiring.py` / `idem_wiring.out.txt` | 同目录幂等 mtime 复核 + 骨架件接线核查 |
| `cjk_utf8.bin` / `cjk_default.bin` | 编码实证原始字节 |
| `noshapely/` | 遮蔽 shapely 的 import shim（用于失败路径复现） |
