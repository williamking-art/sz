# C · AI 管线审查

审查对象：《宋祚 Songzuo》AI 叙事与 agent 管线（只读代码审查 + 一次性脚本实证）
审查时间：2026-09 之后（工作区 HEAD）
解释器：`D:\codebuddy\.audit-venv\Scripts\python.exe`（3.13）
实证脚本：`_dev_tools\_scratch\audit-2026\c_probe1.py` ~ `c_probe4.py`（**未修改 game 下任何源文件**）

> 结论口径：`[确认]` = 有代码行证据或实跑输出；`[疑似]` = 推理未验证。
> 本次同时跑了仓库自带 pytest：**379 passed / 11 failed**（见 C-1 与文末「批次红测」）。

## 结论速览

| 编号 | 严重度 | 一句话 | 文件:行 | 证据类型 |
|------|--------|--------|---------|----------|
| C-1 | P0 | 大臣赈济工具 `relief_grant` **100% 失效**：`applier_pipeline` 调用了已被删除的 `_resolve_path_value` → NameError 被 `_tool_dispatch` 的裸 except 吞成「状态应用层异常，已拒绝」，钱粮完全不落地 | `ai/client_utils.py:792-812` + `engine/state_applier.py:677,710`（`def` 已于 :292 移除） | 确认（实跑 + 自带测试红） |
| C-2 | P1 | 叙事护栏主体（数值区间/人物查表/来源闭集）在生产**零覆盖**：`event_narrative` 唯一生产调用点不传 `state` → 2026-09「人物护栏回喂」修复实际无效 | `ai/client.py:1404-1421`；`core/commands.py:595` | 确认 |
| C-3 | P1 | 复读检测阈值 0.6 + `_prev_texts` 全局跨契约共享：**不同事件/不同大臣的新生成叙事**被判复读 → 换成程序模板；模板还会写进召对缓存与对话记忆库最多 8 回合 | `ai/client.py:928-941`；`core/commands.py:965-978` | 确认（实跑相似度 0.63~0.80） |
| C-4 | P1 | 安全词表误伤本游戏核心题材：`屠城/凌迟/砍头/屠/自杀/废物` 命中即**整单丢弃**改模板（月报/事件/会签均含），且不落 `_error` → 静默降级 | `ai/client_utils.py:187-198`；`ai/safety_lexicon.json:24`；`ai/client.py:911-919` | 确认 |
| C-5 | P2 | LRU 缓存键设计双缺陷：既缺契约自身维度（月报缺 year/month、拟旨缺 minister）又因脱敏随机抖动而几乎**永不命中**；一旦命中即跨月串味并被复读检测吞成模板 | `ai/client.py:633-659,1123-1126,1372` | 确认 |
| C-6 | P2 | 对话记忆：`rollback_after` 删掉概要行后**不回滚 `summarized=1` 标记** → 已总结对话永久消失、召对注入变空 | `memory/dialogue_memory.py:88-108,150-161` | 确认 |
| C-7 | P2 | `MemoryGraph.rollback_after` 按关系 `turn` 单值截断，而 `add_relation` 合并时**覆盖 turn** → 回滚会把更早回合的合法历史整条删除 | `memory/memory_graph.py:155-175,190-193` | 确认 |
| C-8 | P2 | AI 推演失败清单 `_ai_failures` 只写不读：`server.py` 的公开化分支写在 `startswith("_")` 过滤**之后**，不可达 → 玩家侧对 AI 失败全静默（声称的修复无效） | `backend/server.py:201-225`；生产者 `core/agent_router.py:265-268` | 确认 |
| C-9 | P2 | `enable_tools` 四档实际只有「off / 其余」：`simple` 档被忽略仍下发 9 全量 schema；`capability_probe`/`enable_tools()`/`tool_mode` 无生产调用方 | `ai/client.py:255-264,509-537,994-1001` | 确认（实跑） |
| C-10 | P2 | 未接线核实：`contract_adapter`/`async_ai`/`STATE_TOOL_SCHEMAS` 确为 0 调用（文档已标注）；但 `parse_tool_calls → _tool_dispatch` **形状不兼容**（喂进去全部「未知工具」），且 `client_narrative` 9 方法、`parse_decree` 契约+提示词均 0 调用而文档未标注 | `ai/client_utils.py:443-479` vs `:643-650`；`ai/client.py:1247,2444` | 确认 |
| C-11 | P2 | token 分组表缺 9 类部门叙事与 `generate_memorials`（每回合都调）→ 计量表落「其它」，`_METER_INTERNAL` 修复目标未达成 | `ai/token_meter.py:92-111`；`ai/client.py:178-184` | 确认 |
| C-12 | P2 | `desensitize_state` 的「机构信息壁垒」整套（`org_name`/`_org_width`/`_desensitize_influence`）无生产调用方，设计第三条从未生效 | `ai/desensitize.py:70-84,123,150,169,180,207,234` | 确认 |
| C-13 | P2 | `_summary_text` 脱敏失败时**回退原始摘要 JSON**（fail-open）：实测把精确国库/派系/兵力全量写进 prompt | `ai/client.py:62-76` | 确认（需畸形 dict 触发，当前生产未触发） |
| C-14 | P2 | 叙事类兜底丢弃阶段错误码：`AI_EMPTY_RESPONSE`/`AI_INVALID_JSON`/`AI_CONTRACT_FAILED` 对 report/dialogue/event/advice/narrative/memorials 不可观测（覆盖条件要求 fallback 自带 `_error`） | `ai/client.py:902-910` | 确认（实跑） |
| C-15 | P2 | `scenes[].text` 完全绕过安全过滤与数值校验；且前端无任何 `scenes` 渲染方 → 月报/事件提示词要求 6~10 幕、200~360 字全部丢弃（空转 token + 契约字段无消费者） | `ai/client.py:912-923`；`ai/prompts/monthly_report.md`；frontend 无 `scenes` | 确认 |
| C-16 | P2 | `personnel_nominate` 无上限地给**全部**衙门 `backlog += 1`（实测 20 次 → 各衙门 +20）；该字段仅显示不参与计算，故为面板污染而非经济影响 | `ai/client_utils.py:747-756` | 确认 |
| C-17 | P2 | 数值护栏单位闭集不全 + 不支持「亿」+ 不容空格：`十万亩/十万两/二十万匹/一亿口/300 万石` 全部绕过区间校验 | `ai/narrative_guard.py:22,29-44,85-102` | 确认（实跑 10 例） |
| C-18 | P3 | 若干小题：非法档位词被 `normalize_tier` **上调**（"超大"→大、"极强"→极）；5xx/429 无错误码；`_extract_json(dict)` 抛 AttributeError；`_agent_inject` 对非大臣角色注入通用 persona | `content/data.py:1385-1395`；`ai/client.py:784,1625-1640`；`ai/client_utils.py:973-977` | 确认 |

