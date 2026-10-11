# `game/engine/` —— 世界状态应用层（AI 契约的落地口）

> 上级规范：[`game/README.md`](../README.md) ｜ 测试：[`test_step_gap_fills.py`](../../_dev_tools/game-dev/tests/test_step_gap_fills.py)、[`test_three_schemes.py`](../../_dev_tools/game-dev/tests/test_three_schemes.py)、六集合一致性差分 [`test_field_registry_parity.py`](../../_dev_tools/game-dev/tests/test_field_registry_parity.py)

## 职责

把 AI 结构化变更请求安全地写入 `GameState`。它是 `changes` 类变更的受控应用路径，不是游戏中所有状态写入的唯一入口：自由效果和具体工具动作还会经过 `core/free_effect.py`、`game/ai/client_utils.py::_tool_dispatch` 等程序逻辑。审计变更时应按调用路径确认相应校验与守恒保护，不能把多条写入通道误记为单一写者。

| 文件 | 职责 |
|---|---|
| `state_applier.py` | 契约应用器：路径白名单（`VALID_PATHS`）、非负校验（`NON_NEG_PREFIXES`）、**整批回滚 + 抛异常**语义、金钱/粮食守恒分组（`MONEY_PATHS`/`GRAIN_PATHS`）、治理级联（`CASCADE_REASON_FIX`/`CASCADE_RULES`）等 |
| `field_registry.py` | 上述六套路径/规则集合的**唯一数据源**（B-1，2026-10-12）。一行 `PathRule` 声明 → `derive()` 生成六个集合；自检 `validate_registry()`。**刻意不承载**单位、真账归属、镜像关系与**匹配语义** |

## 关键约定（改这里最容易出事）

1. **白名单即能力边界，但清单只写一处**：AI 只能写 `VALID_PATHS` 里声明过的路径。
   新增可写字段 = 在 `field_registry.RULES` 加**一行**（`kind` 与 `cons` 必填，`EXEMPT` 也要显式写），
   六个集合由 `derive()` 自动生成；自检与差分测试见 `tests/test_field_registry_parity.py`。
   - 反例（历史教训）：曾声明 `focus.*.unlocked` 等路径，但 `GameState` 无该字段 → 寻址必然失败，
     而本模块是**整批回滚**语义 → AI 一旦产出即连带同批合法变更全部作废。**不要宣告不存在的能力。**
     现由"运行时可达性"用例钉住（声明必须能在真状态上寻址；禁止用源码正则判存在性）。
2. **人口属"人"轴**：`land.hidden_households` 已从白名单移除（人口必须落 POP 子池，见 `core/pop_structure.py`）。
3. **整批原子性**：任一路径非法 → 本批全部不生效并抛异常（调用方据此让 AI 重试），不要在里面做"部分成功"。
4. 契约的**结构校验**在 `game/ai/schemas.py`（JSON Schema），**语义校验**在 `game/ai/validators.py`，
   本层只管"写入与守恒"。三层职责不要混。
5. **新增钱字段：只改一行 `cons=MONEY`**（原「三处同注册」已于 2026-10-12 收口为单点声明）。
   `cons` 必填（`EXEMPT` 也要写），漏写即自检红；`cons=EXEMPT` 而路径名含
   `wealth/grain/treasury/granary/savings` 等词时**必须给 `exempt_reason`**
   （🔴 关键词只触发"写理由"，**不参与分类**）。漏 `MONEY` 的症状仍是最阴的：
   转账被配对校验判成"缺来源"而**拒掉整批**，报错点离病因很远
   （首次表现为 `transfer_public_funds_to_pops` 返回 0）。参考：`payraise_budget`（M2 加俸）现为一行的 `cons=MONEY`。
6. 🔴 **匹配语义不在这张表里**：五个 matcher 按集合各自保留——同一路径在不同集合里语义**可能不同**
   （`NON_NEG_PREFIXES` 的 `"granary"` 是**无边界前缀**，会命中 `granary_cap`；`VALID_PATHS` 的同名条目是精确匹配）。
   统一 matcher 属**未排期**的独立裁定，禁止借重构顺手收紧或放宽任何判定。
7. **本表不是万能元数据中心**：单位、真账归属、镜像关系、唯一写者都**不在**这里
   （权威源在机制文档与各机制模块，生命周期不同）。契约、顺序不可复现的环路证据与冻结清单见
   [`specs/cross-cutting/field-registry/`](../../_dev_tools/game-docs/specs/cross-cutting/field-registry/)。

## 相关

- 契约生成与校验：`game/ai/`（`contracts_*.py`、`schemas.py`、`validators.py`、`free_effect`）
- 效果口径：`core/decree_effect.py`（诏令）、`core/free_effect.py`（自由效果）
