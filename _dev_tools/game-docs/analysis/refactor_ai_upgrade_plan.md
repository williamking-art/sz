# 《宋祚》AI 架构升级实施计划（2026-08-20 · 整合今日全部改造）

> 状态：计划稿（先不动代码）
> 目标：AI 只通过 Function Call 返回结构化状态变更（changes）改状态；叙事 AI 灵活生成但受护栏；应用层统一验证/合并/执行/组装；本地引擎做确定性计算；Agent 按需唤醒；主 UI 不卡；记忆聚焦有效利用。

---

## 〇、架构总览（改造后）

```
AI（多 Agent，Function Call）→ 结构化 changes + narrative
  → 应用层管道（state_applier 验证/合并/cascade/写库 + narrative_guard 护栏 + memory_graph 写史）
  → narrative_assembler 组装叙事（changes + 记忆素材 + 句式库参考）
本地引擎：12 步结算 + 守恒（确定性，AI 不碰）
Agent 路由：route_agents 按需唤醒（关键词/状态/diff），未唤醒不耗 token
异步化：后台 AI 调用 + 主线程 after 回调（UI 不卡）
```

## 一、改造清单（今日讨论全部方向）

### A. LLM 调用层（ai/client.py）
1. **3 个 Tool Schema**（OpenAI function calling）：
   - `update_state`：changes（path/op/value/reason）+ triggered_events + narrative_hint；op ∈ set/add/mul/remove/push；每 change 必带 reason
   - `query_state`：paths（要查询的 JSON 路径）
   - `trigger_event`：event_id + context
2. **`_call` 支持 `tool_choice: "required"`**：AI 不返回 tool_calls（直接文本）→ 丢弃重请求，附带消息「你上次没有调用工具，请调用 update_state 或 query_state」
3. **`parse_tool_calls(response)`**：提取 tool_calls → 结构化 changes/triggered_events/narrative_hint

### B. Agent 层（34 契约 → 领域 Agent）
1. 每 Agent 调用前**只提取职责内状态子集**（如 finance 只看 treasury.*/tax.*，不给完整状态）
2. system prompt 约束：唯一输出=调用 update_state；禁止工具外自然语言；只改领域字段；不确定先 query_state；数值带 reason；连锁 ≤6 字段
3. 返回格式：`{"agent": "...", "tool_calls": [...], "raw_response": null}`
4. 失败/无效 changes → 错误日志 + 空 changes

### C. 应用层（engine/state_applier.py —— 已建）
1. **验证层**：path 白名单、op/value 类型、0-1 clamp、非负、错误收集返回重试
2. **多 Agent 冲突合并**：按 path 分组、add 累加、set+add 先 set 再 add、合并日志
3. **本地 Cascade**：可配置函数映射（派系 power 变化 → 对立派系反向等）
4. **原子写库**：写世界状态 + 变更日志（path/old/new/reason/source_agent）
5. **返回叙事层**：汇总 changes + narrative_hint

### D. 统一契约（{changes, narrative} 双通道）
- AI 输出 = {"changes": [结构化变更], "narrative": "AI 灵活叙事（受护栏）", "narrative_hint": "组装辅助"}
- changes 唯一改状态；narrative 经 narrative_guard（数字/来源闭集/人物）；句式库作文风参考
- 推演类（15）+ 叙事类（19）统一此契约（contract_adapter 映射表保语义）

### E. narrative_assembler（应用层管道）
- guard_narrative → apply_changes（free_effect 校验/执行）→ write_memory（从 changes 写史，非叙事文本）→ 返回

### F. Agent 路由按需唤醒（core/agent_router.py —— 已建 + 融合 settle_turn）
- 唤醒条件：关键词 / 状态触发 / 上轮 diff 路径；narrative 始终唤醒低 token；economy 始终唤醒
- 执行顺序：diplomacy → finance → military → narrative（前面变更注入后面 cumulative_diff）
- 未唤醒 Agent 不耗 token

