# 开工门台账 · 建筑 / 经营主体 / 岗位 / 生产域

> 依据：设计文档 §14.1 开工门要求。**只读盘点，未改任何代码。**
> ⚠️ **本台账为 Lead 亲自核实**（盘点子代理超限失败，未产出）。每条给 `文件:行`。

## 一、建筑载体

| 载体 | 权威数据 | 粒度 | 写法 | 写入点 | 读取点 |
|---|---|---|---|---|---|
| `prefectures[路]["buildings"]` | 建筑等级槽 | **路级** | **三种并存**（见下） | 见下 | `building_level()` 统一读口 |
| `state.workshops` | 全局作坊列表 | **全局**（键名含路名，账务不分路） | `{wid: {...}}` | `game_state.py:539-568`、`save_load.py:938` | `settlement_econ.py:1535` |
| `state.projects` | 工程 | 项目级 | `{pid: {...}}` | `construction.py`、`blueprint_dynamic` | `settlement_tech._settle_projects` |
| `state.resources[dim]` | 全国仓 | 全国 | `{stock, cap}` | `production_chain.py:78` | 见 market 台账 |

### 1.1 `buildings` 的**三种写法**（这是 P2 的首要障碍）

| 写法 | 写入点 | 有建成月？ | 读法 |
|---|---|---|---|
| 标量 `{"工坊": 2}` | `civil_building.py:988`（岗位类）<br>注释见 `building_jobs.py:139`（称 `_settle_projects` 实际写法） | ❌ | `building_level()` 兼容 |
| `{"lv": n}` | `building_jobs.py:375` | ❌ | 同上 |
| `{"lv": n, "built_month": m}` | `civil_building.py:996` | ✅ **全库唯一有建成月的** | 同上 |
| 纯 int 路径 | `settlement_tech.py:520-537`（工程完工落成，静态+动态蓝图） | ❌ | 待核具体写法 |

- ✅ **统一读口存在**：`building_jobs.py:136 building_level(entry, default)` —— 兼容标量/结构、**保留 0**（`{"closed": true}` → 0）。
- 🔴 **缺"可运营月份"**：除 `civil_building` 的 `built_month` 外，**无任何建筑能表达"完工当月还是次月生效"**
  ⇒ P2 要求"统一规定生效时点"目前**无处承载**。

## 二、岗位与产能

| 机制 | 权威数据 | 五态 | 说明 |
|---|---|---|---|
| 宋侧岗位标定 | `building_jobs.py:54 SONG_JOBS_PER_LEVEL` | 已接线 | `农田 {}`**生计轨不占岗**；`自耕农庄{自耕农120,富农20,贫农20}`；`地主农庄{佃农100,地主20}`；**`工坊{工匠160}`**；**`商铺{商人40}`**；`庄园{佃农100,地主20}`（旧档别名） |
| 职位→POP类 | `building_jobs.py:62 SONG_POSITION_CLASS` | 已接线 | 多职位可横跨多个 POP 类 |
| 主职位兼容层 | `:66 SONG_BUILDING_WORKER` | 已接线 | 单职位调用者/外邦扁平表用 |
| 岗位序 | `:70 SONG_JOB_QUEUE` | 已接线 | POP类→建筑岗位序（同月不重复计入） |
| 配置访问器 | `:85 song_job_cfg()` | 已接线 | 返回**新 dict**；派生 `BUILDING_POSITIONS` / 扁平 `JOBS_PER_LEVEL` |
| 岗位类建筑表 | `content/data_constants.POP_BUILDING_TYPES` | 已接线 | 键集**与 `SONG_JOBS_PER_LEVEL` 相同** |
| 建筑资产单价 | `POP_BUILDING_VALUE = 100000`（**标量**） | 已接线 | 维护费 = 单价 × 等级 × 0.5%/月；调用点 `building_jobs:54,102,105`、`civil_building:87,113,208,272,391`、`settlement_agri:194`、`settlement_officialdom:102,119` |
| 就业分配 | `building_jobs.allocate_employment` / `apply_employment_flow` | 已接线 | 容量≠实到（待核是否有"容量当就业"处） |
| 作坊配方 | `content/data.WORKSHOP_RECIPES` | 已接线 | 酒坊/畜栏/麻坊/丝坊 |

## 三、生产与分派

