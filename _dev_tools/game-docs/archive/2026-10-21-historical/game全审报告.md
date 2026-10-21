# game 文件夹全审报告

> 审查范围：`D:\codebuddy\sz\game`（宋祚 Songzuo · 北宋徽宗治国模拟器）  
> 审查方式：模块并行深审（core/engine · ai/memory/backend · frontend · content/tests）＋人工核实关键安全面  
> 静态统计：约 **90 个 test 文件 / 858 个 test 函数**；Python 本体 core 43 模块、ai 12、content 9、backend 2、memory 2  
> 巨型文件基线：`settlement_steps.py` 281KB · `content/data.py` 191KB · `ai/client.py` 161KB · `commands.py` 83KB · `game_state.py` 82KB

---

## 结论摘要

| 维度 | 判断 |
|---|---|
| **总体** | 架构定稿清晰（POP 挂载律 / 双写通道 / M0–M3 对账 / 契约式 AI），测试体量大且部分很硬（`test_pop_identity`、`test_state_applier`、`test_ai_security_config`）。但**守恒与数值通道仍有可实锤的 P0 洞**，前端有运行时必炸与非幂等双发，配置层有明文 API key。 |
| **可运行性** | pytest 可收集（`game/pytest.ini` → `../_dev_tools/game-dev/tests`）；frontend preload 面小、Electron 基线（contextIsolation/sandbox）良好。 |
| **首要动作** | ① 封死 NaN/Inf 进 free_effect；② events 国库效果改走受控通道；③ 修 free_effect 成本腿假扣/灭粮；④ 修 Dock 异步 Hooks；⑤ 修 DecreePanel 失败双发；⑥ 轮换并迁出明文 api_key。 |

---

## P0 · 必须立刻修

### 1. free_effect 数值通道可被 NaN 击穿 → 凭空铸币 / 崩溃
- `core/free_effect.py:106-107` `_resolve_effect_value`：`isinstance(value,(int,float))` **放行 NaN/Inf/bool**。
- `_clamp(nan, cap)` 中 `min(cap, nan)` 返回 `cap`（CPython 比较语义）→ **NaN 变成 +CAP**。`effects:{"treasury":NaN}` 即 +3,000,000（`content/data.py:1881`）。
- Python `json.loads` 默认接受 `NaN`/`Infinity`（`ai/client_utils.py:1241`），**模型输出即可触发**。
- 同因连带：
  - `free_effect.py:250/264` `int(cost)` 对 NaN 抛未捕获 `ValueError`；
  - `ai/client.py:1940-1941` `duration: NaN` → `nan>0` 为 False → **duration=0（永久制度）**；
  - `duration: Infinity` → `int(inf)` 抛 `OverflowError` 穿透 `_postprocess`（`client.py:1169` 无 try）。
- 测试盲区：`test_free_effect` 无 NaN/Inf/bool 用例（`test_numeric.py` 已防 NaN，此处漏）。

**改法**：`math.isfinite` + 显式拒绝 `bool`；`json.loads(..., parse_constant=...)` 拒非常量；duration 强制有限正整数。

### 2. events.py 事件效果裸改国库，铸/毁币且绕开双通道
- `core/events.py:573-575` `state.change_treasury(effects["treasury"])` **无对手方**。
- 数据里大量 `"treasury": 200000 / -1000000 / -10000000`（`events.py:20-22,31-36,92`）。
- `change_treasury` 仅 `max(0,…)` 截断（`game_state.py:901-903`），**正向即凭空造币**。
- 违反定稿约束 1（POP 挂载）与约束 3（受控写通道仅 `state_applier` / `free_effect`）——`events.apply_event_choice` 实为**第三条写通道**。
- 测试：`test_events_a6.py` 存在，但**无事件 ΔM_ALL==0 断言**（本可抓住却未抓）。

### 3. free_effect 成本腿：假扣账 / 灭粮
| 问题 | 位置 | 现象 |
|---|---|---|
| 假扣国帑 | `free_effect.py:234-238` + `68-70` | `cost.treasury` 走 `_apply_money_delta`，民间池空时 `if not pools: return` **不改 treasury**，日志却记「耗国帑」→ 成本逃逸 |
| 灭粮 | `free_effect.py:239-243` + `93-101` | `change_granary(-cv)` 已出仓，`_grant_grain` 粮池空时直接 `return` → **粮无端消失** |

