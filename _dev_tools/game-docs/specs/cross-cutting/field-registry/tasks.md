# B-1 字段单点注册 · 任务与证据

> 需求见 [`requirements.md`](requirements.md)，设计见 [`design.md`](design.md)。
> 状态口径（`specs/README.md` §状态判定）：**有生产调用路径才算已接线**；
> 「设计完成」「影子期通过」「兼容导入成功」**都不能**单独标成生产接线完成。

## 批次表

| 批次 | 内容 | 状态 | 放行证据 |
|---|---|---|---|
| **B-1 前置** | 全量基线重跑（记录基准提交）+ 回滚场景旧实现实跑 | ✅ 完成 | §P1 / §P2 |
| **B-1a 影子期** | `field_registry.py` + 自检 + L1/L1.5/L2/L3 测试；**生产判定零改动** | ✅ 完成 | §A（`state_applier.py` diff 为空 + 定向 210/0/0/0） |
| **B-1b 数据源切换** | `state_applier.py` 六字面量 → 导入派生；**五 matcher 一字未改** | ✅ 完成（代码 + 定向 + 全量） | §B |
| **未来独立裁定** | 五 matcher 是否统一（含 `granary` 宽松前缀收紧） | ⬜ 未排期 | 需单独设计 + 逐集合匹配契约 + 行为差分证据 |

## P1 · 全量回归基线

- 基准提交：`f6d2dad6139febf40e6ee9271a19a5d312d1671e`（`master`）。
  说明：本会话早期引用的 2689 系**过期快照**（`handover/phase/DSH.json`），**不作为基线**。
- 实测（2026-10-12 01:29:12 → 01:35:43，`--junitxml` 权威口径）：

  | tests | failures | errors | skipped | time |
  |---:|---:|---:|---:|---:|
  | **2737** | **0** | **0** | **2** | 387.68s |

  跳过明细：`pytest.xfail` ×1 + `pytest.skip` ×1。

## P2 · 回滚场景（迁移前实现实跑，先记真实行为）

构造：3 条变更，第 3 条指向中间层缺失路径。**实测记录**（未预设期望）：

| 观测项 | 实测值 |
|---|---|
| 异常 | `KeyError`（消息：`状态路径不可写（中间层缺失）: prefectures.不存在的路ZZZ.mood`） |
| 返回值 | 异常**向上抛出**，不返回字典（`applier_pipeline` 未转成 `{"applied": [], ...}`） |
| 状态 | 前两条写入被**完整逆序回滚**：`state_restored=true`、`field_diff={}` |
| `CHANGE_LOG` | 0 → 0（**未追加**） |

⇒ **旧实现满足预期** ⇒ 可作为 L3 期望值（见 §C 的 `test_l3_rollback_matches_golden`）。
（若当时不符预期，应登记独立缺陷，**不得**借 B-1 顺手修复。）

## A · B-1a 证据

1. **文件级变更**：新增 `game/engine/field_registry.py`、`_dev_tools/game-dev/tests/b1_field_registry_golden.py`、
   `_dev_tools/game-dev/tests/test_field_registry_parity.py`、本目录三份文档。
   **生产代码零改动**：`git diff --name-only -- game/engine/state_applier.py` 为**空**。
2. **可行性判定修正（B-1a 抓到的两处真问题，均修正"声明"而非"旧集合"）**：
   - 初版给 8 条具体 POP 钱/粮行也标了 `non_neg` ⇒ `NON_NEG_PREFIXES` 派生 32 ≠ 原 24。
     原因：原集合对 POP 钱粮用的是**两条通配行**。修正为"具体行只承载守恒、通配行承载非负"。
   - 自检把合法尾点前缀 `era_state.` 误判为"空段" ⇒ 修正为允许尾点作前缀标记。
3. **定向回归**：`tests=210 / failures=0 / errors=0 / skipped=0 / 24.603s`
   （新模块 62 例 + 7 个既有相关模块 148 例）。

## B · B-1b 证据

1. **函数级等价（AST 逐字比对 `HEAD:game/engine/state_applier.py` vs 切换后）**：
   函数数 **23 → 23**、函数名集合相同、**函数体变更数 = 0** ⇒ 五个 matcher 与其余全部逻辑一字未改。
2. **常量级变更**：移除恰为 6 个（`VALID_PATHS`/`NON_NEG_PREFIXES`/`MONEY_PATHS`/`GRAIN_PATHS`/
   `RANGE_100_FIELDS`/`CLAMP_01_FIELDS`），**新增 0 个**；`NO_CONSERVATION_PATHS = None` 保留（E7 冻结）。
3. **单点生效**：六个名字与 `field_registry` 的对应名字**同一对象**（`is` 为真）。
4. **diff 规模**：`1 file changed, 36 insertions(+), 97 deletions(-)`（净 −61 行）。
5. **自检**：`field_registry.validate_registry() == []`。
6. **定向回归**：`tests=210 / failures=0 / errors=0 / skipped=0 / 24.885s`。
7. **全量回归**：见 §C。

## C · 六集合对照与差分

**旧值 / 新值对照**（多重集，含顺序判定）：

