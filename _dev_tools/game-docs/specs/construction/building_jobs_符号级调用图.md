# `building_jobs.py` 符号级调用图（迁移前置）

> 2026-10-06 阶段 0/1 · **只读分析，未移动任何实现、未改任何 import**。
> 承用户裁定：「`apply_employment_flow` 的层次流动耦合先记录为跨域接口事项，**等符号级调用图确认后再拆**」。

## 一、函数间调用（内部，17 函数）

| 调用方 | 被调用 |
|---|---|
| `jobs_by_position` | _lv, _positions_of |
| `jobs_of` | jobs_by_position |
| `allocate_employment_detail` | jobs_by_position |
| `allocate_employment` | allocate_employment_detail |
| `produce_grain_track` | _lv |
| `produce_job_track` | _lv, allocate_employment |
| `evolve_building_levels` | **building_level** |
| `job_flow_unemployed` | _lv |
| `apply_employment_flow` | _lv, allocate_employment, live_job_buildings |
| `apply_bankruptcy` | _lv |

## 二、被外部模块导入

| 函数 | 导入者 |
|---|---|
| `song_job_cfg` | settlement_econ |
| `building_level` | **asset_context, civil_building, era_mechanic, settlement** |
| `allocate_employment` | settlement_econ |
| `produce_grain_track` | settlement_econ |
| `produce_job_track` | settlement_econ |
| `evolve_building_levels` | settlement_econ |
| `job_flow_unemployed` | settlement_econ |
| `apply_employment_flow` | settlement_econ |
| `pay_wages_from_revenue` | settlement_econ |
| `apply_bankruptcy` | settlement_econ |

**主要消费者：`settlement_econ.py`（导入 8 个函数）**。

## 三、🔴 证实你的裁定：等级读口是**真跨域接口**

| 证据 | 说明 |
|---|---|
| `_lv` 被 **7 个函数**内部调用 | `jobs_by_position` / `produce_grain_track` / `produce_job_track` / `job_flow_unemployed` / `apply_employment_flow` / `apply_bankruptcy` 等 |
| `building_level` 被 **4 个外部模块**导入 | `asset_context` / `civil_building` / `era_mechanic` / `settlement` |
| **`evolve_building_levels`（建设）调用 `building_level`** | 调用图实证了「生产 → 建设」方向的跨域读依赖 |

⇒ **裁定成立**：`_lv` 与 `building_level` 应作为**建设域公开只读等级接口**，生产域**单向调用**。
⇒ **不入 `foundation/ledger`** —— 它们是业务读口，不是账本通道。

## 四、🔴 新发现：`pay_construction_cost` **生产代码零调用**

```
game/core/building_jobs.py:717   def pay_construction_cost(...)
tests/test_building_jobs.py:199  cost_info = pay_construction_cost(...)   # 仅测试
docs/…/主要国家与外邦设定分层.md:139  # 仅文档列举
```

全仓检索命中 10 处，**全部是定义、测试或文档**，**没有任何结算/生产路径调用它**。

⇒ 属「**实现已写但未接线**」，与本会话反复遇到的同类问题一致
（市舶开关、`canal_efficiency` 科技、`gentry_resistance` 无下游）。

⚠️ **须裁定**：它是（a）漏接线（应接入营造成本流程），还是（b）已被 `civil_building` 的
「料款与工钱彻底分离」机制**取代**（故可删）？**不臆断** —— 两种可能都存在，
**须以 `civil_building` 与本函数的实际职责比对后才能定**。

## 五、跨域接口事项（记录待拆，承裁定）

| 事项 | 状态 |
|---|---|
| `apply_employment_flow` 与 §3.6 层次演进的耦合 | 🔴 **已记录**，等符号级调用图确认后再拆 |
| `_lv` / `building_level` 作为建设域公开只读接口 | ✅ **调用图已证实**，可进入迁移 |
| `settlement_econ` 导入 8 个函数 | ⚠️ 迁移时须同步改导入方，否则断链 |

## 六、本轮未做

- 未移动 `building_jobs.py` 任何实现；
- 未改任何 import；
- 未改业务逻辑。