---

## 详细条目

### C-1 [P0] 赈济工具 `relief_grant` 全线失效（applier 调用已删除函数，异常被吞）

- 位置：`ai/client_utils.py:792-812`（在册范围）；根因 `engine/state_applier.py:677` 与 `:710`；该函数定义已于 `engine/state_applier.py:292` 注释「已整体移除」
- 证据：[确认]

```python
# engine/state_applier.py:674-677
def _apply_op(state, path, op, value, cur=_UNSET):
    if cur is _UNSET:
        cur = _resolve_path_value(state, path)     # NameError: 该名字已不存在
# engine/state_applier.py:710 （_simulate_underflow 内，守恒预检入口）
            base = _resolve_path_value(state, path)
```

```python
# ai/client_utils.py:792-812（把异常吞成"已拒绝"）
try:
    from engine.state_applier import applier_pipeline
    _r = applier_pipeline(state, [("relief_grant", [...])])
    ...
except Exception:
    res = "赈济未能落地（状态应用层异常，已拒绝）"
```

实测（`c_probe2.py` T9 / `c_probe3.py` T15）：

```
grain=1 -> 赈济未能落地（状态应用层异常，已拒绝） | treasury 5000000->5000000
grain=2..5 -> 同上，国库/民心/流民全不变
applier 抛出: NameError name '_resolve_path_value' is not defined
```

自带回归测试直接红：

```
tests\test_review_2026_09_fixes.py::test_relief_region_resolve_and_refuse FAILED
E  assert '已发 京畿路' in '赈济未能落地（状态应用层异常，已拒绝）'
```

- 影响：大臣办差 9 工具中「赈济」完全不可用；AI 第二轮拿到的是内部错误文本（无法自救），玩家看到的是赈济无效。`applier_pipeline` **全库唯一调用方**就是这个工具（`grep applier_pipeline` 仅 2 处：`ai/client_utils.py:794` 与定义），故 README「变更统一经应用层 state_applier（验证/合并/守恒/原子写库）」的架构陈述与现状不符。同时说明「兜底禁止直写」的 try/except 会把**编程错误**伪装成业务拒绝（可诊断性归零）。
- 验证方式：
  ```powershell
  $env:PYTHONPATH=''; $env:PYTHONIOENCODING='utf-8'; cd D:\codebuddy\sz\game
  & D:\codebuddy\.audit-venv\Scripts\python.exe -m pytest "D:\codebuddy\sz\_dev_tools\game-dev\tests\test_review_2026_09_fixes.py::test_relief_region_resolve_and_refuse" -q
  & D:\codebuddy\.audit-venv\Scripts\python.exe D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\c_probe3.py
  ```
- 建议修复：恢复/重写 `_resolve_path_value`（或让 `_apply_op`/`_simulate_underflow` 改用 `_locate_path` 返回的 old 值，`apply_to_state` 已传入 `cur=old`）；把 `_tool_dispatch` 的裸 `except Exception` 改为区分「业务拒绝」与「编程异常」，后者 `log.exception` 并回给 AI 可操作信息；补一条 `applier_pipeline` 冒烟测试（当前 4 条 `test_state_applier.py` 用例如 `test_underflow_reject_no_mint` 已红）。

### C-2 [P1] 叙事护栏（数值区间/人物查表/来源闭集）在生产路径零覆盖

- 位置：`ai/client.py:1404-1421`（护栏只在 `state is not None` 时启用）；生产唯一调用点 `core/commands.py:595`
- 证据：[确认]

```python
# core/commands.py:593-596  ← 全库唯一 event_narrative 调用（未传 state）
if ai_client and ai_client.available:
    narr_raw = ai_client.event_narrative(event.get("title",""), event.get("desc", ...))
```

```python
# ai/client.py:1404-1421  ← 三类护栏全部挂在 if state is not None 下
if state is not None:
    statuses = build_character_statuses(state)
    _bad, _names = _validate_characters(o["narrative"], statuses)
    ...
_ranges = None
if state is not None:
    _ranges = _build_numeric_ranges(state)
out = self._postprocess(raw, validate, lambda: _narrative_fallback("event"), ranges=_ranges)
```

