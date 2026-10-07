# domains/culture — 教育与礼仪

> 2026-10-06 · 阶段 0 建骨架。
> **2026-10-07 第二十包：本包已有实现**（`literacy.py`，`git mv` 自 `core/`，历史保留）。

## 拥有的规则

识字率（各地各类 POP 自有的社会属性）、科举、教化、礼仪等规则。
当前实际落地的只有**识字率**一条；科举/教化/礼仪**尚未实现**，本包不为它们预留空模块（§10）。

## 已迁入实现（第二十包，2026-10-07）

| 文件 | 来源旧路径 | 公开面（dir() 实测） | 依赖方向 |
|---|---|---|---|
| `literacy.py` | `core/literacy.py` | 桩 **27** 名（37 去 10 个 dunder；含 `_num`/`_clamp`/`_CLASSES`/`_region_mod`/`log`/`logging`/typing 与 `annotations`）| 顶层只 `__future__` + typing + logging + `core.foundation.common.numeric` 的**公开名** `parse_number`/`clamp` ⇒ 业务层向下依赖基础层，合 §6 硬规则 1 |

### 口径（既有设定，本批**只搬不改**）

- **挂载**：`prefectures[路]["pops"][阶层]["literacy"]`，是 POP 自有比率；
  逐路/全国读数是**按 `size` 加权**的派生值，**不落第二份账**（`pop_bridge.MEAN_FIELDS = ("literacy",)`）。
- **不可求和**：实测同一 state 下加权值 = 8.41，而直接求和 = 4977.62（差两个数量级）——
  这是 `test_national_literacy_is_weighted_average_not_sum` 钉住的前提。
- **缺失 ≠ 0**：读不到一律 `None`；实测清空 120 行后 `national_literacy` → `None`，
  而不是回落 0（根 AGENTS §3-3）。
- **唯一写入点**：`settle_literacy`（只写 `pops.*.literacy` 与派生值 `state.literacy`）。
  实测新局开局即稳定点（`init_literacy` 补的就是目标值），故首步结算**一个字段都不动**。
- **缓动**：月度只走 6% 差距（`LITERACY_CONVERGE`），教育是慢变量。

### 判据④（同批完成）

生产 **5 文件 / 6 引用点**改指新路径，旧路径 `core.literacy` 生产引用 **0**：
`decree_effect.py:102`、`game_state.py:1022`、`region_brief.py:42`、
`save_load.py:617`+`:618`、`settlement_econ.py:416`（全部是**函数内延迟导入**）。
测试侧 **3 文件 / 4 点**保留旧桩（兼容门面）。计数：`_scratch/b21_refcount.py literacy core.domains.culture.literacy`。

🔴 **提供方打桩必须随迁（本批唯一一处，也是最容易静默失效的一处）**：
`test_error_observability_settle.py:379` 原先 `import core.literacy as lit` +
`monkeypatch.setattr(lit, "init_literacy", _boom)` 往**桩**上注入异常。
消费者 `save_load.py` 改直认真实家之后，这枚 patch 就打在没人读的名字上——
用例**照绿却什么都没注入**。已同批改指 `core.domains.culture.literacy`，
并且**做了反向变异证明**：把这一行退回旧桩 ⇒ 该用例立刻红（`test_m9_..._warnings_carry_slot_and_type`）。
另加常驻禁令 `test_no_test_patches_the_old_literacy_stub`（AST 解析别名，两种形态都算）。

### 等价性实测（不是只比文本）

`_scratch/b20_equiv_check.py` 用 `git show HEAD:game/core/literacy.py` 重取迁移前原文，
落成临时模块与新实现**同 state 跑同名函数**：10 项输出逐项相等，
并**连跑 12 个月结算**逐月比 `out` 与每个 POP 的 `literacy` ⇒ 轨迹完全相同。
结构比对逐顶层节点比 `ast.dump`，**已声明漂移 1 处**：模块 docstring
——原文写"阶级基准（content.data.POP_LITERACY_BASE）"，实测 `content.data` **没有**这个表
（它定义在本模块 `:57`），属文档与代码不符，按 §6.1 顺手改正（纯注释级，不改任何计算）。

## 未随批搬的候选

- `situation_*` / `events`：§3.1 归**政治与世界状态**，不属本包（`events` 还在 [17] 平铺大环内）。
- 科举/教化：当前**没有对应实现**，不建空模块（§10「缺少功能标作待建，不造空模块或伪实现」）。

## 边界

- 向下依赖 foundation（账本/状态）与 game/content（数据）；**不得反向导入 workflows 或上层**。
- 机制间协作**经显式接口**，不得跨域读写私有内部结构。
- 读数是只读投影，**不得成为结算算法权威**。

## 迁移状态

**已开始**（第二十包，2026-10-07）：`literacy` 已迁入并完成生产改道；本包其余玩法**尚未实现**。
