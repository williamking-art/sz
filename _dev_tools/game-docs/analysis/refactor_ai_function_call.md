# 《宋祚》AI Function Call 结构化改造计划

> 状态：草案 v1 · 用户定稿方向
> 目标：AI 只通过 Function Call 返回**结构化状态变更 changes**（应用层验证/合并/执行，唯一改状态通道）；**叙事文本仍由 AI 生成**（灵活），但受 narrative_guard 护栏（数字真实/来源闭集/人物正确）；**句式库降级为文风参考**（非锁定模板）；本地引擎负责所有确定性计算，AI 只做非显而易见推演。

---

## 一、核心原则

1. **状态变更唯一通道 = Function Call 结构化 changes**：AI 不能凭任何自由文本改状态。
2. **叙事文本 = AI 灵活生成**：不受模板锁死，但受护栏约束（数字在注入区间、只演来源闭集、人物状态正确）。
3. **本地引擎 = 确定性计算**：公式/守恒/阈值全本地，AI 不碰。
4. **AI = 非显而易见推演**：判断/趋势/意图（混沌），输出结构化变更 + 叙事要点。

## 二、现有基础（复用）

| 组件 | 现状 |
|---|---|
| Function Call | `_tool_roundtrip` + `_TOOL_SCHEMAS`（10 工具）+ `_tool_dispatch`（dialogue/polish_decree/council_review 已用）|
| 推演类 AI | 已结构化 JSON 档位（economy_decide/diplomacy_decide/military_decide/free_effect_decide 等 20+）|
| 契约落地 | `free_effect._apply_free_effect`（验证/CAP/成本/合并/执行）|
| 叙事护栏 | `narrative_guard`（数字校验 + 来源闭集 + 人物校验）|
| 工具注册 | `tool_registry`（大臣自设工具）|
| 记忆库 | `memory_graph`（结构化史库，写入/检索/叙事素材）|

## 三、统一 AI 输出契约

```
AI 输出 = {
  "changes": [{"field": "govern", "delta_tier": "中", "region": "两浙路"}],   # 结构化变更（白名单+档位）
  "narrative": "AI 生成的叙事文本（灵活，受护栏）",                            # 叙事（不改状态）
  "narrative_hint": "要点"                                                  # 可选：应用层组装辅助
}
```

- changes：唯一改状态通道（应用层验证白名单/CAP/成本 → 合并执行 → 写记忆）
- narrative：AI 自由生成，应用层经 narrative_guard 校验（数字/来源/人物）后呈现
- 句式库：作「史书笔法参考」注入 prompt（AI 借鉴文风），非锁定模板

## 四、应用层管道（narrative_assembler）

```
AI 输出 → narrative_guard 校验（narrative 数字/来源闭集/人物）
  → changes 经 free_effect 验证/合并/执行（白名单/CAP/成本/守恒）
  → memory_graph 写史（决策/事件/立场实体，来自 changes 非叙事文本）
  → narrative 呈现（护栏通过后）+ 句式库文风已由 AI 借鉴
本地引擎：12 步结算 + 守恒（不变）
```

## 五、分阶段实施

### P1：统一 AI 输出契约（{changes, narrative} 双通道）
- 推演类（20+）：输出统一为 changes 格式（保留现有档位换算）
- 叙事类（monthly_report/event_narrative/dialogue/advice/final_eval/council_review）：输出 {changes, narrative}
- 负责人：言枢密（契约设计）+ 谷承构

### P2：应用层管道（narrative_assembler）
- 新增 `core/narrative_assembler.py`：校验 narrative（guard）→ 执行 changes（free_effect）→ 写记忆
- 句式库 → prompt 文风参考（史翰青素材）
- 负责人：谷承构

### P3：叙事类改造（逐类）
- monthly_report / event_narrative / dialogue / advice / final_eval：AI 输出 {changes, narrative}
- 应用层组装（guard 校验 + changes 落地）
- 负责人：言枢密（prompt）+ 谷承构（接线）

### P4：边界文档 + 测试
- 明确「本地引擎算 vs AI 推演」边界表（每步标注）
- 测试：changes 唯一改状态（叙事文本不影响状态断言）、guard 护栏、守恒
- 负责人：严归正

## 六、边界表（本地引擎 vs AI 推演）

| 步 | 本地引擎（确定性）| AI 推演（changes + narrative）|
|---|---|---|
| 税收/军粮/守恒 | ✅ 本地公式 | — |
| 经济景气/金融趋势 | 读数 | AI 判断（景气/交子/钱荒…changes）|
| 事件触发 | 阈值判断 | AI 推演事件后果（changes）+ 叙事 |
| 政策效果 | — | AI 推演（free_effect changes）|
| 大臣召对 | persona/立场公式 | AI 对话意图（changes 可选 + narrative）|
| 时代推演 | era_state 迁移 | AI era_decide（changes + narrative）|

## 七、约束

- 状态只走 changes（AI 文本不改状态）；叙事受 guard 护栏（数字/来源/人物真实）
- 句式库作文风参考（非模板）；本地引擎确定性（守恒不破）
- pytest 全绿；存档兼容；AI 缺失 → 明确报错不伪造

## 八、异步化（用户补充：主 UI 不卡驻）

### 问题
当前 UI 的 AI 调用全部**同步阻塞主线程**（Tkinter 无响应）：
- `panels_govern.py`：polish_decree(589)/monthly_report(658)/polish(712)/council_review(751)/parse_decree(868)/召对对话
- `panels_economy.py`：council_review(623)

### 方案（Tkinter 非线程安全 → 后台算、主线程 after 应用）

```
主线程（UI）→ after() 调度
  ├─ 发起 AI 请求 → 后台 worker 线程（AI Function Call → 结构化 changes → 本地引擎验证/执行）
  ├─ 后台完成 → after() 回调主线程 → 更新 UI（叙事呈现 + 状态刷新）
  └─ UI 永不阻塞（后台算，前台显示「推演中…」）
```

### 落地
1. **异步包装层**：`core/async_ai.py`（ThreadPoolExecutor）——把 AI 调用 + 应用层执行封装为后台任务，返回 future，主线程 `after()` 轮询。
2. **UI 调用点改造**：panels_govern/economy 的同步调用 → 异步（发起任务 + after 回调更新）。
3. **进度反馈**：后台运行时 UI 显示"推演中..."（防玩家重复点击）。
4. **月度结算**：settle_turn 的 AI 推演放后台（若玩家主动触发），或结算后统一异步叙事。
5. 与 Function Call 重构结合：后台线程 = AI Function Call → changes → 本地引擎执行；主线程 = 呈现。