### 4. M3 双计：银行资本与准备金
- `core/game_state.py:1065-1069` `establish_bank` 把 `moved` 同时记入 `bank.reserve`（进 M_ALL/M2）并 `capital += moved/WON`。
- `core/money.py:273-279` M3 = M2 + `bank_capital_as_guan` → **设行瞬间 M3 虚增 `moved`**。
- 另：`m3` 计入 `jiaozi.reserve` 而 M_ALL 刻意不计（`money.py:30-31`）——口径分裂。

### 5. 铸钱 / 粮分发截断无尾差 + 铸钱未登记
- `settlement_steps.py:1680-1685` `_settle_mint`：`int(_net*0.5*size/total)` **无末位吃尾差**，Σ入账 < `_net`；且从 `resources.stock` 铸钱**未 `register_flow(external)`**（对比 `:1211,2663` 有登记）→ `audit_step` 残差恒正。
- `settlement_steps.py:2495-2499` 太仓→兵/官僚粮分发同样 `int(...)` 截断，`given` 已出仓但 Σ摊派 < given（`_distribute_pop_wealth:1504-1525` 已修尾差，此处漏）。

### 6. 前端：React Hooks 在异步回调中调用（运行时必炸）
- `Dock.tsx:99`、`Dock.tsx:113` 在 `setInterval` 回调里调用 `useGameStore((s) => s.state)?.turn`。
- Hooks 只能在组件渲染期调用；轮询回执触发时会抛 “Invalid hook call” 或读到错误上下文 →「回合报告/推演未成」弹窗的 turn 守卫失效。

### 7. 前端：非幂等动作失败后自动二次提交（双倍副作用）
- `DecreePanel.tsx:103-125`：`issue_decree` 失败后**无条件 fallback** 再发 `issue_free_decree`。
- `/api/action` 已列入 `NON_IDEMPOTENT_PATHS`（`client.ts:452`），但 catch 后第二次 POST 同样非幂等。首请求若已在服务端 commit 仅响应超时/断连 → **重复下诏**。

### 8. 前端：无 CSP
- `index.html:1-12` 无 `Content-Security-Policy`；`main/index.ts:207-214` 也未注入 CSP。
- 一旦渲染进程注入（MapLibre 标签、后端文案），可连外网 / eval。与 #7 的双发、#10 token 暴露可串联。

---

## P1 · 高优先级

### 安全与配置
| # | 问题 | 证据 |
|---|---|---|
| 9 | **api_key 明文落盘**（本地已有真实 key） | `ai/client.py:526-540` `save_config`、`backend/server.py:168-177` 均明文写 `ai_config.json`。已 gitignore、**未进 git 历史**（已核实），但落盘无权限收紧/加密。接口侧已指纹化（`server.py:1097-1112`）。 |
| 10 | **preload 将 Bearer token 暴露给渲染进程** | `preload/index.ts:6` + `main/index.ts:253`：`getBackendToken` 把 `SONGZUO_SERVER_TOKEN` 明文交给 renderer。渲染层 XSS 即可读走 token 直连远程后端。更稳妥：主进程代理请求。 |
| 11 | **will-navigate 放行任意 `file://`** | `main/index.ts:225-228`：`url.startsWith("file://")` 直接 return，可导航到任意本地文件；结合无 CSP 构成本地文件读取面。应白名单到 `loadFile` 具体路径前缀。 |
| 12 | **`enable_tools="simple"` 权限边界失效** | `ai/client.py:459-468` `_tools_active()` 只处理 `off/on`，**`simple` 落入 auto 分支返回 True**。生产 `dialogue` 挂全量 `_TOOL_SCHEMAS`（9 工具，含 `secret_order/military_dispatch/relief_grant`）。配置写 `simple` **实际给满权**。 |
| 13 | **parse_decree 类别静默改写（非拒绝式）** | `ai/client.py:1594-1597`：非法 `category` **静默改 `free_edict`**；`client.py:1610` `params` 原样透传任意 dict。可把任意文本抬进 free_effect 通道，与 #1 串联即「注入→铸币」。 |
| 14 | **`*_decide` validate 默认填充，违背「拒绝式」自述** | `client.py:2419-2427`（faction）、`2491-2502`（land_local）、`2539-2543`（granary）等：非法档位静默 `小/平实`；`1894-1900` 缺失字段填 `"无"`。垃圾输出被洗成合法契约，掩盖模型故障。 |

