# B-1 字段单点注册 · 设计

> 状态：**B-1a 已完成（影子期）/ B-1b 已完成（数据源切换）**——`engine/state_applier.py` 六套字面量
> 已改为导入 `engine/field_registry` 派生；五个 matcher **一字未改**（AST 逐字等价，函数体变更数 = 0）。
> 全量回归 2799/0/0/2（基线 2737/0/0/2，增量恰为新增 62 例）——证据见 [`tasks.md`](tasks.md)。
> 🔴 **未实施**：matcher 统一（未来独立裁定）、B-2/B-3/B-4。
> 授权：用户 2026-10-12 裁定「B-1 有条件通过，按两阶段实施」。
> 范围：**只做** `engine/state_applier` 六套路径/规则集合的单点声明与自动派生。
> 非目标与冻结清单见 [`requirements.md`](requirements.md) §3。

## 1. 问题

`game/engine/state_applier.py` 里同一个"这条路径允许 AI 写吗 / 是不是钱粮 / 能不能为负"的概念，
被拆成 **6 个手写集合**、由 **5 个各写一遍的匹配函数**消费；新增一个字段要人工同步多处，
漏一处不报错、只在运行期以"整批被拒"的形式暴露，报错点离病因很远
（[`engine/README.md`](../../../../game/engine/README.md) 自记的 2026-10-01 `payraise_budget` 教训）。

**实测规模（2026-10-12，静态解析 `state_applier.py`）**：

| 集合 | 条数 | 定义行 |
|---|---:|---|
| `VALID_PATHS` | 35 | :29 |
| `NON_NEG_PREFIXES` | 24 | :86 |
| `MONEY_PATHS` | 9 | :382 |
| `GRAIN_PATHS` | 5 | :388 |
| `RANGE_100_FIELDS` | 11 | :77 |
| `CLAMP_01_FIELDS` | **0** | :72（空通道，有意保留） |
| 合计登记 | **84** | 去重后 **38 行** |

另有 `NO_CONSERVATION_PATHS = None`（:395，全库零引用的死常量，本轮**保留**）。

## 2. 现状语义（必须逐字保持，本轮不改）

### 2.1 五份匹配实现、三种 flavor

| 谓词 | 精确 | 尾点前缀 `.` | 无边界 `startswith` | 段通配 `*`（段数须等长） |
|---|---|---|---|---|
| `_path_ok` :114 | ✅ | ✅（`era_state.`） | ❌ | ✅ |
| `_is_clamp01` :133 | ✅ | ❌ | ❌ | ✅ |
| `_is_range100` :144 | ✅ | ❌ | ❌ | ✅ |
| `_is_non_neg` :156 | ✅ | ❌ | **✅** | ✅ |
| `_match_pattern` :398（MONEY/GRAIN） | ✅ | ✅ | ❌ | ✅ |

**同一路径在不同集合里语义可以不同**（这正是本轮**不**引入单一 `match` 字段的原因）：

```
NON_NEG_PREFIXES 含 "granary" → 无边界 startswith；GameState 同时存在 "granary" 与 "granary_cap"
⇒ _is_non_neg("granary_cap") == True，而 _path_ok("granary_cap") == False
```

宽松前缀实际只对 **9 条单段条目**生效（`treasury` / `imperial_treasury` / `granary` /
`payraise_budget` / `prestige` / `population_satisfaction` / `art_mastery` /
`land.hidden_households` / `waste_reform.savings`）；多段条目走段通配分支。
**`granary`→`granary_cap` 是当前唯一可观测分歧点**，今日经由白名单不可达。

### 2.2 集合间关系（实测）

```
MONEY ⊆ VALID ✅   GRAIN ⊆ VALID ✅   RANGE_100 ⊆ VALID ✅   RANGE_100 ⊆ NON_NEG ✅
NON_NEG \ VALID = 3 条：land.hidden_households、prefectures.*.pops.*.wealth、prefectures.*.pops.*.grain
```

⚠️ `MONEY \ NON_NEG` 作为**字符串集合差**是 6，但这是"同一概念用了不同粒度"的假象
（MONEY 写 6 个具体 POP 类、NON_NEG 写 1 条通配，段匹配下等价）。
**结论：不得用集合差或集合相等作为放行依据**（见 §6）。

### 2.3 顺序：单一声明顺序**无法**复现六个集合

