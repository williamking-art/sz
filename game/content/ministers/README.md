# content/ministers · 大臣数据与立绘

> 层归属：**游戏本体**（数据层）。

## 关键内容
| 文件/目录 | 说明 |
|---|---|
| `data.py` | 大臣名单、立绘路径解析（**优先级 0 = 分层合成**）、分层素材索引 |
| `persona.py` | 人格（persona）：性格/立场/危险度等，供叙事与判定使用 |
| `registry.py` | **M36.7-B+ 大臣内容层登记表**（Q2 职责↔domain 映射、Q9 标签登记、v1 锁定）。**内容层静态数据、运行时只读**；机器判断只认**登记枚举**，自由文本只作叙事；映射不清标 `unknown`（不猜、不按名气补全）；标签**只描述取向**，**不得**用于权限/能力档位/数值；新增 domain/标签**先登记再使用**。覆盖范围以实测档案为准（2026-10-11：43 人／13 个 `trait_ids`／6 类派系） |
| `roster.py` | **M36.7-B3 1101 年历史人物候选库**（约 200 人名册，**只登记、不导入**）。三维严格分离：`historical_status_at_1101`（在世）／`office_status`（在任，读既有 `MINISTERS`，**本模块不写**）／`game_domains`（适合参与的领域，与在职无关）。铁律：**不批量导入**、**不编造**（未核验 ⇒ `None`/`unknown`）、**C/D 组不得入选廷议**、`game_domains` 只取 `DOMAIN_ENUM` |
| `layers/` | **分层合成输入**（头层 + 身体层 PNG；`_offsets.json` 定位）——**打包必须携带** |
| `portraits/` | 成品立绘（合成失败时的回退；`_composed/` 为按需缓存、不入库） |
| `paperdoll/` | **北宋官员 2D 布娃娃换装系统**（方案 B：3D 骨架烘焙 2D 工笔图层，无瑕换装与骨骼微动） |
| `costumes.py` | 官员公服规制（按官阶品级定义服色、革带带銙、鱼袋与朝笏品秩契约） |
| `portrait_assembler.py` | [DEPRECATED] 旧版立绘组装逻辑（已标记废弃，全面转入 paperdoll 模块） |
| `portrait_renderer.py` | 官员立绘渲染入口与品阶外观适配器 |
| `stats.py` | 大臣能力与属性数据结构定义 |

## 关联
- 合成器：`game/core/minister_profile.py::compose_portrait`（经 `/api/portrait/<file>` 供前端）；
- 打包白名单：`SongZuo.spec` 的 datas 明确包含 `content/ministers/layers/` 与 `portraits/*.png`（排除 `_composed`）。
---
最后更新：2026-09-27（补目录文档）
