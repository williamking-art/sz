# foundation — 基础与账本层

> 迁移状态文档。承架构方案 §9-5：「**代码在新目录**」**不等于**「生产调用已接入」。
> 本文件记录**实测**状态，不写计划。

---

## 子包

- `state/` GameState、初始状态构建与状态字段注册 —— ⬜ **空（0 个实现文件）**
- `ledger/` POP/钱粮/物料权威账户与读写 API（含迁移期桥接）—— ✅ **已迁入 7 个**（含 `material_holding` 账本侧拆分）
- `persistence/` 存档读写与版本迁移 —— ✅ **已迁入 2 个**（第七包：`slots.py` + `migrations.py`，
  只取实测无业务依赖的部分；`save_game`/`load_game` **有意留下**，原因见 §五）
- `common/` numeric、errors 等无领域语义的共享工具 —— ✅ **已迁入 1 个**（`numeric`；
  ⚠️ `errors` **未迁**——它本来就是 20 行的真小模块，不是转发桩，别按"行少"误判成已迁）

## 〇、完成度实测（2026-10-07，脚本口径见下）

> 目的：防止"批次都做完了"被误读成"重组快完了"。**交接单候选（甲/乙/丙）做完 ≠ 阶段 2 做完。**

| 度量 | 实测值 | 口径 |
|---|---:|---|
| `core/*.py` 文件总数 | **94** | `ls game/core/*.py \| wc -l` |
| 已迁入新结构的模块 | **8 整模块 + 1 部分** | 整模块：money / pop_bridge / grain_bridge / numeric / pop_structure / prefecture_entity / grain_ledger / material_holding；部分：`save_load` 的 **6 个符号**（第七包，见 §五） |
| ⇒ 按模块数的进度 | **8/94 ≈ 9%** | 仅作量级参考，不是"完成度"指标 |
| `foundation/state` 实现文件 | **0** | 目录存在但空 |
| `foundation/persistence` 实现文件 | **2** | 第七包（2026-10-07）：`slots.py`、`migrations.py`；`save_game`/`load_game` 未搬，见 §五 |
| `core/workflows/` 实现文件 | **0** | 目录存在但空（§2 提案/校验/执行三段尚未落包） |
| `core/settlement/` 目录 | **不存在** | 编排仍在 `core/settlement*.py` 平铺 |
| `core/compatibility/` 实现文件 | **0** | 预留位；兼容路线已定为"旧路径薄桩"，不用集中兼容包 |
| `game/application/` 实现文件 | **2** | 2026-10-07 按 §5.2 新建：`turn_lifecycle.py` + `memory_lifecycle.py`；`commands.finish_turn` 已改薄代理 |
| `domains/` 十子域有实现的 | **1/10** | 仅 `economy`，且只有 `material_trade_ops.py` 一个文件 |
| 外部业务调用方接入新路径 | **0 个文件** | 可核分解见 §二 末：新路径 16 个引用文件 = 转发桩自身 8 + 包内互引 5 + 验收用例 3 |

**§8 五阶段定位**：阶段 0 ✅ / 阶段 1 ✅（SCC=2 + 12 反向边，2026-10-07 已校正其真实形态）/
**阶段 2 🔶 早期**（只做完账本层一小块，两个基础子包仍为零）/ 阶段 3 ⬜（前置=反向边**接口倒置**）/
阶段 4 ⬜。

⚠️ 计数教训：先前用"`≤30 行`即薄转发桩"数模块，会把 `errors.py` 这类**本来就小的真模块**误收为已迁。
分母一律以**新实现文件是否存在**为准，不看行数。

## 一、已完成（实现已迁入）

