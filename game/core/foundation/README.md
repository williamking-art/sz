# foundation — 基础与账本层

> 迁移状态文档。承架构方案 §9-5：「**代码在新目录**」**不等于**「生产调用已接入」。
> 本文件记录**实测**状态，不写计划。

---

## 子包

- `state/` GameState、初始状态构建与状态字段注册 —— ⬜ **空（0 个实现文件）**
- `ledger/` POP/钱粮/物料权威账户与读写 API（含迁移期桥接）—— ✅ **已迁入 7 个**（含 `material_holding` 账本侧拆分）
- `persistence/` 存档读写与版本迁移 —— ✅ **已迁入 2 个**（第七包：`slots.py` + `migrations.py`，
  只取实测无业务依赖的部分；`save_game`/`load_game` **有意留下**，原因见 §五）
- `common/` numeric、errors 等无领域语义的共享工具 —— ✅ **已迁入 2 个模块**（`numeric` + `errors`；
  第八包又向该模块**并入 2 个符号** `_safe_int`/`_safe_float`，仍是 1 个文件，别误数成 2 个）；
  ⚠️ 计数教训保留：先前用"`≤30 行`即薄转发桩"数模块，会把 `errors.py` 这类**本来就小的真模块**误收为已迁——
  `errors` 直到第十一包才**真的**迁入 `foundation/common/errors.py`（见 §九），别把"小"当"已迁"）

## 〇、完成度实测（2026-10-07，脚本口径见下）

> 目的：防止"批次都做完了"被误读成"重组快完了"。**交接单候选（甲/乙/丙）做完 ≠ 阶段 2 做完。**

| 度量 | 实测值 | 口径 |
|---|---:|---|
| `core/*.py` 文件总数 | **94**（含 `__init__.py`）⇒ 有效平铺模块 **93** | `ls game/core/*.py \| wc -l`；分母口径见 `_scratch/b19_completion.py` |
| 已迁入新结构的模块 | **22 整模块 + 2 部分** | 整模块：…（前 17 个见 §十二~§十五）+ `market` / `hoard_settle` / `regime_fiscal`（第十八包，入 `domains/economy`）+ `institution`（第十九包，入 `domains/administration`）+ **`literacy`**（第二十包，入 `domains/culture`）；部分：`save_load` 的 **6 个符号**（第七包，§五）+ `save_load_util` 的 **2 个符号**（第八包，§六）|
| ⇒ 平铺层还剩多少实现 | **71 / 93 = 76.3%**（纯转发桩 22）| 取代此前写的"8/94 ≈ 9%"（那是早期快照，且分母含 `__init__.py`）。口径：AST 判"模块体有无 FunctionDef/ClassDef"，脚本 `_scratch/b19_completion.py`；**同脚本交叉核对**桩集合 == b9 守卫声明的 `MIGRATED_OLD`（22 == 22，零差集）|
| `foundation/state` 实现文件 | **0** | 目录存在但空 |
| `foundation/persistence` 实现文件 | **2** | 第七包（2026-10-07）：`slots.py`、`migrations.py`；`save_game`/`load_game` 未搬，见 §五 |
| `core/workflows/` 实现文件 | **0** | 目录存在但空（§2 提案/校验/执行三段尚未落包） |
| `core/settlement/` 目录 | **不存在** | 编排仍在 `core/settlement*.py` 平铺 |
| `core/compatibility/` 实现文件 | **0** | 预留位；兼容路线已定为"旧路径薄桩"，不用集中兼容包 |
| `game/application/` 实现文件 | **2** | 2026-10-07 按 §5.2 新建：`turn_lifecycle.py` + `memory_lifecycle.py`；`commands.finish_turn` 已改薄代理 |
| `domains/` 十子域有实现的 | **6/10** | `economy`(**6**)、`diplomacy`(2)、`production`(2)、`politics`(2)、`administration`(1，第十九包)、`culture`(1，第二十包)；其余 4 个子域仍空 |
| 外部业务调用方接入新路径 | **41 个文件 / 90 引用点**（第九包，2026-10-07） | 此前为 **0**；判据④达成过程、口径与踩坑见 §七。计数脚本 `_scratch/b9_newpath_count.py`（AST）；生产侧旧桩路径引用点已归零（`_scratch/b9_scope_measure.py`） |

**§8 五阶段定位**：阶段 0 ✅ / 阶段 1 ✅（SCC=2 + 12 反向边，2026-10-07 已校正其真实形态）/
**阶段 2 🔶 进行中**（已迁模块的四条判据**全部成立**，含 ④ 生产改道；但阶段 2 的范围是"所有低耦合叶子"，
`save_load` 只剩反向边阻塞、其余未迁叶子仍在原地）/ 阶段 3 ⬜（前置=反向边**接口倒置**）/
**阶段 4 🔶 已开始**（2026-10-07 第九包：生产侧旧路径引用清零；测试侧仍走旧桩=兼容门面生效面，
"旧入口退役"仍未做）。

⚠️ 计数教训：先前用"`≤30 行`即薄转发桩"数模块，会把 `errors.py` 这类**本来就小的真模块**误收为已迁。
分母一律以**新实现文件是否存在**为准，不看行数。

## 一、已完成（实现已迁入）

| 模块 | 新位置 | 大小 | 公开符号 |
|---|---|---:|---:|
| `money` | `foundation/ledger/money.py` | 35.2 KB | 50 |
| `pop_bridge` | `foundation/ledger/pop_bridge.py` | 25.7 KB | 桩 32 / 实现顶层 35→36（第十二包加 `split_int` 显式接口；旧私有名留别名但**不外泄到桩面**）|
| `grain_bridge` | `foundation/ledger/grain_bridge.py` | 5.6 KB | 6 |
| `numeric` | `foundation/common/numeric.py` | 2.7 KB | 8 |
| `pop_structure` | `foundation/ledger/pop_structure.py` | 12.6 KB | 19 |
| `prefecture_entity` | `foundation/ledger/prefecture_entity.py` | 11.2 KB | 24（dir() 口径）|
| `grain_ledger` | `foundation/ledger/grain_ledger.py` | 4.0 KB | 7（dir() 口径）|
| `material_holding`（账本侧）| `foundation/ledger/material_holding.py` | 36.8 KB | 51（dir()；第十包起含 `attribute_to_seats`/`route_of` 两个显式接口，旧私有名留作别名，**桩面仍 52**）|
| `errors` | `foundation/common/errors.py` | 1.1 KB | 1（`AIRuntimeError`；第十一包，模块内**零 import**）|
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
| `money` | **8** | 9 |
| `pop_bridge` | **8** | 17 |
| `grain_bridge` | **3** | 11 |
| `pop_structure` | **4** | 12 |
| `numeric` | **2** | 18 |
| `prefecture_entity` | **3** | 5 |
| `grain_ledger` | **2** | 2 |
| `material_holding` | **20** | 11 |
| `material_trade_ops`（丙批二新模块）| — | 5 |
| `save_load` | **36** | —（`save_load` 只迁出 6 个符号，桩本体仍是主实现）|
| `save_load_util` | **3** | —（同上，迁出 2 个符号）|

