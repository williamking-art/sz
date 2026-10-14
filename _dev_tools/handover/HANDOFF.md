# HANDOFF · 当前入口（自动生成，勿手改）

> 生成时间：**2026-10-14 06:11 UTC** · 生成器：`_dev_tools/handover/make_handoff.py`（只读交接层与 git；**只链接，不复制正文**）。
> 权威仍是各 `tasks/`、`decisions/`、`phase/`、`specs/` 与代码本身。

## 1. 当前状态（哪个版本有效 · 哪些结果已验证）

| agent | phase（节选） | 更新 |
|---|---|---|
| Cline.json | 阶段：全库审计 + POP 真账守卫生产化（主线A）已落地；M32(_GUARD_INSTALLED) 已销账；地方府库下沉（M33）已裁暂不排期 | 2026-10-10T16:48:43Z |
| DSH-JEV.json | Jev 决策闸门接入 decree_action_plan：对每个动作独立复核「原文是否明确支持」，不足者追加进 unresolved。已实跑验证。 | 2026-10-12T16:05:00Z |
| DSH.json | 《宋祚》主顺序：**各阶段均已勘察完毕**，其中 **P0/P1/P5 已收口**，P2 达其诚实上限（建筑/作坊各 8/14，岗位数由 Jev 裁丁维持 undefined），**P3 是唯一未开工**（须授权）。**主线的口径 backlog 已 Jev 定案完毕**：①外贸载体＝甲 0.875 ②外贸维度分配＝甲… | 2026-10-14 |
| Qoder.json | 阶段2 结构迁移：第二十二包已交付（evaluation → core/workflows/） | 2026-10-09T23:58:31Z |
| _legacy_shared_phase.json | - | - |
| _retired.qoder.json | - | - |

最近提交：

```
1c53c27c7a feat(economy): M177 外贸**派生记账纯函数** `trade_ledger.py`（只算不写 · 守恒精确 · 零接线）
215ab01904 chore(handover): M176b **补档并纠正计数** —— 上一条漏建任务档致 claim 失败（正文写 115，实际 114）
18b0d83dfb feat(economy): M176 主线 F 实施**原子第一片** —— `state.trade_journal` 容器 + 守卫用例（零行为变化）
e530d897a4 docs(spec): M175 外贸**维度分配＝甲（按产能/人口权重）**（Jev 0.550）⇒ 主线 F 前置 **100% 裁完**
6b111313af docs(spec): M174 外贸真账**实施准备·只读侦察** —— 注入点 + **隐藏前置（维度分配口径）**
```

## 2. 下一步（什么尚未完成）

| 任务 | status | 标题 | claimedBy |
|---|---|---|---|
| `B2-guard-quality-gate.json` | in_progress | B-2 守卫进质量放行门：先只读设计与取证，评审后再实施 | DSH |
| `M25-blocked-writesites.json` | open-registered | 阶段3收尾：落实 M25 已裁定的有限依赖注入边界 | DSH |
| `M29-phase-qoder-dup.json` | wont-fix | 清理 phase_qoder 重复键 | DSH |
| `M36-5-ai-decision-wiring.json` | in_progress | M36.5《AI 决策接线》：让外部 AI 能正确使用 M36 的信息与行动接口（不开 M37） | Cline |
| `M36-6-A-minister-proposal-contract.json` | in_progress | M36.6-A《AI 大臣人格化事实视图与提案契约》：数据结构/权限继承/提案格式/状态转换（设计已出，待 P1–P3 裁定后编码） | Cline |
| `M36-7-A-professional-decision-ledger.json` | in_progress | M36.7-A《AI 大臣专业决策模型》总设计裁定台账（零代码）——八层分析模型/四落点/Q1–Q7 与 P1–P3 已裁 | Cline |
| `M36-7-B-ministers-prototype.json` | in_progress | M36.7-B《AI 大臣最小原型》：1 议题 × 3 大臣 × 单轮、不落库（已实现并本地验收） | Cline |
| `M36-inspection-batch.json` | in_progress | M36《察访与监司行动》：监察＝行动者（编制/生命周期/风险反馈/审理链对接） | Cline |
| `M38-building-sink.json` | in_progress | 建筑下沉州府级（主线B 批次2）：seats[治所]["buildings"] 真账 + 路级 Σ 派生聚合（保形态）+ 4 写点全桥 + 已接线 | DSH |
| `M39-transport-sink.json` | in_progress | 交通下沉州府级（主线B 批次1）：水位/漕运逐治所真账 + 路级/全国降为派生 | DSH |
| `M40-storage-sink.json` | in_progress | 仓储下沉州府级（主线B 批次4 仓储片）：storage/changping_stock 治所级真账 + 路级 Σ 派生 | DSH |
| `M41-market-p1-first-slice.json` | in_progress | 统一民间市场 P1 第一条纵向切片（开工门已出；剩余缺口见 inventory-market.md 2026-10-13 复核） | DSH |
| `M42-stock-flow-ledger.json` | in_progress | 逐维商品流量账（P1 第一句「逐月复原商品库存恒等式」的**缺失前置**） | DSH |
| `M50-job-track-config-fallback.json` | pending | 岗位轨「缺政权专档 ⇒ 静默套 default」去静默（主线C 通过标准②的前半步） | - |
| `_meta.json` | ? |  | - |