### G. 领域融合（34 → 10 领域 Agent + 记忆子图）
| 领域 Agent | 聚合契约 | 记忆子图 |
|---|---|---|
| 推演官 | economy_decide | 经济史 |
| 财计 | finance/treasury/granary_decide + finance | 财计史 |
| 军务 | military_decide/military_expand/decree_execute | 军务史 |
| 使节 | diplomacy_decide + diplomacy | 外交史 |
| 按察使 | land_local/relief_decide + local_policy/land_manage/survey_settle | 民政史 |
| 史官 | era_decide + event_narrative | 时代史 |
| 知制诰 | parse_decree/draft/polish + free_effect/invest_decide | 政令史 |
| 铨选 | faction_decide/exam/emperor_personal/hidden_state | 人事史 |
| 起居注 | monthly_report/advice/council_review/final_eval | 朝局史 |
| 大臣 | dialogue | 召对史 |

### H. 异步化（core/async_ai.py）
- 后台（ThreadPoolExecutor ≤2 worker）只做 AI 网络调用 + 纯函数校验（不写 state）
- 主线程 after 回调落地/UI；UI 6 处同步调用点改异步 + 月度结算拆分（AI 推演后台 → 本地结算 → 叙事后补）

### I. 记忆有效利用（用户细化：一轮游戏 = 一个数据库）
**设计理由（用户）**：玩家游戏体验完整（历史连贯可查）+ 后期 AI 不容易漂移（推演有准确历史依据，不靠模糊记忆）。

**架构：一轮游戏 = 一个 SQLite 数据库**（`saves/slot_{slot}.db`，Python 内置 sqlite3）
```
saves/slot_{slot}.db
├── state 表      世界状态快照/变更
├── entities 表   记忆实体（id/type/name/attrs/turn/weight）
├── relations 表  记忆关系（src/dst/rtype/weight/turn/note）
├── summaries 表  压缩概要 + 周期总结（etype=summary/period_summary）
└── change_log 表 变更日志（path/old/new/reason/source_agent/turn）
```

| 需求 | 数据库机制 |
|---|---|
| 写入去重（所有 Agent 共用）| 唯一索引（entities: type+name；relations: src+dst+rtype）→ INSERT OR REPLACE |
| 精确检索/调动 | SQL 查询（领域/时间窗/rtype/top_k/权重排序）+ 索引加速 |
| 每 6 回合压缩（不动之前）| SQL 聚合近 6 回合 → 生成 summary 实体（旧数据不动）|
| 每 12 回合周期总结 | SQL 聚合本轮 → period_summary |
| 原子写入 | SQLite 事务（BEGIN/COMMIT，失败 ROLLBACK）|
| 变更日志 | change_log 表（append）|
| 层级检索 | 先命中 summaries（概要）→ 细节按需查 relations |

**与现有衔接**：`memory/memory_graph.py` 改 SQLite 后端（接口保留：add_entity/add_relation/query/summarize/compress/summarize_period/record_decision/record_event）；state_applier 写库入该 .db（原子事务）；主存档 JSON（GameState）+ 记忆 .db 同槽位分离（可重建）；旧 JSON 记忆文件迁移或重建。
**精确调动**：领域 Agent 只注入领域子图（SQL 领域过滤）+ 跨领域最小关联（相关 diff 摘要）；层级检索（概要→细节）；max_chars 预算截断。

## 二、我的落实建议（顺序 / 优先级 / 依赖）

### 建议顺序（依赖驱动）
```
P0 LLM 调用层（A）→ 一切基础（3 工具 + _call 强制 + parse_tool_calls）
P1 应用层管道（C+E）→ changes 落地链（state_applier 已建 + narrative_assembler）
P2 路由融合（F+G）→ 按需唤醒省 token + 领域 Agent + 记忆子图（已有雏形）
P3 契约统一（D+B）→ 34 契约 → {changes, narrative}（contract_adapter 大改，最后统一）
P4 异步化（H）→ UI 不卡（可与 P3 并行）
P5 记忆聚焦（I）→ 随融合自然落地
P6 测试/验证（J）→ 全阶段 pytest 全绿
```

### 优先级判断（我的建议）
1. **先 P0 + P1**（LLM 层 + 应用层）：这是「AI 只出结构化变更」的地基，所有 Agent 依赖。风险低、收益立现（状态安全 + 验证/合并/cascade）。
2. **次 P2**（路由 + 领域融合）：按需唤醒已落地雏形，扩展为领域 Agent 记忆子图 → **省 token + 记忆聚焦**，直接改善体验。
3. **再 P3**（契约统一）：34 契约大改，contract_adapter 映射表是核心（保语义不破坏）。放后面是因为改动面最大，需地基稳固后统一。
4. **P4 异步**（UI 不卡）可与 P3 并行（不同文件，团队可分工）。