对"每个集合内部相邻元素给出先后约束"建图后**存在环**，最小环 4 节点：

```
defense_lines.*.fortification → defense_lines.*.garrison     （VALID_PATHS 要求）
defense_lines.*.garrison      → land.hidden_households       （NON_NEG_PREFIXES 要求）
land.hidden_households        → waste_reform.savings         （NON_NEG_PREFIXES 要求）
waste_reform.savings          → defense_lines.*.fortification（VALID_PATHS 要求）
```

⇒ 38 行中有 35 行落在环内，**顺序恒等在单一声明结构下不可能**。
按用户裁定：不得伪称顺序恒等。本设计采用**行为证据前提下的放宽比较**（见 §6.2），
并把「是否改为按集合记录顺序元数据」登记为待追认决策（`B1-order-relaxation`）。

**顺序是否可观测（行为证据，非推理断言）**：五个谓词均为布尔判定、`_group_of` 组内返回常量、
守恒错误文案中的路径顺序取自**输入 `changes`** 而非注册表 ⇒ 注册表顺序不进入任何可观测输出。
该结论由 §6.2 的**洗牌不变性测试**证明，而不是靠本段文字。

## 3. 契约

新增 `game/engine/field_registry.py`（纯 stdlib，零 `core`/`ai` 依赖，不新增跨层边）。

```python
class Kind(Enum):  NUMERIC | NON_NUMERIC
class Cons(Enum):  MONEY | GRAIN | EXEMPT

@dataclass(frozen=True)
class PathRule:
    path: str                     # 唯一权威路径模式（字符串与迁移前逐字相同）
    kind: Kind                    # 必填
    cons: Cons                    # 必填：EXEMPT 也必须显式写
    writable: bool = False        # → VALID_PATHS
    non_neg: bool = False         # → NON_NEG_PREFIXES
    max_100: bool = False         # → RANGE_100_FIELDS
    clamp01: bool = False         # → CLAMP_01_FIELDS
    exempt_reason: str | None = None   # cons=EXEMPT 且路径名命中钱粮语义词时必填
    source: str = ""              # 口径出处／事故编号（承接原注释）
    legacy: str | None = None     # 历史例外说明（失效通道、只读镜像等）
```

**没有 `match` 字段**（用户 2026-10-12 裁定）。匹配语义**按集合**在 §2.1 说明；
B-1a/B-1b 都保留原有五个 matcher 实现与语义，五个函数体一字不改。

### 3.1 派生（六集合的唯一生成路径）

```python
RULES: tuple[PathRule, ...]                                  # 38 行
VALID_PATHS      = tuple(r.path for r in RULES if r.writable)
NON_NEG_PREFIXES = tuple(r.path for r in RULES if r.non_neg)
RANGE_100_FIELDS = tuple(r.path for r in RULES if r.max_100)
CLAMP_01_FIELDS  = tuple(r.path for r in RULES if r.clamp01)
MONEY_PATHS      = tuple(r.path for r in RULES if r.cons is Cons.MONEY)
GRAIN_PATHS      = tuple(r.path for r in RULES if r.cons is Cons.GRAIN)
```

`state_applier.py` 中这 6 个名字**继续存在**（B-1b 改为 `from engine.field_registry import ...`），
因此 `from engine.state_applier import VALID_PATHS` 的使用方**一行都不用改**。

### 3.2 治「漏注册」的机关

把默认从"未命中即豁免"反转为"**豁免也要显式声明**"：

- `cons` 必填、`EXEMPT` 显式 ⇒ 新增字段漏表态 = **声明自检失败**（测试期红），不再静默；
- `cons=EXEMPT` 且路径名命中钱粮语义词（`wealth|grain|treasury|granary|money|budget|savings|cost|tax|revenue|payment`）
  ⇒ 必须给 `exempt_reason`。

🔴 **关键词只触发"必须写理由"，绝不参与分类**。不得因为名字含 `savings` 就自动归入某守恒组。
现状分类（含 `waste_reform.savings` 的 EXEMPT）**原样保留**；分类是否正确属另一裁决。

### 3.3 自检 `validate_registry(rules) -> list[str]`

自检必须校验**传入的实际值**（`isinstance` 运行期判定），不得依赖 dataclass 类型标注：