### 写状态 / 对账 / 并发
| # | 问题 | 证据 |
|---|---|---|
| 15 | applier `push` 语义错误：覆盖而非追加 | `state_applier.py:701-702`；白名单 OPS 含 push，AI 可误用 |
| 16 | merge 多 `set` 静默取末，冲突无告警 | `state_applier.py:241` |
| 17 | `CHANGE_LOG` 模块级全局，跨局共享 | `state_applier.py:641`，仅截断 5000 条（`:796-797`） |
| 18 | `agent_router` 并发注入，GameState 非线程安全 | `agent_router.py:303-305` 多线程写 `state._xxx_ai` + 读 `state.posture`，无锁 |
| 19 | 月度对账失败被吞 | `settlement.py:556` `except Exception` 不阻断结算 → M0–M3 对账可长期静默失效 |
| 20 | `change_treasury`/`change_granary` 静默截断 | `game_state.py:903,989`：调用方按全额给对手方入账即净造币（events 已实锤） |
| 21 | `assert` 做恒等式，`python -O` 下失效 | `settlement_steps.py:2521-2522,4727-4728` |
| 22 | `money.py:80-85` 自认违规：`minister_estate`/`estate_wealth`/`estate_hoard` 平行账本仍入 ACCOUNTS | 违反 POP 挂载律第 4 条 |
| 23 | `SINK_ACCOUNTS=()` 真实销毁通道未接 | `money.py:88` |

### 前端资源与状态
| # | 问题 | 证据 |
|---|---|---|
| 24 | MapView 资源泄漏 / 卸载竞态 | `MapView.tsx:74-79` 未 `markers.clearAll()`；`:122-126` debounce 未 clear；`loadGeoData` 无 cancelled 标志；StrictMode 双挂载双 MapController |
| 25 | Dock 推演轮询无卸载清理 | `Dock.tsx:89-138`：`setInterval`/`setTimeout(180_000)` 不随卸载清理 |
| 26 | store 选择器无记忆化，全树重渲 | `gameStore.tsx:173-188` `api` 每次新建；`useGameStore` 直接 `selector(ctx)`，任意 `setState` 全 consumer 重渲 |
| 27 | 伪造进度条与伪属性 | `gameStore.tsx:274-279` 进度由字符串 hash 生成；`AudienceView.tsx:149-157` 大臣 reputation 等由名字 seed 伪随机，与后端无关 |
| 28 | 双路 pollRich 竞态 | `Dock.tsx:91` 与 `AdvancePanel.tsx:26` 同时轮询 `/api/advance/round2` |
| 29 | resolveEvent 仅按 title 定位 | `client.ts:711-715`；同名事件/标题改写会 404；事件对象已有 `id`（`EventPanel.tsx:32`）却不用 |
| 30 | memory_graph 多线程同槽写弱保护 | `memory_graph.py:749` 无锁（对比 `dialogue_memory.py:81-87` RLock） |
| 31 | STATE_TOOL_SCHEMAS.update_state 无路径白名单（潜伏） | `client_utils.py:619-658` `path` 自由 string，不对齐 `state_applier.py:29-54` VALID_PATHS。现无消费方，一旦接线即任意写 |
| 32 | 残留 prompt 注入面 | 玩家输入已 `_wrap_untrusted`；但 `state_summary/posture` 直拼 system/user（`client.py:1269,2040,2407`），`minister_memory` 无边界（`:1263-1264`） |
| 33 | 叙事数值守卫覆盖不全 | `narrative_guard.py:22,72-79`：ranges 未含单位（匹/斤/两…）与纯数字**直接放行** |