调用方核查（`grep` 全仓）：`_validate_narrative_numbers` 只被 `ai/client.py:922` 调用（`ranges` 由 `_postprocess` 传入），`_build_numeric_ranges` 只被 `ai/client.py:1417` 调用，`_validate_characters`/`build_character_statuses` 只被 `ai/client.py:1406-1407` 与 `core/commands.py:1113`（后者只用 blacklist）调用。**事件路径不传 state ⇒ 三者全不执行**；`build_mechanism_closure`/`_validate_mechanisms`（`narrative_guard.py:191-265`）更极端：**全库 0 调用方（连测试都没有）**。
- 影响：2026-09 声称「叙事人物护栏此前只写 `_char_violation` 无读取方 → 现按文档意图回喂一次订正」（`ai/client.py:1422-1438`）在真实游戏里从不发生：已故/已黜人物照旧出场。数值一致护栏（"数字须落注入区间"）与来源闭集同样从未在事件叙事上生效。测试 `test_three_schemes.py` 直接单测这些函数，因此**测试全绿也掩盖了生产零覆盖**。
- 验证方式：
  ```powershell
  $env:PYTHONPATH=''; cd D:\codebuddy\sz\game
  Get-ChildItem -Recurse -File -Include *.py | Select-String -Pattern 'event_narrative\(|_build_numeric_ranges|_validate_characters|build_mechanism_closure'
  & D:\codebuddy\.audit-venv\Scripts\python.exe D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\c_probe1.py   # T5/T6 观察 ranges 未生效
  ```
- 建议修复：`core/commands.py:595` 传 `state=state`（或让 `event_narrative` 的护栏默认从 `state_summary`/调用方注入 state）；把 `build_mechanism_closure`+`_validate_mechanisms` 接入 `_postprocess`（或删除并同步文档）；补一条「生产调用点传 state」的集成测试。

### C-3 [P1] 复读检测把新生成的正品叙事判为复读 → 静默换模板（并被写入召对缓存）

- 位置：`ai/client.py:924-941`（阈值 0.6 + `_prev_texts` 单一全局列表）；放大器 `core/commands.py:965-978`
- 证据：[确认]

```python
# ai/client.py:928-932（跨契约共享同一历史；三个契约的文本互相比较）
txt = obj.get("reply") or obj.get("advice") or obj.get("report") or obj.get("narrative") or ""
if txt and self._prev_texts:
    _recent = self._prev_texts[-3:]
    if max(_similar(txt, p) for p in _recent) > 0.6:
        return fallback()        # ← 合法契约被丢弃，返回本地模板
```

实测（`c_probe3.py` T14）：两个**不同事件**、AI 各返回一次合法契约，第二则被换模板：

```
event#1: 河北蝗蝻大作，官粜仓粟以赈之。
event#2（不同事件，AI 独立回复）: （此事程序未及推演，暂录存档，俟有司复核。） | _fallback= True
月报（与前两则文本相同，跨契约）: {"report": "（起居注官未及具奏…）", "_fallback": true}
```

阈值现实性实测（不同 AI 回复的正常差异度）：

```
0.636  本月漕运畅通，太仓稍盈，米价持稳，民心安定。 | 本月漕运稍阻，太仓略减，米价渐昂，民情尚安。
0.788  臣以为当先修河防，以纾河北之患。 | 臣窃以为宜先修河防，以解河北之困。
0.795  【其一·禁中】上御崇政殿，问边事于宰执… | 【其一·禁中】上御崇政殿，询边事于宰执…
```

放大链路：`core/commands.py:976-978` 只看 `_ai_ok`（AI 是否被调用），不看返回是否 `_fallback` → 模板被当成「大臣回复」写进 `_dialogue_cache`（8 回合复用）与对话记忆库（`dm.add_dialogue`），即**占位文本固化并被反复复读**。
- 影响：月报/事件/召对在高频场景（同类事件、相似朝局措辞）静默降级为「程序未及推演」模板；玩家感知为「AI 经常罢工」，且计费/统计显示 AI 成功（`ai_calls` 计数）。
- 验证方式：`c_probe3.py`（T14）+ 上面的相似度脚本。
- 建议修复：复读检测按 `cache_key`/契约分桶（不要共用 `_prev_texts`）；阈值改为按文本长度自适应或 ≥0.85；`fallback()` 结果必须带 `_fallback` 并让 `audience_dialogue` 据此跳过缓存/计数。

### C-4 [P1] 安全词表误伤历史战争题材，命中即整单丢弃且无错误码

- 位置：`ai/client_utils.py:187-198`（`_safety_filter`）、`ai/safety_lexicon.json:23-28`、`ai/client.py:911-919`
- 证据：[确认]

```python
# ai/client_utils.py:192-198
if not raw: return raw, False
for w in _SAFETY_LEXICON:
    if w and w in raw:
        return "（阁臣所奏措辞或不妥，已为陛下隐去。）", True     # 整段替换
# ai/client.py:915-919：任何被过滤字段命中 → return fallback()
```

```json
// ai/safety_lexicon.json:24（violence 类，宋代战争题材高频词）
"屠杀","虐杀","凌迟","砍头","爆头","肢解","血腥","杀人如麻","屠城"
```

实测（`c_probe1.py` T5）：

```
输入 AI 契约: {"narrative": "金人屠城，血流漂杵，河北震恐。", "severity_hint": "重"}
输出: {'narrative': '（此事程序未及推演，暂录存档，俟有司复核。）', 'severity_hint': '中', 'scenes': [], '_fallback': True}
```

注意：`severity_hint` 被兜底从「重」改成「中」；且返回体内**没有 `_error`**（见 C-14），调用侧无法区分「敏感词命中」与「AI 未接入」。
- 影响：北宋—金战争是核心题材，`屠城/凌迟/砍头` 是正常史笔用词 → 月报、事件、会签（`memo/objections/executions` 同为受检字段）会成群降级为模板；玩家看不到任何原因。
- 验证方式：`c_probe1.py` T5；`D:\codebuddy\sz\game\ai\safety_lexicon.json`。
- 建议修复：violence 类应做**语境白名单**（史书叙述 vs 现代表述）或降低为「打码该词」而非整单丢弃；命中时使用独立错误码（如 `AI_OUTPUT_FILTERED`）并记日志，供 UI 提示。

