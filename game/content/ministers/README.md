# content/ministers · 大臣数据与立绘

> 层归属：**游戏本体**（数据层）。

## 关键内容
| 文件/目录 | 说明 |
|---|---|
| `data.py` | 大臣名单、立绘路径解析（**优先级 0 = 分层合成**）、分层素材索引 |
| `persona.py` | 人格（persona）：性格/立场/危险度等，供叙事与判定使用 |
| `layers/` | **分层合成输入**（头层 + 身体层 PNG；`_offsets.json` 定位）——**打包必须携带** |
| `portraits/` | 成品立绘（合成失败时的回退；`_composed/` 为按需缓存、不入库） |

## 关联
- 合成器：`game/core/minister_profile.py::compose_portrait`（经 `/api/portrait/<file>` 供前端）；
- 打包白名单：`SongZuo.spec` 的 datas 明确包含 `content/ministers/layers/` 与 `portraits/*.png`（排除 `_composed`）。
---
最后更新：2026-09-27（补目录文档）
