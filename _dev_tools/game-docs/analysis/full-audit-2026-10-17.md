# 《宋祚》全项目审计报告（2026-10-17）

> 审计人：DSH Lead + 4 个并行专项审计员（core / ai-admin / frontend / repo）
> 基线：`D:\codebuddy\sz`，分支 `main`，HEAD `1c9ff50c80`（比 `origin/main` 领先 13 个提交）
> 方法：全量 pytest、tsc 双配置、vitest、HEAD 干净导出冒烟、静态扫描（295 个 `game/**/*.py`、约 9.5 万行）、真实 `commands.new_game()` + `run_monthly_settlement()` 探针、逐 API grep 接线核对
> 性质：**只审不改**。本轮未修改任何产品代码；仅新增本报告与 `_scratch/audit-20261017/` 下的探针/日志。
> 判定依据：根 `AGENTS.md` §3 硬约束、`game/core/README.md`、`_dev_tools/game-docs/specs/README.md` 的「已实现 = 有生产调用路径」口径。

---

## 0. 总体结论

**当前状态：不可发布、不可安全提交、不可干净 clone 运行。**

四个独立维度同时不通过：

| 维度 | 结论 | 硬证据 |
|---|---|---|
| 测试 | **不通过** | 全量收集 3354 条，**34 failed** / 3317 passed / 1 skipped / 1 xfailed |
| 前端构建 | **不通过** | `tsc --noEmit -p tsconfig.web.json` 3 个语法错误；vitest 1 个 suite transform 失败 |
| 干净 clone | **不通过** | HEAD 导出后 `import core.domains.economy.procurement` / `logistics_coupler` → `ModuleNotFoundError: spatial_warehouse_bridge` |
| 账目/机制 | **不通过** | 10 项经探针复现的经济/人口账目错误，含单次抹掉 1,716 万石官仓粮、10,000 贯采购实扣 16,000 贯、产出双记、在途货物读档消失 |

根因不是单点 bug，而是三条系统性缺口：

1. **验证门禁缺失**：仓库无 `.github/`、无 CI。`npm run typecheck`、`pytest` 都靠人记得跑；HEAD 里已有编译不过的前端文件，仍被提交。
2. **「模块就绪」被当成「机制生效」**：至少 5 个领域模块（度量衡、生产方式、科举、三年磨勘、资源存量调查）零生产调用，但任务卡写 done。
3. **并发多 agent 同工作树 + `git add -A`**：已发生一次「提交吞掉他人 in-flight 工作」；当前工作树又叠加了未完成的立绘资产迁移与未跟踪核心模块。

---

## 1. 基线数字（可复跑）

| 项 | 本轮实测 | 文档旧基线 | 差异 |
|---|---|---|---|
| pytest 收集 | **3354**（`_dev_tools/game-dev/tests`） | 2689（2026-10-11，`game-docs/README.md` §验证基线） | +665 条 / 6 天 |
| pytest 结果 | **34 failed / 3317 passed / 1 skipped / 1 xfailed** | 0 failed（同上） | **34 条红** |
| 测试文件 | 325 个，57,727 行 | — | — |
| tsc web | **FAIL 3 errors**（`ReadoutHubPanel.tsx:108/166/167`） | 0 错（2026-10-11） | 回归 |
| tsc node | PASS | 0 错 | 一致 |
| vitest | **1 failed file / 11 passed；85 passed tests** | 80 passed | suite 编译失败 |
| Python 模块导入（HEAD 导出） | 290 个模块，**2 个生产模块 ImportError** | — | 干净 clone 不可运行 |
| `game/` 规模 | 295 个 py / 95,237 行 | — | — |
| `.git` 体积 | 804.4 MB（pack 727.2 MB + 39.1 MB 垃圾 tmp_pack） | — | 需 `git gc` |

> 注：`pytest -q` 的最终汇总行会被日志吞掉（项目已知问题）。本轮通过逐行解析进度字符 + 收集数交叉核对得出上述数字；建议后续统一用 `--junitxml`。

---

## 2. P0 · 阻断发布 / 破坏账目 / 可越权（共 18 项）

### 2.1 构建、仓库与契约（P0-A）

| ID | 位置 | 证据 / 现象 | 影响 | 改法与验收 |
|---|---|---|---|---|
| **A-1** | 未跟踪文件 `game/core/foundation/ledger/spatial_warehouse_bridge.py`；引用方 `logistics_coupler.py:31`、`procurement.py:18`、`livestock_and_escort.py:131`、`settlement_pipeline.py:129`、`migrations.py:204-205` | `git ls-files --error-unmatch` rc=1；`git cat-file -e HEAD:…` rc=128；HEAD 导出后 import 两模块 → `ModuleNotFoundError` | **干净 clone 无法运行**：`new_game` 走 migrations、月度结算的采购/物流/空间在途全 ImportError。本机全绿只因文件在磁盘上 | 先 `git add` 该文件并同批提交 `game_init/migrations/settlement_tech/README`；加「HEAD 导出 + import 冒烟」门禁。验收：干净 clone 跑 `import core.domains.economy.procurement` 与 `new_game()` 成功 |
| **A-2** | `game/frontend/src/renderer/panels/ReadoutHubPanel.tsx:108-166`（提交 `fddf9c07e2` 引入） | tsc：`TS17008 div 无闭合`、`TS1381/TS1005`；vitest：esbuild `The character "}" is not valid inside a JSX element` | **前端 HEAD 不可构建**，读数面板整页不可用；`npm run build` 会失败 | 在 `:113` 后补一个 `</div>`（关闭 `flex items-baseline` 容器）。验收：`tsc web` 0 错 + vitest 12/12 files |
| **A-3** | `game/backend/client.py:189-252`；`game/core/commands.py:77-80` | 实测 9 个符号 `hasattr(core.commands, name)==False`：`issue_free_decree`、`issue_kouyu`、`merge_drafts`、`issue_edict_from_review`、`reject_edict_draft`、`propose_inner_transfer`、`confirm_inner_transfer`、`cancel_inner_transfer`、`bestow_imperial_favor` | 前端「御前敕命 / 口谕 / 诏草准奏 / 内帑拨转 / 恩赏」按钮经 `/api/action` 全部 **500**；`server.py` 只接 `ValueError`，`AttributeError` 直接冒泡 | 在 `core/commands.py` 显式 re-export 这 9 个 `commands_decree` 函数，或让 `LocalBackend` 直接分派到 `commands_decree`；加「分派表 ↔ 实现符号」契约测试。验收：逐个 action 最小 payload 不抛 `AttributeError`/不 500 |
| **A-4** | 工作树 130 个 `D`：70 个 `content/ministers/layers/*`、27 个 `paperdoll/{layers,samples}`、33 个 `_src` | 旧路径仍被 `data.py:477,528,555-556`、`server.py:1315-1319`、`SongZuo.spec:42`、`portrait_assembler.py:24,339-402`、`paperdoll/engine.py:100-153` 引用；实测 `compose_portrait('张知县','lv','zheng')=None`、`resolve_layer_paths=0` | 若按现状提交：**非 42 位历史名臣立绘空白 / `/api/portrait` 404 / 打包后 layers 为空 / paperdoll 渲染 0 层**；且 33 个 `_src` 删除使资产管线不可复现 | 冻结提交，禁止 `git add -A`；从 HEAD 恢复 `layers/paperdoll/samples/_src`，或同批完成 `data.py/server.py/engine.py/SongZuo.spec` 改线与新资产接线并加「图层数>0 / 输出非纯色」断言 |

