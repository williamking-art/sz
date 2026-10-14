# 决策台账索引（自动生成）

> 由 `_dev_tools/handover/decisions/*.json` 自动汇总。**一条裁定一文件**是本项目纪律；
> 本索引只做导航（**权威仍是各 json**）。生成者：DSH（M116，2026-10-13）。

- 决策档总数：**76**
- 非法 JSON：**0**

| 档案 | verdict | 前二概率 | 裁定人/来源 | 问题（截断） |
|---|---|---|---|---|
| `5d-身份子池.json` | 用户 2026-10-0 |  | - | 身份子池与宗族 clan 是否下沉州府级 |
| `A-粮价.json` | 解耦全局隐户比例：区域粮 |  | - | 旧粮价是否与全局人口解耦 |
| `AGENT-DSH-NAME-COLLISION.json` | 待裁定 |  | - | 两个并发会话共用 `DSH` 名字，`phase/DSH.json` 被互相覆盖（需裁定归属规则） |
| `B1-legacy-freeze-E1-E8.json` | E1–E8 全部保持现状 |  | 用户 | B-1 冻结清单 E1–E8：历史例外与不对称一律维持现状，测试只锁定不修改 |
| `B1-order-relaxation.json` | 批准 B1-order- |  | 用户 | 六集合顺序无法由单一声明复现 ⇒ 仅对 NON_NEG_PREFIXES / RANGE_100_FIELDS 放宽顺序验收（其余四套仍须顺 |
| `C-invest.json` | recommended- |  | - | invest_decide 回报来源守恒 |
| `CNB-发布通道.json` | 用户 2026-10-1 |  | - | CNB 发布通道（williamkai-2026/songzuo）：已进历史的 ai_config.json 密钥如何处置 / 发布范围与工 |
| `D-复述门.json` | 用户 2026-10-0 |  | - | 复述门『复述的产生方』补不补 |
| `D10-证据触发.json` | 用户 2026-10-1 |  | - | D10：financial_evidence 的触发者（甲 AI 决定→单点执行／乙 奏报自动接钩校／丙 第二证据生产者） |
| `D11-证据权限.json` | 用户 2026-10-1 |  | - | D11：证据权限（谁可见 rumor／official 账／real 账／financial evidence） |
| `D9-察访发现.json` | 用户 2026-10-1 |  | - | D9：察访发现是什么？（宋制术语；原误用明制「察访」，已订正） |
| `G-4-holder.json` | 用户 2026-10-0 |  | - | 原料付款人由实际持有人/供给链位置决定 |
| `G-4-owner.json` | 用户 2026-10-0 |  | - | G-4 工坊营运资金：owner 归属与账内出资 |
| `IMPERIAL-ACTION-停用.json` | 甲 —— 停用，不删除 |  | - | 「帝王行动」暂时停用（选甲·可回退） |
| `JEV-台账-logo替换与印玺抠图-2026-10-13.json` | - |  | - |  |
| `JEV-台账-印玺与官网改版-2026-10-13.json` | - |  | - |  |
| `JEV-台账-官网分页整体复审-2026-10-13.json` | - |  | - |  |
| `JEV-台账-官网字体选择-2026-10-13.json` | - |  | - |  |
| `JEV-台账-统一市场与生产线-2026-10-13.json` | record |  | - | 统一市场 / 生产 / 家计各批的 **Jev 裁定台账**（2026-10-13 会话） |
| `LOCAL-HANDOVER.json` | 本机交接；载体=_dev |  | - | 交接通道：放弃 CloudBase MCP，改用仓库内本机交接层 |
| `M104-maintenance-derivation-scope.json` | 甲 | 甲 0.907 · 乙 0.093 | Jev (tokenrhyt | P2 `maintenance`（维护责任）能否只读派生？ |
| `M111-blueprint-derivation-scope.json` | 甲 | 甲 0.908 · 乙 0.059 | Jev (tokenrhyt | P2 `blueprint`（蓝图版本）只读派生怎么定？ |
| `M117-income-to-derivation-scope.json` | 甲 | 甲 0.788 · 乙 0.212 | Jev (tokenrhyt | P2 `income_to` 能否只读派生为「应然去向」？ |
| `M121-workshop-jobs-source-scope.json` | 丁 | 丁 0.696 · 丙 0.118 | Jev (tokenrhyt | M67 作坊岗位数（容量/在岗）来源取哪条？ |
| `M122-operating-fund-source-scope.json` | 丙 | 丙 0.409 · 甲 0.344 | Jev (tokenrhyt | 作坊营运资金来源（D 线 G-4）取哪条？ |
| `M25-写站点拆环.json` | 路径①依赖注入，但注入面 |  | - | 11 个写站点的接口归属 |
| `M38c-crop-buildings-authorization.json` | 待裁定 |  | - | 是否授权在本阶段新增桑田/麻田/果园/蔗田/茶园等 `content` 条目与可建选项（M38c）？若授权，按工程量评估的哪一档（0/1/2 |
| `M40b-storage-applier-coupling.json` | 待设计 |  | - | 州仓 storage 下沉的前置：engine applier 路径 `prefectures.*.storage` 与 journal 判 |
| `M52-livelihood-shadow-scope.json` | A | A 0.948 · C 0.032 | Jev (tokenrhyt | 主线E（家计/经济归属/税制）本批取哪个切片？ |
| `M53-seat-market-shadow-scope.json` | A | A 0.948 · B 0.049 | Jev (tokenrhyt | 主线F（市场与外贸）第一切片取哪个？ |
| `M54-readout-hub-scope.json` | A | A 0.855 · B 0.126 | Jev (tokenrhyt | 主线A/P5 第一切片取哪个？ |
| `M55-next-batch-tiebreak.json` | decided | B 0.458 · A 0.449 | Jev (tokenrhyt | 目标顺序各第一切片已落地后，下一批做哪个？ |
| `M57-mirror-write-sweep-scope.json` | A | A 0.984 · C 0.011 | Jev (tokenrhyt | 本会话已修 6 处「直写路级镜像」同族缺陷后，本轮做哪个？ |
| `M58-owner-candidates-scope.json` | B | B 0.863 · A 0.121 | Jev (tokenrhyt | 为「谁持有作坊」（M51 的 blocker）做只读候选盘点，范围取哪个？ |
| `M59-盲区补齐-scope.json` | A | A 0.528 · B 0.323 | Jev (tokenrhyt | M57 家族哨兵已覆盖结算管线，剩下两个盲区 + 一项可量化挂账，本轮取哪个？ |
| `M61-backend-action-guard-scope.json` | decided | A 0.518 · C 0.456 | Jev (tokenrhyt | 目标仍未完成、P3/P4/前端待口径，本批做哪个？ |
| `M62-m53-finish-scope.json` | A | A 0.716 · B 0.260 | Jev (tokenrhyt | Round 42 取哪个（均不需玩法裁定）？ |
| `M63-resource-stock-survey-scope.json` | A | A 0.693 · B 0.285 | Jev (tokenrhyt | Round 43 取哪个（M40c 商品/物料存量州府化的前置取证）？ |
| `M64-resource-stock-bridge-scope.json` | decided |  | Jev (tokenrhyt | Round 44 裁定：resources 归属口径取**甲**（保持全国池＋给有路写点加可选路参数桥） |
| `M65-m64b-bridge-remaining-scope.json` | A | A 0.918 · B 0.079 | Jev (tokenrhyt | Round 45 取哪个？ |
| `M66-workshop-owner-scope.json` | A | A 0.665 · C 0.198 | Jev (tokenrhyt | 作坊产权落点（M51 blocker）本批取哪个？ |
| `M67-workshop-wage-scope.json` | D | D 0.567 · C 0.361 | Jev (tokenrhyt | 作坊工资单点（把 shadow_ready 从 0 顶起来的最后前置）本批取哪个？ |
| `M68-g4-perroute-funding-scope.json` | decided |  | Jev (tokenrhyt | Round 48 裁定：G-4 逐路资金到位率（A 0.959）＋ `recipe_cost` 静默 0 缺陷修法取**甲**（0.892） |
| `M69-feed-price-and-m70-grain-tier.json` | decided |  | Jev (tokenrhyt | Round 49 裁定：粮料即粮（甲 0.992）＋ 修粮价单点「按政权求和」缺陷（甲 0.996） |
| `M71-funding-horizons-scope.json` | A | A 0.733 · B 0.159 | Jev (tokenrhyt | Round 50 取哪个（产权落点依据已因 M69/M70 变更）？ |
| `M72-bridge-closure-scope.json` | 甲 | 甲 0.732 · 丙 0.216 | Jev (tokenrhyt | M64 余项（粮维写回：把 resources 的粮维 stock 直接设为 n）怎么处理？ |
| `M73-demand-channel-scope.json` | A | A 0.941 · D 0.026 | Jev (tokenrhyt | Round 52 取哪个？ |
| `M74-durable-channel-scope.json` | decided |  | Jev (tokenrhyt | Round 53：耐用品通道接入影子需求（A 0.953）＋ 合成口径**平手**＋ 修**双重计数**（甲 0.998） |
| `M75-p4-slice-scope.json` | 甲 | 甲 0.451 · 丙 0.438 | Jev (tokenrhyt | P4（府际/边境/远方市场）本批怎么切？ |
| `M76-p2-entity-baseline-scope.json` | 甲 | 甲 0.811 · 乙 0.181 | Jev (tokenrhyt | P2「主体」口径本批怎么切？ |
| `M77-gap1-jobs-readout-scope.json` | 丙 | 丙 0.501 · 甲 0.310 | Jev (tokenrhyt | 「实到岗位」的分派规则取哪个（P1/P2/P4 共同硬阻塞）？ |
| `M78-jobs-readout-correction-scope.json` | 甲 | 甲 0.833 · 乙 0.141 | Jev (tokenrhyt | 岗位队列细化到路/治所级本批怎么切？（会改仿真数值） |
| `M79-p1-pilot-selection-scope.json` | 甲 | 甲 0.709 · 乙 0.221 | Jev (tokenrhyt | Round 58 取哪个？ |
| `M80-p1-pilot-chain-scope.json` | 甲 | 甲 0.985 · 丙 0.011 | Jev (tokenrhyt | Round 59 取哪个？ |
| `M81-readout-hub-wiring-scope.json` | 甲 | 甲 0.625 · 乙 0.370 | Jev (tokenrhyt | Round 60 取哪个？ |
| `M82-pilot-diagnosis-scope.json` | 甲 | 甲 0.996 · 乙 0.004 | Jev (tokenrhyt | Round 61 取哪个？ |
| `M83-readouts-endpoint-hub-scope.json` | 甲 | 甲 0.996 · 乙 0.003 | Jev (tokenrhyt | Round 62 取哪个？ |
| `M84-readout-hub-panel-scope.json` | 甲 | 甲 0.942 · 乙 0.058 | Jev (tokenrhyt | Round 63 取哪个？ |
| `M85-readout-hub-entry-scope.json` | 甲 | 甲 0.994 · 乙 0.006 | Jev (tokenrhyt | Round 64 取哪个？ |
| `M86-entity-projection-scope.json` | 甲 | 甲 0.970 · 乙 0.016 | Jev (tokenrhyt | Round 65 取哪个？ |
| `M87-p2-readiness-readout-scope.json` | 甲 | 甲 0.733 · 丙 0.233 | Jev (tokenrhyt | Round 66 取哪个？ |
| `M90-p2-field-landing-design-scope.json` | 甲 | 甲 0.903 · 乙 0.087 | Jev (tokenrhyt | Round 69 取哪个？ |
| `M91-building-owner-landing-scope.json` | 甲 | 甲 0.866 · 乙 0.098 | Jev (tokenrhyt | 是否放行按 M90 设计实施 P2 第一片（owner 字段）？ |
| `M92-operator-mode-derivation-scope.json` | 甲 | 甲 0.742 · 乙 0.167 | Jev (tokenrhyt | P2 的 operator/operation_mode 怎么定（只读派生，不改 state）？ |
| `M93-building-owner-rules-scope.json` | 甲 | 甲 0.971 · 乙 0.024 | Jev (tokenrhyt | 建筑归属规则是否扩到岗位建筑？ |
| `M94-building-owned-readout-scope.json` | decided |  | DSH（按 M87 同型惯例 | Round 73：建筑归属登记率接进读数索引（13→14 项；零数值） |
| `M96-workshop-projection-scope.json` | 甲 | 甲 0.972 · 乙 0.028 | Jev (tokenrhyt | 规格 §4 P2 原文是「建筑/**经营记录**」——作坊才是经营记录，是否补其投影？ |
| `M97-workshop-readiness-readout-scope.json` | decided |  | DSH（同型惯例扩项：M81 | Round 76：作坊就绪度接进读数索引（14→15 项；同型惯例扩项） |
| `MIG-COMPAT-RETENTION.json` | 待裁定 |  | - | 迁移期兼容入口(core/* 旧路径转发桩)保留多久；是否列为稳定公共 API |
| `POP-faction.json` | design-done |  | - | POP 增派系子池（与阶层分离） |
| `POP真账下沉与肉改商品.json` | decided |  | - | POP 州府级真账下沉与肉改商品 |
| `_meta.json` | - |  | - |  |
| `local-treasury-share-basis.json` | Jev 裁定（token |  | - | 把既有路级 treasury 分摊到治所时，权重依据取哪一项？ |
| `qoder-songzuo-mcp-scope.json` | local | local 0.623 · user 0.195 | Jev (tokenrhyt | 自托管交接状态 MCP（mcp-songzuo v2.0.0，8 工具，端点 http://120.25.223.23:18080/mcp） |
| `地方支出V2-D1-D5.json` | 待裁定 |  | - | D1–D5：① 是否接入这五条消费性出口？② 按甲/乙/丙哪一方案？③ 各项费率与封顶怎么定？④ 欠费科目如何挂？⑤ 穷路（府库近零）如何截 |
| `家计-五等.json` | 用户 2026-10-0 |  | - | 家计五等阈值取值 + 三税三基改造 |

## 待裁定（`status=待裁定`）

- `AGENT-DSH-NAME-COLLISION.json`：两个并发会话共用 `DSH` 名字，`phase/DSH.json` 被互相覆盖（需裁定归属规则）
- `M38c-crop-buildings-authorization.json`：是否授权在本阶段新增桑田/麻田/果园/蔗田/茶园等 `content` 条目与可建选项（M38c）？若授权，按工程量评估的哪一档（0/1/2
- `M40b-storage-applier-coupling.json`：州仓 storage 下沉的前置：engine applier 路径 `prefectures.*.storage` 与 journal 判
- `MIG-COMPAT-RETENTION.json`：迁移期兼容入口(core/* 旧路径转发桩)保留多久；是否列为稳定公共 API
- `地方支出V2-D1-D5.json`：D1–D5：① 是否接入这五条消费性出口？② 按甲/乙/丙哪一方案？③ 各项费率与封顶怎么定？④ 欠费科目如何挂？⑤ 穷路（府库近零）如何截
