# `game/content/` · 游戏静态数据

本目录提供游戏数据、常量、地理行政基础、文案和大臣资料。复杂派生、结算规则与状态变更放在 `game/core/`，不要在数据表中复制运行逻辑。

## 模块索引

| 文件/目录 | 内容 |
|---|---|
| `data.py` | 向其他模块提供的兼容总入口；新增导出时同步维护显式导出表。 |
| `data_constants.py` | 规则常量、公式参数、档位和脱敏映射。`MATERIAL_PRICE_BASE` 是静态基准价；运行期价格发现由 `core/market_price.py` 负责。 |
| `data_tech.py` | 科技、建筑蓝图与研发相关静态数据。动态蓝图的校验/注册逻辑位于 `core/blueprint_dynamic.py`。 |
| `data_workshop_jobs.py` | **作坊岗位/月工价表（G-4 影子口径，2026-10-21）**：酒坊/畜栏/麻坊/丝坊按每级岗位数显式登记，月工价沿用 `WAGE_RATE` default 1.5 贯/岗；⚠️ **玩法设定、非史料**，仅用于 `workshop_fund_shadow` 影子预算，不接正式结算。 |
| `data_imperial.py`、`data_decree.py` | 年号、帝行与诏令内容/参数。 |
| `data_military.py`、`data_external.py` | 军制、兵种、军械及外部势力/省域静态数据。 |
| `data_geo_tables.py`、`geo_admin.py` | 路级地理经济数据与路/府等行政归属。地图几何资源另见 `game/assets/map/`。<br>⚠️ `geo_admin.CIRCUIT_INFO.members` 是**州府实体清单的权威来源**（136 席，主键 `路\|治所`）；`REGIME_DEMOG` 的道/区域总量为**游戏设定值**（辽已于 2026-10-02 按《辽史》对齐为 55 万户）。 |
| `demography.py` | 地区人口/经济派生读数；按实际调用方确认用途，不作为独立人口账本。<br>⚠️ 外邦州府级 `regime_prefecture_demog()` **强制带口径标注**：`historical_ub`（辽，史料上限+分摊）／`setting`（西夏·吐蕃·大理，**玩法设定/未有可靠总量**），并附 `source`／`is_historical` 回答"谁报告、依据是什么"；**禁止**标成 `historical`。宋侧崇宁户口见 `data_households_hist.py`。 |
| `data_households_hist.py` | **宋州府级史料户口**（《宋史·地理志》崇宁户），已录 96 席、13/21 路成路。<br>纪律：**只收「崇宁户」**——「元丰户」（万州/施州）与**无年号**者（汉州/兴化军）**一律不入表**；同名不同府须查原文「本X州」映射（常德府本鼎州、宝庆府本邵州、赣州本虔州、瑞州本筠州…）。 |
| `seat_products.py` | **《宋史·地理志》州级贡物 → 物料维映射表**（卡1.4 · 2026-10-04）。66 条显式映射，`validate_map()` 自校验防拼写错误落维。⚠️ **贡物是存在性证据、不含数量** ⇒ 只用于产地权重，**不可当产量**；无记录 ≠ 不产，**不得归零**。未映射 149 种**如实登记，不臆造商品凑数**（AGENTS §3-7）。 |
| `seat_aliases.py` | （**未落地**）治所别名对照表 —— 游戏简体名与《宋史》完整地名精确匹配仅 7/126，子串匹配已否决。待人工考据，**不臆造**。 |
| `data_external_admin.py` | **外邦州府静态表（P1 只读骨架，2026-10-19）**：辽/西夏/高丽/日本/大理/安南的 T1 州府名、相对权重、近似坐标；**不填人口/兵力、不接结算**，仅登记行政区划。 |
| `data_prefecture_demog.py` | **生成物，勿手改**。由 `build_prefecture_demog.py` 生成，把路级总量拆到 136 州府，`basis` 四态（`historical`/`area_x_anchor`/`area_only`/`merged`）**写在表内作单一来源**。 |
| `build_prefecture_demog.py` | 州府人口经济表生成器。**含恒等式自检，`Σ子+residual==父级` 不成立即拒写**；已录史料且该路席位齐全者按**崇宁户比例**分配，否则回退"面积×锚点"（部分覆盖不启用，避免同路掺两种口径）。 |
| `build_map_geo.py` | 舆图数据构建工具；资源生成和前端消费路径见 `game/assets/map/README.md`。 |
| `codex_data.py`、`codex_text.py`、`legacy_gazette.py`、`situation_seeds.py` | 图鉴、开局邸报与局势种子内容。 |
| `faction_schema.py` | **势力配置的中立结构定义**（P1 · 2026-10-06 用户裁定）：**中立的是结构/校验/查询接口，不是数据**；宋与外邦都是各自提供配置的势力。🔴 **不得把宋配置当外邦默认值**；官制（职位/职位→阶层映射/机构/官制参数）**全按势力提供**；经济基础建筑目录**跨势力共用**（不为外邦另造「粮田/桑麻田」重复类型）。缺失≠0 也≠1.0：本模块**只定义结构与校验，不提供任何默认数值**。 |
| `faction_registry.py` | **势力配置统一注册表**（P1）：按势力名加载 `content/data_factions/*`；**共用机制定义与势力参数分离**；查不到势力 ⇒ **显式报错**，**不落 default**。 |
| `data_factions/` | 各势力配置数据（宋/辽/西夏/吐蕃/大理…），结构契约见 `faction_schema.py`；见 [`data_factions/README.md`](data_factions/README.md)。 |
| `ministers/` | 大臣基础资料、人格、**M36.7-B+ 登记表 `registry.py`**、**B3 历史候选库 `roster.py`** 和相关立绘资源，见 [`ministers/README.md`](ministers/README.md)。 |

## 修改约定

1. 同一规则数值只保留一个权威来源；兼容导出集中在 `data.py`，不在调用方复制常量。
2. 改人口、税负、产量或商品基准数据时，核对对应机制文档、结算消费方和存档迁移；历史报告中的基线不自动代表当前参数。
3. 动态价格、交易、需求与市场读数在 `core/` 有不同职责；不要因为本目录含静态价表，就认为动态交易机制不存在或已自动接入。
4. 大体积资源的入库规则以仓库忽略配置与 `game/assets/README.md` 为准；修改资源前确认它属于源料、运行资源还是可重建产物。
5. 新增/调整货币账户、库存或 POP 子池，须同步核心账本口径和回归覆盖，确保来源与去向可追踪。

相关专题：[`游戏机制说明.md`](../../_dev_tools/game-docs/docs/游戏机制说明.md)、[`POP改良_合并版_2026-09-27.md`](../../_dev_tools/game-docs/analysis/POP改良_合并版_2026-09-27.md)。