### 2.2 经济与账目（P0-B，均有探针实测）

| ID | 位置 | 证据 / 现象 | 影响 | 改法与验收 |
|---|---|---|---|---|
| **B-1** | `core/domains/economy/procurement.py:142-208`；`spatial_warehouse_bridge.py:144-179` | 10,000 贯采购单：`Δlocal=-16,000`、`Δ商人=+12,000`、`Δ工匠=+4,000`、料场 `+3,000`，而 `paid_total=10,000`；`transfer_goods_ownership` 不扣源仓/不加目标仓；工程按中文「木」领料仍 `0` | 政府采购**双付 + 凭空造料 + 中英文物料维分叉**，直接污染玩家账目 | 只付一次；`transfer_goods_ownership` 真扣真加并走 `MATERIAL_DIMS`；验收：`Δlocal+Δ商+Δ工==0`、`Δlocal==-paid_total`、`Δ商人物料+Δ官仓==0`、`consume_project_materials_spatial("木")>0` |
| **B-2** | `foundation/ledger/storage_bridge.py:199-201` | `changping_set` 无条件把 `changping_stock` 写进 `warehouses.public_granary.stocks.grain`。实测京畿官仓 12,345 → 668,312；真实 8→9 月两浙官仓 **20,151,985 → 2,996,181**（-1,715.6 万石） | 常平仓一次覆盖官仓粮，**数千万石粮食凭空消失**；粮价/赈济/军粮全部失真 | 删除无对价覆盖；`changping_stock` 若只是 `public_granary` 的视图则不得独立成账；验收：任意 `changping_add` 不改官仓（除非同笔真实成交），`grain_snapshot` 连续两月闭合 |
| **B-3** | `core/settlement_econ.py:1819-1869` | 一月结算：`绸` POP goods `+10,510` 且 `resources["绸"] +11,116`；`meat` `+75,947` 且 `+80,000` | 同一批产出**同时记入 POP 与国家资源两份 custody**，可被重复消费/交易 | 只保留一个权威载体；验收：任一月每成品 `ΔPOP_goods + Δresources` 等于一次产量 |
| **B-4** | `core/domains/economy/industry_chains.py:207-212,246-250,292-373` | 月结报表称 `refined_iron=398,725`、`copper_ingots=325,220`，实际仓中 `铁锭/铜锭/熟铁` 均为 `None`，`copper_ore=464,600` 原样存在又额外 `resources["铜"]=325,220` | 八大产业链**只写报表不动物理库存**；铜「凭空精炼」 | 改成真实 stock-to-stock 流水（扣输入/加输出/每步记账），或把任务卡降为「仅报表、未接实物链」；验收：每条链 `Σinputs_used==Σinputs_deducted`，无 `output>0 而仓存为 0` |
| **B-5** | `foundation/ledger/material_holding.py:620-667,884-907` | 新局 1 月：`resources["木"]=1,620,414`、`merchant_goods["木"]=0`、`supply_goods_to_seats={}`；`holding_report` 仍 `ok=True` 且 `gap=1,620,414` | 「全商品配货」步骤**实际空转**，建材永远到不了商人，C-c「只从本地取料」退化为「永远缺料」；自检还把空转判成通过 | 空货栈商人也要纳入 holders；`_attribute_by_weights` 参数类型修正；配货必须实扣 `resources`；`holding_report` 改 `held==stock`。验收：一月后 `Σmerchant goods>0` 且 `resources` 相应减少，`gap==0` |
| **B-6** | `core/settlement_common.py:531-533` | `transfer_public_funds_to_pops` 收款路径写 `prefectures.<路>.pops.<类>.wealth`（路级派生镜像）。实测转 1,000 贯，同步后 M_ALL `337,809,947 → 337,808,947` | **钱转出去后同步即销毁**；研发/工程款等所有走此通道的支出都可能丢钱 | 改走治所真账 / `pop_obj_add`；验收：转账后 Σseats 增加额 == 转出额，M_ALL 不变，`money_audit.residual==0` |
| **B-7** | `spatial_warehouse_bridge.py:210-285`；`save_load.py:250-337` | 发 300 铁后 `in_transit_batches` 有 1 批；存档/读档后该属性不存在、批次 0、源仓仍 200 | **在途货物与客运读档即消失**（300 铁蒸发）；跨州物流不可用 | 把 `in_transit_batches`/`passenger_trips` 加入 `GameState` + save/load，或改接 `transport.material_transit`；验收：发货→存档→读档批次字段逐项一致；到货后 `源+目标+在途==发货前` |
| **B-8** | `core/domains/economy/pop_livelihood.py:77,166`；`industry_chains.py:208`；`mineral_deposit.py:262-264` | `derive_pop_livelihood` 两次各扣 `-290,000`，真实一月 `-580,000`，而单次 `extract_circuit_minerals` 只扣 `-290,000`；`derive_raw_production` docstring 称纯函数却真扣储量 | **采矿双倍提取**；任何只读派生读数都会继续耗竭矿藏 | 拆「纯派生」与「一次开采」；验收：每月储量变化 == 单次 extract；任意只读 API 前后储量不变 |
| **B-9** | `core/settlement_pipeline.py:65-71,186-253` | 49 步中 `critical=True` 仅 **13** 步；注入 `supply_goods_to_seats` 抛错 → 只记 WARN，`turn` 仍 +1、资源已落账 | **半结算月**：钱/货/人已改一半，异常被吞，玩家无感；回滚保障名存实亡 | 所有动账本/动 POP/动库存的步标 critical（至少 production_chain、industry_chains、supply、workshops、civil_construction、pop_livelihood、extensions、military、focus、disaster、situations），或整月快照+整体回滚。验收：注入每个动账步异常 → 全字段与月初一致 |
| **B-10** | `core/settlement_military.py:152-161`；`settlement_common.py:348-365` | 欠饷 30 万 → `troops -300`、`ΣPOP Δ0`；AI 裁汰 5 万 → `ΔΣPOP=0`，日志仍写「人丁还民」；`_return_men` 只写路级镜像后被 sync 冲回 | 违反 POP 挂载律：**兵额凭空消失/裁汰不减人口**，欠饷变成免费减员 | 逃亡/裁汰按比例落 `流民` 或农 POP（`pop_obj_add`/`move_pop_people(..., state)`）；验收：`Δ兵编制 + Δ兵/农/流民 POP == 0`，日志有「还民」必有对应增量 |

