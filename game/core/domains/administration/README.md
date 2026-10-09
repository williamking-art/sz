# domains/administration — 行政与官制

> **2026-10-07 第二十四包（DSH）**：新增 `read_models/` 子包，迁入 `minister_profile.py`
> （群臣档案，纯派生**读数**、只读不写 state ⇒ 按架构方案 §3.1 归 `read_models/`）。
> **2026-10-07 第二十五包（DSH）**：迁入 monthly_gazette.py（月度奏章九章）。
> **2026-10-07 第二十六包（DSH）**：迁入 minister_agent.py（官员个体 Agent 状态机）。
> **2026-10-07 第三十三包（DSH，收尾）**：迁入 estate_mechanic.py（大臣家产/建筑/投资）。
> **2026-10-07 阶段 3 首包（DSH）**：迁入 settlement_officialdom.py（官制吏制 4 个结算步骤）。
> 2026-10-06 · 阶段 0 建骨架。
> **2026-10-07 第十九包：本包已有实现**（`institution.py`，`git mv` 自 `core/`，历史保留）。
> `officialdom.py` / `clerks.py` / `minister_*.py` **仍在 `core/`**，理由见「未随批搬的候选」。

## 拥有的规则

官员履历、任免、官僚/吏员**编制参数**、机构规则（事权 → 执行主体）

## 已迁入实现（第十九包，2026-10-07）

| 文件 | 来源旧路径 | 公开面（dir() 实测） | 叶子资格 |
|---|---|---|---|
| `institution.py` | `core/institution.py` | 桩 **23** 名（31 去掉 8 个 dunder；含私有 `_SPEC`/`_matter_of`/`_org_table`/`_executor_by_*`/`_EXECUTOR_KEYS` 与 typing 绑定名 `Any`/`Dict`/`Tuple`）| 🔴 **零 `core` import**：顶层只 `typing` + `content.data.INSTITUTION_PARAM_SPEC`，函数内只 `content.data.normalize_tier` / `content.ministers.data`。由 `test_new_home_is_a_leaf` 钉住 |
| `read_models/minister_profile.py` | `core/minister_profile.py` | 桩 **3** 名（含私有 `_portrait_url`；`test_portrait_*` 直接取该私有名，故桩面必须含之）| ✅ 对 `core` 平铺零反向边 |
| `monthly_gazette.py` | `core/monthly_gazette.py` | 桩 **23** 名 | ✓ 只 import `__future__`+`typing`，**零 core/content import**；`settlement.py` 是唯一生产调用方，已同批改指新路径 |
| `minister_agent.py` | `core/minister_agent.py` | 桩 **19** 名 | ✓ 只 import `__future__`+`typing`，**零 core 依赖**；4 个生产调用方（`decree_confidential` / `decree_confirm` / `ministry_council` / `settlement_decree`）已同批改指新路径 |
| `estate_mechanic.py` | `core/estate_mechanic.py`（第三十三包 2026-10-07，`git mv`）| 桩 **31** 名 | ✓ 只 import `content.data` / `content.ministers.*` ⇒ 零 `core` 依赖；6 个消费方（`game_state` / `save_load` / `settlement_econ` / `backend/server` / `content/ministers/persona` / `foundation/ledger/money`（docstring 引用））已同批改指新路径。⚠️ M7 + M9 两处 monkeypatch 已改指实现模块，否则会打在旧桩上静默失效 |
| `settlement_officialdom.py` | `core/settlement_officialdom.py`（**阶段 3 首包** 2026-10-07，`git mv`）| 桩 **7** 名 | ✓ 4 个结算步骤（`_settle_officialdom`/`_settle_clerks`/`_settle_clan`/`_settle_upkeep`）**同属官制吏制一域**，无跨域混入；自身依赖仅 `officialdom`/`clerks`/`domains.administration.institution`/`building_jobs`/`settlement_common`；唯一调用方 `settlement_steps.py`（编排器）已同批改指新路径。⚠️ 该模块**原不在 [17] 大环内**（是挂环外的叶子）⇒ 本包不减环，收益在「结算步骤归属业务部」本身 |

职责边界（本模块自己的口径，不是本次迁移新增）：**改制＝移动参数，不是新建系统**——
只做三件事：单点约束参数值域、给结算提供 `get()`/`set_param()`、给 `free_effect`
的 `institution` 字段与 `/api/readouts` 供读数。事权校验（`check_authority`/`resolve_executor`）
复用 `content/ministers/data.py` 的 `AUTHORITY_MATTERS` 与 `CENTRAL_ORG_INFO`，
运行期以 `state.central_orgs` 活账为准——**没有新开账本**（POP 挂载律的同一模式）。

### 消费方改指（判据④，同批完成）

生产侧 **6 文件 / 7 引用点**已改指新路径，旧路径 `core.institution` 生产引用 **0**：