---

## P2 · 结构 / 死代码 / 可维护性

### 巨型文件必拆（≥300 行函数见下）
| 文件 | 规模 | 建议拆点 |
|---|---|---|
| `core/settlement_steps.py` | **281KB / ~4900 行** | 12 步结算全部内联 → 按 `_settle_granary` / `_settle_finance` / `_ext_econ_phases` / mint 等拆模块 |
| `content/data.py` | **191KB / 2947 行 / ~455 顶层符号** | 按 `ministers/` 先例拆：`constants_econ/military/decree`、`tech.py`、`geo_tables.py`、`imperial.py`、`desensitize.py`、`external.py` |
| `ai/client.py` | **161KB / 2951 行** | God-file，40+ 契约方法内联 validate → 按契约域拆 + 抽 `validators.py` |
| `core/commands.py` | 83KB | 按命令域拆 |
| `core/game_state.py` | 82KB | `__init__` 441 行，抽 builder/defaults |
| `content/geo_admin.py` | 71KB | 地理表拆分 |
| `core/save_load.py` | 46KB | `load_game` **491 行**（`:347-837`）必拆 |
| frontend | AudienceView 883 / DecreePanel 696 / SettingsPanel 564 / gameStore 435+ / client.ts 755 | 组件拆子组件；client 按资源域拆 |

**≥300 行函数**：
- `load_game` 491（`save_load.py:347-837`）
- `GameState.__init__` 441（`game_state.py:435-875`）
- `_settle_granary` 425（`settlement_steps.py:2403-2827`）
- `_settle_finance` 393（`settlement_steps.py:4387-4779`）

200–299 行：`_ext_econ_phases` 251、`_apply_decree_effect` 248、`settle_situations` 218、`_settle_projects` 215、`run_monthly_settlement` 210、`save_game` 208、`_settle_extensions` 201、`_settle_external_economy` 182、`_settle_land_local` 177。

### 死代码 / 未接线
| 项 | 位置 | 建议 |
|---|---|---|
| `core/async_ai.py` 整模块未接线 | `async_ai.py:4` | 文档自认 B7；保留三态标注或接线 |
| `estate_mechanic.invest_decide` 无生产调用 | `estate_mechanic.py:240` | 同上 |
| `_finance_ai` 有生产者无消费者 | `agent_router.py:42-43` | **唤醒即白烧 token** |
| `PENDING_CONTRACTS._reform_ai` 无方法 | `agent_router.py:159-165` | 补齐或删登记 |
| `ai/contract_adapter.py` 全模块无调用 | `:17-24` | 自述待接线 |
| `ai/schemas.py` 仅注册 5/34 契约 | `schemas.py:100-112` | jsonschema 缺失/异常**一律放行**；retry 不复检 |
| `map/simplify.ts` 整模块无调用 | frontend | 可删 |
| `saveDecreeDraft` / `do_personal_action` / `issue_secret_decree` 无调用 | `client.ts:791` 等 | 可删或接线 |
| `mapController` `setLayerData`/`flyToFeature`/`resetView` 无调用 | `:258/271/280` | 同上 |
| `markers.clearAll` 无调用（但 #24 需要它） | `:219` | 接线修泄漏 |
| preload `minimize/maximize/close` 渲染层未用 | preload | 退出走 `window.close()` |
| `@turf/turf`、`tailwind-merge` 零引用 | package.json | 可删依赖 |
| 零引用常量 `DECREE_MAX_BANDWIDTH` 等 | `content/data.py:105-118` | 定义未接线 |
| 死常量 `LAND_TAX_RATE=0.15` | `data.py:189` | 实现只用 `LAND_TAX_RATE_BENEFIT/BASE` |
| `COMMERCE_TAX_RATE_DEFAULT=0.06` 与注释矛盾 | `data.py:393` | 注释写 0.055→0.05 |
| `changping_stock` 初始化 `/12*0.2` 双处魔法数 | `game_state.py:789` + `save_load.py:748` | 单点化 |
| `_cascade_farmer_wealth` 空占位 | `state_applier.py:282-288` | 补规则或删 |
| 60+ 处 `except Exception: pass` | `settlement_steps.py:1264-1310`、`settlement.py:187,200`、`save_load.py:700,702,828`、`briefing.py`×12 | 至少记日志/指标 |

