# domains/politics — 政治与世界状态

> **2026-10-07 阶段 3 第二包（DSH）**：由 `core/settlement_imperial.py` 按域拆入 `settlement_imperial.py`（帝王行动 + 皇帝健康衰减）。
> 2026-10-06 · 阶段 0 建骨架。  
> **2026-10-07 第十七包：本包已有实现**（`split.py`、`voice.py`，`git mv` 自 `core/`）。`faction_settle` / `faction_basis` / `faction_metrics` / `situation_*` / `events` **仍在 `core/`**，理由见下。

## 已迁入实现（阶段 3 第二包，2026-10-07）

| `settlement_imperial.py` | 由 `core/settlement_imperial.py` 按域拆出（2026-10-07 用户裁定「拆开」，阶段 3 第二包）| **2026-10-20 复用批去重**：帝王行动 5 函数（`_settle_emperor_personal` / `_imp_split_tier` / `_imp_tier_delta` / `_apply_imperial_action` / `_apply_imperial_effects`）与 flat 版逐字节重复且**生产无调用方**，已删死副本；本文件只保留真身 `_settle_emperor_health_decay`（由 `core/settlement_imperial.py` 取用） |
| `edict_closure.py` | **新建**（2026-10-20）| `sweep_edict_closure` `closure_status` `is_zhongzhi` | 圣旨核销闭环：每道旨（含中旨）超期必入执行台账；中旨落地系数 0.75；颁布回合未知者视为未决挂起、不误核销；幂等不改已有条目 |
| `decree_duration.py` | **新建**（2026-10-20 batch4）| `resolve_decree_duration` | 诏令生效月数：天道节奏档(速6/常12/缓18) × 主持官能力 × 皇威 × 后续跟进，clamp 3–36；纯函数无随机；breakdown 记来源 |
| `trend_tier.py` | **新建**（2026-10-20 天道档位化 batch2）| `resolve_power_trend` `resolve_attitude_shock` `resolve_pressure_level` | 国势/外交/事件压力档位→程序换算；**缺档返回 None ⇒ 调用方沿用原随机（零行为变更）** |
| `sentiment_tier.py` | **新建**（2026-10-20 民心线天道化）| `resolve_sentiment` / `apply_sentiment_trend` / `resolve_unrest` / `apply_unrest` / `shock_delta` / `apply_shock` | 民心三条线全部档位化：**月度趋势**（大坏→大好，−3~+3）、**民变规模**（无→大乱，0/−1/−2/−4）、**事件冲击**（轻/中/重，−1/−2/−3）；缺档 ⇒ 程序先验严格回退旧行为；有界 [0,100] |
| `longterm_case.py` | **新建**（2026-10-20 参考外部 UI）| 长期旨案卷化：案号/承办人/授权/专款/底册/阶段/进度/持续效果/推进日志/达成与失控 | 只做案卷层，进度仍归 `longterm_task`；缺失=None、专款真实扣减、白名单持续效果、幂等 |
| | | 🔴 **帝王行动目前处于「暂时停用」状态**：`settlement.IMPERIAL_ACTION_ENABLED = False`（用户 2026-10-07 裁定选甲·可回退不删除）。恢复 = 改该常量 + 去掉 `tests/test_imperial_action.py` 的 module 级 skip，仅此两处。归 `politics` 是**暂定**，重做帝王行动时可能再调整 |

## 拥有的规则

派系、局势、事件及跨机制政治状态（**独立域，经接口协作**）

# 已迁入实现（第十七包，2026-10-07）

| 文件 | 来源旧路径 | 公开面（桩面实测） | 叶子资格 |
|---|---|---|---|
| `split.py` | `core/faction_split.py` | 20 名（含 `_` 私有与 typing/logging 绑定名）| 顶层 import 只有 logging/typing/content 与 `core.foundation.common.numeric` **公开名** |
| `voice.py` | `core/faction_voice.py` | 19 名 | 同上，另函数内引 `content.ministers.data` |
| `legacy_mechanic.py` | `core/legacy_mechanic.py` | 18 名（含 10 个 `_` 私有）| 真叶子：**零 import**（无任何顶层依赖）|

> **2026-10-07 第二十二包（DSH）**：新增 `legacy_mechanic`（帝国修正机制）。
> 生产侧旧路径引用已改指新路径（`commands.py` / `settlement.py`），复扫为 **0**。

# 未随批搬的候选（各有明确理由，不是遗漏）

- `faction_basis.py`、`faction_metrics.py`：**二者自身构成 faction 环**（SCC 第二个环），搬它们=把环搬个位置；须先按 §5 反向边接口倒置。
- `faction_settle.py`：**不是叶子**——顶层 import `core.faction_basis` / `core.faction_metrics`（环内模块）。本批已把它的 `faction_split` 调用改指新路径，其余留待阶段 3。
- `situation_*.py`、`events.py`：未在本批判责范围内，§3.1 要求它们"提供稳定读写接口"，属接口设计工作。

## 边界

- 向下依赖 foundation（账本/状态）与 game/content（数据）；**不得反向导入 workflows 或上层**。
- 机制间协作**经显式接口**，不得跨域读写私有内部结构。
- 读数是只读投影，**不得成为结算算法权威**。

## 迁移状态

**已开始**（第十七包，2026-10-07）：`split.py`（派系立场占比）+ `voice.py`（话语权）已迁入；
`faction_basis` / `faction_metrics` / `faction_settle` 仍在 `core/`（前两者自不成环，属阶段 3 裁定项）。
