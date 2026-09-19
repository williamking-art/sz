# 记忆库专项检查（2026-09-19）

> 范围：游戏内记忆子系统的**功能核对 + 缺陷定位**。对话记忆库 `memory/dialogue_memory.py`、
> 主记忆库 `memory/memory_graph.py`、读写接线（`core/commands.py`、`core/settlement*.py`、
> `core/save_load.py`）、只读端点（`backend/server.py`）、前端记忆面板。
>
> 检查方式：真实存档只读核对（`~/Documents/宋祚/saves`）+ 临时槽位端到端复现 + 全量测试。
> 真实存档未被写入（`slot_0_dialogue.db` 检查前后同为 `dialogues=30 / summaries=0`，mtime 未变）。

## 一、结论

**机制本身成立，问题集中在「呈现层缺通道」**。玩家看到的两个症状（召对面板只有开场白、
记忆面板「召对纪要」空白）各自有独立根因，且都不是记忆算法本身出错 —— 是**存了一半、
读了没有、而展示时机与生成时机错位**。本次已修 4 项（含 3 项通道缺失 + 1 项归属错标），
另有 5 项登记为待决（含 1 项容量治理口径问题，属平衡决策，未擅自改）。

## 二、症状与根因（实测证据）

### 症状 1：召对面板关掉再开，对白全没了

- 根因：`panels/AudienceView.tsx` 的会话流只存在组件 `useState` 里（开场白为硬编码字符串），
  **面板无任何留档回读**；后端也没有按大臣取会话流的接口。
- 证据：`state.dialogue_history` 确实随存档落盘（`core/save_load.py:124/419`），但它是**扁平
  混合表** `[(speaker, text), …]`（所有大臣混在一起、「朕」之言不归属到人），无法用于分人会话。

### 症状 2：记忆面板「召对纪要」空白

- 根因：该栏只读 `summaries` 表，而该表仅在 `finish_turn` 中 `state.turn % 3 == 0` 时生成
  （`core/commands.py`）。玩家连续召对 30 次而**从不推进回合** → `summaries` 恒空 → 面板恒空。
- 证据：真实 `slot_0_dialogue.db` = `dialogues 30 / summaries 0`，30 条全部 `summarized=0`、`turn=0`。
- 反证（机制无辜）：手工调用 `summarize_dialogues(0)` 立即把 30 条压缩成 1 条概要；
  `finish_turn(0)` 亦触发（`0 % 3 == 0`）。**即：能生成，只是玩家没走到生成时机。**
- 附带缺陷：`/api/memory` 只返回 `dialogue_summaries`，**全无原始对话字段**；上一批新增的
  `fetch_dialogues_by_ids` / `summary_refs` 没有任何 API/面板消费方 → 「细节按需下钻」在
  API 与面板层是断的（AI 侧 `query_for_dialogue` 用了，玩家侧没用）。

### 症状 3（隐藏）：会话流只有大臣说话

- 根因：`dialogues` 表的写入点只有 `audience_dialogue_apply`（写回奏），
  `audience_dialogue_prepare` 里的「朕言」只进 `dialogue_history` 内存表，**从不落库**。
- 因此即使修好症状 1、2，回看也只能看到单边对白 —— 面板无法呈现「问 + 答」。
- 同类缺口：本地预过滤模板与召对缓存复用两条分支在 `prepare` **之前** return，
  整轮对话既不落库也不进后续总结（面板回看出现「整轮空缺」）。

## 三、已验证正确（不算问题，勿改）

| 项 | 验证方式 | 结果 |
|---|---|---|
| 记忆库随存档、分槽隔离 | `save_game(3)`/`save_game(0)`/`load_game(3)`/`load_game(0)` | `slot_3.db`/`slot_0.db` 各自独立、无交叉污染 |
| 读档不得「记得未来」 | DB 水位 7 > 存档水位 2 时 `load_game` | `memory.turn` 对齐为 2，检索不返回未来回合关系 |
| 结算失败回滚 | 两库 `rollback_after(turn)` | 只删 `> turn`，不误删同回合合法写入 |
| 归档幂等且不物理删 | `archive()` 两次 | 首次归档 1 条、二次 0 条；`relations` 长度不变 |
| 只读端点零写 | `/api/memory` 调用前后 `len(entities/relations)` | 不变 |
| 冲突合并不丢数据 | `summarize_dialogues` 重复期 | 走 `ON CONFLICT` 合并追加，对话不静默丢弃 |

## 四、本次已修（含验证）