| 模块 | 新位置 | 大小 | 公开符号 |
|---|---|---:|---:|
| `money` | `foundation/ledger/money.py` | 35.2 KB | 50 |
| `pop_bridge` | `foundation/ledger/pop_bridge.py` | 25.7 KB | 32 |
| `grain_bridge` | `foundation/ledger/grain_bridge.py` | 5.6 KB | 6 |
| `numeric` | `foundation/common/numeric.py` | 2.7 KB | 8 |
| `pop_structure` | `foundation/ledger/pop_structure.py` | 12.6 KB | 19 |
| `prefecture_entity` | `foundation/ledger/prefecture_entity.py` | 11.2 KB | 24（dir() 口径）|
| `grain_ledger` | `foundation/ledger/grain_ledger.py` | 4.0 KB | 7（dir() 口径）|
| `material_holding`（账本侧）| `foundation/ledger/material_holding.py` | 36.8 KB | 49（dir()；42 实义符号含私有，7 为 typing/future 名）|
| `save_load`（**部分**·槽位机械）| `foundation/persistence/slots.py` | 3.7 KB | `SLOT_MIN` `_slot_ok` `_slot_path` `get_save_slots`（4 符号，原文逐字等价）|
| `save_load`（**部分**·旧档迁移）| `foundation/persistence/migrations.py` | 4.0 KB | `_merge_regions` `_migrate_pops_to_seats`（2 符号；仅桥导入改指新路径）|

旧路径 `core/money.py` `core/pop_bridge.py` `core/grain_bridge.py` `core/pop_structure.py`
`core/numeric.py` `core/prefecture_entity.py` `core/grain_ledger.py`
均为**薄转发桩**（11–26 行），**不复制实现**。
✅ `core/material_holding.py` 自**丙批二**起同为**纯转发桩**：账本 42 名转发
`foundation/ledger/material_holding`、交易 3 名转发 `domains/economy/material_trade_ops`，
对外 dir() 仍 52 名（42+3 实现名 + typing/future 7 名）。

🔴 **搬模块必查 `__file__` 相对路径耦合**（丙批一实测踩坑）：
`_build_tribute_index` 按 `dirname(__file__)/../../_dev_tools/sources/songshi/gong_prefecture.json`
读贡物数据，**缺文件静默返回空表**——迁入 `ledger/` 后层级差 2 级，测试直接炸出空索引。
纪律：迁移前先 `grep -n "__file__" <模块>`；此类静默路径**必须加"数据非空"哨兵断言**
（已钉在 `test_ledger_split_real_channel_nonempty`）。

✅ 阶段 1 标注的 ledger 两处跨包残余依赖（`pop_bridge→prefecture_entity`、
`grain_bridge→grain_ledger`）已随第五、六包**全部闭合**（新实现均在 `ledger/` 内、
import 改指新路径）——**ledger 包现已自足**（对外仅依赖 `content/*` 与 stdlib）。
⚠️ `pop_bridge.seat_pop_weights` 的 lazy import 包在 `try/except` 里**静默返回 []**，
路径断链不会炸 import —— 断言**权重非空**才算接通（回归已守）。

## 二、🔴 尚未接入：生产调用点仍走旧路径

**计数口径（可复现）**：`game/` + `_dev_tools/game-dev/tests/` 中 import 该模块的
**文件数**（仅排除该模块自身的转发桩与新实现；两种形态
`from core.X import` / `from core.foundation.ledger import X` 均计入；脚本 `_scratch/pe_refcount.py`）。
⚠️ 第五包当轮曾把 `_dev_tools/` 全目录扫入导致虚高（如 money 38），本表已按声明口径校正。

| 模块 | 旧路径引用文件 | 新路径引用文件 |
|---|---:|---:|
| `money` | **26** | 0 |
| `pop_bridge` | **21** | 3 |
| `grain_bridge` | **12** | 2 |
| `pop_structure` | **15** | 0 |
| `numeric` | **15** | 0 |
| `prefecture_entity` | **6** | 3 |
| `grain_ledger` | **2** | 2 |
| `material_holding` | **34** | 2 |
| `material_trade_ops`（丙批二新模块）| 0 | 2 |

⇒ 新路径引用目前**全部来自 `foundation/`/`domains/` 包内部与迁移验收用例**（甲批规则 1
「新迁入模块彼此用新规范路径」）；外部业务调用方仍 100% 走旧路径。
⇒ 上表**别横向相加**：同一文件可能同时引用多个模块，行与行有重叠，加总不是文件数。
⇒ 2026-10-07 另做一次**独立口径**的去重快测（正则与上表不同，只用于下面的分解，不用于替换上表）：
引用过新路径的文件共 **16** 个 = 旧入口转发桩自身 **8** + 新实现之间的包内互引 **5**
（`ledger/` 4 个 + `domains/economy/material_trade_ops.py`）+ 迁移验收用例 **3**。
⇒ 也就是说**外部业务调用方接入新路径 = 0 个文件**。这是"接入率 0%"的可核分解。
⇒ `material_holding` 行统计**入口模块**引用；账本实现 `foundation/ledger/material_holding.py`、
交易实现 `domains/economy/material_trade_ops.py`（dir() 同一性断言已覆盖两侧）。

