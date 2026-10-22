# `_dev_tools/game-dev/tools/` · 离线工具

**放什么**：需要**驱动结算/读档/建新局**的离线工具。
它们不能住在 `game/core/` 下——`core/ai` 等业务层**不得反向依赖** `core.settlement` /
`core.commands` / `application`（`test_architecture_import_guard` 的 R2/R3，且守卫明确要求
「改代码而不是往 `_FROZEN_UPLINK` 加行」）。所以：**纯逻辑留在 `core/`，接线与 CLI 在这里**。

| 工具 | 作用 | 用法 |
|---|---|---|
| `tiandao_labels.py` | **回测标签生成器**（代理真值）：逐月对每个 objective 的每个候选分支强制跑一个月，只在「唯一帕累托支配」时打标签 | 见下 |

## `tiandao_labels.py`

```powershell
$py = "D:\codebuddy\.audit-venv\Scripts\python.exe"
cd D:\codebuddy\sz
# 新局起算 12 个月（约 3~5 分钟；每次试验约 0.4s/月）
& $py -X utf8 _dev_tools\game-dev\tools\tiandao_labels.py --months 12 --out "$env:TEMP\labels.json"
# 从存档起算 6 个月
& $py -X utf8 _dev_tools\game-dev\tools\tiandao_labels.py --save <save.json> --months 6 --out labels.json
```

产出直接喂回测器（`--labels`）：

```powershell
cd D:\codebuddy\sz\game
& $py -m core.ai.tiandao_backtest <save.json> --labels "$env:TEMP\labels.json"
```

**口径**（判定在 `game/core/ai/tiandao_labels.py`，本文件只接线）：
- 度量向量 =（国库, Σ地方府库, 太仓, −Σ民怨, −Σ流民），**越大越好**；
- **只有唯一**分支「全面不劣且至少一项更优」才打标签；并列/互有胜负 **跳过**
  —— 不设权重、不臆造真值，故覆盖率天然有限（实测 6 个月约 1/3）；
- 是**代理真值**（「事后哪种做法让国计民生更好」）：度量校准与排序，**不证明因果**，
  也不含长期后果（变法/考课的十年收益看不到）。

**踩过的坑**：
- 必须**冻结观测**（`frozen_observe`）：月结 Step 0 会重新观察并覆盖 `state._tiandao_observe`，
  不冻结则"强制某分支"在第一步就被冲掉，反事实实验失效。
- 标签 `turn` 取**观测副本自带的 `turn`**，不要用 `state.turn or (i+1)`——首月 `state.turn==0`
  会被 falsy 判成 1，导致与 `decision_log` 错位并产生重复标签（实测覆盖率 0.33→0.27）。