### 内容生成管线冲突
- **双管线互相覆盖**：`layers/_lay2.py:111`（权威 4 步）vs `_src/_gen2.py:23`（旧版，pad 0.015 vs 0.02、渐隐 vs 不透明）及 `_src/_bodyclean.py:40` 可独立跑并覆盖 `body_*.png`。
- **产物入库约 103MB PNG**（`layers/` 74MB + `_src/` 29MB）；`.gitignore` 只忽略 `_composed` → 应 LFS 或出库。

### 其他 P2
| # | 问题 | 证据 |
|---|---|---|
| 34 | Dev 服务器暴露面 | `electron.vite.config.ts:35-38`：`host: "0.0.0.0"` + `allowedHosts: true` |
| 35 | sessionGuard 逻辑硬，但 busy 竞态 | `AudienceView.tsx:354,424,478` finally 无条件 `setBusy(false)`，切换会话后旧请求会解除新会话 busy |
| 36 | `personnel_nominate` 给**所有** yamen backlog+1 | `client_utils.py:1000-1003` 疑似逻辑 bug |
| 37 | `_cached_call` LRU 不随 provider 切换失效 | `client.py:851-877` |
| 38 | `_load_prompt` `name` 未做 `..` 校验 | `client_utils.py:249-259`（现调用方均字面量，低危） |
| 39 | `clerks.py:155` 直写 `pop["clerks"]` 子池 | 须确认与 `officialdom` 不变量①②同步 |

---

## P3 · 风格 / 小问题

- TS `as any`：`OverlayStack.tsx:144,162,186`、`AudienceView.tsx:497,500`、`MinistersPanel.tsx:104,146-148`、`FocusPanel.tsx:42`。
- `as unknown as`：`mapController.ts:169,189,215`、`simplify.ts` 整文件、`TechPanel.tsx:30,113`。
- `GameState` 为 `{[key:string]:unknown}`（`client.ts:4-6`），下游全靠断言。
- XSS 面（低但存在）：`markers.ts:193` `el.innerHTML` 仅拼 class（kind 受限），label 走 `textContent`——当前安全，模式危险。全库无 `dangerouslySetInnerHTML`。
- `SecretDecreePanel.tsx:35` 硬编码「上限 2」。
- `SettingsPanel.tsx:50` 自动存档写槽位 `0`，与 UI 1-based 不一致。
- `markers.ts:229` 重复导出 `TIER`/`Selected` 类型。
- `memory_graph.py:420` f-string 拼 SQL（键来自常量表，当前安全，风格差）。

---

## 测试质量与盲区

### 覆盖好的部分
- `test_pop_identity.py:41-106`：逐步账本 W/G/P + 完整 `_STEPS` 镜像（**结构性风险**：改结算步序会静默漂移）。
- `test_officialdom.py:48-54`：双账 / ΣPOP 守恒。
- `test_ai_security_config.py`：SSRF / 配置事务 / 注入。
- `test_persistence_safety.py`：坏档 / 并发 / `.corrupt`。
- `test_state_applier`（守恒 / 穿底 / 通配）、`test_review_p0_conservation`、`test_save_roundtrip_money`。

### 弱测试
- `test_review_p0_conservation.py:41-57` 断言过松（`pool1<=pool0`、`money1<=money0+1`）。
- `test_regression_2026_08.py` 5 测 6 断言；`test_tuning_fixes.py` 仅区间断言。
- `test_uncovered_modules.py:52,64,120` 大量 `isinstance` / `in (True,False)` 弱断言。
- `test_state_applier.py:5` 脏路径依赖 conftest 兜底。