### 2.3 AI / 事权 / 后端（P0-C）

| ID | 位置 | 证据 / 现象 | 影响 | 改法与验收 |
|---|---|---|---|---|
| **C-1** | `core/commands_decree.py:324-395`；`settlement_decree.py:176-185`；`game_state.py:766` | UI 路径 `issue_decree` 后 `pending_decrees` 缺 `addressees/enforce_troops/route/effects`；无受命人时整段 `confirm_decree` 被跳过并记 `confirmed`；新局 `minister_agents` 长度 0，有受命人又全 `unknown_actor/unauthorized` | **M325 枢密院调兵门禁 / 法统门禁 / 中旨扣皇威在生产链路不可达**；执行台账失真 | `issue_decree` 归一化并保留 `addressees/enforce_troops/route/effects`；无受命人不得跳过军权/事权校验；开局为在任官员建 Agent；`record_execution` 只在 `status==CONFIRMED` 时写 confirmed。验收：无受命人 + enforce_troops → 拒绝且不记 confirmed |
| **C-2** | `commands_decree.py:528,538`；`settlement.py:269-377`；`commands.py:1509-1552` | `issue_free_decree` 把客户端 `parse_result.reform` 直接送 `settle_reform`，**不经 `check_authority`**；实测把 `authority_matters["调兵"].owner` 从枢密院改为中书省 | 任意客户端可**改机构树/事权归属**（修好 A-3 后即成活越权入口）；军令增募/调赴/换帅/裁撤同样无枢密院 gate | `settle_reform` 强制 `executor` 并逐项 `check_authority`；`issue_military_order` 过枢密院 gate；客户端 `reform` 只接受服务端解析产物。验收：非掌「调兵」主体提交改权限 → 拒绝且 `authority_matters` 不变 |
| **C-3** | `core/decree_confirm.py:663-689` | 模块内**无 `log` 定义**却调用 `log.debug` → `NameError`；补 logger 后同一异常返回 `confirmed/authorized=true` / `reason=recitation_matches` | 事权校验一旦异常，**整条确认链崩溃或 fail-open 放行**（与「缺失即拒」相反） | 顶部补 `log`；异常统一落 `STATUS_UNDEFINED`/`STATUS_UNAUTHORIZED` 且 `authorized=False, withheld=True`；验收：monkeypatch 校验抛错 → 绝不 `authorized=True` |
| **C-4** | `frontend/.../DecreePanel.tsx:106-111`；`commands_decree.py:297-395` | 前端「御前敕命」只发 `text/title/minister`；实测「赈济两浙路灾民」落成固定财政模板 `treasury+300000 / satisfaction-3` | 玩家写任何内容都会变成**固定财政数值**，不经 AI 解析，语义错配 | 前端走 AI 解析→拟旨→会签；`issue_decree` 缺 `category/effects` 时拒绝并提示「请先解析诏意」。验收：同文本不同品类不再固定同效果 |

---

## 3. P1 · 应修（按模块归组）

### 3.1 经济/结算（13 条，详见 `audit-core.md`）

1. `application/load_game.py:47,109-165`：`_dlog` 未定义，迁移异常时抛 `NameError` 而非「失败不拒档」。
2. `mineral_deposit.py:188-205` + `save_load.py`：`mineral_deposits` 不落档，开采后读档储量回满（枯竭被重置）。
3. `spatial_warehouse_bridge.py:101-118`：缺失物料维返回 `0.0`（应 `None`）；`test_spatial_warehouses.py:34` 还把这个违规写成断言。
4. `spatial_warehouse_readout.py:44-145`：四仓看板读错路径（读 `p["public_depot"]` 而非 `seats[].warehouses`），实测 `public_depot_summary=None`。
5. `stock_identity.py:43,124-166`：`CUSTODY_KEYS` 漏四仓；`pending_stock_by_dim` 恒 `{}`，待定货从恒等式消失。
6. `production_methods.py`：8/8 API 零生产调用；M317「PM 驱动八大链」实为未接线。
7. `logistics_coupler.py:111-231`：调拨/耦合零生产调用；M314 声称已接入 pipeline，实际无调拨相位。
8. `livestock_and_escort.py`：畜牧生产零调用；镖局费只累计 `total_fees_paid` 从不 `transfer_money`。
9. `settlement_decree.py:604-612`：诏令 `imperial_treasury` 负值直改，无对手方/无 `register_flow`（造币/毁币）。
10. `material_holding.py:884-907`：`holding_report` 只判 `held>stock`，`stock>held` 仍 `ok=True`（掩盖 B-5）。
11. `settlement_military.py:145-146`：`corruption=0` / `ability=0` 被 `or 0.3`/`or 0.5` 吞掉。
12. `logistics_coupler.py:151,223`：`barges_pool=0` 被 `or 50` 变成 50 条船。
13. `land_reclamation.py:96-146`：官方垦荒零调用且扣款按请求额而非实际可用库银，可能超额开垦、无 burn 登记。