> 已完成任务共 **102** 条，见 `INDEX.md`（看板）。

## 3. 关键约束 / **待人决定**

| 决策档 | status | 主题 |
|---|---|---|
| `AGENT-DSH-NAME-COLLISION.json` | 待裁定 | 两个并发会话共用 `DSH` 名字，`phase/DSH.json` 被互相覆盖（需裁定归属规则） |
| `M38c-crop-buildings-authorization.json` | 待裁定 | M38c 建筑语汇统一（桑/麻/果/蔗/茶园各成一建）· 是否需要该阶段单独授权？ |
| `M40b-storage-applier-coupling.json` | 待设计 | 州仓 storage 下沉的前置：engine applier 路径 `prefectures.*.storage` 与 journal 判据的耦合 |
| `MIG-COMPAT-RETENTION.json` | 待裁定 | 迁移期兼容入口(core/* 旧路径转发桩)保留多久；是否列为稳定公共 API |
| `地方支出V2-D1-D5.json` | 待裁定 | 地方支出 V2（M34-①）：行政/治安/水利/救灾/仓廪五条消费性出口的接入口径 D1–D5 |

> 硬约束：仓库根 `AGENTS.md` §3（POP 挂载律 / 口径单点 / **缺失≠0** / 不新增平行账本 / 保留他人未提交改动）。

## 4. 证据入口（按任务链到权威文件，细节按需展开）

| 要什么 | 去哪儿 |
|---|---|
| 看板 / 全部任务状态 | `INDEX.md`（`handover.py summary` 重建） |
| **所有 Jev 裁定与概率** | `DECISIONS-INDEX.md` |
| **待拍板的决策（一页简报）** | `_dev_tools/game-docs/specs/cross-cutting/待裁清单_*.md` |
| **接手指南 / 收口总表** | `_dev_tools/game-docs/specs/economy/unified-civilian-market/{接手指南,收口总表}_*.md` |
| 逐批实测数字与门禁结论 | `worklog/`（追加式，一条一文件） |
| 全量回归原始输出 | `_scratch/full_regression_*.log`（各 agent 约定） |
| 规范与设计 | `_dev_tools/game-docs/specs/**`（含 `接手指南_*.md`） |
| 提交与哈希 | `git log`（`claim finish --commit <hash>` 亦记录） |

### P6 长局哨兵（60/240 月 · 固定种子）

```powershell
& $py -m pytest _dev_tools/game-dev/tests/test_m162_long_run_sentinel.py -q -p no:cacheprovider   # 12 月（默认档）
$env:SONGZUO_LONG_RUN="1";   & $py -m pytest _dev_tools/game-dev/tests/test_m162_long_run_sentinel.py -q   # 60 月（约 46s）
$env:SONGZUO_LONG_RUN="240"; & $py -m pytest _dev_tools/game-dev/tests/test_m162_long_run_sentinel.py -q   # 240 月（约 184s）
```
锁定四项：**无异常** · 货币恒等式残差 **0** · POP 守恒违规 **0** · 读数契约违规 **0**（60/240 月实测均通过）。

### 提交前门禁（每次提交不可省）

```powershell
& $py _dev_tools/handover.py check
git diff --cached --check                                   # 尾随空白/冲突标记 ⇒ 非 0 阻止提交
& $py -m pytest _dev_tools/game-dev/tests/test_readme_sync.py -q -p no:cacheprovider
& $py -m pytest _dev_tools/game-dev/tests -q -p no:cacheprovider > $env:TEMP\full.log 2>&1
"FULL EXIT=$LASTEXITCODE"                                   # 🔴 只看退出码
```

### 三条护栏（违反即交接失效）

1. **不得混淆验证层级**：「离线检查通过」≠「人工已接受」；「全量回归 EXIT=0」≠「功能已被验收」。
2. **授权不继承**：旧交接里的发布/实施计划不得当作新一轮授权；改数值/改 state/对外发布须当轮取得确认。
3. **保留边界**：原始数据、冻结评估、哈希、独有决策、**他人未提交改动**一律保留；**无明确清理请求不删文件**；「还能重新下载」不是删除理由。