### 明确盲区（应补）
| 盲区 | 现状 |
|---|---|
| free_effect NaN/Inf/bool/duration 无界 | 无 |
| free_effect cost.granary 灭粮、民间池空假扣账 | 无 |
| 事件 ΔM_ALL==0（events 国库裸写） | 无 |
| `_settle_mint` 尾差 / `register_flow` | 无 |
| 太仓粮分发尾差 | 无 |
| M3 / `bank_capital` 双计 | 无 |
| **`audit_step` / `money_audit` / `cum_residual` 零引用** | 月度对账层完全无测试 |
| `enable_tools=simple` 限制生产工具面 | 仅测枚举可落盘 |
| parse_decree 非法 category 改写 | 无 |
| `*_decide` 静默默认填充 | 仅 happy path |
| applier `push` op、多 `set` 冲突、`CHANGE_LOG` 隔离 | 无 |
| `agent_router.inject_woken_agents` 并发写 | 无 |
| STATE_TOOL_SCHEMAS ↔ VALID_PATHS 对齐 | 无 |
| history role=system 注入 | 无 |
| memory_graph 多线程同槽写 | 无 |
| `content/geo_admin.py`（71KB）、`demography.py`、`codex_text.py`、`legacy_gazette.py`、`build_map_geo.py` | **全部无测试** |
| `ai/client_narrative.py` | 自认盲区（`test_uncovered_modules.py:5`） |

### 可运行性
- `game/pytest.ini:2` `testpaths=../_dev_tools/game-dev/tests`：以 `game/` 为 rootdir 时正确。
- 仓库根无 pytest.ini，从 `D:\codebuddy\sz` 直接跑 `pytest` 不会收集该套件（需 `cd game` 或 `-c game/pytest.ini`）。
- 各测试自带 `../../../game` sys.path + `conftest.py` 统一注入；SAVE_DIR 已重定向 tmp。

---

## 架构符合度（对照 README 定稿约束）

| 约束 | 判定 | 说明 |
|---|---|---|
| 1. 人挂 6 类 POP size | ⚠️ | 主路径 `officialdom.sync_legacy_mirror` 合规；`clerks.py:155` 直写子池待核；events 国库违反钱/粮条款 |
| 2. 钱粮挂 POP wealth/grain 或国库/内帑 | ❌ | events 裸写国库；`minister_estate` 等平行账本；free_effect 成本腿可灭粮/假扣 |
| 3. ΣPOP 守恒 | ⚠️ | 裁汰回流等已修；铸造/粮分发尾差仍净销毁 |
| 4. 禁止平行存量账本 | ❌ | `money.py:80-85` 自认 `minister_estate`/`estate_wealth`/`estate_hoard` 仍入 ACCOUNTS |
| 5. 受控写通道仅 2 条 | ❌ | `events.apply_event_choice` 为第三条；`settlement_steps` 确定性结算直写可接受 |
| M0–M3 月度对账 | ⚠️ | `audit_step` 存在但被 `settlement.py:556` 吞；M3 双计；M_ALL/M3 对 `jiaozi.reserve` 口径分裂 |
| 契约式 AI（拒绝式 validate） | ⚠️ | 多处静默默认填充 + parse_decree 静默改写，与自述不符 |
| officials 并入 POP | ✅ | 主路径合规 |

---

## 建议修复顺序

| 批次 | 内容 | 对应 |
|---|---|---|
| **批次 0 · 数值安全（当天）** | free_effect 封死 NaN/Inf/bool；json.loads 拒非常量；duration 有限正整数 | #1 |
| **批次 0 · 守恒堵洞（当天）** | events 国库改走受控通道 + ΔM_ALL==0 测试；free_effect 成本腿假扣/灭粮 | #2 #3 |
| **批次 1 · 货币口径** | M3 双计；铸钱/粮分发尾差 + `register_flow`；对账失败不可吞；`audit_step` 补测试 | #4 #5 #19 |
| **批次 1 · 前端必炸** | Dock 异步 Hooks；DecreePanel 失败双发改幂等/单次；CSP；token 不进 renderer；will-navigate 白名单 | #6 #7 #8 #10 #11 |
| **批次 2 · 权限边界** | `enable_tools=simple` 真正限工具面；parse_decree/`*_decide` 统一拒绝式；api_key 权限收紧/迁出 | #9 #12 #13 #14 |
| **批次 2 · 写通道** | applier `push` 语义；merge 冲突告警；CHANGE_LOG 实例化；对账 fail-loud | #15–#17 #20 #21 |
| **批次 3 · 结构** | 拆 `settlement_steps` / `data.py` / `ai/client` / `load_game`；清死代码；合并立绘生成管线 | P2 表 |
| **批次 4 · 测试补齐** | 上表盲区逐项；geo_admin/demography 恒等式测试 | 盲区表 |

