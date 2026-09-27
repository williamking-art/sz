# `game/ai/` —— AI 叙事与契约层

> 上级规范：[`game/README.md`](../README.md) ｜ 测试：[`test_ai_*`](../../_dev_tools/game-dev/tests/)、[`test_narrative_*`](../../_dev_tools/game-dev/tests/)

## 职责

与 LLM 打交道的**全部**内容：契约（提示词→结构化输出→校验）、叙事客户端、失败降级、脱敏、
token 计量、知识库检索、可选语义检索。**AI 只产出"建议/叙事/结构化变更请求"**，
真正写状态的是 `game/engine/state_applier.py`。

## 关键文件

| 文件 | 职责 |
|---|---|
| `client.py` | AI 叙事客户端（总入口） |
| `client_narrative.py` | 部门叙事子模块（9 类 prompt 调用 + 通用叙事） |
| `client_utils.py` | 客户端工具函数 |
| `contracts_settle.py` | **结算推演契约**（各 `*_decide`、`survey_settle`） |
| `contracts_decree.py` | 诏令契约（拟诏/解析/自由效果/执行拆解） |
| `contracts_court.py` | 朝堂契约（召对/润色/会签/外交对话） |
| `contracts_misc.py` | 叙事/事件/建言/结局契约 |
| `contract_adapter.py` | 契约统一映射层 |
| `schemas.py` | 输出契约 JSON Schema 注册表（**结构层校验**） |
| `validators.py` | 契约校验共享辅助（**语义层校验**） |
| `narrative_guard.py` | **叙事-数值一致守卫**（防 AI 叙事与账本矛盾；只给档位词，不给真值） |
| `narrative_fallback.py` | 叙事模板库（AI 失败时的**分级降级**本地兜底） |
| `desensitize.py` | 事实脱敏（真值→档位词再送给 AI/前端） |
| `token_meter.py` | token 计量（tiktoken 可选层） |
| `semantic.py` | 本地语义嵌入后端（ONNX + bge-small-zh，**可选层**） |
| `vector_store.py` | 向量近邻检索（sqlite-vec，纯 Python 兜底） |
| `kb_query.py` | 游戏内知识库查询（本地 SQLite FTS5，**随游戏分发、只读**） |
| `model_setup.py` | 语义模型下载器（一次性工具） |
| `safety_lexicon.json` / `SensitiveWords.SOURCE.md` | 敏感词与来源说明 |
| `prompts/` | 提示词模板（按用途分文件） |

## 关键约定

1. **脱敏优先**：任何送给 LLM/前端的数字都应先过 `desensitize.py`（档位词），真值只留在内核。
   `narrative_guard.py` 是第二道闸门（叙事与账本对不上就拦）。
2. **失败必须有兜底**：AI 不可用时走 `narrative_fallback.py`（模板），**不得让主流程崩**；
   `ai_config.json` 缺失即视为"禁用客户端"（`backend/server.py` 的构建逻辑）。
3. **契约三层**：`schemas.py`（结构）→ `validators.py`（语义）→ `engine/state_applier.py`（写入与守恒）。
   新加契约请三处同步，并在 `_dev_tools/game-dev/tests/` 配测试。
4. **密钥不入库**：`game/ai_config.json` 已被 `.gitignore` 忽略（含 base_url/key），不要提交。
5. 可选层（tiktoken / ONNX / sqlite-vec / edge-tts）**缺失必须静默降级**，不能成为硬依赖。
