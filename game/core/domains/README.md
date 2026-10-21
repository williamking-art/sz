# `game/core/domains/` — 机制域索引

> **2026-10-21 新建**：各机制域有自己的 README，但域根此前没有总索引。
> 本页只做导航与"实现是否已迁入本目录"的现状说明；算法单点与迁移总表见
> [`../README.md`](../README.md) 与 [`../foundation/README.md`](../foundation/README.md)。

| 目录 | 机制 | README | 现状 |
|---|---|---|---|
| `administration/` | 行政与官制（考课、磨勘、科举、官额） | [README](administration/README.md) | 部分实现已迁入，其余仍在 `core/` |
| `construction/` | 建设机制（营造、升级、产权、建筑下沉） | [README](construction/README.md) | 部分实现已迁入 |
| `culture/` | 教育与礼仪（识字率、礼制） | [README](culture/README.md) | 部分实现已迁入 |
| `diplomacy/` | 外交与外事（使节、岁币、外贸路线） | [README](diplomacy/README.md) | 部分实现已迁入 |
| `economy/` | 财政与市场（需求、价格、贸易、采购、读数） | [README](economy/README.md) | 主要实现已迁入，`core/` 仍有结算编排 |
| `military/` | 军事机制（军队、战役、军令、边患） | [README](military/README.md) | 部分实现已迁入 |
| `politics/` | 政治与世界状态（派系、事件、诏令、长期案卷） | [README](politics/README.md) | 部分实现已迁入 |
| `population/` | 人口与户籍（POP、隐户、州府下沉） | [README](population/README.md) | 部分实现已迁入 |
| `production/` | 生产机制（农业、工坊、产业链、岗位） | [README](production/README.md) | 部分实现已迁入 |
| `transport/` | 交通与物流 | [README](transport/README.md) | **实现仍在 `core/transport.py`**（未迁移；README 已更新为当前事实） |
| `events/` | （预留）事件域 | — | **空目录**，无代码；事件机制当前在 `core/events.py`，迁移前勿在此建实现 |

## 纪律

- 本目录下**新模块不得导入旧转发桩**（`core/xxx` 兼容层）；域间不得横向 import，跨域协作走 `foundation/` 或显式接口。
- `transport/` 是"目录先建、实现未迁"的典型：改运力/队列请去 `core/transport.py`，不要按目录臆造新实现。
- 每域 README 记录该域**当前事实**；迁移进度以 `foundation/README.md` 的迁移表为准。
