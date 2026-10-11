# 交接索引 · 宋祚（本机交接层）

> 由 `python _dev_tools/handover.py summary` 生成，**请勿手改**；
> 生成时间：2026-10-11T09:17:43Z · 协议见 [`README.md`](README.md) · 停用说明见 [`NOTICE.md`](NOTICE.md)

## 各 agent 当前阶段

- **Cline**（updatedAt=2026-10-10T16:48:43Z）：阶段：全库审计 + POP 真账守卫生产化（主线A）已落地；M32(_GUARD_INSTALLED) 已销账；地方府库下沉（M33）已裁暂不排期
- **DSH**（updatedAt=2026-10-11）：州路档案 UI 与单军档案已落地：左侧多页面抽屉（概览/人口/民情/施政/军政/营建/财赋）+ 三入口共用的单军档案；后端补单军月饷/月粮读数；计划第4步兵种注册兵饷州府桥接已收尾提交。
- **Qoder**（updatedAt=2026-10-09T23:58:31Z）：阶段2 结构迁移：第二十二包已交付（evaluation → core/workflows/）

## 任务板（未完成）

- `M25-blocked-writesites` 阶段3收尾：落实 M25 已裁定的有限依赖注入边界 ｜status=**open-registered**｜claimedBy=DSH
- `M36-inspection-batch` M36《察访与监司行动》：监察＝行动者（编制/生命周期/风险反馈/审理链对接） ｜status=**in_progress**｜claimedBy=Cline

## 待裁 / 未闭环决策

- `C-invest` [recommended-no] invest_decide 回报来源守恒
- `D10-证据触发` [open] D10：financial_evidence 的触发者（甲 AI 决定→单点执行／乙 奏报自动接钩校／丙 第二证据生产者）
- `D11-证据权限` [open] D11：证据权限（谁可见 rumor／official 账／real 账／financial evidence）
- `D9-察访发现` [open] D9：察访发现是什么？（宋制术语；原误用明制「察访」，已订正）
- `MIG-COMPAT-RETENTION` [待裁定] 迁移期兼容入口(core/* 旧路径转发桩)保留多久；是否列为稳定公共 API
- `POP-faction` [design-done] POP 增派系子池（与阶层分离）

## 最近 8 条工作日志

- `20261011T050727Z-Cline` → [`worklog/20261011T050727Z-Cline.md`](worklog/20261011T050727Z-Cline.md)
- `20261011T051439Z-Cline` → [`worklog/20261011T051439Z-Cline.md`](worklog/20261011T051439Z-Cline.md)
- `20261011T052536Z-Cline` → [`worklog/20261011T052536Z-Cline.md`](worklog/20261011T052536Z-Cline.md)
- `20261011T065118Z-Cline` → [`worklog/20261011T065118Z-Cline.md`](worklog/20261011T065118Z-Cline.md)
- `20261011T072513Z-Cline` → [`worklog/20261011T072513Z-Cline.md`](worklog/20261011T072513Z-Cline.md)
- `20261011T080143Z-Cline` → [`worklog/20261011T080143Z-Cline.md`](worklog/20261011T080143Z-Cline.md)
- `20261011T082030Z-Cline` → [`worklog/20261011T082030Z-Cline.md`](worklog/20261011T082030Z-Cline.md)
- `20261011T091742Z-Cline` → [`worklog/20261011T091742Z-Cline.md`](worklog/20261011T091742Z-Cline.md)

## 计数

- tasks 13（未完成 2）· decisions 16（未闭环 6）· worklog 111 · phase 文件 3
- 云端原始存量：`archive/cloud_2026-10-09/`（只读留档，勿改）