### 3.2 AI/行政/后端（17 条，详见 `audit-ai-admin.md`）

1. `/api/resolve_event` 信任请求体 `req.event`，实测可伪造事件 +8 皇威（应只接受 title/choice，从 `active_events` 反查）。
2. 中旨+强推重复扣皇威：50 → 34（应 40）；`state.prestige=` 直写绕过 `_prestige_history`。
3. 准奏奏折数值效果全归 0（`_build_memorial_effects` 输出 1/2/3/5 被当档位词再 `normalize_tier`）。
4. `administrative_efficiency` 唯一写入方在死模块（`official_appraisal`/`imperial_exam` 零生产调用），新局实测 `None`，天道月报永久未定义。
5. `effect_channels` 名为只读，实测首次调用写 136 个 `prefect_officials` / 21 个 `circuit_officials`；两册不入档。
6. 136 个州府只有 20 个不同知州名、126 个监司岗位只有 31 个不同姓名；任免不落档。
7. 名将加成是假的：`MINISTERS` 无 `ability` 字段，`c_abil` 恒 0.5，`(c_abil-0.5)*3` 恒 0。
8. 两段式推进 daemon 不持 server `_lock`；后台结算失败回滚会吞掉玩家窗口内动作（实测 `action_lost=true`）。
9. `HttpBackend.save_slots` 从不请求 `/api/save_slots`，远程模式读的是客户端本地槽位。
10. `validate_free_effect` 允许 `institution`，但 AI prompt 白名单不含它；`executor` 直接信任 AI 自报。
11. `settlement_military.py` 对 `unrest=None` 直接 `float(None)` 抛 `TypeError`；该步非 critical → 半结算。
12. `decree_effect.py` 连署率把缺失字段当「已连署」（`get("countersigned", True)`）。
13. 其余：魔数入常量表、`change_prestige` 单次 cap 非月度累计、死代码、文档漂移等 15 条 P2。

### 3.3 前端（5 条，详见 `audit-frontend.md`）

1. `TechPanel.tsx:12,61-88` 前端复刻 `tech_cost_with_era/node_status`，且校验比后端更严 → UI 挡住后端可研节点（`M2_spindle` 为例）。违反「前端不复制算法」。
2. `PrefecturePanel.tsx:44-76,161` 读数失败时伪造 `50/30/40/0` 与 `risk_label「警」`，`yield` 缺失显示 `1.0`。违反「缺失≠0≠1.0」。
3. 后端 `finance/granary` 失败下发 `{}`（`server.py:778-783,791-803`），`AccountingPanel/GranaryPanel` 用 `asNum(...,0)` 渲染成 `0 贯/0 石`；`humanizeCoin(null)` 返回「0贯」。
4. `layers.ts:86-89` 民怨池为空时硬编码两浙路红警/京东黄警 —— 舆图假数据。
5. `GovernanceHub.tsx:247-264` 准奏/留中 catch 只 `console.error`，玩家无失败反馈。

### 3.4 仓库/文档/可移植性（6 条，详见 `audit-repo.md`）

1. 33 个 `_src` 删除使 `_lay2.py` / `PORTRAIT_PIPELINE.md` 的复现命令断链（资产管线不可重建）。
2. 11 个未跟踪测试（78 个用例）不在 git；干净 clone 无法复现空间仓储/天道/采购/经济账用例。
3. `game/assets/paperdoll/` 166 文件 / 31.5 MB 未跟踪且零代码引用；决策 A 只要 `new_vector_modular`（3.64 MB）。
4. 22 个 decisions + 3 个 tasks + 3 个 worklog + 8 个 md 未跟踪，但 `INDEX.md` 已计数 → clone 后索引与实际不符。
5. `songzuo/ai_config.json` 含 51 字符真实 key；目录被 gitignore，但发行包可能外泄（建议轮换或构建排除）。
6. `specs/README.md` 声称 36 份实际 90 份；全库 878 个 md 有 48 个断链；30 个 tracked 文件含 `D:\codebuddy` / `C:\Users\william` 绝对路径。

---

## 4. P2 · 卫生与可维护性（摘要）

- `.git` 804 MB + 39 MB 垃圾 `tmp_pack`；建议 owner 跑 `git gc --prune=now`（本轮未执行）。
- `AGENTS.md:281-282` 仍写 `sz/README.md` / `game/frontend/README.md` 被忽略（实际已入库）；`AGENTS.md:18` 的 2178 用例基线已过期。
- `.gitignore` 有失效旧规则，且缺 `.credentials`/`*.pem`/`*.key` 通用规则。
- 26 个 M 文件有 LF/CRLF 噪声；`.gitattributes` 只覆盖 `*.bat/*.cmd`。
- `game/content/ministers/README.md` 把 `compose_portrait` 指到不存在的 `core/minister_profile.py`。
- `songzuo_server/`（Rust，80 KB）最后更新 2026-10-03，已落后 Python 13+ 提交；建议明确归档或标注「实验/不对齐」。
- 无 CI、无 `pyproject.toml`/`requirements.txt` 锁定测试依赖；建议至少加 `verify-all` 的 tracked-only 门禁。

---

## 5. 误报澄清（看起来像缺陷，实测合规）