### C-5 [P2] LRU 缓存键：既缺契约维度（跨月/跨拟旨人串味）又被脱敏抖动打成 0 命中

- 位置：`ai/client.py:633-659`（`_cached_call`）、`:1123-1126`（draft 的 input_key）、`:1372`（monthly）
- 证据：[确认]

```python
# ai/client.py:643
key = f"{cache_key}:{input_key}:{self._state_hash(state_summary)}"
# monthly：cache_key="monthly", state_summary=posture —— year/month 不在键内
raw = self._cached_call("monthly", posture, sys_p, "", 0.7, 600)
# draft：input_key 只有 player_intent|turn —— minister_name/persona/minister_advice 不在键内
... input_key=f"{player_intent or ''}|{getattr(state,'turn',0) ...}"
```

实测 A（`c_probe1.py` T2，显式固定 posture 模拟稳定摘要）：

```
网络调用次数: 1 （期望 3）
r1: 一月月报正文
r2: （起居注官未及具奏，兹录存档…）      ← 命中缓存后被 C-3 复读检测吞掉
r3: （起居注官未及具奏，兹录存档…）
cache_stats: {'hits': 2, 'misses': 1, 'rate': 0.667}
```

实测 B（`c_probe1.py` T3，真实 `state.posture`）：

```
posture 两次相同? False          ← desensitize_band 每次 ±5% 抖动
_summary_text 两次相同? False
网络调用次数: 3 （3 = 全部未命中） ; cache_stats: {'hits': 0, 'misses': 3, 'rate': 0.0}
```

- 影响：两处症状互为因果——① 生产摘要永远抖 → `_cached_call` 的 LRU **结构性 0 命中**（省 token 目标落空，`cache_stats()` 面板与实际都失真）；② 若输入稳定（显式文本、或各脱敏项落到 `几无余财/太仓告罄` 等无抖动分支、或同 turn 同 intent 的不同拟旨人）则跨月/跨人串味，且第二次因文本与上次相同被 C-3 判复读 → 返回模板。二者叠加后果都是「拿到别的内容或模板」。
- 验证方式：`c_probe1.py` T1/T2/T3（T4 需 monkeypatch `ai.desensitize.desensitize_for_ai` 为定值才能稳定重现跨拟旨人串味）。
- 建议修复：键纳入契约自身全部区分维度（monthly：year/month/era；draft：minister_name+advice hash）；对 `_state_hash` 使用**未加 jitter** 的稳定摘要（脱敏文本仅用于 prompt，不用于 key）；命中缓存时跳过复读检测。

### C-6 [P2] 对话记忆回滚不回退 `summarized` 标记 → 已总结对话永久丢失

- 位置：`memory/dialogue_memory.py:88-108`（rollback）、`:150-161`（标记）、`:123-126`（`summarized=0` 过滤）
- 证据：[确认]

```
[T16] rollback_after(2)（结算失败水位）-> {'dialogues': 1, 'summaries': 1}
  summaries 行: []                      ← 概要行被删
  对话行: [(1, 1), (2, 1)]              ← 但 summarized 标记仍是 1
  重新总结 turn=3 -> [] （空 = 已标记，永不重算 → 1~2 回合对话内容永久丢失）
  召对注入查询: {'summary': '', 'details': [], 'source': 'db'}   ← 该大臣记忆注入永久为空
```

- 影响：任一次结算异常回滚后，该 3 回合窗口的召对内容既不在 `summaries`，也永不参与后续总结，且 `query_for_dialogue` 的 `details` 只取 `summarized=0` → 大臣「前番之言」彻底失忆。2026-09 的 P2-46「静默丢数据」修复只覆盖了「概要已存在」的分支，未覆盖「概要被回滚删除」的分支。
- 验证方式：`c_probe4.py` T16（脚本把 `content.data.SAVE_DIR` 指向 scratch，未污染仓库）。
- 建议修复：`rollback_after` 同时把对应窗口的 `dialogues.summarized` 复位为 0（按 `period`/`ref_ids` 反查），或改为「先删标记再删概要」。

### C-7 [P2] `rollback_after` 按 `turn` 单值截断，会删掉更早回合的合法关系历史

- 位置：`memory/memory_graph.py:155-175`（`add_relation` 合并时 `r["turn"] = turn`）、`:190-193`（回滚按该单值删）

- 证据：[确认]

```
[T18] turn=3 关系: [... 'turn': 3, 'weight': 1.0 ...]
      turn=6 叠加后: [... 'turn': 6, 'weight': 2.0 ...]（turn 被改写为 6）
      rollback_after(4): {'relations': 1, ...}
      剩余关系: []   ← 第 3 回合的历史一并被删
```

- 影响：文档承诺「只删 > turn，不误删同回合内失败前的合法写入」，但关系合并后 `turn` 只剩最后一次，回滚会把**跨回合累积的语义（权重/note/首次发生回合）整条抹掉**；同时被删的权重增量也无法复原。图谱写「史」的连贯性在异常路径上退化。
- 验证方式：`c_probe4.py` T18。
- 建议修复：`add_relation` 增记 `first_turn`（或 `created_turn`），回滚按 `first_turn` 截断；或回滚改为「权重做差」而非删行（配合 change_log 重放）。

### C-8 [P2] `_ai_failures` 生产者存在但消费者不可达 → AI 失败对玩家全静默

- 位置：`backend/server.py:201-225`（不可达分支）；生产者 `core/agent_router.py:265-268`、`core/async_ai.py:266-267`

- 证据：[确认]

```python
# backend/server.py:201-203
for k, v in vars(s).items():
    if k.startswith("_"):
        continue                       # ← _ai_failures 在这里已被丢掉
    ...
    if k == "_ai_failures" and isinstance(v, list):   # :217 永远不可达
        out["ai_failures"] = [...]
```

