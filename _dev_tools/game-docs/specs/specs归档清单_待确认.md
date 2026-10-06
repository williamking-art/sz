# specs 归档清单（待确认）

> 2026-10-06 阶段0：**本文仅交付清单，未移动任何文件**。

## 总览

| 目标子目录 | 条目数 |
|---|---|
| `specs/construction/` | 8 |
| `specs/cross-cutting/` | 6 |
| `specs/diplomacy/` | 5 |
| `specs/economy/` | 5 |
| `specs/population/` | 3 |
| `specs/transport/` | 2 |
| **合计** | **29** |

## 映射明细（现路径 → 目标路径）

| 现路径（相对 `specs/`）| 目标 | 主归属理由 |
|---|---|---|
| `README.md` | `cross-cutting/` | specs 索引，跨全部机制 |
| `代码层机制模块化架构方案_2026-10-06.md` | `cross-cutting/` | 架构方案，跨全部机制 |
| `decree-action-chain/` | `cross-cutting/` | 政令链路＝工作流，跨全部业务域 |
| `州府级真账总批计划.md` | `cross-cutting/` | 州府级真账：同时牵动 POP/建筑/交通/钱，无单一主属 |
| `州府级真账计划_深化版.md` | `cross-cutting/` | 同上（深化版） |
| `语义核对_public_support与gentry_resistance.md` | `cross-cutting/` | 民心/士绅抵制为治理横切指标，被建设与政治共用 |
| `seats下沉_根因诊断.md` | `population/` | POP 挂载与身份子池拆分＝人口域基础 |
| `新局seats下沉_落地受阻记录.md` | `population/` | 同上（受阻记录） |
| `yields与POP结构不相容_决定性发现.md` | `population/` | 结论落在 POP 结构与产出需求不相容 |
| `market-civilian-economy/` | `economy/` | 市场/需求/工价 |
| `unified-civilian-market/` | `economy/` | 统一民用市场 |
| `消费端实测_真在消费吗与能否复购.md` | `economy/` | 消费端复购＝市场需求 |
| `地方府库下沉州府级_阻塞记录.md` | `economy/` | 地方府库＝财政载体 |
| `种植产出归属税收_设计稿与影子推演.md` | `economy/` | 主线是归属与税收；种植归生产但本文重点在税基 |
| `建设主体与产权设计.md` | `construction/` | 建设主体与产权 |
| `建造部门_民间与官有.md` | `construction/` | 建造部门与劳役 |
| `营造部门实体的治理语义与落点.md` | `construction/` | 营造部门实体 |
| `营造部门线_落地状态与验证.md` | `construction/` | 营造线状态与验证 |
| `官有营造建筑清单与规格草案.md` | `construction/` | 官有营造清单与规格 |
| `官有营造付款渠道_未完成.md` | `construction/` | 官有营造的付款阻塞；虽涉钱账本，阻塞点在营造 |
| `非经济回报的落点与映射.md` | `construction/` | 建设的非经济效用 |
| `九维建筑基数校准与盐异常.md` | `construction/` | 九维建筑产出参数 |
| `ROUTE_WATERWAY逐路可航性.md` | `transport/` | 逐路可航性 |
| `交通下沉州府级.md` | `transport/` | 交通的州府级化 |
| `宋与外邦贸易设计.md` | `diplomacy/` | 外邦贸易设计主线 |
| `外贸调研_开局关闭且不走货.md` | `diplomacy/` | 外贸市舶调研 |
| `外贸缺失是实现缺陷非史实认定.md` | `diplomacy/` | 外贸实现缺陷认定 |
| `接入前规则收口与接入方案.md` | `diplomacy/` | 外贸接入方案 |
| `接入条件5_6事实核查.md` | `diplomacy/` | 外贸接入条件核查 |

---

## 需裁定：production 缺口

本次清单只建 6 个子目录（按你的裁定），但以下文档的主归属是**生产机制**：

| 文档 | 实为 |
|---|---|
| 九维建筑基数校准与盐异常 | 建筑产出参数 |
| 种植产出归属税收_设计稿与影子推演 | 生产与产出 |
| 消费端实测_真在消费吗与能否复购 | 需求与复购 |

=> 本清单把前者归 construction/、中者归 economy/（以税基为主线）、后者归 economy/。
**这是「正好归别处」，不是真正的主归属。**

**请裁定**：是否新增 production 子目录，还是维持现有 6 个。

---

## building_jobs.py 函数职责拆分清单（本阶段不移动）

文件 800 行 / 18 函数。按你的裁定拆分：

### 归建设机制（2 个）

| 函数 | 行范围 | 职责 |
|---|---|---|
| `evolve_building_levels` | 337-420 | 建筑等级演化（升级/降级都是事件，非时间衰减）|
| `pay_construction_cost` | 717-748 | 营造费与出资（升级费全额转给工匠 POP wealth）|

### 归生产机制（16 个）

| 函数 | 行范围 | 职责 |
|---|---|---|
| `song_job_cfg` | 85-120 | 岗位配置 |
| `_lv` | 123-133 | 建筑条目→等级（兼容旧写法） |
| `building_level` | 136-157 | 建筑等级统一读口 |
| `_positions_of` | 160-173 | 建筑→职位映射 |
| `jobs_by_position` | 176-190 | 分职位岗位数 |
| `jobs_of` | 193-195 | 岗位总数 |
| `allocate_employment_detail` | 198-260 | 多职位优先队列就业分配 |
| `allocate_employment` | 263-271 | 就业分配（兼容签名） |
| `produce_grain_track` | 274-298 | 轨 A 生计轨（粮） |
| `produce_job_track` | 301-334 | 轨 B 岗位轨（原料/成品） |
| `job_flow_unemployed` | 423-482 | 失业驱动的阶层流动 |
| `live_job_buildings` | 488-517 | 筛出在册且岗位>0 的建筑 |
| `apply_employment_flow` | 520-665 | 岗位缺口驱动阶层流动（ΣPOP 守恒） |
| `pay_wages_from_revenue` | 672-714 | 雇佣与发薪 |
| `apply_bankruptcy` | 751-799 | 轻量倒闭 |

### 跨界依赖（已实测）

- `building_level` / `_lv` 是**只读建筑等级**口，而 `evolve_building_levels`（建设）需调用它 => 拆分后 `production` 依赖 `construction` 的读口。
- `apply_employment_flow` 与 §3.6 层次演进耦合。

=> **不能整文件搬移**：拆分后需先抽**共享读口**（如 `foundation/ledger` 或 `domains/construction/read_models/`）。

---

## 本轮未做

- 未移动 specs 任何文件（待你确认清单）；
- 未移动 `building_jobs.py` 任何实现；
- 未改任何 import；
- 未运行全量测试（本轮无代码变更，上一轮基线 = 2305 passed）。

