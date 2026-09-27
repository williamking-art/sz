# `game/engine/` —— 世界状态应用层（AI 契约的落地口）

> 上级规范：[`game/README.md`](../README.md) ｜ 测试：[`test_step_gap_fills.py`](../../_dev_tools/game-dev/tests/test_step_gap_fills.py)、[`test_three_schemes.py`](../../_dev_tools/game-dev/tests/test_three_schemes.py)

## 职责

把 **AI/大臣产出的结构化"契约"**（JSON）安全地写进 `GameState`。是"AI 说了什么"与"世界变成什么样"之间**唯一的落地口**。

| 文件 | 职责 |
|---|---|
| `state_applier.py` | 契约应用器：路径白名单（`VALID_PATHS`）、非负校验（`NON_NEGATIVE_PATHS`）、**整批回滚 + 抛异常**语义、金钱/粮食守恒分组（`MONEY_PATHS`/`GRAIN_PATHS`）、治理级联（`CASCADE_REASON_FIX`）等 |

## 关键约定（改这里最容易出事）

1. **白名单即能力边界**：AI 只能写 `VALID_PATHS` 里声明过的路径。新增可写字段必须同时考虑：
   非负/范围校验、是否属"钱/粮"守恒组、是否需要 cascade、以及"是否本来就该由程序算"。
   - 反例（历史教训）：曾声明 `focus.*.unlocked` 等路径，但 `GameState` 无该字段 → 寻址必然失败，
     而本模块是**整批回滚**语义 → AI 一旦产出即连带同批合法变更全部作废。**不要宣告不存在的能力。**
2. **人口属"人"轴**：`land.hidden_households` 已从白名单移除（人口必须落 POP 子池，见 `core/pop_structure.py`）。
3. **整批原子性**：任一路径非法 → 本批全部不生效并抛异常（调用方据此让 AI 重试），不要在里面做"部分成功"。
4. 契约的**结构校验**在 `game/ai/schemas.py`（JSON Schema），**语义校验**在 `game/ai/validators.py`，
   本层只管"写入与守恒"。三层职责不要混。

## 相关

- 契约生成与校验：`game/ai/`（`contracts_*.py`、`schemas.py`、`validators.py`、`free_effect`）
- 效果口径：`core/decree_effect.py`（诏令）、`core/free_effect.py`（自由效果）
