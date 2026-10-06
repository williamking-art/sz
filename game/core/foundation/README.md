# foundation — 基础与账本层

> 迁移状态文档。承架构方案 §9-5：「**代码在新目录**」**不等于**「生产调用已接入」。
> 本文件记录**实测**状态，不写计划。

---

## 子包

- `state/` GameState、初始状态构建与状态字段注册 —— ⬜ **空（0 个实现文件）**
- `ledger/` POP/钱粮/物料权威账户与读写 API（含迁移期桥接）—— ✅ **已迁入 7 个**（含 `material_holding` 账本侧拆分）
- `persistence/` 存档读写与版本迁移 —— ⬜ **空（0 个实现文件）**
- `common/` numeric、errors 等无领域语义的共享工具 —— ✅ **已迁入 1 个**（`numeric`；
  ⚠️ `errors` **未迁**——它本来就是 20 行的真小模块，不是转发桩，别按"行少"误判成已迁）

## 〇、完成度实测（2026-10-07，脚本口径见下）

> 目的：防止"批次都做完了"被误读成"重组快完了"。**交接单候选（甲/乙/丙）做完 ≠ 阶段 2 做完。**

| 度量 | 实测值 | 口径 |
|---|---:|---|
| `core/*.py` 文件总数 | **94** | `ls game/core/*.py \| wc -l` |
| 已迁入新结构的模块 | **8** | money / pop_bridge / grain_bridge / numeric / pop_structure / prefecture_entity / grain_ledger / material_holding |
| ⇒ 按模块数的进度 | **8/94 ≈ 9%** | 仅作量级参考，不是"完成度"指标 |
| `foundation/state` 实现文件 | **0** | — |
| `foundation/persistence` 实现文件 | **0** | — |
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
| `state/`、`persistence/` 与其余 `domains/*` | ⬜ 空骨架 | **除 `domains/economy`（已有 `material_trade_ops`）外均无实现**；结算域迁移属阶段 3，前置=12 条反向边接口化（阶段 1 文档 §五） |
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