| 集合 | 旧 | 新 | 多重集 | 顺序 |
|---|---:|---:|---|---|
| `VALID_PATHS` | 35 | 35 | ✅ | ✅ |
| `NON_NEG_PREFIXES` | 24 | 24 | ✅ | ❌（见下） |
| `MONEY_PATHS` | 9 | 9 | ✅ | ✅ |
| `GRAIN_PATHS` | 5 | 5 | ✅ | ✅ |
| `RANGE_100_FIELDS` | 11 | 11 | ✅ | ❌（见下） |
| `CLAMP_01_FIELDS` | 0 | 0 | ✅ | ✅ |
| 合计 | **84** 条登记 | **84** 条 | — | 38 行声明 |

**顺序不可复现（已实测，非推测）**：对六个集合内部相邻元素建先后约束图 ⇒ **存在环**
（最小环 4 节点：`defense_lines.*.fortification` → `garrison` → `land.hidden_households` →
`waste_reform.savings` → 回到起点；38 行中 35 行在环内）。按用户裁定**不伪称顺序恒等**，
采用"行为证据前提下的放宽比较"：L1 比多重集，L1.5 用**洗牌不变性**证明顺序不进入任何可观测输出
（3 个种子 × 64 样本 × 5 谓词 + 2 个种子 × 3 场景）。追认登记：`handover/decisions/B1-order-relaxation.json`。

**差分测试**（`test_field_registry_parity.py`，62 例）：

| 层 | 例数 | 覆盖 |
|---|---:|---|
| L0 自检 + 负向 | 3 + 19 | 缺 `cons`/`cons` 非枚举/`kind` 非枚举/布尔位与字符串位类型错/路径空串与空段/尾点前缀合法/重复声明（同语义与异语义）/`max_100` 缺 `non_neg`/`max_100` 与 `clamp01` 并存/非数值带数值元数据/守恒组不可写/钱粮词无理由/给理由后不自动改分类/入参非序列 |
| L1 集合 | 6 + 6 + 2 | 六集合 vs golden 多重集；`state_applier` vs golden；接线"全切或全不切"；顺序分歧集合集锁定 |
| L1.5 顺序 | 3 + 2 | 洗牌后谓词不变；洗牌后管道不变 |
| L2 谓词 | 3 | 64 样本 × 5 谓词 vs golden；宽松前缀分歧锁定；通配非负仍覆盖第 7 类 |
| L3 管道 | 15 + 1 | 15 场景 `applied/rejected/errors/conservation_failed/CHANGE_LOG/state_delta` vs golden；回滚场景 vs golden |
| 可达性 | 1 | 真状态实例化逐条寻址（禁止源码正则） |
| golden 溯源 | 1 | `GOLDEN_SOURCE.commit/generated_at` 必须存在 |

golden 来源可审计：`b1_field_registry_golden.py` 记 `commit=f6d2dad…`、生成时间与产出脚本；
产出脚本已入库 `_dev_tools/game-dev/b1_baseline_probe.py`（**从 git 修订提取六集合**，`--emit` 前有
fail-closed 守卫：工作树与 `--rev` 不一致即拒绝写出——B-1b 后工作树已无那六套字面量，照旧提取会写出空集合。
实测：在当前树对 `--rev f6d2dad` 跑 `--emit` → 拒绝且 golden SHA256 未变）。
各次 junit 落 `_scratch/b1_*.xml|txt`（临时区，不入库）。
**独立复核**：在 B-1b 之后的树上跑 capture-only 探针，15/15 场景 + 回滚记录 + 谓词样本（64 条 / 8 种结果）
与 golden 逐字段一致（不依赖测试模块的第二条证据链）。

## D · 全量回归终态

`cd sz; pytest _dev_tools/game-dev/tests`（同一基准提交 `f6d2dad`；2026-10-12 01:39:52 → 01:46:19）：

| 时点 | tests | failures | errors | skipped | time |
|---|---:|---:|---:|---:|---:|
| 基线（B-1 之前） | 2737 | 0 | 0 | 2 | 387.68s |
| **B-1b 之后** | **2799** | **0** | **0** | **2** | 385.55s |
| 增量 | **+62** | 0 | 0 | 0 | — |

增量恰为新模块 62 例；跳过项未变（`pytest.xfail` ×1 + `pytest.skip` ×1）。
**验收口径**：无新增失败/错误、跳过变化有解释，**不机械要求新旧总数相等**。
前端未改（`git status` 无 `game/frontend/**` 变更），故未跑 tsc/vitest。

**回退证据**：B-1a 生产零改动（`state_applier.py` diff 为空，可整体删除新增文件即回退）；
B-1b 为**单文件**变更（`+36 / −97`，可单提交 revert），且 golden 数据与差分测试都在测试侧，
revert 后仍可运行以复验。

## 遗留与追认

| ID | 事项 | 处置 |
|---|---|---|
| `B1-order-relaxation` | 六集合顺序无法由单一声明复现 | 已按证据实施"放宽 + 洗牌不变性"，登记 decisions 待追认 |
| `E1`–`E8` | 宽前缀 / 孤儿行 / `era_state.` / `art_mastery` / 规则不对称 / `savings` 分类 / 死常量 / 全面显式化 | 已裁定**维持现状**（`B1-legacy-freeze-E1-E8.json`），测试只锁定不修改 |
| B-2 / B-3 / B-4 | 守卫进放行门 / 结算步序契约 / 机制台账机器可读 | **冻结**，本轮未动 |

---
最后更新：2026-10-12。
