# workflows — 流程编排层

> 2026-10-06 · 阶段 0（架构基线）建包 · **2026-10-09 第二十二包起有实现**
> （`evaluation.py`，旧路径 `core.evaluation` 留薄转发桩）。
> 逐包状态唯一权威 = `game/core/foundation/README.md`。

| 代码域 | 责任 | 现有候选 | 不负责 |
|---|---|---|---|
| **提案流程** | 玩家意图/AI 建议 → 结构化提案 | commands_decree 拟诏、decree_plan、longterm_* | 不拥有业务计算 |
| **校验流程** | 完整性/合法性/可执行性；确认、复核、拒绝 | decree_confirm、契约校验、机密知情边界、**终局/退位/收束判定（`evaluation`）** | **不以叙事文本代替执行** |
| **执行流程** | 派发到业务域，协调跨机制用例 | commands、plan_commit | **不复制业务规则**，不拥有第二份状态 |

## 流程约束

提案 → 校验/确认 → 执行 → 结果回报。简单命令可跳过不适用步骤，但**必须有显式路径**。
命令入口不得私自复制业务规则。

## 迁移状态

- ✅ **第一份实现落地（第二十二包，2026-10-09）**：`evaluation.py`（205 行，结算评价 + 终局判定）。
- ⬜ 阶段 3 仍从 `commands.py` 抽回合生命周期协调（`decree_plan` 方向阻塞，见架构方案 §2 注记）。

### `evaluation` 为什么落这里（§7 写的是"基础或应用支持域（逐项定）"，实测排除了两个候选）

| 候选 | 判定 | 实测证据 |
|---|---|---|
| `core/foundation/`（基础层） | ❌ 不可 | `evaluate_game` 取用业务域符号 `core.domains.military.army_models.army_power`（`:31` 函数内），基础层引业务域＝违 §6 硬规则 1（依赖只向下） |
| `game/application/`（应用层） | ❌ 不可 | ① `application/__init__.py:7` 把 `core.evaluation` 写成**应用层向下依赖的东西**；② 主要生产消费者是 `core/commands.py:68`（**顶层** import，另 3 处调用点 `:307 :938 :963`）——搬上去就等于让 `core` 顶层引 `application`，正是 `application/__init__.py` 禁令② 挡的那条边；③ §5.2 落地注记里 `commands → application` 一律**函数内延迟**，本批不该把它变成顶层 |
| `core/workflows/`（流程编排层） | ✅ 采用 | 出边 `content.data` + `core.domains.military.*` 全为**向下**；入边来自 `core.commands`（接口适配层）与 `application.turn_lifecycle`（应用层），方向都合法；原先"平铺 core 引业务域"这条可疑边，落层后方向才成立 |
| 新建 `core/domains/outcome/` | ❌ 未采 | 为单个模块预设新业务域＝在 §1 的 9 域之外再造一层，属"预设固定数量"，与本方案"模块数量由实际机制边界决定"相反 |

## 落层后的两条不许回潮的口径（`evaluation`）

1. **防线阈值是两套语义，不得合并**：退位判"任一边防空虚"（阈值 20、无年份约束），
   京城陷落判"指定线 `内线_东京城防` 且年 ≥1126"（阈值 10）；缺 `garrison` 键时
   取默认 **100**（不是 0）。常驻用例 = `test_workflows_evaluation_b22.py`。
2. **打在旧桩上的 patch 无效**：消费者按 `core.workflows.evaluation` 延迟导入，
   `monkeypatch.setattr(core.evaluation, …)` 会静默不生效。本批抓到一处并已随迁
   （`test_turn_lifecycle.py::test_terminal_check_never_unsets_game_over`，加了 `fired` 断言防退化空跑）。