**循环依赖扫描口径（丙批二起升级）**：`_scratch/mh_scc_scan_v2.py` 用**全路径节点名**
（桩与实现不再因同尾名折叠成假环），实测 **SCC=2、成员与阶段 1 基线一致**，
`foundation.*`/`domains.*` 均为叶子链不成环；旧 v1 尾名折叠口径保留作对照，两口径结论目前一致。
⇒ 符合迁移期设计，但**必须显式记录**，避免后人误以为已切换。

## 三、未完成 / 受阻

| 项 | 状态 | 说明 |
|---|---|---|
| `material_holding` | ✅ **已完成（移出本表的历史项，留此一行指路）** | 丙批一账本 42 符号入 `ledger/`（`cdc7af3933`）、丙批二交易 3 项入 `domains/economy/material_trade_ops.py`、core 收敛纯桩（`53d0a0c5d5`）；旧失败残留定性过期留档 `_scratch/mh_residue_2026-10-06/`。**`read_models` 有意不建**：读数/守恒接口按甲批归属留在 ledger，无"第三批" |
| `state/` 与其余 `domains/*` | ⬜ 空骨架 | **除 `domains/economy`（已有 `material_trade_ops`）与 `persistence`（第七包起有 `slots`/`migrations`）外均无实现**；结算域迁移属阶段 3，前置=12 条反向边**接口倒置**（阶段 1 文档 §五，2026-10-07 已校正其形态） |
| 依赖图（§8 阶段 1）| ✅ **已做**（2026-10-06 补齐）| 实测 **SCC=2**（18 模块环 + faction 2）与 12 条反向边登记，见 `specs/cross-cutting/阶段1_依赖图与循环依赖.md`；更正阶段 0「循环=0」错误结论 |

## 四、🔴 与架构方案的偏离（自查）

| 条款 | 要求 | 实际 |
|---|---|---|
| §6-6 | 包 `__init__.py` 只暴露稳定服务/类型，**不通配 re-export 整个旧模块** | 转发桩 re-export **全部符号（含私有）** |
| §8 阶段 2 | **每一小批只迁一个业务包；当轮只处理一个职责域** | 第一批一次迁了 **3 个模块** |
| §8 阶段 1 | 先产出 import 图与循环依赖 | **跳过**，直接进阶段 2 |

### `material_holding` 拆分冲突点与执行结果（✅ 已闭环）

测试 `test_seat_products_tribute.py` 曾**直接访问私有符号** `_TRIBUTE_BY_CIRCUIT`；
转发桩若只导出公开符号即 `AttributeError`。
⇒ 该 §6-6 冲突点**已裁定并解决**（2026-10-06 `2135e29f68`）：补公开读口
`tribute_circuits()`，测试改用它。
⇒ **两批拆分已按 §8 执行完毕**（丙批一 `cdc7af3933` 账本侧 / 丙批二 `53d0a0c5d5` 交易侧）。
与原计划 29 项的差异（实测修订，详见甲批文档 §六）：中间新增 `tribute_circuits`/
`HOLDER_MAP`/`HOLDER_PROVENANCE` 等公开符号、私有 helper 与常量不可跨文件拆分，
账本侧实为 **42 实义符号**；交易 3 项归 `domains/economy/material_trade_ops.py`；
"只读读数"不另立第三批（归属判据留在 ledger）。

## 五、第七包：`save_load` 为什么是"部分迁入"（2026-10-07）

按 §4.1 该搬 `save_load` → `foundation/persistence/`。**实测不允许整搬**——
逐函数扫非本层 import（脚本 `_scratch/slice7.py`）：

