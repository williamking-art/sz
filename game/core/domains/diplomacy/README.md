# domains/diplomacy — 外交与外事

> 2026-10-06 · 阶段 0（架构基线）· 本包为空骨架：未移动实现、未改 import

## 拥有的规则

外交协议、外邦交互和外事读数

## 已迁入的实现（第十四包，2026-10-07）

| 文件 | 来源旧路径 | 符号（= 旧路径公开面，含私有） | 叶子资格判据 |
|---|---|---|---|
| `treaty.py` | `core/diplomacy_treaty.py` | `TREATY_TYPES` `_att_delta` `apply_treaty` + 6 个 content 常量 | AST 实测顶层 import 只有 `content.data`，**零反向边** |
| `external_view.py` | `core/external_view.py` | `external_pop_view` `external_provinces` + 3 个 content 表名 | 同上，**零反向边** |
| `map_overlay.py` | **新建**（2026-10-19 舆图 M3）| `map_overlay` `overlay_summary` | **只读**：按 `state.regions` 派生舆图 overlay（owner/occupied/transition/owner_changed）；不写 state、不重建 geojson；开局 owner_changed=0（视觉零变更） |

⚠️ 两条旧路径都保留 `dir()` 显式转发桩（**含私有名**），迁移前后名字集合逐字相等。
⚠️ `external_view` 生产侧被引 **0** 次：本批只搬代码，**不得据此声称外邦视图已接入**，也不得按死代码删。

## 边界

- 向下依赖 foundation（账本/状态）与 game/content（数据）；**不得反向导入 workflows 或上层**。
- 机制间协作**经显式接口**，不得跨域读写私有内部结构。
- 读数是只读投影，**不得成为结算算法权威**。

## 迁移状态

**🔵 已开始**（第十四包：2 个零反向边叶子入包，生产侧 2 处调用改指新路径）。
**未做**：§7 同域候选里的外贸/市舶规则尚未盘点；外交**协议数据**的真账归属未定（现仍挂 `state` 字段）。