`grep _ai_failures` 全仓只有 4 处：2 处写入、2 处本文件（写入分支 + 该 `if`），**无任何读取方**；前端也没有 `ai_failures` 字段消费。
- 影响：非 economy 的唤醒 Agent 契约失败（diplomacy/military/relief/faction/granary/…）只落本地兜底，玩家与 UI 完全无感；2026-09 声称的「AI 失败对玩家全静默」修复实际未生效（分支写在了 `continue` 之后）。
- 验证方式：`Get-ChildItem -Recurse -File -Include *.py | Select-String -Pattern '_ai_failures'`（4 处）+ 阅读 `server.py:201-225`。
- 建议修复：把 `_ai_failures` 的判断移到 `startswith("_")` 过滤之前；前端 `AdvancePanel`/`Dock` 显示「本月 N 项推演未成，已用本地兜底」。

### C-9 [P2] `enable_tools` 四档实际只剩两档：`simple` 被忽略、能力探测无调用方

- 位置：`ai/client.py:255-264`（`_tools_active`）、`:509-537`（`enable_tools`）、`:994-1001`（dialogue 恒用 `_TOOL_SCHEMAS`）

- 证据：[确认]

```
[T10] mode='auto'    enable_tools_mode='auto'   tool_mode='tool_full' _tools_active()=True  capability_probe 被调用? False
      mode='on'      enable_tools_mode='on'     tool_mode='tool_full' _tools_active()=True  capability_probe 被调用? False
      mode='off'     enable_tools_mode='off'    tool_mode='tool_full' _tools_active()=False capability_probe 被调用? False
      mode='simple'  enable_tools_mode='simple' tool_mode='tool_full' _tools_active()=True  capability_probe 被调用? False
[T11] enable_tools=on     : 下发 schema = 9 个全量工具
      enable_tools=simple : 下发 schema = 9 个全量工具（未走 SIMPLE_TOOL_SCHEMAS）
```

`grep enable_tools`/`capability_probe` 全仓：除定义与 `backend/server.py` 的配置读写外，无生产调用方；`_call_with_tools`（唯一消费 `tool_mode`）也 0 调用。
- 影响：① `enable_tools="simple"`（弱模型降级档）在真实召对/会签里**不生效**，弱端点会一直吃到 9 工具全量 schema（更容易报错/不调工具）；② `auto` 与 `on` 行为等价，`capability_probe` 四维探测与「简单重试」降级链（`_call_with_tools`）整条未接线；③ C1 属性遮蔽修复本身是好的（`enable_tools_mode` 与方法不再冲突），但「双向同步」只有文字声明，实际由构造函数直接写字符串、`tool_mode` 永远停留 `tool_full`。
- 验证方式：`c_probe2.py` T10/T11。
- 建议修复：`_tools_active` 依据 `tool_mode` 判定；构造函数在 `auto/simple` 时调用 `capability_probe`；`dialogue`/`_tool_roundtrip` 按 `tool_mode` 选 `SIMPLE_TOOL_SCHEMAS`。

### C-10 [P2] 未接线模块核实结果 + `parse_tool_calls → _tool_dispatch` 形状不兼容

- 位置：`ai/client_utils.py:443-479`（`parse_tool_calls`）vs `:643-650`（`_tool_dispatch` 读 `tc["function"]`）；`ai/client.py:1247,2444-2459`（`parse_decree`）

- 证据：[确认]

实测（`c_probe2.py` 附加段）：

```
[parse_tool_calls] [{'call_id': '1', 'name': 'register_draft', 'arguments': {'title': 'T', 'summary': 'S'}}]
[dispatch(parsed)] [('', '未知工具：')]      ← 键名不同（call_id/name/arguments vs id/function）
  诏草数变化: 0 -> 0
```

接线核实（`grep` 全仓，排除测试/构建清单）：

| 模块 | 生产调用方 | README/注释是否如实标注 |
|------|-----------|------------------------|
| `ai/contract_adapter.py` | 0（仅测试 + `build_exe.py` hiddenimports） | **是**（「待接线…这不构成缺陷」） |
| `core/async_ai.py` | 0（仅测试 + hiddenimports） | **是**（B7 已披露） |
| `STATE_TOOL_SCHEMAS` / `_call_with_tools` | 0 | **是**（注释标明「暂无生产调用方」） |
| `ai/client_narrative.py` 9 个方法 | **0** | **否**（README 列为「叙事 agent 客户端」；`ai/client.py:178-184` 还按「9 类部门叙事已在生产」的口气修了计量） |
| `AIClient.parse_decree` + `prompts/decree_parse.md` + `schemas.SCHEMAS["parse_decree"]` | **0**（唯一消费者 `core/commands_decree.issue_free_decree` 的 `parse_result` 由前端硬编码传入：`DecreePanel.tsx:117` / `:182`） | **否**（README 把自由拟旨描述为 AI 解析契约；`commands_decree.py:393` 仍写「parse_result: ai.decree.parse_decree 返回结构」） |

- 影响：① 未来把 function calling 正式接线时，若按文档「parse → dispatch」串接会 100% 得到「未知工具：」（且被 `_tool_dispatch` 的 `except` 吞成正常回执文本）；② 契约审计视图（`contract_adapter`）覆盖 34 契约，但其中 `parse_decree` 等已无生产者，口径失真。
- 验证方式：`c_probe2.py`（附加段）+ `Get-ChildItem -Recurse -File -Include *.py,*.ts,*.tsx | Select-String -Pattern 'parse_result|parse_tool_calls|contract_adapter'`。
- 建议修复：给 `_tool_dispatch` 加形状适配（同时接受 `function.arguments` 与 `name/arguments`）；把 `client_narrative`/`parse_decree` 的接线状态写进 README，或删除死契约。