| 检查 | 违反 |
|---|---|
| `path` 非 `str`／空串／含空段（`a..b`）／首尾空白 | 红 |
| `kind` 非 `Kind`、`cons` 非 `Cons` | 红 |
| 布尔位非 `bool`（含 `numpy.bool_` 之外的 0/1） | 红 |
| `exempt_reason` 非 `str`/`None` | 红 |
| 重复 `path` 且语义不一致 | 红 |
| `cons ∈ {MONEY, GRAIN}` 但 `writable=False`（今日 14 条全部 writable，成立） | 红 |
| `RANGE_100 ⊆ NON_NEG` 不成立 | 红 |
| `kind ≠ NUMERIC` 却带 `non_neg`/`max_100`/`clamp01`/`cons≠EXEMPT` | 红 |
| `max_100` 与 `clamp01` 同时为真 | 红 |
| `MONEY` 与 `GRAIN` 同时命中同一行（结构上不可表达，保留防御） | 红 |
| `cons=EXEMPT` + 命中钱粮语义词 + 无 `exempt_reason` | 红 |
| `MONEY/GRAIN/NON_NEG/RANGE_100/CLAMP_01 ⊆ VALID`（关系自检） | 红（MONEY/GRAIN/RANGE_100/CLAMP_01 必须成立；NON_NEG 今日**不**成立，见 §3.4） |

### 3.4 必须原样保留的 3 条"在 NON_NEG、不在 VALID"

`land.hidden_households`（失效行）、`prefectures.*.pops.*.wealth`、`prefectures.*.pops.*.grain`（通配比白名单宽）。
**不得删、不得收窄、不得改写成具体类**（E1–E8 冻结）。因此"`NON_NEG ⊆ VALID`"**不是**自检不变式。

### 3.5 运行时可达性检查（测试期，非 import 期）

用 `new_game()`/`GameState("史实")` 真状态把每条 `writable` 声明**具体化**（`*` → 真实路/派系名），
断言 `_locate_path` 不返回"中间层缺失"。这条钉死历史事故 `focus.*.unlocked` / `factions.*.power`
（"不要宣告不存在的能力"）。

⚠️ **必须实例化真状态，禁止源码正则**：实测 `self.payraise_budget: int = 0`（带类型标注）会被
`self\.(\w+)\s*=` 漏掉，产生 3 个假阳性。

## 4. 迁移映射

| 现状集合 | 条数 | 落成 | 语义变化 |
|---|---:|---|---|
| `VALID_PATHS` | 35 | 每条第 1 行，`writable=True` | 无 |
| `NON_NEG_PREFIXES` | 24 | 与 VALID 重叠的 21 条**合并行**置 `non_neg=True`；余 3 条单独立行（`writable=False`） | 无 |
| `RANGE_100_FIELDS` | 11 | 合并行置 `max_100=True` | 无 |
| `CLAMP_01_FIELDS` | 0 | 无行（`clamp01` 位保留） | 无 |
| `MONEY_PATHS` | 9 | 合并行置 `cons=MONEY` | 无 |
| `GRAIN_PATHS` | 5 | 合并行置 `cons=GRAIN` | 无 |

**兼容路径 / 动态字段 / 历史例外**：六个常量名与五个谓词名全不动；`era_state.`（尾点前缀）与 `*`（段通配）
由字符串原样承载；`controlled_by` 是唯一需要 `kind=NON_NUMERIC` 的条目（否则自检会要求给字符串字段加非负）。

## 5. 影响面

| 类别 | 内容 |
|---|---|
| 新增 | `game/engine/field_registry.py`；`_dev_tools/game-dev/tests/test_field_registry_parity.py` |
| 改（B-1a） | **无**（生产判定路径零改动，`state_applier.py` diff 应为空） |
| 改（B-1b） | `state_applier.py`：6 处字面量 → 导入派生；**五个 matcher 不动** |
| 回归但不改 | 4 个生产调用方：`ai/client_utils.py:1196`、`core/situation_settle.py:101`、`core/settlement_common.py:539`、`core/commands.py:1147`；7 个既有测试模块 |
| 文档 | 本目录三份；`game/engine/README.md` §关键约定 5；`specs/README.md` 索引；`specs/cross-cutting/decree-action-chain/tasks.md` 受管写路径行 |
| 明确不改 | `game/core/**` 规则与账本、`game/ai/**`、POP/粮/商品守卫与桥接、`SONGZUO_POPS_GUARD`、数值口径、存档 schema |

