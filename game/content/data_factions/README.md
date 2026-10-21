# content/data_factions — 势力中立表结构

> 玩家自设/中立势力的**表结构**与各势力配置。
> 依据：用户裁定「**官制因势力而异**」「**经济基础建筑目录跨势力共用**」。

## 模块（1 个）

| 模块 | 内容 |
|---|---|
| `song.py` | 宋的势力配置（P1）。**引用** `core/building_jobs` 的 `SONG_*` 常量，不复制数值 |

## 🔴 关键语义（易被误改）

- `get('liao')` **返回 `None`**——那是「查不到」，**不是 0、也不是 1.0**（`AGENTS.md §3` 缺失 ≠ 0 ≠ 1.0）。别写回落默认值。
- `check_not_applicable_reason` 会**拒绝**「暂无数据 / 未实现 / todo」这类占位语，避免用一句空话把「为什么不适用」糊弄过去。
- 势力配置**不得复制** `core/building_jobs` 的数值，只引用（单点来源）。

上级索引见 [`../README.md`](../README.md)；集团归属/校验的单点在 `core/faction_basis.py`（**不存在** `core/faction_registry.py`）。