### C-11 [P2] token 分组表缺 9 类部门叙事与 `generate_memorials`，「其它」桶持续膨胀

- 位置：`ai/token_meter.py:92-111`（`TOKEN_GROUPS`/`token_group_of`）；对照 `ai/client.py:178-184`

- 证据：[确认]

```
token_group_of(govern_yamen) = 其它     token_group_of(local_policy) = 其它
token_group_of(land_manage)  = 其它     token_group_of(finance)      = 其它
token_group_of(exam/science/military_expand/diplomacy/reform) = 其它
token_group_of(generate_memorials) = 其它      ← 每回合 advance_and_settle 都调
token_group_of(dialogue) = 召对·AI      token_group_of(polish_decree) = 拟旨
```

- 影响：`_METER_INTERNAL` 补登记 `_narrative_call` 的目的是「让 9 类部门叙事按月报叙事细分」，但分组表里根本没有这些方法名 → 目标未达成；`generate_memorials` 是**每回合必调**的生产契约，其 token 永久落在「其它」，玩家看到的计量表分项与实际账单结构不符。
- 验证方式：上面的一行脚本（`ai.token_meter.token_group_of`）。
- 建议修复：`TOKEN_GROUPS` 增 `"部门叙事": {govern_yamen, local_policy, land_manage, finance, exam, science, military_expand, diplomacy, reform}` 与 `"奏折": {"generate_memorials"}`，并补 `TOKEN_GROUP_ORDER`。

### C-12 [P2] 脱敏的「机构信息壁垒」整套无生产调用方

- 位置：`ai/desensitize.py:70-84`（`_ORG_PRECISION`/`_org_width`）、`:123,150,169,180,207`（各维度取值）、`:234`（`_desensitize_influence`）、`:276-284`（`desensitize_for_ai(state, org_name="")`）

- 证据：[确认]

```
client.py:69  ds = desensitize_state(state_summary)          ← 无 org_name
client.py:88  return desensitize_for_ai(state)               ← 无 org_name
client.py:1120/1221  _ctx = desensitize_for_ai(state)        ← 无 org_name
desensitize.py:234 def _desensitize_influence(...)           ← 全库 0 调用
```

召对路径（`core/commands.py:1102-1144`）传入的 `state_summary` 是 persona+闭集+黑名单文本，根本不走 `desensitize_for_ai`；`dialogue()` 也不使用 `desensitize_state`。
- 影响：设计文档第一条「机构信息壁垒：召对大臣时按其机构注入不同精度」从未生效；`_ORG_PRECISION` 的 8 个机构精度表、`_desensitize_influence` 均为死代码；同时意味着财政/兵力区间宽度在生产中恒为默认（国库 0.25、军力 0.25、流民 0.25），户部/枢密院并不「看得更准」。
- 验证方式：上面的 `Select-String` 输出。
- 建议修复：`dialogue()`/`council_review()` 传入说话人所司机构（`state.org_of(minister)`）到 `desensitize_for_ai(state, org_name=...)`；否则删除该设计并同步文档。

### C-13 [P2] `_summary_text` 脱敏失败回退原始摘要 → fail-open 全量真值入 prompt

- 位置：`ai/client.py:62-76`

- 证据：[确认]（当前生产未触发，属 latent）

```python
# ai/client.py:66-76
if isinstance(state_summary, dict):
    try:
        from ai.desensitize import desensitize_state
        ds = desensitize_state(state_summary)
        return json.dumps(ds, ensure_ascii=False, indent=1)
    except Exception:
        pass                                    # ← 静默 downgrade
try:
    return json.dumps(state_summary, ensure_ascii=False, sort_keys=True)   # 原样真值
```

实测：

```
_summary_text(畸形 dict) 是否回退为原文 JSON? True | 长度 9558
（原始 get_state_summary 含 treasury.amount=5000000、factions[].influence/satisfaction
  精确值、military.armies[].troops、refugee_count 精确值）
```

- 影响：`desensitize_state` 对摘要形状有硬假设（`factions` 必须是 dict、`military.armies` 必须是 dict…），任一形状变化（上游 `get_state_summary` 重构、测试替身、旧存档补字段）都会让**全部精确真值**进入 prompt，且没有任何告警。脱敏失败必须 fail-closed（拒发/仅给定性），不能 fail-open。
- 验证方式：`c_probe4.py` 末段 / 上文一行脚本（把 `d["factions"]` 改成 list 触发）。
- 建议修复：`except` 分支改为记 warning 并返回「（朝局摘要不可用）」空串或纯定性文本，绝不 dump 原 dict。

### C-14 [P2] 叙事类兜底丢弃阶段错误码（6 码中有 3 码对叙事契约不可观测）

- 位置：`ai/client.py:902-910`

- 证据：[确认]

```python
# ai/client.py:902-910
fb = fallback()
if _fail_code and isinstance(fb, dict) and fb.get("_error"):     # ← 要求 fallback 自带 _error
    if _fail_code in AI_ERROR_CODES:
        fb["_error"] = _fail_code
return fb
```

实测（`c_probe1.py` T7）：

```
empty      -> {"report": "（起居注官未及具奏…）", "_fallback": true}          ← 无 _error
badjson    -> {"report": "（起居注官未及具奏…）", "_fallback": true}          ← 无 _error
contract   -> {"report": "（起居注官未及具奏…）", "_fallback": true}          ← 无 _error
parse_decree contract fail -> {"_error": "AI_CONTRACT_FAILED", "_fallback": true}   ← 正确（fallback_decree 自带 _error）
```