| 项 | 结论 |
|---|---|
| 后端鉴权/并发/原子写 | **合规**：`_require_auth` 有 token/回环双分支，`hmac.compare_digest`；`/api/*` 在 `_lock` 内；存档 `os.replace` 原子写；立绘路由做了 basename + 扩展名白名单。 |
| Electron 安全 | **合规**：`contextIsolation`/`sandbox`/CSP/preload 暴露面均通过；`ApiClient` 有 30s 超时/重试/中文错误。 |
| 217 处 POP 字段直写 | **多数合规**：均为 `pop_obj_add/_pop_obj_add(...) is None` 后的回落分支，符合「桥接优先」写法；真正风险是守卫未在生产安装（已在 `test_prod_pops_guard` 等覆盖）。 |
| `state.population = max(10_000_000, …)` | **刻意设计**：旧审查文档已明确为「设计内」，非缺陷。 |
| 舆图产物不在 git | **刻意**：`assets/map/web/*`、`public/map/*.topojson` 生成物忽略，新 clone 按 §4 重建；当前几何测试红与此无关。 |
| `songzuo_server` 与 Python 不一致 | **已知**：README/AGENTS 明写「Rust 并行实验、不保证一致、不作发行版权威」。 |
| `_i2i.py:5` 硬编码 key | **用户 2026-10-03 已豁免**；仅登记，不要求本轮处理。 |
| `industry_chains` 商人物权直写 | **合规**：先 `pop_obj_add(wealth, -paid)` 再回落，符合桥接写法（但 B-4 的「只写报表」是真缺陷）。 |

---

## 6. 建议处置顺序（按依赖与收益）

### 第 0 步：先止血（当天，禁止再提交）
1. 冻结工作树：**不要 `git add -A`**；把当前 130 个 `D` / 51 个 `??` 按归属拆成独立提交或恢复。
2. `git add game/core/foundation/ledger/spatial_warehouse_bridge.py`（A-1），并跑一次 HEAD 导出 import 冒烟。
3. 修 `ReadoutHubPanel.tsx` 缺 `</div>`（A-2），跑 `npm run typecheck && npm run test`。
4. 修 `core/commands.py` 的 9 个 re-export（A-3），加 dispatch 契约测试。
5. 恢复或完成立绘资产迁移（A-4），恢复后跑 `compose_portrait` + paperdoll 非空断言。

### 第 1 步：修账目 P0（1–2 天）
按影响排序：B-2（常平覆盖官仓）→ B-1（采购双付）→ B-6（转账销毁）→ B-3/B-4（产出双记/报表链）→ B-5（配货空转）→ B-7（在途不落档）→ B-8（采矿双提）→ B-10（兵额不落 POP）→ B-9（critical 划分）。
每条先补**失败用例**（用真实 `new_game` + 月结），再改，再跑定向。

### 第 2 步：修 AI/事权 P0（1–2 天）
C-3（fail-open）→ C-2（越权）→ C-1（诏令字段/Agent）→ C-4（UI 模板）。补「门禁不可达」的端到端用例：从 `/api/action` 进，而不是直接调函数。

### 第 3 步：清理 34 条红与基线
- 先区分「代码回归」与「过期断言」：`test_declarative_pipeline`（48→49）、`test_domains_administration_b19`（14→15/参数）、readout 数量（21→27）属过期断言；`test_econ_price_review::test_failed_settlement_rolls_back_whole_month` 的 monkeypatch 打在旧函数对象上，必须改到 pipeline step 的 `func`。
- 加 `--junitxml` 与 tracked-only 收集门禁，避免「本机绿、clone 红」。

### 第 4 步：P1/P2 分批
按 `audit-core.md` / `audit-ai-admin.md` / `audit-frontend.md` / `audit-repo.md` 的 P1 表逐项认领；每批同步更新任务卡状态（未接线就标 🟡），并在 `game-docs` 回写口径。

### 第 5 步：建立门禁（本周）
- CI（或本地 `verify-all.ps1` 强制）：pytest（junit 计数）+ tsc 双配置 + vitest + HEAD 导出 import 冒烟 + docs 链接检查 + `git ls-files` 目标存在检查。
- 多 agent 提交规约：提交前 `git status` 逐条确认归属；禁止 `git add -A` / `git commit -a`。

---

## 7. 本次未覆盖 / 材料不足

- 240 月长局平衡与性能（需 `SONGZUO_LONG_RUN=1`，本轮未跑）。
- 前端像素级/交互验收与真机 Electron 打包（本机缺 `electron/dist`，`electron-builder` 不可用）。
- 外邦 38 政权、Rust 后端与 Python 本体的功能对齐。
- 立绘/舆图美术质量本身（只验证了资产存在性与引用完整性）。
- 历史提交的完整回归（本轮聚焦 HEAD + 工作树）。

---

## 8. 复核命令

```powershell
$py   = "D:\codebuddy\.audit-venv\Scripts\python.exe"
$node = "D:\codebuddy\tools\nodejs\node-v20.19.5-win-x64\node.exe"

# 1) 全量 pytest（建议加 junit，避免汇总行被吞）
cd D:\codebuddy\sz
$env:PYTHONPATH=""; $env:CODEBUDDY_SAFE_DELETE_ENABLED="0"
& $py -m pytest _dev_tools/game-dev/tests -q -p no:cacheprovider --junitxml=_scratch\audit-20261017\junit.xml

# 2) 前端
cd D:\codebuddy\sz\game\frontend
& $node .\node_modules\typescript\bin\tsc --noEmit -p tsconfig.web.json
& $node .\node_modules\typescript\bin\tsc --noEmit -p tsconfig.node.json
& $node .\node_modules\vitest\vitest.mjs run

# 3) 干净 clone（HEAD 导出）import 冒烟
cd D:\codebuddy\sz
git archive --format=zip -o _scratch\audit-20261017\head.zip HEAD
# 解压后：$env:PYTHONPATH="<export>\game"; & $py -c "import core.domains.economy.procurement"

# 4) 账目探针（复现 P0-B）
& $py _scratch\audit-20261017\probe_core.py
& $py _scratch\audit-20261017\probe_changping.py

# 5) 分派表契约
& $py _scratch\audit-20261017\verify_dispatch2.py
```

---

## 9. 证据与产物