| 符号 | 处置 | 依据 |
|---|---|---|
| `SLOT_MIN` `_slot_ok` `_slot_path` `get_save_slots` | ✅ 迁入 `persistence/slots.py` | 自由名只有 `json/os/SAVE_DIR/builtins`，纯叶子 |
| `_merge_regions` `_migrate_pops_to_seats` | ✅ 迁入 `persistence/migrations.py` | 前者零依赖；后者只用 `foundation/ledger/` 的两个桥（**方向合法**：POP 只能走桥，ledger 不反向依赖 persistence）|
| `save_game` | ❌ 留下 | 本体无上层 import，但**调用** `_plan_schema_versions` ⇒ 间接携带 2 条反向边 |
| `load_game`（749 行，占全文 63%）| ❌ 留下 | `army_models` `blueprint_dynamic` `game_state` `longterm_task` `ministers` `settlement_imperial` —— 登记表 12 条反向边里 4 条在此 |
| `_plan_schema_versions` / `_load_situations` | ❌ 留下 | 本身就是登记在案的反向边 |
| `_safe_int` / `_safe_float` | ❌ 留下一批 | **本批未迁，但留下的理由已按实测改写**：它们其实是**纯叶子**（`_safe_int` 只用 builtins，`_safe_float` 只多用 `math`），真正阻塞的是"和第八包混批"。先前写的"有 4 个跨域调用方"**是错的**——全项目只有 `core/save_load.py` 一处 import（内部 10 个调用点）；`ai/client_utils.py:708` 与 `core/free_effect.py:30` 是**各自另写的同名 `_safe_int`（签名不同）**，`settlement_econ.py:1765` 只在注释里提到它 |
| `_strip_unknown_faction_keys` | ❌ 留下一批 | 引用 util 的 `FACTION_NAME_SET`，搬它会新造 `foundation → core` 反向导入 |
| `migrate_army_units` | ❌ 留下 | `core.army_models`（业务）|

⇒ **整搬等于把反向边搬进基础层**（正是阶段 1 文档警告的"把环搬个位置"）。所以本批只取叶子，
`persistence` 由此从零变成"有实现且方向干净"的包，剩下的按接缝逐批推进。

**等价性与不变量（全部机器校验）**
- AST 原文切片：**漂移符号 1 个 / 漂移点 2 处**。独立复核脚本
  `_scratch/b7_equiv_recheck.py`（直接从 `git show HEAD:game/core/save_load.py` 重取原文逐节点比
  `ast.dump`，不复用生成脚本）实测：6 个搬迁符号中 **5 个逐字等价**，
  唯一漂移的 `_migrate_pops_to_seats` 内含 **两处** 差异：
  ① 两处桥导入 `core.pop_bridge`/`core.grain_bridge` 改指 `core.foundation.ledger.*`（声明的机械改道）；
  ② docstring 末尾追加"⚠️ 已知静默点"一段——**不改运行时语义，但确实进 `ast.dump`**，
  所以本批的声明漂移是 **2 处而不是 1 处**，别按"只改了 import"理解。
  （`_slot_path` 第一版曾被顺手改 docstring 造成额外漂移，已还原，纠正内容改写成函数上方的
  "迁移注记"——注释不进 `ast.dump`。）
- `dir(core.save_load)` 与改动前快照求差集 = **空**。独立复核脚本
  `_scratch/b7_surface_recheck.py`（把 `git show HEAD:game/core/save_load.py` 落成临时模块
  再导入比对，不依赖改动前留存的快照）实测 **20 个非 dunder 名 / 含 dunder 共 28 名，
  lost=none、added=none**；6 个搬迁符号 `旧路径 is 新实现` **6/6 同一对象**；
  `_safe_int` 等 re-export 面未受损。
- 非空哨兵**三条**，且**都被证明会红**：① 桥路径故意写错 → `_migrate_pops_to_seats` 的
  `except: return 0` 吞掉 → 2 条用例立刻红（"没报错"证明不了接通）；恢复后与备份逐字节一致；
  ② `SAVE_DIR` 重定向同源断言（防污染玩家真档）；③ 建目录/写入路径同源断言（见下条）。
- ⚠️ 本批**未修**、仅登记：`_migrate_pops_to_seats` 与 `pop_bridge.seat_pop_weights` 同属
  "断链静默返回空/0" 形态，修它属口径变更，另立批次。