## 6. 兼容性测试设计（三层 + 两项门）

原则：**不得仅凭"生成后集合相等"宣布安全**；所有期望值必须来自**旧实现的实跑记录**，不得把未验证的预期当旧行为。
golden 由 [`_dev_tools/game-dev/b1_baseline_probe.py`](../../../../game-dev/b1_baseline_probe.py) 产出：
六集合**从 git 修订**提取（不读工作树），`--emit` 前有 fail-closed 守卫（工作树与 `--rev` 不一致即拒绝写出）；
证据链与独立复核见 [`tasks.md`](tasks.md) §C。

### 6.1 L1 集合层

- 六集合 vs **冻结 golden**（迁移前逐字抄录，存于测试模块）比对 **多重集相等**；
- 输出**顺序分歧报告**（哪几个集合的顺序无法由单一声明复现、以 §2.3 环路为证据），
  **不断言顺序恒等**。

### 6.2 L1.5 顺序不变性（行为证据，替代顺序恒等）

对每个集合取 N 个随机排列（固定种子），在样本集 P 上断言五个谓词输出**完全不变**，
并对 3 个代表性 `applier_pipeline` 场景断言结果不变。
⇒ 这是"放宽顺序比较"的**前提证据**；证据不成立则停止，改走"按集合记录顺序元数据"分支。

### 6.3 L2 谓词层

样本集 P（覆盖：每条声明的具体化实例与字面形、段数错配、`era_state` 三态边界、
`granary`/`granary_cap`/`granary_` 宽前缀边界、大小写、空串、`"."`、非 `str`、POP 全 6 类 × {wealth,grain}、
**第 7 类 `pops.吏.wealth`**、`focus.*.unlocked`、`factions.*.power`）上，
断言 `_path_ok` / `_is_non_neg` / `_is_range100` / `_is_clamp01` / `_group_of` 与 **旧实现实跑 golden** 逐条一致。

### 6.4 L3 管道层

对 14 个场景断言 `applier_pipeline` / `apply_to_state` 的
`applied`（path/old/new）/`rejected`/`errors`/`conservation_failed`/`CHANGE_LOG` 长度 与状态摘要，
与旧实现实跑 golden 逐字段一致。场景覆盖：单字段 set、钱组成对、单边补记账、无关键词硬拒绝、
钱组穿底、**非**守恒字段穿底（只截断不整单拒）、通配 fix 预分摊、多 Agent 合并、cascade、
`push` 到数值字段、`max_100` 的 set 越界 / add 负增量、`era_state.` 前缀通道、第 7 类 POP 拒绝、
**中间层缺失 → KeyError → 逆序回滚 → `CHANGE_LOG` 不追加**。

🔴 **回滚场景先做旧实现基线**：该路径历史审计从未真正执行过。若旧实现**不满足**预期，
登记为独立缺陷（`decisions`），**不得借 B-1 顺手修复**，也不得把新旧差异包装成"重构验收通过"。

### 6.5 放行门

- 定向：`test_field_registry_parity.py` + 7 个既有相关模块；
- 全量：`pytest _dev_tools/game-dev/tests`，记录**基准提交标识**与完整结果；
- 总用例数会因新增测试而增加：**验收看"无新增失败/错误 + 跳过项变化有解释"**，不机械比总数。

## 7. 回退

1. B-1a 生产判定零改动 ⇒ 回退 = 删除新增文件（或 revert 单提交）。
2. B-1b 单提交 revert ⇒ 回到 B-1a 的字面量形态；L1/L2/L3 golden 与 §6.2 证据留在测试模块，revert 后仍可运行。
3. 任一阶段出现行为差异 ⇒ **立即停止**，保留证据，重新裁定。
4. 禁用 `git checkout -- .` / `git clean`；保留工作区他人未提交改动。

## 8. 与 B-2/B-3/B-4 的边界

B-1 只消除"同一字段的校验规则要人工维护多份"这一失效模式，且仅在 `state_applier` 的六集合范围内。
**不宣称**四类事故已被结构性消除；B-2（守卫进放行门、哪些违规阻断/仅记录）、
B-3（实际跨步写入检测）、B-4（测试验证生产调用方）各自实施并通过各自测试后，才作对应结论。

---
最后更新：2026-10-12（设计修订：删除 `match` 字段、六集合顺序不可复现的环路证据、自检校验实际值、关键词不参与分类）。