🔴 **本表已于第九包（2026-10-07）重算并替换**，脚本 `_scratch/b9_refcount_table.py`。
表内两列都按 README 声明口径计 **game/ + tests/** 的文件数，所以：
⇒ **"旧路径引用文件"这一列现在几乎全是测试侧**——8 个已迁模块在**生产侧**的旧路径引用
已 **归零**（`_scratch/b9_scope_measure.py` 复扫 = 0 文件 / 0 引用点），
测试仍走旧桩＝兼容门面生效面（阶段 4 明文允许）。
⇒ **外部业务调用方接入新路径 = 41 个去重文件 / 90 引用点**
（`_scratch/b9_newpath_count.py`，与上表脚本**相互独立、同口径互证**）。
⇒ 上表**别横向相加**：同一文件可能同时引用多个模块，行与行有重叠（旧列合计 89、新列合计 90
只是行加总，不是文件数；去重生产业务文件才是 41）。
⇒ 判据④的达成过程、本批踩到的"分流模块整体改道"bug 与常驻守卫见 §七。
⇒ `material_holding` 行统计**入口模块**引用；账本实现 `foundation/ledger/material_holding.py`、
交易实现 `domains/economy/material_trade_ops.py`（dir() 同一性断言已覆盖两侧）。

**循环依赖扫描口径（丙批二起升级）**：`_scratch/mh_scc_scan_v2.py` 用**全路径节点名**
（桩与实现不再因同尾名折叠成假环），实测 **SCC=2、成员与阶段 1 基线一致**，
`foundation.*`/`domains.*` 均为叶子链不成环；旧 v1 尾名折叠口径保留作对照，两口径结论目前一致。
⇒ 符合迁移期设计，但**必须显式记录**，避免后人误以为已切换。

> 🔴 **第十九包（2026-10-07）再升级：v2 本身有两处盲区，已被 `mh_scc_scan_v3.py` 取代。**
> ① `from core import X` 形态一条都不计；② 节点名用斜杠、边名用点分，
> 所有指向 `foundation.*` / `domains.*` 的边在 DFS 里被丢 ⇒ **v2 只在 core 顶层平铺子图上找环**。
> v3 实测平铺大环成员 **[16] → [17]**（`settlement_military` 一直在环内）。
> ⇒ 本文件各批次记录（§六~§十六）里写的 `SCC [16]+[2]` 是**当时 v2 口径下的测量**，
> 保留不追改；**当前事实以 v3 的 `[17]+[2]` 为准**，跨批比较数字必须先确认同口径。
> 成因、逐条边与纪律见 `阶段1_依赖图与循环依赖.md` §一之补。

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
## 六、第八包：`save_load_util` 的两个数值件并入 `common/numeric`（2026-10-07）

`_safe_int` / `_safe_float` 原文迁入 `foundation/common/numeric.py`（该模块本来就是"数值工具
单一权威"），`core/save_load_util.py` 改显式转发，`core/save_load.py` 的取用改指新路径（少一跳）。

**为什么落 `common/` 而不是 `persistence/`**：这两个函数体**零存档语义**（只按类型/可转换性判定），
符合架构方案 §106「跨域且无业务归属」；留在 persistence 会把通用件锁进专用目录（§196 禁垃圾桶，
也禁"通用件藏在专用层"）。⚠️ 刻意**不进 `__all__`**、不进 `core.numeric` 公开面（下划线名按模块私有，
调用方显式 import），由 `test_not_added_to_numeric_public_api` 锁住。

| 符号 | 处置 | 依据（全部实测） |
|---|---|---|
| `_safe_int` `_safe_float` | ✅ 并入 `common/numeric.py` | 函数体自由名只有 builtins（+ `_safe_float` 的 `math`），零存档语义 |
| `_strip_unknown_faction_keys` | ❌ 留下 | 引用同文件 `FACTION_NAME_SET`（由 `content.data.FACTION_NAMES` 造），单搬它要拆一对耦合符号 |
| `FACTION_NAME_SET` / `FACTION_NAMES` | ❌ 留下 | 集团名是**业务口径**，不属 `common`；搬进基础层就是把业务词汇下沉 |
| `migrate_army_units` | ❌ 留下 | 函数内 `from core.army_models import …`，构成 persistence/common→业务 反向边 |
| `math`（`save_load_util` 顶层名） | ⚠️ **保留但已无使用者** | 只为 `dir(core.save_load_util)` 公开面（8 名）不掉而留着；源码注释已点名"别按未使用删" |

**等价性与不变量（机器校验，脚本都落盘可复跑）**
- `_scratch/b8_equiv_check.py`：对 `git show HEAD:game/core/save_load_util.py` 重取原文比 `ast.dump`
  ⇒ **漂移 0 处**（本批无任何声明改道）；旧文件**不残留同名 def**，只剩一条转发 `ImportFrom`。
- `_scratch/b8_surface_recheck.py`：`core.save_load_util` / `core.save_load` /
  `core.numeric` 三条旧路径 `dir()` 与迁移前冻结快照（`_scratch/b8_surface_before.json`）
  **完全一致**；只有新落点 `core.foundation.common.numeric` 多出 `_safe_int`/`_safe_float`（预期）。
- 同一性：`save_load_util._safe_int is numeric._safe_int is save_load._safe_int`（`_safe_float` 同）
  ⇒ 2/2 三路径同对象。
- **三类"会红证明"都跑过**（`_scratch/b8_mutation_proof.py`）：语义真值表 / 同一性 / 公开面
  各造一次破坏，三次 `EXIT=1`，还原后逐字节一致且全文件 `EXIT=0`。
  ⚠️ 变异 B 一开始差点做成**假证明**：把复制实现插到转发 import **之前**，import 会把名字绑回真实现、
  断言根本不红；改成追加到文件末尾才真验出。

**新登记的两条事实（不是本批修的）**
1. `_safe_int` 与 `parse_number` 是**刻意并存的两套口径**，实测三处差异：
   缺失回 `None` vs `0.0`；`_safe_int("2.7")` → **`None`（判为缺失，不是截断）** vs `2.7`；
   `_safe_int(2.7)` → `2`（截断）。⇒ 存档里整数字段被写成小数串时**静默按缺失处理**，
   这一条此前无人写过。合并属口径变更，另立批次。
2. `_safe_int` 在仓库里有**三处同名不同实现**（`save_load_util.py:63` 权威份、
   `ai/client_utils.py:708` 带区间夹取、`core/free_effect.py:30` 无区间）。
   按名字 grep 会得跨实现假命中——本包写引用计数时就是这么踩的（注释里的
   `test_persistence_safety` 被文本正则误判成 `_safe` 导入），最终改 **AST 按导入来源**判定。

**引用计数（`_scratch/b8_refcount.py`，AST 按导入来源判定）**
- `from core.save_load_util import` **2** 个文件（`core/save_load.py` + 审计用例）；
  `import core.save_load_util` **1** 个（本批回归用例）。
- `from core.foundation.common.numeric import` **3** 个文件：`core/numeric.py`（转发桩）、
  `core/save_load_util.py`（本批新转发）、`core/save_load.py`（改指新路径）。
- **按导入来源**真正取用 `_safe_*` 的只有 `core/save_load.py` 一个业务文件 ⇒ 外部业务接入仍为 0。

**全量验证（串行 + `>file 2>&1; echo EXIT=$?`）**
- `EXIT=0`、`FAILED/ERROR` 计数 **0**、1 例 skip；**本批无回归**（第七包那类红没再出现）。
- collected **2376** = 批次前 **2346** + 本批新增 `test_common_numeric_split_b8.py` **30** 例
  （求和脚本 `_scratch/b7_collected.py`，`--collect-only -q` 按文件行相加；汇总行本机不可信）。
- SCC 复扫：仍 **2 环**、成员与阶段 1 基线一致，扫描模块数 **123**（本批未新增文件，
  只是把两个符号搬进既有模块）⇒ **无新环**。

## 七、第九包：阶段2 判据④ —— 生产调用改指新路径（2026-10-07）

架构方案 §8 的"做完"四判据里，**④ 外部调用方引用改指新路径**此前**全部未做**
（README §〇 原记 "外部业务调用方接入新路径 = 0 个文件"）。本包把 8 个已迁模块的
生产侧旧桩引用一次性改指到新路径，并把它做成**常驻守卫**。

**改道面（AST 定位 + 文本级改行，绝不 `ast.unparse` 重建）**

| 项 | 实测值 | 口径 |
|---|---:|---|
| 改前生产旧路径引用点 | **91** / 42 文件 | `_scratch/b9_scope_measure.py`（排除桩自身与实现自身） |
| 改后生产旧路径引用点 | **0** / 0 文件 | 同上，复扫 |
| 改道形态 | `ImportFrom` 90 + `Import` 1 | 那条 `import core.prefecture_entity as pe` 在 `transport.py:107` |
| 改后新路径业务消费 | **41 文件 / 90 引用点** | `_scratch/b9_newpath_count.py` |
| diff 纯度 | 91 增 / 91 删，**非纯路径替换的行对 = 0** | 逐行对：把旧名换成新名后必须与加行完全相等 |
| 桩 / 实现文件改动 | **0 个** | 本批只动消费者；`dir()` 公开面无需重测即不变 |
| 测试侧 | 45 文件 / 73 引用点**保留旧路径** | 阶段 4 明文允许"测试仍用旧路径时保留兼容门面" |

**🔴 本批踩到的真 bug（也是本批最有价值的产出）**

`core.material_holding` 的符号**分两个家**：账本项在 `foundation/ledger/material_holding.py`，
丙批二的 3 个交易项（`commodity_dims` / `supply_merchant_materials` / `trade_material`）在
`domains/economy/material_trade_ops.py`。我按"一个模块 → 一个新模块"**整体改道**，
把交易符号也指到了 ledger ⇒ `cannot import name 'commodity_dims'`，
而它发生在**月度结算内部**的延迟 import 里，于是**级联炸穿 50 个测试文件**。

修法是**符号级**改道，并把"家"的判定从手抄映射改成**从桩自己的转发语句里读**：
`_scratch/b9_fix_wrong_home.py`（建 191 个名字的 `符号 → 实现模块` 表 → 扫全仓新路径 import
→ 名字不在声明模块上就报/改）。修后复扫 **指错家 = 0**，全量回 `EXIT=0`。

**常驻守卫 `test_newpath_imports_b9.py`（4 条，已证明会红）**
1. `game/` 内每一处 `from core.foundation.* / core.domains.* import X`，X 必须真在该模块上（扫到 118 个名）；
2. 生产代码不得再 import 8 个已迁模块的旧桩路径（判据④不回退）；
3. 桩面 ⊆ 实现面、**逐名同一对象**、且**桩内不自带实现**；每个名字的"家"取自桩的转发语句；
4. 分流事实钉死：3 个交易项的真实家必须是 `material_trade_ops`。

**会红证明**：把 `market_readout.py` 的 `commodity_dims` 故意改回 ledger ⇒ 守卫第 1 条
`EXIT=1` 并直接指到 `game/core/market_readout.py:131`；还原后与备份 `cmp` 逐字节一致。

**三条方法教训（都写进了守卫或脚本，不靠记性）**
- **安全扫描器本身要先证会响**。第一版 patch 扫描报"0 命中"，我以为没有隐患；
  拿已知有 12 处命中的 `core.save_load` 做对照组一跑——**它也是 0**，说明扫描器漏了
  `monkeypatch.setattr(模块别名, ...)` 这种最常见写法。v2 先把别名解析成点分路径后才可用。
- **"提供方 patch" 改道必须与消费者同批改**。`test_error_observability_settle.py` 有 4 处
  按旧路径打补丁到已迁提供方（3 处 `core.money`、1 处参数化 `"core.pop_structure"`）。
  消费者改指实现后，打在桩上的 patch 够不到真来源——这类**不会假绿**（断言"失败必须可见"会红），
  但必须同步把 patch 目标改到真实现，否则等于把可观测性用例废掉。
- **判据方向别写反**：桩的不变量是"桩 ⊆ 实现且同对象"，不是"桩覆盖实现全部名字"；
  也不是"一个桩对一个实现"。两条都反了就会得到成批假红，反过来就会漏掉本次这种真红。

**验证**：全量串行 `EXIT=0`、`FAILED/ERROR=0`；SCC 仍 **2 环**、成员与阶段 1 基线一致
（扫描 123，改道**未新增环**）；`game/core` 全 123 模块 import 冒烟 0 失败。
collected 由 2376 → **2380**（守卫 4 条）。

## 八、第十包：私有符号接口化，销 §6 规则 2 偏离（2026-10-07）

`domains/economy/material_trade_ops.py` 此前借用 ledger 的两个私有符号
（`_attribute_to_seats` / `_route_of`），是架构方案 §6 规则 2「不得跨域读写私有内部函数」的
**已登记偏离**。本包把它们提升为 ledger 显式接口并销账。

| 项 | 处置 | 说明 |
|---|---|---|
| `attribute_to_seats` / `route_of` | ✅ 新公开名（进 `__all__`） | ledger 实现里的定义改名；行为**逐字未动** |
| `_attribute_to_seats` / `_route_of` | ⚠️ 保留为**兼容别名** | `core/material_holding.py` 薄桩仍转发旧名，桩的 `dir()` 公开面必须守恒；新代码不得再用 |
| `material_trade_ops` 借用 | ✅ 改读公开名（3 个调用点 + import 行） | 顶部"迁移期已知妥协"注记改为"已销账" |
| `grain_bridge → pop_bridge._split_int` | ❌ **本包不销**（同包内，非跨域） | 守卫单列"只减不增"清单登记；销账动作同样是接口化，另批处理 |
| `material_trade.py:143 _route_of` | ❌ 不合并 | 与 ledger 那份**逐字相同**的私有副本（同名不同实现第三处）；删重复属另批工作，已在 `route_of` docstring 留指路 |

**实现面 49 → 51 名**（多出 2 个显式接口），**桩面 52 名不变**——这正是接口化应有的方向：
新 API 走新路径，旧路径公开面一格不多、一格不少。

**新增常驻守卫 `test_ledger_interface_b10.py`（5 条）**
1. 公开名存在且进 `__all__`，旧私有名是同对象别名；
2. 桩面守恒：旧名仍在、**新接口名不得回流旧路径**；
3. 🔒 **跨包不得 import 他模块下划线符号**（规则 2 常驻拦截；同包欠账走"只减不增"清单）；
4. `attribute_to_seats` 真实通道非空：Σ治所桶「木」**精确 == 100**；
5. `route_of` 只按**对象同一性**匹配（内容相同但不同对象不得认同一 POP）。

**两条"方向判错"的教训（都改到了实现里，不是改断言放宽）**
- 既有 `test_material_holding.py` 把不变量写成「实现面 ⊆ 桩面」，接口新增名于是被要求
  同时出现在旧路径上——那是**扩大旧路径 API**，违反 dir() 守恒。正确方向是「**桩面 ⊆ 实现面
  且逐名同一对象**」；例外（新接口名）必须点名，不许整体放宽。
- 同一轮里我还把 `material_holding` 当成"单一家"比对，撞上它其实是**分两家**的桩
  （`commodity_dims` 等来自 `domains/economy`）。凡是分流桩，名字的家必须**按桩自己的转发语句**解析
  ——这条已是 `test_newpath_imports_b9.py` 的固定做法，本包把 `test_material_holding.py` 也统一过去。

**验证**：全量串行 `EXIT=0`、`FAILED/ERROR=0`；collected **2386** = 批次前 2380 + 本批 6 例
（b10 5 条 + `test_material_holding.py` 新增 1 条）；SCC 仍 **2 环**、成员同基线；
"指错家"静态复扫 **0**；ledger/桩/交易三侧子集回绿。

## 九、第十一包：`errors` 迁入 `foundation/common/`（2026-10-07）

§106 点名 `common/` 该装 "numeric、errors 等真正跨域且无业务归属的基础工具"。
`numeric` 早在第二批就进去了，`errors` 一直是**未迁**状态——
README 原先那句"别按行少误判成已迁"就是为它写的（它 20 行是真小模块，不是桩）。本包完成迁入。

| 项 | 处置 | 实测 |
|---|---|---|
| `AIRuntimeError` | ✅ 原文迁入 `foundation/common/errors.py` | 对 `git show HEAD:game/core/errors.py` 取原文比 `ast.dump` ⇒ **等价**（第一次写入把 `newline=''` 漏在写侧，`\r\n` 变成 `\r\r\n` ⇒ 等价校验直接红，改回两侧同参后通过） |
| `core/errors.py` | ✅ 收敛为显式转发桩 | `dir()` 公开面**恰好** `{AIRuntimeError}`，不多不少 |
| 生产侧 8 处 import | ✅ **同批**改指新路径（`ai/client.py` 5、`backend/server.py` 1、`core/commands.py` 1、`core/commands_decree.py` 1） | 复扫生产侧 `core.errors` 引用 = 0（判据④同批达成，不留半成品） |
| 测试侧 5 处 | 保留旧路径 | 兼容门面生效面 |
| `core.errors` 纳入常驻守卫 | ✅ 加进 `test_newpath_imports_b9.py` 的 `MIGRATED_OLD` 与桩面清单 | 判据④从此对 9 个模块持续生效 |

**新增守卫 `test_common_errors_b11.py`（5 条）**
1. 桩公开面**恰好**等于 `{AIRuntimeError}`（防"顺手多转发一个名字"）；
2. 旧路径 `is` 新实现（两份异常类会让上层 `except` 漏捕——这是本迁移唯一的真风险）；
3. 🔴 **新模块内 `import` 语句必须为 0**：`errors` 存在的理由就是"不导入任何业务模块，供各层共享"，
   迁移时手滑加一行 `from content.data import AI_ERROR_CODES` 不会报错，但会把依赖引进基础层；
4. 异常语义逐条锁：默认构造 `code=''`、传 `None` 回落空串、`isinstance(RuntimeError)`、
   按 `RuntimeError` 捕获路径仍在、可再子类化；
5. 生产侧不得再 import `core.errors`（AST 扫，桩自身除外）。

**验证**：全量串行 `EXIT=0`、`FAILED/ERROR=0`；collected **2391** = 批次前 2386 + 本批 5 例；
SCC 仍 **2 环**、成员与阶段 1 基线**逐字一致**，扫描模块数 123 → **124**（新增 `errors.py`），
新文件未进任何环；`core.errors` 语义实测（raise/except/`.code`/子类化）全部通过。

## 十、第十二包：`_split_int` 提升为显式接口，同包私有欠账清零（2026-10-07）

第十包销的是**跨包**借用（§6 规则 2），当时把唯一一条**同包**借用
（`grain_bridge.py:100` 借 `pop_bridge._split_int`）登记进守卫的"只减不增"清单。本包把它销干净。

| 项 | 处置 | 说明 |
|---|---|---|
| `split_int` | ✅ 新公开名，**进 impl `__all__`** | 守恒基元：按权重拆整数、**尾差归权重最大者**、Σ 精确等于 total |
| `_split_int` | ⚠️ 保留为兼容别名（同一对象） | `core/pop_bridge.py` 桩的 `dir()` 与 `__all__` **各 32 名**，迁移前后**逐字相等**——改名不许缩桩面 |
| impl 内 5 处自用 | ✅ 改读公开名 | impl 里 `def split_int` 仅 1 处、无 `_split_int` 的 def（防双实现，用例锁住） |
| `grain_bridge` 借用 | ✅ 改读 `split_int` | AST 复查：`grain_bridge` 从 `pop_bridge` 导入的名字里**不再有下划线名** |
| `KNOWN_SAME_PKG_DEBT` | ✅ **清空** | 留空本身就是判据——今后再借同包私有符号，`test_ledger_interface_b10.py` 直接红 |

**`split_int` 的返回形状有语义，接口化时逐条钉死**（`test_pop_bridge_interface_b12.py`）：
`total == 0` 或权重和 `<= 0` ⇒ **每个治所 0**；**没有治可拆** ⇒ `{}`。
调用方靠这个区分"拆了但都是 0"与"无治可拆"，后续重构**不得**顺手统一成空表。
另锁：`Σ == total` 对多组权重/额度遍历成立、`split_int(10,[(a,1),(b,2)]) == {a:3,b:7}`（尾差进 b）。

**验证**：全量串行 `EXIT=0`、`FAILED/ERROR=0`；collected **2395** = 批次前 2391 + 本批 4 例；
SCC 仍 **2 环**、成员与阶段 1 基线一致；桩面快照（迁移前落盘
`_scratch/b12_stub_surface_before.json`）与迁移后**完全相等**。

## 十一、第十三包：两条反向边真被拆出环（阶段 3 第一刀，2026-10-07）

阶段 1 文档 §五 把 12 条反向边的"替代接口方向"**按文件名猜**，实测抓到两处错标：
`asset_context:176` 与 `focus_mechanic:445` 被写成"读数应从读数服务取"，
实际取用的是 `settlement_common` 的**守恒写通道**
（`transfer_public_funds_to_pops` / `_distribute_cash`）。
按错标签去做只读服务 ⇒ 直接破 `ΣΔ == 0`。⇒ 先逐站点判性（**写 11 / 只读 5**，
实测表见 `阶段1_依赖图与循环依赖.md` §五之补），再决定动哪条。

**本批实际改动**（只动这 2 个站点，不做需要裁定的注册表设计）：

| 项 | 处置 | 说明 |
|---|---|---|
| `distribute_cash` | ✅ `_distribute_cash` 提升为显式接口 | 别名保留同一对象；`settlement_steps` 的再导出面不变 |
| `asset_context:176` | ✅ 改直认 `core.settlement_common` | 原来绕道 `settlement_steps`（结算**编排器**）取写原语 |
| `focus_mechanic:445` | ✅ 同上 | 现场在 `try/except` 内，失败全额退库——语义未动 |
| `settlement_imperial` / `settlement_officialdom` | ✅ 同批改读公开名 | 同一对象，守恒不变 |
| 测试打桩目标 | ✅ `si._distribute_cash` → `si.distribute_cash` | ⚠️ **不改就是废用例**：patch 打在消费者绑定上，改名后旧目标不存在（`AttributeError` 实测先红过一次） |

### 🔴 我上一轮的判断错了，这里按实测更正

我先前说"这刀**不减少 18 模块环**，只是消掉写原语由编排器宿主"。**实测推翻**：
`mh_scc_scan_v2.py` 复扫结果是 **环数仍 2，但大环成员 18 → 16**，
脱离环的正是 `asset_context` 与 `focus_mechanic`，**无新成员加入、faction 环不变**。
机制：这两个模块此前是"业务模块 → 环内编排器 → … → 回到自己"的一环；
改指**环外**的 `settlement_common` 后该回路断开，它们就不再属于强连通分量。

⇒ 结论要改写：**反向边不是"一条都拆不动"**，而是"能拆的那几条恰好是
*调用方在环内、被调方其实在环外* 的形态"。剩下 11 个写站点里，
`commands_decree` / `save_load` / `settlement_steps→settlement` / `game_state` 的
被调方本身就在环内（`settlement`、`settlement_decree`、`settlement_imperial`），
所以那些仍需①依赖注入或②归位，**仍是裁定项**。

**验证**：全量串行 `EXIT=0`、`FAILED/ERROR=0`；collected **2400** = 批次前 2395 + 本批 5 例
（`test_edge_path_b13.py`）；SCC `[16] + [2]`（历史基线 18 模块环见阶段 1 文档，本批起为 16）；
守恒语义直接实测：`distribute_cash(10000, {工匠 .4, 商人 .6})` ⇒
`Σ POP wealth 增量 == 分发额 == sum(applied)`；无接收池 ⇒ 返回 0 不凭空记数。
守卫含一条**读文档表行**的用例：那两行若再被写回"读数"，CI 直接红。

## 十二、第十四包：开 `domains/diplomacy/`（2026-10-07）

候选**按 AST 实测叶子资格**筛（`_scratch/b14_leaf_survey.py` 给每个未迁模块量反向边数、生产被引数、
符号数三件事），不按文件名猜——第十三包刚因为"按名字判"写错过文档。零反向边候选 24 个，本批取
其中符号最少且同属一个机制域的两个：`diplomacy_treaty`（124 行 / 3 实义符号）与 `external_view`（62 行 / 2 符号），
两者顶层 import **只有 `content.data`**。

| 项 | 处置 | 实测 |

|---|---|---|

| `game/core/domains/diplomacy/treaty.py` | ✅ `git mv`（保留历史） | `TREATY_TYPES` `_att_delta` `apply_treaty` + 6 个 content 常量绑定 |

| `game/core/domains/diplomacy/external_view.py` | ✅ `git mv` | `external_pop_view` `external_provinces` + 3 个表名 |

| 两条旧路径 | ✅ 收敛为 `dir()` 显式转发桩 | 桩面 9 名 / 5 名，与迁移前冻结快照**逐字相等**；**含私有名** `_DIPLO_ATT` `_att_delta` `_EXTERNAL_PROVINCES_DEFAULT` |

| 生产侧 2 处调用 | ✅ 同批改指新路径（判据④） | `ai/contracts_court.py:268`、`core/commands.py:1698`；复扫生产侧旧路径引用 **0 文件 / 0 引用点** |

| 测试侧 3 处 | 保留旧路径 | 兼容门面生效面（阶段 4 允许）|


**两条如实声明**

- ⚠️ `external_view` 生产侧被引 **0** 次（迁移前后都是 0）：本批只搬代码，
  **不得据此说外邦视图已接入界面**，也不得按"零调用"删（`test_uncovered_modules.py` 依赖它）。
- ⚠️ `_att_delta` 是私有符号，桩面**必须**照转：本仓有测试直取私有名的先例，漏一个就是静默断链。

**新增 `test_domains_diplomacy_b14.py`（6 条）**：桩面等集 / 全部 14 个名字（含私有）旧路径 `is` 新实现 /
新落点仍无业务 import（叶子资格常驻）/ 生产不得再引旧路径 /
`apply_treaty` 真实通道（返回契约 `{ok,msg,attitude_delta,cost}`、和亲被接受且外邦状态真变、
未知协议必须**拒绝**不静默成功）/ `external_provinces`+`external_pop_view` 非空与字段形状。

**验证**：全量串行 `EXIT=0`、`FAILED/ERROR=0`；collected **2406** = 批次前 2400 + 本批 6 例；
SCC 仍 **2 环**（`[16] + [2]`），扫描模块 124 → **126**，两个新落点未入环；
生产侧旧路径引用（10 个已迁模块合计）**0 文件 / 0 引用点**，测试侧 46 文件仍走旧路径。

**一处未解释的差异，不留成第二个真相**：`_scratch/b9_newpath_count.py` 的"业务侧真实消费"由第九包的 41
涨到 45，但本批只新增 2 个消费文件（另 2 个未能逐文件归因）。
⇒ 因此本 README 的接入进度**以 `b9_scope_measure.py` 的"生产侧旧路径引用 = 0"为准**，
该口径可逐文件复核；41/45 那个分桶数暂不作完成度宣称，待有人把差值归因清楚再启用。

## 十三、第十五包：`dynamic_price` + `demand` 并入 `domains/economy/`（2026-10-07）

§7 把 `market*.py`、`demand.py` 列为经济域候选。本批取两个**实测零反向边**的叶子：
`dynamic_price`（顶层 import 只有 `__future__`/typing，连 `content` 都不引）、`demand`（顶层 typing + 函数内 `from content import data`）。
**其余经济域候选未随批搬**：`settlement_finance` / `settlement_granary` / `settlement_econ` 的被调方在 16 模块环内，属阶段 3 裁定项，不是机械搬迁。

| 项 | 处置 | 实测 |

|---|---|---|
| 两模块 | ✅ `git mv` 入 `domains/economy/` | 桩面 10 名 / 12 名与迁移前快照**逐字相等**（含 `Dict`/`Optional`/`Tuple`/`Any`/`annotations` 这些公开面上的绑定名，和私有 `_clamp`/`_num`/`_cfg`）|
| 生产 5 处 import | ✅ 同批改指新路径 | `income_readout.py` ×3、`settlement_econ.py` ×1、`settlement_granary.py` ×1；复扫生产侧旧路径引用 **0 文件 / 0 引用点**（13 个已迁模块口径）|
| 测试侧 | 保留旧路径为主 | `test_dynamic_price_logistics.py` 的 **getsource 目标改指实现**（见下）|
| 48 个测试文件 | 仍走旧路径 | 兼容门面生效面 |

### 🔴 本批扫出的**新隐患类型**：测试读源码散文

`test_dynamic_price_logistics.py:125` 用 `inspect.getsource(core.dynamic_price)` 断言**模块里写了那句话**（"金属 ≠ 钱"的边界声明须出现在代码中）。这类断言不吃 import、不吃对象同一性，只看**文本**——实现搬走后桩里只剩转发语句，断言要么假红、要么被人在桩里补一段话糊过去。处置：① 把 `getsource` 指向实现模块（比指向桩更忠实）；② 新增**常驻扫描**`test_no_getsource_on_migrated_stub_anywhere`——任何文件对已迁模块的旧桩取源码都直接红，别名解析走 AST（与第十三包那条"按名字判不可信"的教训一致）。

> **本批直接证据**：把这两个新桩纳入 b9 清单后，守卫**立刻抓到我自己的桩写歪了**——
> 我让桩自己 `from typing import ...` / `from __future__ import annotations`，
> 而既有桩范式是"公开面上每个名字都从**实现模块**转发"。判据是
> "`dir()` 里每个名字都得能在桩的转发语句里找到来源"，本地 import 不算来源 ⇒ 直接红
> （`core.dynamic_price.Dict/.Optional/.Tuple` 三条）。**改桩不改判据**。
> 这类偏离不会报错、也不影响功能，只会在下次比对时留下"两份真相"，所以必须有机器判据兜。
**已证明会响**：临时放一个 `getsource(core.demand)` 的探针文件，守卫立即点出`_tmp_b15_mutprobe.py:8`，探针随后删除。

### 顺带量到的两条代码事实（本批未改，只是别再误以为它们存在）
1. `logistics_rate()` 的地形/战乱系数**只在显式传 `cfg` 时**才乘，默认 `cfg=None` ⇒    战乱**不会**抬高运费。我一开始按"战乱应更贵"写断言，实测 `0.5 vs 0.5` 才发现是预期无依据。
2. `update_goods_prices()` 按 `cfg["GOODS_BASE_PRICE"]` 迭代 ⇒ 无基准价的品**被跳过而非编造**   （正是"缺失不臆造"）；月涨跌 ±20% 会把带内目标价再削一层（盐 100→150→**120**、茶 50→25→**40**）。   两条都已钉进用例，断言值按推导写死，不留区间。

**验证**：全量串行 `EXIT=0`、`FAILED/ERROR=0`；collected **2412** = 批次前 2406 + 本批 6 例；
SCC 仍 `[16]+[2]`、成员未变（扫描模块 126 → **128**，两个新落点不在环内）；
生产侧旧路径引用 **0 文件 / 0 引用点**（`_scratch/b9_scope_measure.py`，现覆盖 13 个已迁模块），
测试侧 48 文件仍走旧路径。

## 十四、第十六包：开 `domains/production/`（2026-10-07）

§7 把"农业、岗位、配方、生产链"列为生产域候选。本批取两个实测**零反向边**模块：`production_chain`（273 行 / 公开面 14 名）、`farm_procurement`（250 行 / 15 名），函数内 import 只有 `content` 与 `core.foundation` / `core.domains` 的**公开名**。`building_jobs.py` **不随批搬**——它引 `pop_bridge`/`grain_bridge` 且被结算多步分别调用，要先定"岗位/就业归生产域还是行政域"，那是判责不是搬家。

| 项 | 处置 | 实测 |

|---|---|---|
| 两模块 | ✅ `git mv` 入 `domains/production/` | 桩面 14 / 15 名与迁移前快照**逐字相等**（含 `_pick_seat`/`_write_pending`/`_take_goods` 等私有名与 typing 绑定名）|
| 生产 3 处 import | ✅ 同批改指新路径 | 全部在 `settlement.py` 的函数内延迟导入；复扫生产侧旧路径引用 **0 文件 / 0 引用点**（15 个已迁模块口径）|
| 测试侧 | 保留旧路径 | `production_chain` 11 文件、`farm_procurement` 0 文件（本就没有测试直接 import 它）|
| 跨域边 | ⚠️ **登记不改** | `production_chain` 引 `domains/economy.material_trade_ops.commodity_dims`：跨域但**走公开名**，符合 §6 规则2；新增用例锁"跨域 import 里不得出现下划线名"|

### 一条我凭想象写错、被实测纠正的断言

我第一版给生产链写了"`pending_total` 要与本轮产出读数同源"的断言，跑出来 `0 == 16,205,802` 直接红。读码后事实是三条，与我的想象无关：
① `settle_production_chain` 返回的 `{dim: 本月产量}` 是**封顶前**口径，写仓被 `cap` 截断 ⇒    `Σproduced (16,205,802) > ΔΣresources.stock (9,433,738)`，**拿返回值当入仓量会多出 677 万**；
② `pending_stock` 是**归属待定**槽，按用户裁定 6.33 **不并入** `state.resources`（后者被五处消费者当国库资产），   所以生产了不代表在途有数——新局在途保持 0；
③ 写仓不击穿 `cap`、库存不倒退（盐 300 万即顶在 cap 上）。
⇒ 用例改成钉这三条实测事实。**教训同第十三包**：机制类断言必须先量后写，不能按"应该怎么设计"写。

**验证**：全量串行 `EXIT=0`、`FAILED/ERROR=0`；collected **2417** = 批次前 2412 + 本批 5 例；
SCC 仍 `[16]+[2]`、成员未变（扫描模块 128 → **130**，两个新落点不在环内）；
生产侧旧路径引用 0 文件 / 0 引用点（`b9_scope_measure.py`，现覆盖 15 个已迁模块）；测试侧 50 文件。

## 十五、第十七包：开 `domains/politics/`（2026-10-07）

§3.1 把 `faction_*` / `situation_*` / `events` 定为**跨机制能力**，应作独立域并经接口协作。本批取两个实测零反向边模块：`faction_split`（235 行 / 桩面 20 名）、`faction_voice`（166 行 / 19 名）。

**主动预防了第九包那类失效**：开工前扫出 **2 处打在提供方桩上的 `monkeypatch`**（`test_error_observability_settle.py:385` 注 `ensure_faction_split`、`test_faction_flows.py:267` spy `set_split`）。消费者都是 `from core.faction_split import …`在**调用时**解析模块属性 ⇒ 若不同批改指，patch 会落到桩上、注入静默失效（第九包是被红抓到的，这次是提前查出来的）。两处已同批改指实现模块，且**两个用例跑完全绿**——绿本身不说明注入有效，所以另加一条常驻断言`test_stub_is_not_a_behavior_switch`：**桩不是行为开关**（在桩上改名不影响实现模块），任何行为类 patch 必须打实现。

**未随批搬的（各有理由，不是遗漏）**：`faction_basis` + `faction_metrics` 自身构成 faction 环，搬它们=把环换个位置；`faction_settle` **不是叶子**（顶层 import 那两个环内模块）；`situation_*` / `events` 需要先设计稳定读写接口（§3.1 原话）。

**验证**：全量串行 `EXIT=0`、`FAILED/ERROR=0`；collected **2421** = 批次前 2417 + 本批 4 例；SCC 仍 `[16]+[2]`、**faction 环成员未扩大**（这是本批的关键判据），扫描模块 130 → **132**；生产侧旧路径引用 0 文件 / 0 引用点（17 个已迁模块口径）；测试侧 56 文件仍走旧路径。
⚠️ 一处自我修正：本轮曾把一次全量误启动成后台任务又差点重跑，靠**先查日志体积/进度**确认在跑才没造成两份并发全量（§9 禁并发争内存）。

## 十六、第十八包：`market` + `hoard_settle` + `regime_fiscal` 并入 `domains/economy/`（2026-10-07）

三个模块 AST 实测都是叶子：`market`（210 行，顶层 import 只有 `__future__`/typing，**连 `content` 都不引**）、`hoard_settle`（137 行，`random`/typing + 函数内 `content.data`）、`regime_fiscal`（110 行，typing + `core.foundation.ledger.pop_structure` 公开名——人口写入走桥接，符合 POP 挂载律）。桩面 **15 / 13 / 11 名**与迁移前快照逐字相等。

判据④同批：生产 **7 处** import 改指新路径（`material_market`、`settlement_granary`、`settlement_econ`、`settlement_finance`、`income_readout` ×2、**`domains/economy/material_trade_ops.py`** ——最后这条意味着经济域内部不再绕 `core` 平铺）。复扫生产侧旧路径引用 **0 文件 / 0 引用点**（20 个已迁模块口径）。

### 🔴 `market` 带来一类新状态：桩背后的**模块级可变台账**

`market` 有 `_TRADE_LEDGER`（防同一 `trade_id` 重复成交）。放在桩后面有两种失效方式，都被写成断言（`test_trade_ledger_is_one_shared_dict`）：
① 桩与实现各持一份 dict ⇒ 防重形同虚设，重复成交会被放行；
② 测试在**桩**上重绑 `_TRADE_LEDGER = {}` ⇒ 实现看不见，"清台账"变假动作。
实测：台账是同一个对象、经桩 `reset_trade_ledger()` 能清掉实现侧状态；另加防重真实通道用例（一次成交货与钱都动、同 `trade_id` 二次被拒且不再改库存）。
⇒ 这条与第七包（`SAVE_DIR`）、第十三包（提供方 patch）同型：**桩保住的只是"名字与对象"，不保住"谁持有可变状态"**——可变状态必须有专门的断言。

**验证**：全量串行 `EXIT=0`、`FAILED/ERROR=0`；collected **2426** = 批次前 2421 + 本批 5 例；SCC 仍 `[16]+[2]`、成员与基线一致（扫描模块 132 → **135**，三个新落点未入环）；测试侧 58 文件仍走旧路径。

## 十七、第十九包：开 `domains/administration/`（`institution`，2026-10-07）

§7 行政与官制域的第一个候选。`institution.py`（312 行 / 16 函数）AST 实测是**零 `core` import 的真叶子**：
顶层只 `typing` + `content.data.INSTITUTION_PARAM_SPEC`，函数内只 `content.data.normalize_tier`
与 `content.ministers.data`（事权/机构表）。桩面 **23 名**（31 去 8 个 dunder）与迁移前快照逐字相等。

**一批一包（§8 硬纪律）**：原计划同批再迁 `literacy` → `domains/culture/`，那是**两个包**，
已拆分为第二十包（云端 `M23`）。本批只交 administration 一个包。

### 🔴 本批最大产出不是搬文件，而是查出既有扫描器的两处口径盲区

勘察调用方时，第一版脚本按 `from core.institution import …` 形态只量到 **1 个**生产消费方，
实际是 **7 处 / 6 个文件**——另有 6 处写作 `from core import institution as _inst`。
按名字 grep 同样会漏（`_inst` 是别名）。修正后的判定必须覆盖三种形态：
`import core.X` / `from core.X import …` / `from core import X [as Y]`（脚本 `_scratch/b19_consumers.py`）。

顺着这条去查常驻 SCC 扫描器 `mh_scc_scan_v2.py`，发现**同一个盲区它一直就有**：

| 盲区 | 后果 |
|---|---|
| ① 它只认 `node.module.startswith('core.')`，所以 `from core import X`（module 恰为 `core`）**一条都不计** | 实测 core 内有 **13 条**这类边被漏 |
| ② 节点名用 `relpath` 的**斜杠**形式，边名却是**点分**形式 | 所有指向 `foundation.*` / `domains.*` 的边在 DFS 里被 `w not in mods` 丢弃 ⇒ v2 实际只在 core 顶层平铺子图上找环 |

用 `mh_scc_scan_v3.py`（点分节点名 + 三形态全计）重扫，平铺大环成员 **16 → 17**：
`settlement_military` **早就在环内**（靠 `settlement_military -> core.events`，:251 的 `from core import` 形态），
是 v2 漏了它，不是本批造出来的。⇒ **更正第十二~十六包记录的 `[16]+[2]`：那是 v2 口径下的下界，
按 v3 口径大环是 `[17]+[2]`。** 少算边只会漏环、不会造出假环，所以此前"无新增环"的结论方向仍成立。

**本批未造环的证据（同口径前后对比，不动工作树）**：用 `git archive HEAD game/core` 解出批次前只读副本，
对副本跑 v3 ⇒ 环成员 **17 个逐字相同**，新增/移出皆空集（`_scratch/b19_scc_v3_pre.txt` vs `_scratch/b19_scc_v3.txt`）。
同时 `from core import X` 形态边 **13 → 7**，差值正好等于本批改道的 6 处 institution 引用——
两条独立数字互相咬合，才敢说改道完整。

### 判据④与完成度（脚本口径，非手算）

- 新路径生产消费方 **6 文件 / 7 引用点**；旧路径 `core.institution` 生产引用 **0**；测试侧 **5 文件**保留旧桩（阶段 4 兼容面）。`_scratch/b19_refcount.py`
- 完成度换成更硬的口径：`game/core/*.py` 有效平铺模块 **93**（不含 `__init__.py`），
  其中**纯转发桩 21**、**实现仍在原地 72** ⇒ 仍有 **77.4%** 的平铺模块持实现。`_scratch/b19_completion.py`
- 同一脚本做**双台账交叉核对**：AST 判出的桩集合必须等于 b9 守卫用例里声明的 `MIGRATED_OLD`
  ⇒ 实测 21 = 21，两侧零差集（本批把 `core.institution` 同时补进 b9 的 `MIGRATED_OLD` 与 `stubs` 两张表）。

### 本批钉住的断言（`test_domains_administration_b19.py`，9 例）

除桩面/同一性/桩无自带实现外，三条是本批新挣来的：
① `_SPEC` 是 `content.data.INSTITUTION_PARAM_SPEC` 的**别名**，桩与实现必须指向同一份字典
（第十八包 `_TRADE_LEDGER` 同型：桩只保住"名字与对象"，不保住"谁持有可变状态"）；
② 常驻扫描全测试目录，**禁止任何用例把 `core.institution` 当 `monkeypatch` 提供方**
（第十三/十七包都是这类失效，这次做成机器守着的禁令而不是口头纪律）；
③ `_org_table` 的回退分支 `except Exception: return {}` 会**静默吞断链** ⇒ 必须实测
"机构表非空且含户部、户部事权含官营放贷"，只断言 import 成功不算接通。
另有事权约束的行为用例（无主体拒、非掌权者拒、经`{post: 抵当所提举}`放行、不受约束参数不看主体、
`didang_loan_rate` 加档被值域上限 0.05 钳住）——机制类断言全部先实测再写（第十四/十五包教训）。

**变异实验 3 组**（证明断言非空跑，跑完 `cmp` 逐字节恢复）：桩漏转发 `TIER_STEP` ⇒ 2 条红；
桩内自带 `def clamp` ⇒ 1 条红；`clerks.py` 退回旧路径 ⇒ b9 生产改道用例红。

**验证**：全量串行 `FULL_EXIT=0`、`FAILED/ERROR=0`；collected **2435** = 批次前 2426 + 本批 9 例
（`--collect-only` 按文件行求和，204 个文件）。

**顺手修的文档不实之处**（§6.1）：`domains/production`、`domains/politics`、`domains/economy`
三份 README 的「迁移状态」还写着**未开始**，而三包分别自第十六/十七/十八包起就有实现；
`domains/economy/__init__.py` 仍写"阶段 0 空骨架"（实有 6 个模块）。四处已按实测改写。

## 十八、第二十包：开 `domains/culture/`（`literacy`，2026-10-07）

识字率（198 行 / 7 函数）AST 实测是叶子：顶层只 `__future__` + typing + logging
+ `core.foundation.common.numeric` 的**公开名** `parse_number`/`clamp`，连 `content` 都不引
（阶级基准表 `POP_LITERACY_BASE` 就定义在本模块里）。桩面 **27 名**（37 去 10 个 dunder，
含 `annotations` 与 `__all__`——后者按 skill 纪律**原样拷贝**，不是重生成，
用例 `test___all__is_a_verbatim_copy_not_a_regeneration` 把"内容相等但不是同一份 list"钉住，
防止将来有人改成动态生成而悄悄扩大公开面）。

判据④同批：生产 **5 文件 / 6 引用点**改指新路径（全部函数内延迟导入），旧路径生产引用 **0**；
测试侧 3 文件 / 4 点保留旧桩。`_scratch/b21_refcount.py`（通用版，三形态全计）。

### 🔴 提供方打桩随迁，并且**用反向变异证明它是必需的**

`test_error_observability_settle.py:379` 原本 `import core.literacy as lit`
再 `monkeypatch.setattr(lit, "init_literacy", _boom)`。消费者 `save_load.py:617` 改直认真实家后，
这枚 patch 落在没人读的名字上 ⇒ **用例照绿、异常根本没注入**（第十七包预防过同一类，这次是实打实存在的）。
改指实现后，把这一行**退回旧桩**跑一次 ⇒ 该用例立刻红。
这才是"红得起来"的证明：不是断言写得凶，而是**改回去会失败**。
另加常驻禁令 `test_no_test_patches_the_old_literacy_stub`（AST 解析别名，`import core.literacy as lit`
与 `from core import literacy as lit` 两种形态都算）。

### 等价性用真实调用证，不是只比文本

`_scratch/b20_equiv_check.py`：`git show HEAD:game/core/literacy.py` 重取迁移前原文 →
落成临时模块 → 同一 `GameState` 上 **10 项函数输出逐项相等**，再**连跑 12 个月结算**
逐月比 `out` 与每个 POP 的 `literacy`（轨迹全等，终值 8.41）。
逐顶层节点比 `ast.dump`，**已声明漂移 1 处**：模块 docstring 原文写
"阶级基准（content.data.POP_LITERACY_BASE）"，实测 `content` 里**没有**这张表（定义在本模块 `:57`）
⇒ 按 §6.1 顺手改正，纯注释级、不改任何计算。

### 🔴 我又犯了一次第十四/十五包那个错（机制断言必须先量后写）

首版 `test_missing_reads_are_none_not_zero` 写了
`assert settle_literacy(清空 literacy 的 state)["national"] is None`——
理由是"缺失就是缺失，不许回落 0"。**实测是 8.41**：`settle_literacy` 对缺失行走的是
`pop["literacy"] = target; changed += 1; continue` 分支，先补值再算全国，
而且这些行**不计进 `out["pops"]`**（`continue` 在计数之前）。
⇒ 口径（缺失≠0）推不出函数返回值；写机制断言前必须先跑一遍量实测。已按实测改写，
并把"补齐 120 / changed 120 / national 8.41"这三件真实事实写成断言。

**完成度**（`_scratch/b19_completion.py`）：平铺有效模块 **93**、纯转发桩 **22**、仍持实现 **71**（**76.3%**）；
桩集合与 b9 `MIGRATED_OLD` 交叉核对 **22 == 22**（零差集）。
**SCC（v3 口径）**：`[17] + [2]`，成员与第十九包基线**逐字相同**（扫描模块 136 → **137**，新落点未入环）。

**顺手清的四处口径引用**（"文档里带日期的断言会腐烂"——改一条要 grep 同文档全部引用）：
`game/core/AGENTS.md` 的"12 条反向边 12/12 函数内"补上第 13 条是**顶层**；
`domains/economy/README.md`、`domains/production/README.md` 的"16 模块环"改 [17] 并指路；
`specs/cross-cutting/README.md` 索引行加"当前口径以 §一之补为准"的指针；
本文件 §二 扫描口径段声明 **v3 取代 v2**、各批写的 `[16]` 是当时 v2 口径下的测量（保留不追改）。

**验证**：全量串行 `FULL_EXIT=0`、`FAILED/ERROR=0`（docstring 改正后**重跑过一次**）；
collected **2448** = 批次前 2435 + 本批 13 例（`test_domains_culture_b20.py`，205 个文件）。
变异 3 组均可红：桩漏转发 `_num` ⇒ 桩面用例红；调用方退回旧路径 ⇒ b9 红；
patch 提供方退回旧桩 ⇒ M2 可观测性用例红。跑完 `cmp` 逐字节恢复。