---

## 与历史全审的关系

本次为对 `sz/game` **当前代码**的独立全审，与仓库根既有的 `宋祚全审报告.md`、`宋祚代码质量全检.md`、`MingSalvageSim_审查报告.md` 互补：
- 历史报告中的公式常量单点化、数值 helper 收敛（`core/numeric.py`）、officials 双账修复，**本次已确认生效**。
- 本次新增硬货集中在：**NaN→铸币链路**、**events 第三写通道**、**free_effect 成本腿**、**M3 双计**、**前端 Hooks/双发/CSP/token**、**simple 工具满权**——这些在历史报告中未以当前形式出现。


---

## 修复状态（2026-09-22 收口）

> 基线：**917 passed**（`cd sz/game && python -m pytest ../_dev_tools/game-dev/tests/ -q`）；`tsc --noEmit` web/node 均干净。

---

## 改进方案落地（2026-09-22 · 合并版批 0–7，基线 929→980 passed）

> 依据 [`改进方案_合并版_2026-09-22.md`](../../../_dev_tools/game-docs/analysis/改进方案_合并版_2026-09-22.md)（明末经验 + 外邦产业链 + 玩家体验三线合并）。

| 批次 | 内容 | 关键改动 | 基线 |
|---|---|---|---|
| **批 0** | Phase F 清理 + 两池守恒 | `agg_res` 零残留；`test_external_two_pool_conservation.py` 24 月双残差恒 0 | 936 |
| **批 1** | 州/路面板 + 财政三值 | 民心/动乱/士绅阻力/到账率/存粮垫 + 可排序表 + 真实进度条 + hover formula | 936 |
| **批 2** | 局势系统 v1 | 开局 3 局势条件 DSL + `new_game` 挂载 + readout 投影 + 面板公开成败/代价 | 940 |
| **批 3** | 月度奏章八章 | `core/monthly_gazette.py` 八章 + 七言联 + ▲▼；GazettePanel 结构化 | 945 |
| **批 4** | 建筑-岗位-就业 | `core/building_jobs.py` + `core/production_chain.py`（宋侧产出链/单通道） | 961 |
| **批 5** | 大臣工具化 | 财政草案→核定→`state_applier`；颁诏 409 守卫；话术 chip | 968 |
| **批 6** | 粮=硬通货 | 外邦本色饷/官仓平粜/本色粮税 + 粮残差公式 + 计价位防双计 | 973 |
| **批 7** | 14 维原料 + 动态价 + 物流 | `core/dynamic_price.py`；宋侧 RAW_DIMS 扩至 15 维 | **980** |

### 已全部落地

| 批次 | 内容 | 关键改动 |
|---|---|---|
| **0** | 数值安全与守恒堵洞 | `free_effect` 封死 NaN/Inf/bool；`json.loads` 拒非常量；duration 有限非负；events 国库走 `_apply_money_delta`；成本腿原子（无池不扣账/不灭粮） |
| **1** | 货币口径与前端必炸 | M3 去 capital 双计；铸钱/粮分发尾差归最大府 + `register_flow`；对账 fail-loud；Dock 异步 Hooks；DecreePanel 防双发；CSP；token 主进程注入；`will-navigate` 白名单 |
| **2** | 权限边界与写通道 | `enable_tools=simple` 限 4 工具；parse_decree/`*_decide` 拒绝式；applier `push` 追加语义；多 `set` 留痕；`reset_change_log()` |
| **3** | 结构拆分 | `data.py`→7 模块；`settlement_steps.py`→9 领域模块；`ai/client.py`→契约 Mixin；`save_load` 工具/军队迁移抽出 |
| **4** | 测试盲区 | `test_money_audit`（6）+ `test_geo_demography`（7）+ schema 对齐测试 |
| **收尾** | P2 残留 | 死代码清理；`personnel_nominate` 单点；dev host 收紧；busy 竞态；MapView/Dock 泄漏；resolveEvent id；`_load_prompt` 路径校验；`_cached_call` provider 键；`changping_stock` 常量化；旧立绘管线废弃头 |