| 环节 | 位置 | 说明 |
|---|---|---|
| 开局作坊 | `game_state.py:539-568` | 每路 2 酒坊 + 2 畜栏；**B1 补**每路 1 麻坊 + 每 3 路 1 丝坊（共 107 个） |
| 作坊耗料 | `settlement_econ.py:1535` 起 | 从**全局** `state.resources` / 太仓扣 |
| 成品分派 | 🔴 `settlement_econ.py:1608-1634` | **按各路工匠 `size` 占比分派**到各路工匠 `goods`；末路取余数保 Σ 不丢 |
| 生产链入仓 | `production_chain.py:78` | 按路 `yields` 年额÷12×建筑乘数 → **全局** `state.resources` |
| 工程领料 | `settlement_tech.py:403-420` | 从 `state.resources` 真扣；按 `_mat_left_*` 摊还 |
| 工程款 | `settlement_tech.py:421-446` | 按 `_coin_left` 摊还；经 `transfer_public_funds_to_pops(GOV_SPEND_TO)` 真付给**本路工匠/商人** |
| 民间营造 | `civil_building.py`（Step 3.85） | 四动因；料真扣仓、钱经 `transfer_money` 划转本路工匠；**唯一写 `built_month` 处** |
| 农业投资 | `settlement_agri.py`（Step 3.5.2） | 四项成本先扣后产；维护费走既有 `_settle_upkeep` |

## 四、未闭合流向（按严重度）

| # | 流向 | 证据 | 影响 |
|---|---|---|---|
| 1 | 🔴 **作坊产出地点丢失 → 按人口占比分派** | `settlement_econ.py:1608-1634` 自陈"作坊产出是**全局**记账（`state.workshops` 不分路），故按各路**工匠 size 占比**分派" | **直接违反设计文档 §14.1**「不允许用人口比例分派掩盖地点缺失」；P2 首要解决 |
| 2 | 🔴 **`buildings` 三种写法并存** | 标量 `civil_building:988` / `{lv}` `building_jobs:375` / `{lv,built_month}` `civil_building:996` | 结构不统一 ⇒ P2 的"建筑实例"无处落；**任何新字段都要兼容三种** |
| 3 | 🔴 **无"可运营月份"概念** | 仅 `civil_building:996` 有 `built_month` | P2 要求"完工当月/次月生效应统一"**无处承载** |
| 4 | 🟠 **`buildings` 与 `workshops` 是两套产能来源** | `buildings`=等级槽（岗位）；`workshops`=全局配方产能 | 设计文档点名"建筑等级/岗位、政府项目、全局 `state.workshops` 配方产出**并非统一实体**" |
| 5 | 🟠 **无所有者/经营者/产权字段** | 三种写法里都只有等级（+建成月） | P2 要求的"蓝图版本/所有者/经营者/维护责任/经营方式/生产方法"**全缺** |
| 6 | 🟠 **`POP_BUILDING_VALUE` 是标量** | `content/data_constants.py`，全库一个值 | 无法按建筑类型区分资产价值；维护费对所有建筑一视同仁 |

## 五、对 P2「建筑资产—经营主体并轨」的直接建议

**可复用**（勿重造）：
- ✅ `prefectures[路]["buildings"]` 作为**唯一建筑载体**（**全库无第二份建筑账本**，已核）
- ✅ `building_level()` 作为**唯一读口**——新字段必须让它能读
- ✅ `SONG_JOBS_PER_LEVEL` / `song_job_cfg()` 作为岗位权威（**不要另建岗位表**）
- ✅ `civil_building` 的 `built_month` 作为"可运营月份"的**既有先例**——建议推广到所有建筑
- ✅ `settlement_tech` 的 `_coin_left`/`_mat_left_*` 摊还口径（B4-6 已过门）

**必须新建**：
1. **建筑实例 schema**：`blueprint_id / 等级 / built_month / 所有者 / 经营者 / 维护责任 / 经营方式 / 生产方法 / 岗位容量与实到 / 配方 / 投入产出库存 / 收入去向`
   —— 建议**首期嵌在 `buildings[name]` 的结构写法里**（§14.4 允许"经营记录嵌在建筑实例中"），
   但**必须同时兼容标量与 `{lv}` 两种旧写法**（否则旧档全崩）。
2. **`state.workshops` 的地点迁移**：键名已含路名（`麻坊_京畿路_2`），**地点信息是有的**——
   应**解析键名补出地点字段**，而不是重建作坊；无法解析的进**显式"未定位桶"**，
   **不得按工匠占比继续分派**。
3. **停业/停产状态**：`{"closed": true}` 已被 `building_level` 认作 0，可复用为新语义入口。

**坑（有证据）**：
- ⚠️ `workshops` 的键名格式是 `{类型}_{路名}_{序号}`，**路名解析要防歧义**（路名本身含"路"字，如"京畿路"；序号在末段）
- ⚠️ 改分派口径会**立刻改变各路工匠 `goods`**，进而影响布/绸成交与价格 ⇒ 必须**先加守恒回归**再改
- ⚠️ `POP_BUILDING_VALUE` 是标量：若 P2 要按类型区分资产价值，**先确认维护费通道不会双计**（B4-6 已踩过一次）