1. **两侧对白对称入库**：`audience_dialogue_prepare` 补写 `speaker="朕"` 行，
   `topic` 取 `_topic_key(player_input)` 使问答同组。
2. **短路路径统一写入口径**：新增 `_record_dialogue_row()`，预过滤模板／召对缓存复用／
   `_apply` 三处共用（失败不阻断召对，兼容层 `dialogue_history` 保留）。
3. **概要按发言者标注**：不标注则陛下口谕被并入大臣之言，而该概要会作为「卿前番之言」
   喂回 AI —— 等于让大臣把上意记成己见。现按 `speaker：text` 标注。
4. **只读回放接口**：`list_dialogues`（完整会话流：不因 `summarized` 丢行、不截断正文、
   按时间正序、含两侧）、`list_sessions`（会话列表：末条预览/条数/末次回合）。
5. **端点会话视图**：`GET /api/memory?minister=<名>` → 该大臣会话流 + 其按期纪要 +
   涉其近关系 + 全量 `sessions`；不传参即原全局视图（契约不变）。
6. **区间归属错标**：`summarize_dialogues` 的 `start_turn/end_turn` 原式 `p*3-3+1`（第 1 期标
   「1–3」）与分组口径 `turn//3` 错开一期 —— 面板「第1–3回合」下挂的其实是第 3–5 回合的对话。
   现改为第 p 期 = `[3p, 3p+2]`，并加回归断言。
7. **前端重制**（用户定稿）：召对面板改社交式会话面板（会话名录 + 消息流 + 传谕栏），
   记忆库内嵌为顶栏按键开合的右侧抽屉（纪要／会话原文／相关关系／史略／留痕 + 水位条）；
   留档回放与会话列表消费上述新接口，空态直接说明生成时机（不再出现「空白无解释」）。

## 五、仍存问题（待决，本次未改）

| 级别 | 问题 | 说明 / 建议 |
|---|---|---|
| P1 | 归档接线**零测试覆盖** | `finish_turn` 的 `state.turn % 12 == 0 → mg.archive()`（`core/commands.py`）与 `memory_graph._ARCHIVE_INTERVAL = 12` 是**两处独立硬编码**，改一处即静默漂移；且无任何测试触碰该分支。建议抽单一常量 + 补「第 12 回合确实调用 archive」断言。 |
| P1 | 容量治理早期近乎空转 | `MEMORY_ARCHIVE_WEIGHT=0.25`，而 `MEMORY_RELATION_DECAY` 里 `governs λ=0.01` → 需 `Δ ≥ ln(1/0.25)/0.01 ≈ 139` 回合（约 11.6 年）才归档；`produces/involves λ=0.03` → 47 回合；`promises λ=0.05` → 28 回合。**属平衡口径，未擅改**；建议按「首次归档应在 12–24 回合内发生」反解阈值，或按关系类型分别定阈。 |
| P2 | 会话流无界增长 | `dialogues` 只打 `summarized=1` 标记、从不删；`list_dialogues` 有 `limit`，但库本身无上限（长局累积）。可考虑按 `MEMORY_ARCHIVE_WEIGHT` 同思路做冷归档，或保留「原文全留」并明确为设计选择。 |
| P3 | 全局面板只加载一次 | `MemoryPanel` 仅在挂载时取一次 `/api/memory`（手动刷新）。会话抽屉已随召对自动刷新；全局面板建议同样加「回合变更后自动刷新」或轮询。 |
| P3 | 内帑调拨不入会话流 | 内帑提议/批准走 `propose/confirm_inner_transfer` 动作（非 `audience_dialogue`），是**即时气泡**、不落对话库，关面板后不再回看（待准状态本身在 `state.pending_inner_transfer`，未丢信息）。若要回看需在动作侧补写。 |

## 六、测试覆盖变化

- 新增 `_dev_tools/game-dev/tests/test_audience_session_stream.py`（10 项）：三条召对路径两侧落库、
  已薨不伪造对白、`list_dialogues` 完整性/正序/`limit`/只读、`list_sessions` 末条预览、
  空库不抛、概要发言者标注、区间归属、`/api/memory?minister=` 收窄且只读。
- 全量：471 → **481 passed / 0 failed**（含他人未提交的 `test_memory_recall.py` 12 项全绿）。
- 前端：`tsc --noEmit` 通过；`electron-vite build` 通过（renderer 1.96 MB，产物含全部新面板文案）。
- 探针：`_dev_tools/_scratch/audit-2026/_probe_dialogue_panel.py`、`_probe_audience_stream.py`（全 PASS）。