| 文件 | 内容 |
|---|---|
| `_scratch/audit-20261017/audit-core.md` | 核心经济/结算：10 P0 / 13 P1 / 12 P2 |
| `_scratch/audit-20261017/audit-ai-admin.md` | AI/行政/军事/后端：6 P0 / 17 P1 / 15 P2 |
| `_scratch/audit-20261017/audit-frontend.md` | 前端：2 P0 / 5 P1 / 多条 P2 |
| `_scratch/audit-20261017/audit-repo.md` | 仓库/文档/密钥：3 P0 / 6 P1 / 10 P2 |
| `_scratch/audit-20261017/probe_core.out.txt` | 采购/配货/双记/常平/在途/采矿等实测数字 |
| `_scratch/audit-20261017/probe_changping.out.txt` | 常平覆盖官仓的逐月前后值 |
| `_scratch/audit-20261017/pytest.log` | 全量 pytest 原始输出 |
| `_scratch/audit-20261017/failed_reasons.log` | 34 条失败的逐条原因 |
| `_scratch/audit-20261017/head-export/` | HEAD 干净导出（用于 import 冒烟） |

> 报告生成时间：2026-10-17 · HEAD `1c9ff50c80` · 工作树含他人未提交改动，引用前请以最新 `git status` 为准。
---

## 10. 修复闭环（2026-10-17 晚 · 用户裁定「修」后落地）

> 本轮在 HEAD `ee7236947c` 之上完成整改；全部改动已通过全量回归，**未提交任何密钥/存档/构建产物**。

### 10.1 P0 状态

| 审计编号 | 状态 | 落地摘要 | 验证 |
|---|---|---|---|
| A-1 bridge 未跟踪 | ✅ 已由并发 M326 入库 | `spatial_warehouse_bridge.py` 已 tracked | 干净导出 import 通过 |
| A-2 前端 JSX 不闭合 | ✅ fixed | `ReadoutHubPanel.tsx` 补 `</div>`；`client.ts` ActionName 补 3 动作 | tsc 双配置 0；vitest 98 passed |
| A-3 后端 9 个 action 符号缺失 | ✅ fixed | `core/commands.py` 显式 re-export 9 个 `commands_decree` 函数 + 契约测试 | `test_backend_action_contract.py` 2 passed |
| A-4 立绘资产删除 | ✅ fixed（止血） | 130 个 D 全部从 HEAD 恢复；`compose_portrait`/`PaperdollRenderEngine` 恢复；新 `game/assets/paperdoll/` 仍未接线（单独分支） | D=0；portrait 测试绿 |
| B-1 采购双付 | ✅ 已由 M326 修复 | 只付一次 + 物权真扣 | 采购守恒用例绿 |
| B-2 常平覆盖官仓 | ✅ fixed | `changping_set` 不再无对价覆盖 `public_granary` | 官仓 12345→12345、常平 +1000 |
| B-3 作坊产出双记 | ✅ fixed | 成品唯一权威载体 = POP `goods`；`ΔPOP+Δresources=一次产量` | 产绸 100 → +100/0 |
| B-4 八链只写报表 | ✅ fixed | 治所四仓真实 stock-to-stock；铜先扣矿再入锭；无仓时显式 report_only | 24 成品键均有仓存增量 |
| B-5 配货空转 | ✅ fixed | 空 goods holder 纳入、helper 参数修正、resources 实扣、holding_report 等式 | 木 out=1000/merchant=1000/gap=0 |
| B-6 转账写镜像销毁 | ✅ fixed | 收款落 seats 真账（`pop_obj_add`） | M_ALL Δ=0 |
| B-7 在途不落档 | ✅ fixed | `in_transit_batches`/`passenger_trips` 初始化 + save/load | 300 铁 batch 1→1 |
| B-8 采矿双提取 | ✅ fixed | `derive_raw_production` 纯派生；同 turn 幂等；月度显式提取一次 | 一月 -290000（单次） |
| B-9 管线半结算 | ✅ fixed | 49/49 步 critical；逐一步注入异常均整月回滚 | 51 条原子性用例绿 |
| B-10 逃亡不落 POP | ✅ 已由 M326 + 本轮补 `from_army_pop` | 先扣兵 POP 再回流农/流民 | ΔΣPOP=0 |
| C-1 诏令字段/Agent 不可达 | ✅ fixed | 保留 addressees/enforce_troops/route/effects；未确认记 not_required；开局建档中枢 holders | 李清臣+调兵 unauthorized；蒋之奇 confirmed |
| C-2 事权越权 | ✅ fixed | `settle_reform` 要「官吏铨选」；军令要「调兵」 | 户部拒绝且 owner 不变 |
| C-3 confirm fail-open | ✅ fixed | 补 logger；异常 fail-closed（undefined/false/withheld） | 探针不再 NameError/放行 |
| C-4 UI 固定财政模板 | ✅ fixed | 缺解析结果明确拒绝；前端失败不清空输入 | tsc 0 |
| 附加 P1 | ✅ fixed | `/api/resolve_event` 只接受 title/choice；结算窗口 409；准奏失败可见；舆图假警色移除；TechPanel 去算法复制 | 前端 98 passed；backend 24 passed |

### 10.2 最终基线（2026-10-17）

| 项 | 结果 |
|---|---|
| pytest | **3437 tests / 0 failed / 0 errors / 2 skipped**（junit `_scratch/audit-20261017/junit-final2.xml`，1072.8s） |
| tsc | web 0 错 / node 0 错 |
| vitest | 17 files / 98 tests 全绿 |
| 工作树 | `D` 计数 0；未跟踪仅剩 `game/assets/paperdoll/`（迁移待接线）与 4 个开发工具文件 |
| 干净 clone | bridge 已入库；导出后 `import core.domains.economy.procurement` 通过 |

### 10.3 仍未闭环（下一批）

1. `game/assets/paperdoll/` 新资产接线（`data.py`/`portrait_assembler.py`/`SongZuo.spec`）与旧 layers 退场顺序 —— 需单独分支。
2. 文档卫生：`specs/README.md` 计数（36 vs 90）、48 个断链、30 个机器绝对路径、`.git` 804MB/39MB 垃圾 pack（`git gc` 未执行）。
3. P1/P2 未接项：`effect_channels` 只读写 state、官员册不入档/重名、后台结算锁的完整队列化、`administrative_efficiency` 以外的考课/科举接线等（见四份专项报告 §3）。
---

