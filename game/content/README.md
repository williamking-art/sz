# `game/content/` —— 静态数据与内容（单一权威源）

> 上级规范：[`game/README.md`](../README.md) ｜ 文档：[`游戏机制说明.md`](../../_dev_tools/game-docs/docs/游戏机制说明.md)
>
> **本目录只放"数据/常量/文案"，不放逻辑**。逻辑改动请去 `game/core/`。
> 数值改动几乎都会影响长局平衡，改完请跑全量测试并看 `verify_money_fix`/长局探针。

## 一、数值与常量

| 文件 | 职责 |
|---|---|
| `data.py` | **游戏内容数据总入口**：静态数据表、跨模块 re-export（`from content.data import X` 的 X 大多在此转出） |
| `data_constants.py` | **公式常量 / 数值工具 / 档位契约 / 脱敏映射**（单一权威源）。含 `GRAIN_CONSUME_PER_CAPITA`（**六类 POP 的唯一权威清单**）、`PERSONS_PER_HOUSEHOLD`、`DING_RATIO`、`TAX_POLL_RATIO`/`POLL_TAX_NOMINAL_SHARE`、`POP_BUILDING_TYPES` 等 |
| `data_tech.py` | 科技树 / 建筑蓝图 / 研发预算 |
| `data_imperial.py` | 帝行矩阵 / 年号 / 个人行动 |
| `data_military.py` | 军制 / 兵种 / 军械 |
| `data_decree.py` | 诏令参数 / 固定程序模板 |
| `data_external.py` | 外部势力 / 省域 / 外交协议（含外邦 `EXTERNAL_ECON`：岗位表、工资率、价格带） |

## 二、地理与人口派生

| 文件 | 职责 |
|---|---|
| `data_geo_tables.py` | **路府州县地理表**（`PREFECTURE_INFO`/`PREFECTURE_LIST`）：每路 `households`/`population`/`land`/`grain`/`monthly_tax`/`yields` 等。**2000 万明户 × 5 口 = 1 亿在籍口**的口径在这里落数据 |
| `geo_admin.py` | 地理行政归属（路/府两级，单一权威源；含外邦道/司级 `district_base`） |
| `demography.py` | 州/府级人口经济**派生**（只读，单一权威源）——由路级总量 × 面积占比 × 席位权重推出 |
| `build_map_geo.py` | 舆图 GeoJSON **生成器**（开发期构建工具，不参与运行） |

## 三、文案与图鉴

`codex_data.py`（图鉴数据）· `codex_text.py`（图鉴文案，只读常量）·
`legacy_gazette.py`（开局邸报与待办三事）· `situation_seeds.py`（局势开局种子）

## 四、子目录

| 目录 | 内容 |
|---|---|
| `ministers/` | 大臣数据与他人设（`data.py`/`persona.py`）、**立绘素材**：`layers/`（分层部件，入库）、`portraits/`（成品立绘，入库；`_composed/` 是**合成缓存、不入库、可删**） |

## 五、纪律

1. **单一权威源**：同一个数只定义一次。`GRAIN_CONSUME_PER_CAPITA` 的键序就是"六类 POP"的权威定义
   （守卫测试 [`test_pop_class_single_source.py`](../../_dev_tools/game-dev/tests/test_pop_class_single_source.py)）。
2. **不要在本目录写业务逻辑**（保持"数据可审阅"）；派生读数请放 `core/`。
3. **改户均口数/税率类常量**：注意"(ii) 保财政绝对量"的口径链——`PERSONS_PER_HOUSEHOLD`、
   `TAX_POLL_RATIO`、`CRAFT_OUTPUT_PER_CAPITA`、`SALT_POP_BASE`、`ANNUAL_TAX_BASE` 之间存在
   等额关系（见 [`POP改良设计_对照V3_2026-09-27.md`](../../_dev_tools/game-docs/analysis/POP改良设计_对照V3_2026-09-27.md)），
   `test_farm_slices.py::test_poll_tax_amount_equal_to_b05_baseline` 会守住这条。
4. **大二进制不要随手入库**：立绘/地图每改一次就会在 git 历史里多一份完整 blob
   （2026-09-27 曾因此把 257 个资产的"历史版本"重置为单版本）。新增/替换大图前请先确认
   是否该走 LFS 或"资产不入库"（见 [sz/README.md](../README.md) §五）。
