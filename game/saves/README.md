# `game/saves/` —— 存档目录（运行产物，不入库）

> 上级规范：[`game/README.md`](../README.md) ｜ 存档实现：[`game/core/save_load.py`](../core/save_load.py)

## 职责

存放**玩家存档**（运行产物）。

- 目录内容被 `.gitignore` 忽略（`game/saves/*`），仅保留 `.gitkeep` 占位 → **不要在此提交任何存档**；
- 存档的**格式、版本迁移与兼容**是 `core/save_load.py` 的职责：新增字段请在读档路径做
  `setdefault`（幂等），并对旧档做显式迁移（如 `ensure_hidden_in_pops`、`ensure_farm_slices`）。

## 约定

1. **存档兼容是硬要求**：任何影响 `GameState` 结构的改动，都要问一句"旧档读得进来吗？"
   - 新增 POP 子池 → 读档时幂等补齐（已有先例：`land.hidden_households`、`农` 的职位/丁口子池、`士绅.estate*`）；
   - 新增字段 → `setdefault` 或在 `_init_extensions` 之后补。
2. **不要手工编辑存档**（zstd/JSON 结构复杂，且会绕过迁移逻辑）；测试请用
   [`test_save_roundtrip*`](../../_dev_tools/game-dev/tests/) 系列。
3. 多个存档槽位的合法性由 `backend/server.py` 与 [`test_slot_guard.py`](../../_dev_tools/game-dev/tests/test_slot_guard.py) 共同守着。
4. 排查"读档后数对不上"时，优先怀疑**迁移缺失**（旧档少了新子池）而非结算逻辑。
