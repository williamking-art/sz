# domains/military — 军事机制

> 2026-10-06 · 阶段 0 建骨架。
> **2026-10-07 第二十一包：本包已有实现**（`army_models.py`，`git mv` 自 `core/`，历史保留）。
> `settlement_military.py` 仍在 `core/`（它在平铺大环内，属阶段 3 裁定项）。

## 拥有的规则

军队模型（编制/装备/士气/训练/欠饷）、募兵裁军、军令与军事结算的**规则侧**。

## 已迁入实现（第二十一包，2026-10-07）

| 文件 | 来源旧路径 | 公开面（dir() 实测） | 依赖方向 |
|---|---|---|---|
| `army_models.py` | `core/army_models.py` | 桩 **36** 名（45 去 9 个 dunder；含 6 个私有名与 `dataclass`/`field`/`Optional`/`branch_std`/`annotations` 等绑定名）| 🔴 **零 `core` import**：顶层只 `__future__`/`dataclasses`/`typing` + `content.data`（12 个数据名），函数内只 `content.data.ARMY_ORG`（纯内容叶子）|

### 口径（既有设定，本批**只搬不改**）

- 部队规模由 content 表驱动：实测开局 **35 支**（禁军/厢军/乡兵三档 × 各路），
  `_DEFENSE_LINE_OF` 5 条防线、`EQUIP_KEYS` 7 项装备实物键。
- 战力与军饷走**纯函数**：`army_power`（单车）、`army_power_total`（编制总）、
  `unit_monthly_pay`、`unit_enforcement_mult`；实测 `army_power_total(开局编制, 火药=20) = 298950.0`。
- `resolve_battle` 是**确定性**判定（无随机数），实测 `(100, 50) → (胜, 10.0, 未破城)`。
- `__all__` 只有一项 `EQUIP_STD`——这是**迁移前既有事实**（`from core.army_models import *` 只给这一项），
  本批不"顺手补全"：扩大 `*` 公开面属于口径变更。桩按纪律**原样拷贝**该列表。

### 🔴 同批销了一笔 §6 规则2 的账：四个私有名提升为显式接口

迁移前有 **4 个跨模块生产点**直接取用私有名——`evaluation.py:31`（`_army_power`）、
`settlement_imperial.py:468`（`_army_power`/`_army_power_total`/`_resolve_battle`）、
`settlement_steps.py:265`（`_army_power_total`）、`settlement_tech.py:510`（`_defense_line_for`）。
搬进 `domains/military/` 后它们就成了"跨域读写私有内部函数"，正是 §6 规则 2 禁止的形态。
销法照第十/十二包先例：在实现末尾加 **4 行公开别名**（`army_power`/`army_power_total`/
`resolve_battle`/`defense_line_for`，**同一对象**而非包装），把 4 个消费者的 import 与 6 处调用点
改指公开名，旧 `_` 名保留为兼容别名（桩面因此逐字不变）。

两个常驻断言钉住：`test_public_aliases_are_same_objects`（是别名不是复制）、
`test_production_never_imports_private_names_from_new_home`（扫全 `game/`，任何人再从新路径取
`_` 开头名字立即红）。

### 判据④（同批完成）

生产 **11 文件 / 11 引用点**改指新路径，旧路径 `core.army_models` 生产引用 **0**；
测试侧 **5 文件 / 8 点**保留旧桩（兼容门面）。
计数：`_scratch/b21_refcount.py army_models core.domains.military.army_models`。

🔴 **提供方打桩随迁（本批被红抓到的实例）**：`test_decree_effect.py` 有 **3 个用例**
用 `import core.army_models as am` + `monkeypatch.setattr(am, "military_channels", …)`
喂假可靠度（钳位/上限/单调性三组口径）。消费者改道后这些 patch 落到旧桩上——
`test_military_mult_is_clamped_for_display` **当场红**（期望 1.0，实测 0.8118，即真实通道的值）。
三处已同批改指实现模块，并做反向变异（退回旧桩 ⇒ 该用例再红）证明随迁是必需的。

### 等价性实测

`_scratch/b21_equiv_check.py`：`git show HEAD:game/core/army_models.py` 重取原文 →
同 state（深拷贝两份）跑 **12 项**比对——含会改状态的 `reorganize_xiang_to_jin` 与
`distribute_arsenal`，比输出**并比两边的 state 快照**（部队序列 + 武库库存）⇒ 全部相等。
逐顶层节点 `ast.dump`：**0 处漂移**，追加节点正好是 4 个公开别名 `Assign`（已声明）。

## 未随批搬的候选

| 候选 | 实测事实 | 为什么本批不搬 |
|---|---|---|
| `settlement_military.py` | 在平铺大环（v3 口径 [17]）内 | 环内模块**禁止**"移动文件"式迁移（架构方案 §二约束），只能先抽接口再脱离，属阶段 3 |
| 兵额与 POP 的通道 | 军额变动经 `pop_bridge`（`military_channels` 只读） | POP 挂载律：军队人数**不许**在军事域另立账本，本包只消费读数 |
| 军饷/粮械 | 走既有账户与 `material_holding` | 同上：不复制账本 |

## 边界

- 向下依赖 foundation（账本/状态）与 game/content（数据）；**不得反向导入 workflows 或上层**。
- 机制间协作**经显式接口**，不得跨域读写私有内部结构（本批已清一笔，见上）。
- 读数是只读投影，**不得成为结算算法权威**。

## 迁移状态

**已开始**（第二十一包，2026-10-07）：`army_models` 已迁入并完成生产改道 + §6 规则2 销账；
`settlement_military` 待阶段 3 环内裁定。
