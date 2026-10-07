# renderer/data — 前端静态数据

> 构建期可读的 JSON 数据，**不含业务算法**。

| 文件 | 大小 | 用途 |
|---|---:|---|
| `codex.json` | 3738 行 | 图鉴/Codex 文案 |
| `constants.json` | 1770 行 | 前端常量 |
| `ministers_dict.json` | 346 行 | 大臣名录（显示用） |
| `focus_tree.json` | 197 行 | 焦点树结构 |

## 🔴 纪律

- 🔴 这些是**显示用副本**，不是权威源。玩法口径单点在 `content/` 与 `core/`，
  在此改数值会造成两套口径分叉。
- `ministers_dict.json` 是名录快照；新增大臣以 `content/ministers/` 为准。
