# 交接索引 · 宋祚（本机交接层）

> 由 `python _dev_tools/handover.py summary` 生成，**请勿手改**；
> 生成时间：2026-10-14T09:02:45Z · 协议见 [`README.md`](README.md) · 停用说明见 [`NOTICE.md`](NOTICE.md)

## 各 agent 当前阶段

- **Cline**（updatedAt=2026-10-10T16:48:43Z）：阶段：全库审计 + POP 真账守卫生产化（主线A）已落地；M32(_GUARD_INSTALLED) 已销账；地方府库下沉（M33）已裁暂不排期
- **DSH-JEV**（updatedAt=2026-10-12T16:05:00Z）：Jev 决策闸门接入 decree_action_plan：对每个动作独立复核「原文是否明确支持」，不足者追加进 unresolved。已实跑验证。
- **DSH**（updatedAt=2026-10-14）：《宋祚》主顺序：**各阶段均已勘察完毕**，其中 **P0/P1/P5 已收口**，P2 达其诚实上限（建筑/作坊各 8/14，岗位数由 Jev 裁丁维持 undefined），**P3 是唯一未开工**（须授权）。**主线的口径 backlog 已 Jev 定案完毕**：①外贸载体＝甲 0.875 ②外贸维度分配＝甲
- **Qoder**（updatedAt=2026-10-09T23:58:31Z）：阶段2 结构迁移：第二十二包已交付（evaluation → core/workflows/）

## 任务板（未完成）

- `B2-guard-quality-gate` B-2 守卫进质量放行门：先只读设计与取证，评审后再实施 ｜status=**in_progress**｜claimedBy=DSH
- `M25-blocked-writesites` 阶段3收尾：落实 M25 已裁定的有限依赖注入边界 ｜status=**open-registered**｜claimedBy=DSH
- `M36-5-ai-decision-wiring` M36.5《AI 决策接线》：让外部 AI 能正确使用 M36 的信息与行动接口（不开 M37） ｜status=**in_progress**｜claimedBy=Cline
- `M36-6-A-minister-proposal-contract` M36.6-A《AI 大臣人格化事实视图与提案契约》：数据结构/权限继承/提案格式/状态转换（设计已出，待 P1–P3 裁定后编码） ｜status=**in_progress**｜claimedBy=Cline
- `M36-7-A-professional-decision-ledger` M36.7-A《AI 大臣专业决策模型》总设计裁定台账（零代码）——八层分析模型/四落点/Q1–Q7 与 P1–P3 已裁 ｜status=**in_progress**｜claimedBy=Cline
- `M36-7-B-ministers-prototype` M36.7-B《AI 大臣最小原型》：1 议题 × 3 大臣 × 单轮、不落库（已实现并本地验收） ｜status=**in_progress**｜claimedBy=Cline
- `M36-inspection-batch` M36《察访与监司行动》：监察＝行动者（编制/生命周期/风险反馈/审理链对接） ｜status=**in_progress**｜claimedBy=Cline
- `M38-building-sink` 建筑下沉州府级（主线B 批次2）：seats[治所]["buildings"] 真账 + 路级 Σ 派生聚合（保形态）+ 4 写点全桥 +  ｜status=**in_progress**｜claimedBy=DSH
- `M39-transport-sink` 交通下沉州府级（主线B 批次1）：水位/漕运逐治所真账 + 路级/全国降为派生 ｜status=**in_progress**｜claimedBy=DSH
- `M40-storage-sink` 仓储下沉州府级（主线B 批次4 仓储片）：storage/changping_stock 治所级真账 + 路级 Σ 派生 ｜status=**in_progress**｜claimedBy=DSH
- `M41-market-p1-first-slice` 统一民间市场 P1 第一条纵向切片（开工门已出；剩余缺口见 inventory-market.md 2026-10-13 复核） ｜status=**in_progress**｜claimedBy=DSH
- `M42-stock-flow-ledger` 逐维商品流量账（P1 第一句「逐月复原商品库存恒等式」的**缺失前置**） ｜status=**in_progress**｜claimedBy=DSH
- `M50-job-track-config-fallback` 岗位轨「缺政权专档 ⇒ 静默套 default」去静默（主线C 通过标准②的前半步） ｜status=**pending**｜claimedBy=（未认领）

## 待裁 / 未闭环决策

- `AGENT-DSH-NAME-COLLISION` [待裁定] 两个并发会话共用 `DSH` 名字，`phase/DSH.json` 被互相覆盖（需裁定归属规则）
- `C-invest` [recommended-no] invest_decide 回报来源守恒
- `M38c-crop-buildings-authorization` [待裁定] M38c 建筑语汇统一（桑/麻/果/蔗/茶园各成一建）· 是否需要该阶段单独授权？
- `MIG-COMPAT-RETENTION` [待裁定] 迁移期兼容入口(core/* 旧路径转发桩)保留多久；是否列为稳定公共 API
- `POP-faction` [design-done] POP 增派系子池（与阶层分离）
- `地方支出V2-D1-D5` [待裁定] 地方支出 V2（M34-①）：行政/治安/水利/救灾/仓廪五条消费性出口的接入口径 D1–D5

## 最近 8 条工作日志

- `20261014T084147Z-DSH` → [`worklog/20261014T084147Z-DSH.md`](worklog/20261014T084147Z-DSH.md)
- `20261014T085540Z-DSH` → [`worklog/20261014T085540Z-DSH.md`](worklog/20261014T085540Z-DSH.md)
- `20261014T085656Z-DSH` → [`worklog/20261014T085656Z-DSH.md`](worklog/20261014T085656Z-DSH.md)
- `20261014T085745Z-DSH` → [`worklog/20261014T085745Z-DSH.md`](worklog/20261014T085745Z-DSH.md)
- `20261014T085915Z-DSH` → [`worklog/20261014T085915Z-DSH.md`](worklog/20261014T085915Z-DSH.md)
- `20261014T090008Z-DSH` → [`worklog/20261014T090008Z-DSH.md`](worklog/20261014T090008Z-DSH.md)
- `20261014T090126Z-DSH` → [`worklog/20261014T090126Z-DSH.md`](worklog/20261014T090126Z-DSH.md)
- `20261014T090245Z-DSH` → [`worklog/20261014T090245Z-DSH.md`](worklog/20261014T090245Z-DSH.md)

## 计数

- tasks 148（未完成 13）· decisions 82（未闭环 6）· worklog 393 · phase 文件 4
- 云端原始存量：`archive/cloud_2026-10-09/`（只读留档，勿改）