`narrative_fallback.fallback_report/dialogue/event/advice/narrative/memorials` 均只带 `_fallback`，不带 `_error`。故 `AI_EMPTY_RESPONSE`/`AI_INVALID_JSON`/`AI_CONTRACT_FAILED` 在这 6 类契约上被**算出后丢弃**；对照 README「6 码全生产者」——生产者存在，但叙事路径上观测不到。另：`_ai_unavailable(kind)` 的默认码是 `AI_NOT_CONFIGURED`，于是「AI 已配置但契约不合法」的 `free_effect`/`research`/`hidden_state` 等失败也被标成「未接入 AI」（错码）。
- 影响：诊断信息丢失（运维/玩家无法区分超时、空响应、契约失败、未配置）；遥测（`SONGZUO_TELEMETRY`）也不会有错误码维度。
- 验证方式：`c_probe1.py` T7。
- 建议修复：覆盖条件放宽为「`isinstance(fb, dict)` 即写入 `_error`」；`_ai_unavailable` 调用点按实际失败原因传码。

### C-15 [P2] `scenes[].text` 绕过安全过滤与数值校验，且前端无渲染方

- 位置：`ai/client.py:911-923`（受检字段清单里没有 `scenes`）；提示词 `ai/prompts/monthly_report.md`、`event_narrative.md`

- 证据：[确认]

```
[T6] out5: {"report": "本月诸事如常。", "scenes": [{"scene": "边事", "text": "金人屠城，死者三百万口，国库一千二百万缗尽失。"}]}
```

```python
# ai/client.py:912-914（只扫这些标量字段，scenes 是 list[dict] 被跳过）
for _field in ("reply","advice","report","narrative","body",
               "commentary","court_report","gazette","memo","objections","executions"):
```

前端核查：`Get-ChildItem frontend/src -Recurse -Include *.ts,*.tsx | Select-String scenes` → **0 命中**；`AdvancePanel.tsx:10`/`CourtPanel.tsx:66`/`Dock.tsx:69` 只用 `res.report`。
- 影响：① 契约层「所有 AI 文本统一过敏感词/数值护栏」的承诺被 `scenes` 破口（当前因无渲染方而未暴露给玩家，属 latent，一旦前端补渲染即直接外泄编造数字与违规表述）；② 提示词强制 6~10 幕 / 4~6 幕（200~360 字）纯属空转 token，且 `report` 又被要求「融会各幕」，重复生成两次。
- 验证方式：`c_probe1.py` T6 + 前端 grep。
- 建议修复：`_postprocess` 递归处理 `scenes[*].text`（过滤+区间校验）；若确认不用分幕，删除提示词中的 scenes 要求与 validator 分支，或补上渲染方。

### C-16 [P2] `personnel_nominate` 无上限地污染全部衙门 `backlog`

- 位置：`ai/client_utils.py:747-756`

- 证据：[确认]

```python
elif name == "personnel_nominate":
    nm = str(args.get("name", "某人")); post = str(args.get("post", ""))
    if "yamen" in state.__dict__ and isinstance(state.yamen, dict):
        for y in state.yamen.values():
            if isinstance(y, dict):
                y["backlog"] = int(y.get("backlog", 0)) + 1     # 所有衙门 +1，无上限
```

实测（`c_probe2.py` T9）：`personnel_nominate ×20 → 各衙门 backlog 增量 [20, 20, 20]`（初始全 0）。
- 影响：一次召对里模型可返回任意多个 `personnel_nominate` 工具调用（`_tool_dispatch` 无条数上限、无成本），把 20+ 个衙门的积压值任意拉高。经核对，`backlog` 全仓只被 `settlement_steps.py:904` 自增衰减与两个前端面板显示，**不参与任何经济计算** → 实际后果是面板失真（"积压 20"），而非经济偏移；但它证明「AI 可以无代价、无上限地连续改状态」这一通道是敞开的（同批工具中的 `check_treasury` 也仅以 1 点带宽计价，可被反复调用）。
- 验证方式：`c_probe2.py` T9；`Get-ChildItem -Recurse -File -Include *.py,*.ts,*.tsx | Select-String -Pattern backlog`。
- 建议修复：`personnel_nominate` 应落到人事（或明确标为"仅叙录"）并对同名/同回合重复调用去重；`_tool_dispatch` 建议对单次响应的工具调用数设上限（如 ≤4）。

### C-17 [P2] 数值护栏单位闭集不全、不支持「亿」、不容空格

- 位置：`ai/narrative_guard.py:22`（正则）、`:29-44`（中文数字）、`:85-102`（区间表）

- 证据：[确认]

```python
_NUM_RE = re.compile(r"(\d+|[零一二两三四五六七八九十百千万]+)(万)?(贯|石|口|户|缗|里|人)")
```

实测（`c_probe2.py` T8，ranges = 贯/缗 750万、石 1500万、口 8000万、户 1600万、里 6000、人 150万）：

```
放过 | 隐田十万亩，尽入版籍。            ← 亩 不在单位表
放过 | 岁币银十万两，绢二十万匹。        ← 两/匹 不在单位表
放过 | 调兵三万人，战马五千匹。          ← 匹 不在单位表（三万人 命中则不改写，因在区间内）
放过 | 人口达一亿口。                    ← 字符类不含「亿」→ 整串不匹配
放过 | 赈济 三百万 石，活民无算。        ← 数字与单位之间空格
放过 | 粮价每石三贯。                    ← 贯在表内但在区间内（正确放过）
命中 | 国库一千二百万缗尽失。 -> 国库充盈尽失。   ← 中文数字+万+缗 正常拦截
```