### 关键风险与对策
| 风险 | 对策 |
|---|---|
| contract_adapter 映射保语义（34 契约 → changes 不丢档位语义）| 映射表单一权威源 + 每条映射单测 |
| 异步化线程安全（Tkinter/GameState 非线程安全）| 后台只做网络+纯函数，写状态/UI 回主线程 |
| 记忆碎片化 | 领域记忆子图（每领域一条时间线）|
| 大改造回归 | 分阶段、每批 pytest 全绿、回放验证 |
| 强制 tool_choice required 部分端点不支持 | 探测降级（json_mode 已有先例）|

## 三、执行建议（团队分工）

| 阶段 | 负责人 |
|---|---|
| P0 LLM 层（3 工具 + _call + parse_tool_calls）| 谷承构（落地）+ 言枢密（schema 定稿）|
| P1 应用层（narrative_assembler + state_applier 完善）| 谷承构 |
| P2 路由 + 领域融合（10 领域 Agent + 记忆子图）| 谷承构 + 言枢密（领域字段白名单）|
| P3 契约统一（contract_adapter + prompt）| 言枢密（映射表）+ 谷承构（接线）|
| P4 异步化（async_ai + UI 接线）| 谷承构 + 景呈宣（UI）|
| P5 记忆聚焦 | 谷承构 + 言枢密 |
| P6 测试（changes 唯一改状态/guard/守恒/异步）| 严归正 |

## 四、验证口径

1. **changes 唯一改状态**：叙事文本零状态影响（断言）
2. **guard 护栏**：数字区间/来源闭集/人物校验通过
3. **守恒**：12 步记账不破
4. **异步**：AI 调用期间 UI 不卡（无「未响应」）
5. **token**：按需唤醒后未唤醒 Agent 零消耗（日志断言）
6. **记忆**：领域子图聚焦（每领域一条时间线，非碎片化）

---

## 五、大臣个性保障（用户定稿：不同大臣对话/拟旨都不一样）

> 大重构（Function Call 结构化 / 记忆库数据库化 / 领域融合 / 契约统一）中，大臣个性（persona）必须确保不丢——**不同大臣的对话、拟的旨都要体现个性差异**（蔡京逢迎、陈瓘直谏、章惇强硬）。

### 可能被重构影响的地方
| 重构 | 个性风险 | 保障 |
|---|---|---|
| AI 只 Function Call | 召对从自由文本改结构化 → 组装可能"千人一面" | 叙事组装注入 persona（语气/性格/称呼/惯用词）|
| 记忆库数据库化 | persona 数据可能丢 | persona 表入数据库（ministers_persona 表）|
| 领域融合 | 大臣 agent（dialogue）融合时个性化丢失 | dialogue 保持独立（大臣领域 Agent 专管召对个性）|
| 契约统一 {changes, narrative} | narrative 组装忽略个性 | narrative 注入 persona 视角 |

### 保障机制
1. **persona 数据入数据库**：`ministers_persona` 表（0-100 六维 + baseline_stance + style/speech）——数据库化不丢。
2. **召对叙事注入 persona**：narrative_assembler 组装对话时注入大臣 persona——蔡京"先意承旨"、陈瓘"刚直敢谏"、童贯"宦官腔"。
3. **拟旨差异**：draft_decree 拟旨时注入拟旨大臣 persona——**不同大臣拟不同风格的旨**（蔡京拟旨逢迎上意、陈瓘拟旨直陈利害、章惇拟旨强硬峻切）；decree_drafter prompt 注入 {minister_persona} 拟旨人视角。
4. **立场演化保留**：persona 驱动（程序公式）不改——立场演化史入数据库（stance 关系时间戳）。
5. **个性可观测**：召对/月报/事件中玩家感受到大臣个性；测试断言同一事件不同大臣的叙事/拟旨风格不同。

### 验证
- 测试：同一事件不同大臣的组装叙事风格不同（蔡京 vs 陈瓘）；同一政令不同大臣拟旨措辞/立场不同。
- persona 数据在数据库化后不丢（迁移测试）；立场演化史连贯（数据库时间戳）。

---

## 六、结合游戏实际的计划改进点（主 agent 审查）

### ① query_state 融合（不新建冲突）
游戏已有 `query_state` 工具（9 工具之一，14 target 枚举，省 token）。计划的新 query_state（paths 查询）应**扩展现有工具**（保留 14 target 快捷 + 新增 paths 通用路径查询），不新建同名冲突工具。

