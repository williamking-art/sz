# `game/ai/` —— AI 叙事与契约层

> 上级规范：[`game/README.md`](../README.md) ｜ 测试：[`test_ai_*`](../../_dev_tools/game-dev/tests/)、[`test_narrative_*`](../../_dev_tools/game-dev/tests/)

## 职责

与 LLM 打交道的内容：契约（提示词→结构化输出→校验）、叙事客户端、失败降级、脱敏、
token 计量、知识库检索和可选语义检索。AI 提供结构化请求、工具意图或叙事；具体变更由程序校验并执行。
状态应用并非只有一个函数入口：结构化 changes 经 `engine/state_applier.py`，自由效果和已注册工具分别走
`core/free_effect.py` 与 `client_utils._tool_dispatch` 等受控处理逻辑。新增写入类型时要核对对应执行路径和账本约束。

## 关键文件

| 文件 | 职责 |
|---|---|
| `client.py` | AI 叙事客户端（总入口） |
| `client_narrative.py` | 部门叙事子模块（9 类 prompt 调用 + 通用叙事） |
| `client_utils.py` | 客户端工具函数 |
| `contracts_settle.py` | **结算推演契约**（各 `*_decide`、`survey_settle`） |
| `contracts_decree.py` | 诏令契约（拟诏/解析/自由效果/执行拆解）＋ **`decree_action_plan`（行动计划，规格 decree-action-chain）**＋ **`decree_narrative_decide`（因果叙事，档位+叙事，拒绝式）** |
| `contracts_court.py` | 朝堂契约（召对/润色/会签/外交对话） |
| `contracts_misc.py` | 叙事/事件/建言/结局契约 |
| ~~`contract_adapter.py`~~ | **2026-09-27 已移出** → `_dev_tools/unwired/`（待接线、不随分发） |
| `schemas.py` | 输出契约 JSON Schema 注册表（**结构层校验**） |
| `validators.py` | 契约校验共享辅助（**语义层校验**） |
| `narrative_guard.py` | **叙事护栏**：① 数值一致（区间外改写定性词）② **取材闭集**（`_build_source_closure` 喂真实 state）③ **人物查表**（已故/已黜不得出场）④ **完成宣称核对**（见下） |
| `narrative_fallback.py` | 叙事模板库（AI 失败时的**分级降级**本地兜底） |
| `desensitize.py` | 事实脱敏（真值→档位词再送 AI/前端） |
| `token_meter.py` | token 计量（tiktoken 可选层）。**`TOKEN_GROUPS` 必须覆盖每个 `*_decide` 方法**，漏组会被 `test_token_meter.py` 抓出 |
| `semantic.py` | 本地语义嵌入后端（ONNX + bge-small-zh，**可选层**） |
| `vector_store.py` | 向量近邻检索（sqlite-vec，纯 Python 兜底） |
| `kb_query.py` | 游戏内知识库查询（本地 SQLite FTS5，**随游戏分发、只读**） |
| `model_setup.py` | 语义模型下载器（一次性工具） |
| `jev_gate.py` | **Jev 决策闸门（可选层）**：用 TypeSafe System One（决策模型）给 AI 提议做**独立**复核。当前接线点：`contracts_decree.decree_action_plan` —— 对每个动作问 noul「圣旨原文是否明确支持该动作」，不足者追加进 `unresolved`（下游 `core/plan_commit` 与 UI 消费）。**缺配置即整层禁用**，无配置/超时/报错一律返回 `None`，主流程行为不变 |
| `safety_lexicon.json` / `SensitiveWords.SOURCE.md` | 敏感词与来源说明 |
| `prompts/` | 提示词模板（按用途分文件） |

## 关键约定

1. **脱敏优先**：任何送给 LLM/前端的数字都应先过 `desensitize.py`（档位词），真值只留在内核。
   `narrative_guard.py` 是第二道闸门（叙事与账本对不上就拦）。
2. **失败必须有兜底**：AI 不可用时走 `narrative_fallback.py`（模板），**不得让主流程崩**；
   `ai_config.json` 缺失即视为"禁用客户端"（`backend/server.py` 的构建逻辑）。
   **路径单点**在 `client_utils._ai_config_path()`：**写**用户数据目录 `~/Documents/宋祚/`，
   **读**新位置优先、旧位置（`_app_root()`，即安装目录/exe 同级）作一次性回退。
3. **契约三层**：`schemas.py`（结构）→ `validators.py`（语义）→ `engine/state_applier.py`（写入与守恒）。
   新加契约请三处同步，并在 `_dev_tools/game-dev/tests/` 配测试。
4. **密钥不入库**：配置住在**用户数据目录** `~/Documents/宋祚/ai_config.json`（与存档同根，
   2026-10-03 前在 `game/ai_config.json` —— 装到只读安装位置会写不进去，故迁址）。
   仓库内任何 `ai_config.json` 都已被 `.gitignore` 忽略（`:15 **/ai_config.json`、`:339 game/ai_config.json`），
   不要提交；旧位置若有残留，一次成功 `save_config()` 会把它清掉。
5. 可选层（tiktoken / ONNX / sqlite-vec / edge-tts）**缺失必须静默降级**，不能成为硬依赖。
6. **护栏必须接线，且接线要有测试**：`narrative_guard` 的 `_validate_completion_claims`
   （叙事说"告成/竣工"而工程未到 `operating` → 改写为如实表述；否定语境如"尚未完工"不误伤）
   由 `client._postprocess` 调用，**需传入 `state`**。
   - 未传 `state` → **跳过核对**（不猜、不误伤），这条边界由 `test_postprocess_..._noop_without_state` 锁定；
   - 有测试只测函数本身**不够**——那可能全是死码。必须有一条测**真实链路**的用例。
7. **新增契约要同步三处**：提示词 ＋ `validate` ＋ `token_meter.TOKEN_GROUPS`；
   `decree_action_plan` / `decree_narrative_decide` 已登记「推演」组（漏组会被覆盖测试抓出）。
8. **失败即整单失败**：契约 `validate` 返回 `None` 表示**整单拒绝**，不得部分接受。
9. **可选决策模型（`jev_gate.py`）的纪律**：它是**可选层**，与 tiktoken/ONNX 同规矩——
   缺配置即整层禁用；**无配置 / 超时 / 报错一律返回 `None`，调用方行为完全不变**（不得抛进主流程）。
   另两条：① Jev 只出**判断**，阈值折算由本模块做，**玩家可见文案只用档位词、不带概率数字**（脱敏优先）；
   ② 多个待判断项**打包成一次调用**（Jev 的 state 只摄入一次），退化成 N 次调用即回归失败。
   配置住在 `ai_config.json` 的 `jev` 段（缺失即关闭），环境变量 `SONGZUO_JEV_ENABLED` / `TYPESAFE_API_KEY` 可覆盖。