- 🔴 **本批踩中的真雷（全量实测红 3 例，不是纸面推演）**：`_slot_path` 原文 docstring 写着
  "刻意留在本模块，抽走会让 `SAVE_DIR` patch 失效"。**本批把它抽走了，这句话就成真了**——
  首跑全量 `EXIT=1`，3 例 `FileNotFoundError`（`test_m6_resources_bad_shape_falls_back`、
  `test_m7_faction_split_persisted`、`test_legacy_personal_action_migration`）：
  这些用例只 patch `core.save_load.SAVE_DIR` 再手工拼 `tmp_path/slot_N.json`，
  而 `_slot_path` 迁走后读的是**属主模块**的 `SAVE_DIR`，两边分叉。
  - **根因不是用例写错，是旧路径留了第二份真相**：`save_game` 的 `os.makedirs(SAVE_DIR)`
    读 `core.save_load` 的模块级 `SAVE_DIR`，而真正写入的路径由
    `foundation/persistence/slots.SAVE_DIR` 决定 ⇒ "建了 A 目录、写进 B 目录"。
  - **修的是生产代码那行**（本批**唯一一处函数体改动**，超出"只搬原文"，故显式声明）：
    `os.makedirs(os.path.dirname(_slot_path(slot)), exist_ok=True)`——建的就是写的。
    `core.save_load.SAVE_DIR` 仍在（`dir()` 公开面要求），但降级为**只为公开面保留**，
    源码注释已点名真正的开关在属主模块。
  - **用例侧**：`test_audit_batch1_fixes.tmp_save_dir` / `test_imperial_action._patch_save_dir`
    补 patch 属主模块（**不改断言、不改口径**，只补重定向目标）；
    `conftest._CRITICAL_SAVE_DIR_MODULES` 补入 `core.foundation.persistence.slots`
    ——同源自检必须点名真写入路径，否则补丁漏覆盖会**写进玩家真实存档目录**。
  - **新守卫 `test_save_game_creates_the_dir_it_writes_into` 已被证明会红**：把 `makedirs`
    改回 `SAVE_DIR` 形式 → `FileNotFoundError ... owner_dir\slot_4.json.tmp`（EXIT=1），
    恢复后与备份 `cmp` 逐字节一致、定向 47 例回绿。
  - 由此纠正原"前提"式写法：先前只写"依赖 conftest blanket 重定向 + session 末跳闸"，
    **实测证明该前提不足以覆盖显式 patch 单一模块的用例**。这条已落成硬断言，不再靠假设。
- 实测纠正一处假设：**新局 `GameState` 各路也没有 `seats`**（20 路全需迁移），
  所以该迁移并非只作用于旧档；docstring 的"新档开箱即带 seats"指的是首月结算/落盘之后。

引用计数（口径同 §二，`_scratch/b7_refcount.py`）：旧路径 `core.save_load` **36** 个文件、
新路径 `core.foundation.persistence` **5** 个。这 5 个**全不是业务调用方**，分解：
`game/core/save_load.py`（转发桩自身，`from` 形态 2 行）+ 本批回归用例
`test_persistence_split_b7.py`（`import … as` 形态 2 行）+ 因 `_slot_path` 搬家而必须点名属主模块的
`conftest.py`／`test_audit_batch1_fixes.py`／`test_imperial_action.py`（**只是 monkeypatch 的字符串目标，不是 import**）。
⇒ 外部业务调用方仍 100% 走旧路径。

SCC 复扫：仍 **2 环**、成员与阶段 1 基线**逐字一致**；扫描模块数 121 → **123**，
新增两个 persistence 文件**未进任何环**（`save_load` 仍在 18 模块环内，符合"只迁叶子"的预期）。

**全量验证（本批最终数，串行 + `>file 2>&1; echo EXIT=$?` 取真实退出码）**
- 首跑 `EXIT=1`：3 例红，全因 `_slot_path` 搬家导致的 `SAVE_DIR` 不同源（见上条 🔴）。
- 修后复跑 `EXIT=0`、`FAILED/ERROR` 计数 **0**、1 例 skip。
- collected **2346**（`--collect-only -q` 按文件行求和，192 个文件；脚本
  `_scratch/b7_collected.py`）＝ 批次前 **2338** + 本批新增 `test_persistence_split_b7.py` **8** 例。