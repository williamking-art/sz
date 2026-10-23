# 交接索引 · 宋祚（本机交接层）

> 由 `python _dev_tools/handover.py summary` 生成，**请勿手改**；
> 生成时间：2026-10-23T00:05:01Z · 协议见 [`README.md`](README.md) · 停用说明见 [`NOTICE.md`](NOTICE.md)

## 各 agent 当前阶段

- **Cline**（updatedAt=2026-10-10T16:48:43Z）：阶段：全库审计 + POP 真账守卫生产化（主线A）已落地；M32(_GUARD_INSTALLED) 已销账；地方府库下沉（M33）已裁暂不排期
- **DSH-Audit**（updatedAt=2026-10-20T15:45:00Z）：2026-10-20 全审完成（只审不改）：sz 游戏本体四维并行审查 + Lead 实测复跑。必修 4：外贸货腿造币链（12月 cum_residual +13,470,432）、陆路榷税无付款方、长期案卷专款双扣+账外余额、天道档位槽失败不清空；应修含 AI 生产者签名错配/_ai_failures 不清、案卷页数
- **DSH-JEV**（updatedAt=2026-10-12T16:05:00Z）：Jev 决策闸门接入 decree_action_plan：对每个动作独立复核「原文是否明确支持」，不足者追加进 unresolved。已实跑验证。
- **DSH-lead**（updatedAt=2026-10-22T23:20:00+08:00）：收口长期任务批次完成：结算幂等端到端 + 审查B1全处置 + 云口径转阿里云 + 发行打包 + Git 推送；MCP 上传阻塞（服务 502/无凭据）
- **DSH**（updatedAt=2026-10-14）：《宋祚》主顺序『可自决部分』全部收口并终局认证（M37–M293，会话 256 轮）。P0 5/5；P1 收口（丝坊 28/总 128 · recipe 共享根因修复 · 阈值 570 · 验收 Jev 甲 0.764 · 60/240 月复测）；P2 双口径就绪度（建筑 8/9=88.9% · 作坊 8/11=72.
- **Qoder**（updatedAt=2026-10-09T23:58:31Z）：阶段2 结构迁移：第二十二包已交付（evaluation → core/workflows/）

## 任务板（未完成）

- `INC-2026-10-17-dsh-deleted-tests` 事故：DSH 清理 sz/tests/ 时误删 antigravity 名下 M323/M324 的两个测试文件 ｜status=**mitigated**｜claimedBy=DSH
- `M25-blocked-writesites` 阶段3收尾：落实 M25 已裁定的有限依赖注入边界 ｜status=**open-registered**｜claimedBy=DSH
- `M300-stage3-pop-and-officialdom` Stage 3: POP 微观生计闭环（告别强行运转）+ 科举三级取士唱名与官员三级差遣考课磨勘 ｜status=**in_progress**｜claimedBy=Antigravity
- `M317-v3-production-methods-and-neutral-intermediates` 中性通用中间物体系与维多利亚3风格生产方式（PM）建筑架构重构 ｜status=**in_progress**｜claimedBy=Antigravity
- `M318-organization-pm-and-living-goods` 组织形态生产方式（作坊vs工厂）与民生文教消费闭环 ｜status=**in_progress**｜claimedBy=Antigravity
- `M324-metrology-engine-and-reforms` 度量衡统一转换引擎、公制双轨接口与体制变法博弈 ｜status=**in_progress**｜claimedBy=antigravity
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
- `M50b-regime-job-track-shards` 补齐 28 类政权岗位轨专档（M50 拒绝产出的前置；本批只登记） ｜status=**pending**｜claimedBy=（未认领）
- `RUST-IDEMPOTENCY-GAP` Rust 实验后端的结算幂等语义未与 Python 侧对齐（本批只登记） ｜status=**open-registered**｜claimedBy=（未认领）
- `WIRING-GAPS-antigravity-2026-10-20` 未接线模块收口清单（M298-M325 审计 §9 剩余项） ｜status=**open-registered**｜claimedBy=（未认领）

## 待裁 / 未闭环决策

- （无）

## 最近 8 条工作日志

- `20261022T080134Z-DSH-lead` → [`worklog/20261022T080134Z-DSH-lead.md`](worklog/20261022T080134Z-DSH-lead.md)
- `20261022T112435Z-DSH-lead` → [`worklog/20261022T112435Z-DSH-lead.md`](worklog/20261022T112435Z-DSH-lead.md)
- `20261022T124528Z-DSH-lead` → [`worklog/20261022T124528Z-DSH-lead.md`](worklog/20261022T124528Z-DSH-lead.md)
- `20261022T132841Z-DSH-lead` → [`worklog/20261022T132841Z-DSH-lead.md`](worklog/20261022T132841Z-DSH-lead.md)
- `20261022T151741Z-DSH-lead` → [`worklog/20261022T151741Z-DSH-lead.md`](worklog/20261022T151741Z-DSH-lead.md)
- `20261022T152359Z-DSH-lead` → [`worklog/20261022T152359Z-DSH-lead.md`](worklog/20261022T152359Z-DSH-lead.md)
- `20261022T172300Z-DSH-lead` → [`worklog/20261022T172300Z-DSH-lead.md`](worklog/20261022T172300Z-DSH-lead.md)
- `20261023T000501Z-DSH-lead` → [`worklog/20261023T000501Z-DSH-lead.md`](worklog/20261023T000501Z-DSH-lead.md)

## 计数

- tasks 215（未完成 20）· decisions 257（未闭环 0）· worklog 820 · phase 文件 6
- 云端原始存量：`archive/cloud_2026-10-09/`（只读留档，勿改）