## 11. 第二批整改（P1 · 2026-10-17 晚）

> 在 `4b0e555df2` 之上继续修 P1；全量回归 *3449 tests / 0 failed / 0 errors / 2 skipped*。

### 11.1 已修

| 项 | 落地 | 验证 |
|---|---|---|
| P1-2 矿藏不落档 | `mineral_deposits` 入 save/load；`migrations.ensure_mineral_deposits` 旧档幂等补全 | 开采后 499,710,000 → save/load 仍 499,710,000 |
| P1-3 四仓缺失维返回 0 | `warehouse_stock_get` 缺失维/仓位 → `None`；同步 `or 0.0` 调用方与测试 | missing=None / explicit-zero=0.0 |
| P1-4 四仓看板读错路径 | `spatial_warehouse_readout` 改遍历 `seats[治所].warehouses` | depot 13,615,976.3 == summary；空 state 为 None |
| P1-5 库存恒等式漏四仓 | `CUSTODY_KEYS += seat_warehouses`；pending 展平；在途兼容两套账 | snapshot 含四仓；pending 木=123；in_transit 铁=100 |
| P1-9 内帑造币/毁币 | 负值向官僚 POP 守恒划转，正值从 POP 实征 | ΔM_ALL=0（-1000 / +500） |
| P1-3 准奏奏折效果归 0 | `_build_memorial_effects` 输出档位词并兼容旧数值 | 5 类中档实测 treasury 800000 / defense_bonus 3 / satisfaction 3 / prestige 4 |
| P1-5 只读读数写 state | `get_prefect_officials`/`get_circuit_officials` 纯只读；`game_init.init_official_books` 新局显式建册 | effect_channels 前后 vars(state) 键不变；new_game 136/21 |
| P1-9 远程 save_slots 读本地 | `HttpBackend.save_slots` → GET `/api/save_slots` | mock 断言 path+GET；失败抛 RuntimeError |
| P1-11 unrest=None | `parse_number` 处理 | None→21.2 不抛 |
| P1-12 连署缺失当已签 | 缺失按未签并输出 `countersign_undefined/reason` | 9 席全缺失 → ratio 0.0 / undefined 9 / mult 0.315 |
| 文档卫生 | 断链 48 → **0**（884 md）；`specs/README` 去写死计数；代码/测试/脚本/AGENTS 绝对路径 31 → 1 | `check_links_all.py` / `test_readme_sync` 48 passed |
| 可移植性 | 21 个测试 `sys.path` 改 `Path(__file__)`；5 个资产脚本/3 个 ps1 改路径推导 | 140 passed；ps1 parse 0 错 |

### 11.2 最终基线（第二批后）

| 项 | 结果 |
|---|---|
| pytest | **3449 tests / 0 failed / 0 errors / 2 skipped**（junit `_scratch/audit-20261017/junit-batch2.xml`，1227.5s） |
| tsc | web 0 / node 0 |
| vitest | 17 files / 98 passed |
| 链接检查 | 884 md / **broken 0** |
| 绝对路径 | 代码/测试/脚本/AGENTS 31 → 1（剩 `game/ai/jev_gate.py:132` keys_file，建议改环境变量） |

### 11.3 仍未闭环（第三批候选）

1. **官员册持久化**：`state.prefect_officials` / `state.circuit_officials` 尚未入 save/load（本轮已改为新局显式建册 + 只读纯函数，但读档后需重建）；同人重复任职（136 席仅 20 个知州名）需统一人物 ID/姓名池。
2. **paperdoll 新资产接线**：`game/assets/paperdoll/`（166 文件/31.5MB）仍未入库/接线；旧 layers 已止血恢复。
3. **未接线模块**：`production_methods`、`imperial_exam`、`run_triennial_appraisal`、`metrology` 效果、`logistics_coupler` 调拨等——任务卡已如实降级为 in_progress，接线属功能开发。
4. **仓库体积**：`.git` 804MB + 39MB 垃圾 pack，需 owner 放行后 `git gc --prune=now`。
5. `game/ai/jev_gate.py:132` 的 keys_file 机器绝对路径。
---

## 12. 第三批整改（官员册 · paperdoll 入库 · 可移植性收尾）

### 12.1 已修

| 项 | 落地 | 验证 |
|---|---|---|
| P1-6 官员册重名 | `prefect_officials`/`circuit_officials` 引入稳定 `person_id` + 确定性姓名分配器：历史/池名优先（historical=True），不足用姓氏池×双字名池生成（historical=False） | 272 任命 → **272 唯一姓名/person_id**；126 岗位 → **126 唯一**；跨册交集 **0**（修复前 35/31 个姓名） |
| P1-6 官员册持久化 | `save_load` 写入/恢复两册；`migrations.ensure_official_books` 旧档幂等重建，已有册只补 `person_id` 不覆盖任免；任免入口落 person_id | 6 条新用例：唯一性、save/load 逐字段、旧档幂等、空册重建、裸档任免 |
| paperdoll 资产入库 | 按 JEV 决策 A 只纳入 `new_vector_modular`（31 文件 / 3.64MB）；`SongZuo.spec` 加 datas；新增资产契约测试（PNG 可解码、800×1000/RGBA、10 目录非空、非忽略） | 23 passed；B/C/loose 135 文件仍未纳入 |
| jev_gate 绝对路径 | `keys_file` 不再写死 `D:\codebuddy\...`，改 `TYPESAFE_KEYS_FILE` 环境变量（默认 None，key 优先 env） | 导入正常；无测试依赖旧路径 |
| 性能门禁抗负载 | `test_readout_performance_gate` 保留空载 50ms 绝对门限；同机重负载时按固定纯 Python 校准基线等比放宽（4× 上限），仍能抓 O(n²) 级退化 | 单测/整套 situations 绿 |

### 12.2 最终基线（第三批后）