- 影响：护栏杆自称「数字须落在注入区间，区间外改写定性词」，但**亿级数字、亩/两/匹/斤/艘/顷 等常见单位、任何带空格的表述**都可原样输出给玩家（史实题材里「十万亩」「十万两」恰恰是最常见的伪造数字形态）。由于 C-2，该护栏在生产中的实际覆盖面本就为零，本项属「修好 C-2 后会立刻暴露」的次级缺陷。
- 验证方式：`c_probe2.py` T8。
- 建议修复：单位表补齐（亩/顷/两/匹/斤/斗/升/艘/骑/员/名/头/匹），字符类加「亿/兆」，允许 `\s*`，并优先匹配最长数字串（现在 `(万)?` 与含「万」的字符类存在重叠，靠贪婪侥幸正确）。

### C-18 [P3] 其他已确认小题（合并列出）

- 位置 / 证据：
  1. **非法档位词被上调**（`content/data.py:1385-1395`）：`normalize_tier("超大")='大'`、`("极强")='极'`、`("巨大")='巨'`、`("显著")='大'`。`dialogue` 的 `mood`（`ai/client.py:986-988`）实测得到 `mood='大'`。README 的「档位字段一律向下降级、绝无一处落到大/巨/极」在 `military_decide`/`relief_decide`/`invest_decide`/`survey_settle`/`dialogue` 等契约上不成立（受 `TIER_RANGE`/`TIER_VALUE_CAP` 封顶，量级影响有限）。[确认]
  2. **5xx/429 无错误码**（`ai/client.py:784`）：实测 `500/429 → AIRuntimeError(code='')`；对照 401/403 → `AI_AUTH_FAILED`、读超时 → `AI_TIMEOUT`（均 `attempts=1`，非幂等重试策略**正确**：连接类失败 `attempts=3`，超时/4xx/5xx 不重发）。[确认]
  3. **`_extract_json(dict)` 抛 AttributeError**（`ai/client_utils.py:973-977`）：实测 `_extract_json({'a':1})` → `AttributeError: 'dict' object has no attribute 'strip'`；`_postprocess` 的 `raw` 理论上可能收到 `_call` 的 dict 形态（tools 路径），当前调用方均已归一为 str，属 latent。[确认·latent]
  4. **`_agent_inject` 对非大臣角色注入通用 persona**（`ai/client.py:1625-1640`）：`_agent_inject(s,"使节")`/`("枢密使")` 均返回「【身份】朝中大臣，性格：循例奉公…」，`state.memory.query(role)` 恒空 → diplomacy/military/relief 三个 `*_decide` 的角色记忆注入是空转（还会把无关 persona 塞进 prompt）。[确认]
  5. **`_postprocess` 的 `_flagged` 未使用**（`ai/client.py:922`）：数值越界只做就地改写，无任何计数/遥测，护栏是否触发不可观测。[确认]
  6. **`MemoryGraph.load` 失败后 `save()` 清库**（`memory/memory_graph.py:634-661,777-781`）：`load` 失败置空镜像但保留 `_slot`，`finish_turn` 随后 `save()` 会 `DELETE FROM entities/relations/summaries` 再写入空集 → 可写但读取异常的库会被清成空库且无备份。[疑似]（未构造出稳定的可复现损坏场景）

---

## 附：本次跑过的验证命令与脚本

```powershell
$env:PYTHONPATH=''; $env:PYTHONIOENCODING='utf-8'
Remove-Item Env:CODEBUDDY_TOOL_CALL_ID -ErrorAction SilentlyContinue
Remove-Item Env:CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR -ErrorAction SilentlyContinue
cd D:\codebuddy\sz\game

# 全量自带测试：379 passed / 11 failed
& D:\codebuddy\.audit-venv\Scripts\python.exe -m pytest "D:\codebuddy\sz\_dev_tools\game-dev\tests" -q -p no:cacheprovider

# 4 个一次性实证脚本（只读 game 源码；SAVE_DIR 改指 scratch）
& D:\codebuddy\.audit-venv\Scripts\python.exe D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\c_probe1.py   # 缓存键/脱敏抖动/安全过滤/错误码
& D:\codebuddy\.audit-venv\Scripts\python.exe D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\c_probe2.py   # 数值护栏绕过/工具注入面/enable_tools/错误码映射
& D:\codebuddy\.audit-venv\Scripts\python.exe D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\c_probe3.py   # 错误码重试/计量/复读串味/赈济 applier
& D:\codebuddy\.audit-venv\Scripts\python.exe D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\c_probe4.py   # 记忆库回滚水位/总结窗口/save 快照
```

### 批次红测（11 failed，供交叉参考；除 C-1 外均不在 C 范围）
`test_briefing.py::test_briefing_desensitized`（国库危机判据改走 `treasury_deficit` 未同步）、`test_briefing.py::test_briefing_urgent_flags`、`test_core_logic.py::test_game_over_treasury_collapse`、`test_game_over_abdication`、`test_pop_identity.py::test_maritime_trade_ledger_closed`、`test_regression_2026_08.py::test_treasury_stays_above_crisis_line`、`test_review_2026_09_fixes.py::test_relief_region_resolve_and_refuse`（=C-1）、`test_state_applier.py::test_cascade_faction_power / test_pipeline_apply_log / test_pipeline_rejected_collected / test_underflow_reject_no_mint`（后 4 条均由 C-1 的 `_resolve_path_value` NameError 引起）。

### 已核实的「历史修复仍有效」项（不重复报告）
`enable_tools_mode` 属性遮蔽；召对工具第二轮 str 穿透归一为文本并返回（两轮计费各记 1 次，实测 `calls=2`）；`_coerce_effects_to_list` 双向归一；非幂等重试收敛（连接失败 3 次、超时/401/403/5xx 各 1 次）；T1 重发补记 usage（路径存在，`ai/client.py:829-834`）；`_add_usage` 加锁与按方法分桶；`query_sql` 全部参数化（无注入面）+ `exp()` 在当前 SQLite 3.53.1 可用；对话总结窗口 `[1,3]/[4,6]/[7,9]` 不重叠且不丢数据（T17）。