### 模块拆分结果（入口 re-export 兼容，`from content.data import X` / `from core.settlement_steps import X` / `from ai.client import AIClient` 不破坏）

| 原巨型文件 | 拆后 |
|---|---|
| `content/data.py` 191KB | `data.py` 58KB 入口 + `data_constants/external/tech/military/geo_tables/imperial/decree` |
| `core/settlement_steps.py` 283KB | `settlement_steps.py` 14KB 入口 + `common/decree/econ/finance/granary/tech/officialdom/military/imperial` |
| `ai/client.py` 161KB | `client.py` 62KB 核心 + `validators` + `contracts_court/decree/settle/misc` Mixin |

### 新增回归测试（累计 +16）

`test_nan_inf_bool_rejected` · `test_cost_leg_no_false_deduct_no_vanish` · `test_cost_leg_conservation_when_pools_exist` · `test_event_treasury_conservation_no_mint` · `test_m3_no_double_count_bank_capital` · `test_push_appends_not_overwrite` · `test_merge_multi_set_takes_last` · `test_change_log_reset_isolates_games` · `test_enable_tools_simple_limits_tool_surface` · `test_parse_decree_illegal_category_rejected` · `test_decide_rejects_invalid_tier_no_silent_default` · `test_state_tool_schemas_align_with_valid_paths` · `test_money_audit.py`×6 · `test_geo_demography.py`×7

### 代码质量重检（2026-09-22 · 批 0–7 新增代码）

> 对批 0–7 新增/改动代码做静态审查，发现并修复 6 项质量问题。修复后全量 **994 passed** + tsc 干净。

| # | 文件 | 问题 | 修复 |
|---|---|---|---|
| Q1 | `core/building_jobs.py:270` | 死代码：`target = art if ...` 被紧随的 `if art_open > 0` 覆盖 | 删除冗余赋值，改为单一 `target = art if art_open > 0 else mer` |
| Q2 | `core/building_jobs.py:400` | 未用变量 `job_share_keys` | 删除 |
| Q3 | `core/dynamic_price.py:19` | 未用 `import math` | 删除 |
| Q4 | `core/dynamic_price.py:86` | `civil_logistics` 参数 `unit_value` 从未使用 | 从签名移除（测试同步） |
| Q5 | `core/commands_decree.py:313` | `_pending.__len__()` 反模式 | 改为 `len(_pending)` |
| Q6 | `core/production_chain.py` | `__all__` 缺导出 `goods_direct_production_backup` | 补入 |

**审查通过项**（无需修改）：
- 守恒：工资发放/营造回流/物流分账均为成对划转（付费方 −N、承运方 +N），无 burn 路径
- 拒绝式：财政草案走 `state_applier`（验证/守恒/原子写库），失败整批回滚
- 旧档兼容：`setdefault` 幂等；缺 `yields`/`grain_pay`/`monthly_gazette` 键不抛异常
- POP 挂载律：新增模块只写 POP wealth/grain 或 `resources`，无平行账本
- 金属≠钱：`RAW_DIMS_14` 含金属四但无自动折算 treasury 路径
- 计价位：粮 valued 仅展示，不并入 M_ALL

### 拆分时踩坑（记录）

1. 跨模块互调漏 import → AST 扫出统一补
2. import 误插进多行括号 → 清理脚本
3. PowerShell `Set-Content -NoNewline` 把数组拼成一行（`data_constants.py` 被压扁）→ **AST 从 git 原版按 172 导出名重建**
4. 测试 monkeypatch 打在 facade 上 → 调用时从 facade 取符号，不绑死领域模块全局
5. `_slot_path` 必须留在 `save_load.py`（测试 patch `SAVE_DIR`）


---
