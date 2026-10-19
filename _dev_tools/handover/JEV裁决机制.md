# JEV 裁决机制（本机开发记忆）

> 记录日期：2026-10-18　归属：本机交接层（跨会话权威）
> 目的：把「JEV 是**项目裁决模型**，不是 teammate/子代理」固化下来，避免再犯。

## 1. 是什么

- JEV = **TypeSafe System One / TokenRhythm NeoHorse-Jev-4B**，是**决策模型**，不是聊天模型。
- 三种原语：
  - `noul` → P(成立)，0~1；
  - `choice` → 选中项 + 各选项概率 + confidence；
  - `score` → 加权位置 + 各档概率 + confidence。
- 只返回判断/概率；**阈值折算由调用方做**，玩家可见文案不带概率数字。

## 2. 项目内两个入口

| 入口 | 用途 | 纪律 |
|---|---|---|
| `game/ai/jev_gate.py` | 游戏运行期可选闸门：`review_actions`（动作是否有原文依据）、`assess_irreversibility`（是否含不可逆后果） | 缺配置即整层禁用；无配置/超时/报错一律返回 `None`，主流程行为不变 |
| `tools/jev/jev_client.py` | 开发/裁决客户端：`client_for(provider).noul/choice/score` | 支持多 key 轮询、缓存、usage 记账；一次 `state` 打包多问题，只调一次 |

配套：`tools/jev/jev_cli.py`、`jev_ask.py`、`jev_calibrate.py`、`thresholds.json`。

## 3. 配置与 key

- 游戏内配置：`~/Documents/宋祚/ai_config.json` 的 `jev` 段（`enabled/provider/api_key/threshold/timeout`）。
- 环境变量：`SONGZUO_JEV_ENABLED=1`、`TOKENRHYTHM_API_KEY`、`TYPESAFE_API_KEY`、`JEV_KEYS_FILE` 等。
- 本机开发 key：`~/.dsh/.credentials.yaml` 的 `TOKENRHYTHM_API_KEY`；`jev_client` 会自动读取。
- **key 不进仓库、不写进文档、不打印**。

## 4. Provider 与阈值

| provider | endpoint | model | 阈值 |
|---|---|---|---|
| `tokenrhythm`（默认） | `https://tokenrhythm.studio/v1/decision` | `NeoHorse-Jev-4B` | 0.40 |
| `typesafe`（兜底） | `https://api.typesafe.ai/v1/systemone` | `jev-latest` | 0.45 |

概率不可跨 provider 沿用；阈值来自 `tools/jev/thresholds.json` 的校准结果。

## 5. 裁决台账

- 一条裁决一文件：`_dev_tools/handover/decisions/JEV-DEC-<主题>-<日期>.json`。
- 字段：`id / createdAt / agent / question / options / verdict / probabilities / provider / authority / premises_verified_by_me / applied_in / reopen_if`。
- 示例：`JEV-DEC-党争机制-2026-10-18.json`（P0–P2b=A；P3a=B；P4a=C）。

## 6. 调用示例（开发侧）

```python
import sys
sys.path.insert(0, r"D:\codebuddy\tools\jev")
from jev_client import client_for

c = client_for("tokenrhythm")          # key 自动从 ~/.dsh/.credentials.yaml 读取
r = c.choice(state, "问题", {"A": "方案 A", "B": "方案 B"})
print(r["choice"], r["probabilities"])
```

## 7. 使用纪律（防再犯）

1. **JEV 不是 teammate/subagent**：不要 `spawn_teammate(name="jev")`，不要用子代理输出冒充 JEV。
2. 设计取舍走 `tools/jev` 的 `choice/noul/score`；真实结果落 `JEV-DEC-*.json`。
3. 子代理/草案 Markdown 只能标“待审草案，以 JEV 台账为准”。
4. JEV 不替代测试：实现后仍须定向 + 全量 pytest 验收。
5. `jev_gate` 在运行期是**可选层**：失败返回 `None`，不得抛进主流程；开发侧裁决失败要明确报错并留痕。