```
game/core/clerks.py:37                      from core.domains.administration import institution as _inst
game/core/officialdom.py:47                 同上
game/core/free_effect.py:260                同上（函数内）
game/core/settlement_finance.py:93,1002     同上（函数内，两处）
game/core/settlement_officialdom.py:105     同上（函数内）
game/backend/server.py:849                  from core.domains.administration.institution import describe
```

测试侧 **5 文件**仍走旧桩（阶段 4 的兼容门面生效面，不是遗漏）。
计数可复现：`_scratch/b19_refcount.py`（AST，只计两种导入形态，排除桩自身与实现自身）。

🔴 **勘察踩坑（务必读）**：第一版按 `from core.institution import …` 形态扫调用方，
只量到 **1 个**消费方（`server.py`）；实际另有 **6 处**写作 `from core import institution as _inst`。
按名字 grep 也会漏（`_inst` 是别名）。**调用方必须按导入来源解析这三种形态**：
`import core.X` / `from core.X import …` / `from core import X [as Y]`（脚本 `_scratch/b19_consumers.py`）。
同一盲区让既有 SCC 扫描器 `mh_scc_scan_v2.py` **一条这类边都没计过**，影响见
`_dev_tools/game-docs/specs/cross-cutting/阶段1_依赖图与循环依赖.md` §一之补（v3 已把环成员从 16 更正为 17）。

### 本批钉住的隐患类型（都有永久断言）

- **桩背后的共享字典**：`_SPEC` 是 `content.data.INSTITUTION_PARAM_SPEC` 的别名。
  若桩自己 `dict(...)` 复制一份，值域校验就会两套真相（第十八包 `_TRADE_LEDGER` 同型）
  ⇒ `test_spec_and_tier_tables_are_one_shared_object` 断言 `桩 is 实现 is content.data 那份`。
- **旧桩不是行为开关**：打在桩上的 patch 不影响实现 ⇒ `test_stub_is_not_a_behavior_switch`，
  并常驻扫描全测试目录，禁止任何用例把 `core.institution` 当 patch 提供方。
- **`try/except` 会静默吞断链**：`_org_table` 的回退分支捕获一切异常返回 `{}` ⇒
  `test_real_content_channels_are_non_empty` 直接断言机构表非空且含「户部」、户部事权含「官营放贷」。
- **变异实验**（证明断言不是空跑，均已恢复并 `cmp` 逐字节一致）：
  桩漏转发 `TIER_STEP` ⇒ 2 条红；桩内自带 `clamp` 实现 ⇒ 1 条红；
  `clerks.py` 退回旧路径 ⇒ b9 生产改道用例红。

## 未随批搬的候选（不是遗漏，各有实测理由）

| 候选 | 实测事实（2026-10-07） | 为什么本批不搬 |
|---|---|---|
| `officialdom.py` | 884 行；唯一的 `core` 平铺依赖 = `core.faction_basis`（:104、:131 两处函数内） | `faction_basis` 本身在 **2 模块环**（`faction_basis ↔ faction_metrics`）且未迁；本批只交"开包 + 首个候选"，不与环内模块耦合着搬 |
| `clerks.py` | 436 行；唯一平铺依赖 = `core.officialdom`（:423 函数内） | 依赖 `officialdom` ⇒ 必须**同批或按序**搬，先搬 clerks 会让包内出现"新包引旧平铺、旧平铺又在新包"的绕行 |
| `minister_profile.py` / `minister_agent.py` | 89 / 220 行；**零 `core` import**（真叶子） | §7 明令"AI Agent/画像与任免制度分离"——`minister_agent` 属 AI 基建适配，不进官制包；`minister_profile` 的归属需先裁定（画像数据 vs 官制规则），属**判责**不是结构迁移 |
| `institution.py` 的其余同域参数表 | `content/data_constants.py` 的 `FREE_EFFECT_CAP["institution"]` 等 | 静态内容留 `content/`，核心包可依赖内容表，内容层**不得反向导入**核心（§3.1） |

## 边界

- 向下依赖 foundation（账本/状态）与 game/content（数据）；**不得反向导入 workflows 或上层**。
- 机制间协作**经显式接口**，不得跨域读写私有内部结构。
- 读数是只读投影，**不得成为结算算法权威**。

## 迁移状态

**已开始**（第十九包，2026-10-07）：`institution` 已迁入并完成生产改道；
包内其余候选见上表，均为**待判责/待排序**，不是未完成的本批工作。

## 官僧子池写入纪律（2026-10-08 定）

两条不变量（由 `_norm_subpool_row` 单点维护，**州府级与路级共用同一口径**）：

1. `officials + clerks == size`
2. `on_post + waiting + sinecure == officials`

- `ensure_subpools(pref)` 已下沉 ⇒ **逐治所**维护（各治所以自身 `size` 为权威）；
  未下沉 ⇒ 原路级路径（回退分支）。
- **分配依据**：若路级已有官/史总数，按各治所 `size` 加权拆分；
  无依据时回落 `CLERK_PER_OFFICIAL`（**不捣造比例**）。

实施：批 1-A `f5d2e5c3da`。