### ② update_state 与 12 步结算的边界时序（明确）
- 推演契约（economy_decide 等）changes：**结算前应用**（作为输入，_economy_ai 等 → 结算用）。
- 叙事类 changes（对话微调等）：**结算后应用**（不干扰守恒步）。
- 明确 AI changes 不是"随便改状态"，而是按时序插入结算流程。

### ③ 守恒校验（关键缺口，必须补）
state_applier 合并 changes 后必须加**记账守恒校验**：AI changes 不能凭空造钱粮（treasury add 需有来源，如注明"市舶税入"或"内帑补贴"；对应来源=去向）。否则 AI 漂移破坏守恒。守恒校验复用现有守恒机制（钱粮/职业流动/科举/金融 CAP）。

### ④ trigger_event 融合现有事件系统（不新造）
trigger_event 工具应**调用现有事件系统**（events.py，按 event_id 触发既有事件卡，含改写位/战略/史实/随机四级优先级），AI 触发的是"既有事件"，不是自由造事件。

### ⑤ 异步化时序依赖（推演 → 结算 → 叙事后补）
结算依赖 _economy_ai（推演结果）——**必须等 AI 推演完成才能结算**。异步化时序：后台推演 → 回调主线程本地结算 → 叙事后补（不阻塞结算完成）。不能"结算不等推演"。

### ⑥ path 白名单对齐实际字段（只读/派生保护）
VALID_PATHS 从**实际 GameState 字段**生成/对齐；保护只读/派生字段（money_supply 派生、defense_lines 派生、economy_history 真值）——AI 不能改只读/派生字段。

### ⑦ 大臣个性（对话/拟旨差异）
narrative_assembler 组装对话/拟旨时注入 persona（不同大臣不同风格）；拟旨注入拟旨人视角（蔡京逢迎/陈瓘直谏）；测试断言差异。

---

## 七、回合结束时序（用户定稿：AI 推演 → 系统结算 → 形成叙事）

```
回合结束（settle_turn）：
  ① AI 推演（先）——推演契约（economy/diplomacy/military/relief 等，route_agents 按需唤醒）
       → changes → state_applier 应用（结算前，作为输入）
  ② 系统结算（后）——run_monthly_settlement（12 步本地引擎，读 _economy_ai 等，守恒）
  ③ 形成叙事（最后）——narrative_assembler 组装（changes + 记忆素材 + 句式库，异步后补）
```

- 推演契约 changes 结算前应用（输入）；叙事类 changes 结算后（不干扰守恒）。
- 异步化时序：后台推演 → 回调主线程本地结算 → 叙事后补（不阻塞结算完成）。

---

## 八、专家团分工（均衡，按工作量）

| 专家 | 主任务 | 工作量 | 依赖 |
|---|---|---|---|
| 谷承构（架构）| T1 LLM 调用层（3 工具 + tool_choice required + parse_tool_calls + 强制重试）| 中-大 | 无 |
| 言枢密（AI 管线）| T5 契约统一（contract_adapter 映射 + 34 契约 prompt 统一 {changes,narrative}）| 大 | T1 |
| 沈舶司（AI 落地）| T7 记忆数据库化（SQLite 一轮一库 + 去重/6回合压缩/12回合总结/精确调动）| 大 | 无 |
| 蔡权衡（数值）| T2 守恒校验完善 + T8 persona 数值保障（对话/拟旨差异数值）| 中 | 无 |
| 景呈宣（UI）| T6 异步化（async_ai + 6 处 UI 接线 + 结算拆分）| 大 | T5 |
| 严归正（QA）| T9 测试矩阵（守恒/changes 唯一改状态/guard/异步/token/个性差异）| 中-大 | 全程 |
| 析微澜（数据）| T4a 领域路由字段白名单 + 记忆数据库 schema 设计 | 中 | 无 |
| 史翰青（叙事）| T8b 句式库文风参考 + 拟旨差异素材（蔡京逢迎/陈瓘直谏）| 小-中 | 无 |
| 邹运筹（主理人）| 统筹 + 回合时序 + 边界文档 | 小 | 全程 |

**协作链**：T1 → T5 → T6（串行依赖）；T7/T2/T4a/T8b 独立并行；T9 全程。