| 项 | 结果 |
|---|---|
| pytest | **3458 tests / 0 failed / 0 errors / 2 skipped**（junit `_scratch/audit-20261017/junit-batch3-green.xml`） |
| tsc | web 0 / node 0 |
| vitest | 17 files / 98 passed |
| 文档链接 | 884 md / broken 0 |
| 工作树 | 仅剩 `game/assets/paperdoll/` 其余 135 个淘汰/过程资产未跟踪（按决策 A 不入库） |

### 12.3 仍未闭环（后续批次）

1. **paperdoll 生产合成器接线**：`new_vector_modular` 资产已入库，但 `portrait_assembler.py`/`data.py` 仍走旧 `layers`；需新合成器 + `SongZuo.spec` 打包验证 + 真机目视。
2. **未接线模块**：`production_methods`、`imperial_exam`、`run_triennial_appraisal`、度量衡效果、物流调拨——任务卡已降级为 in_progress，属功能开发。
3. `.git` 804MB + 39MB 垃圾 pack：需 owner 放行后 `git gc --prune=now`。
4. `game/assets/paperdoll/` 其余 135 个 B/C/loose 资产：建议归档到不入库目录或删除，避免长期占 28MB 工作树。---

## 13. 第四批整改（科举/磨勘接线 · 度量衡效果接线）

### 13.1 已修

| 项 | 落地 | 验证 |
|---|---|---|
| M300 科举全流程接线 | officialdom._triennial_exam_wired 在科次年正月委托 imperial_exam.run_triennial_exam_full（解试→省试→殿试）；last_exam_year 幂等；recruit_log 记账；失败记 personnel_cycle_error+WARN | 科次年开科、同年不重复、非科次年不开、失败不静默（5 条用例） |
| M300 三年磨勘接线 | settlement_officialdom._run_personnel_cycle 在第 18/54… 回合委托 official_appraisal.run_triennial_appraisal | 第 18 回合触发、同回合幂等、第 17 回合不触发 |
| M324 制造倍率 | _settle_workshops 产出乘 manufacturing_mult（只乘产出） | 真实月结作坊产出：传统 100 / 统一 110 / 公制 130 |
| M324 物流损耗 | advance_in_transit_batches 途耗乘 (1-logistics_loss_reduction) | 1000 石陆运净到：700 / 730 / 775 |
| M324 清丈抗隐田 | apply_fangtian_survey 的 effective_intensity 加 tax_leakage_resistance | 京畿路查出隐田 2,224,375 / 2,758,225 / 3,559,000 |
| M324 吏胥抗拒 | _next_grip 增 grip_resistance，结算传当前体制值 | 月结 clerks_grip：0.1125 / 0.1069 / 0.0990（单调下降） |
| M324 宗族民怨 | apply_reform 按 gentry_unrest_spike 一次性扣民心 | 传统 0 / 统一 -2 / 公制 -6 |

> 说明：传统体制（0）下五项效果均为中性，默认行为逐位不变；清丈入口原本就无月度自动调用，本轮只把体制效果接进该入口。

### 13.2 最终基线（第四批后）

| 项 | 结果 |
|---|---|
| pytest | **3469 tests / 0 failed / 0 errors / 2 skipped**（junit _scratch/audit-20261017/junit-batch4.xml，957.6s） |
| tsc | web 0 / node 0 |
| vitest | 17 files / 98 passed |

### 13.3 仍未闭环

1. **M317/M318 生产方式（PM）**：production_methods 8 个 API 仍零生产调用；需接作坊产出/建筑吞吐。
2. **M314 物流调拨**：logistics_coupler.dispatch_industry_logistics 仍零生产调用；需接管线调拨相位。
3. **官方垦荒**：reclaim_land_government 仍零生产调用。
4. **paperdoll**：按用户裁定**冻结**，不再改动（新资产已入库，合成器接线不做）。
5. `.git` 804MB + 39MB 垃圾 pack：需 owner 放行后 git gc --prune=now。---

## 14. 第五批整改（生产方式 PM · 官方垦荒）

### 14.1 已修

| 项 | 落地 | 验证 |
|---|---|---|
| M317/M318 生产方式（PM） | production_methods 新增只读 `relative_throughput_multiplier`（current/default 四槽乘积）；`_settle_workshops` 对作坊产出乘该相对倍率（只乘产出、不改投入；找不到 seat 回退 1.0） | 造船作坊 yield=100：默认 PM 100 / 切 pm_org_manufactory（relative=1.8）180 / 切回复原 100；非法 PM=1.0 |
| M317/M318 任务卡 | M317/M318 audit_status 改为「PM 已接线：相对倍率（默认中性），切换 PM 生效」；多级产业链全面驱动仍注明后续 | 任务卡 JSON |
| P1-13 官方垦荒 | 新增机构参数 `gov_reclamation_share`（默认 0、0–5%、度支调度事权）；每年二月按国库比例向荒地最多的路拨款；`reclaim_land_government` 付款腿改为「国库 → 本路农/工匠 POP」守恒转移，并禁止超国库实有 | 默认 0 零变化；share=2% 时荒地↓、官田↑、国库支出 ≤5%、ΔM_ALL=0；非二月不触发 |

Jev：官方垦荒「默认 0 的机构参数 + 年度国库比例拨款」**p=0.982**（`decisions/JEV-全审整改第五批-2026-10-18.json`）。

### 14.2 最终基线（第五批后）

| 项 | 结果 |
|---|---|
| pytest | **3476 tests / 0 failed / 0 errors / 2 skipped**（junit `_scratch/audit-20261017/junit-batch5.xml`，945.8s） |
| tsc | web 0 / node 0 |
| vitest | 17 files / 98 passed |

### 14.3 仍未闭环

1. **M314 物流调拨**：`logistics_coupler.dispatch_industry_logistics` 仍零生产调用；需要「何时/向谁调拨」的调度策略（会改平衡），建议单独裁定后接管线调拨相位。
2. **paperdoll**：按用户裁定**冻结**，不再改动。
3. `.git` 806.8MB + 39MB 垃圾 pack：需 owner 放行后 `git gc --prune=now`。
4. PM 多级产业链全面驱动（八大链按 PM 计算投入产出）仍属后续；本轮只接作坊产出相对倍率。