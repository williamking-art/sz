# 交接索引 · 宋祚（本机交接层）

> 由 `python _dev_tools/handover.py summary` 生成，**请勿手改**；
> 生成时间：2026-10-10T03:57:09Z · 协议见 [`README.md`](README.md) · 停用说明见 [`NOTICE.md`](NOTICE.md)

## 各 agent 当前阶段

- **DSH**（updatedAt=2026-10-10）：POP 州府真账迁移维护：批 1-A～1-E、批 2-1/2-2 已完成；真实月结全管线守卫回归已扩为 15 月。
- **Qoder**（updatedAt=2026-10-09T23:58:31Z）：阶段2 结构迁移：第二十二包已交付（evaluation → core/workflows/）

## 任务板（未完成）

- `M25-blocked-writesites` 11 个写站点裁定（①依赖注入 vs ②横向域依赖） ｜status=**open-registered**｜claimedBy=DSH
- `M30-rebind-cache-debt` 销账：material_tech / settlement_agri 的 _ALIAS_INDEX 是 global 重绑型惰性缓存 ⇒ 旧 ｜status=**open-registered**｜claimedBy=（未认领）

## 待裁 / 未闭环决策

- `A-粮价` [open] 旧粮价是否与全局人口解耦
- `C-invest` [recommended-no] invest_decide 回报来源守恒
- `MIG-COMPAT-RETENTION` [待裁定] 迁移期兼容入口(core/* 旧路径转发桩)保留多久；是否列为稳定公共 API
- `POP-faction` [design-done] POP 增派系子池（与阶层分离）

## 最近 8 条工作日志

- `20261010T021556Z-DSH` → [`worklog/20261010T021556Z-DSH.md`](worklog/20261010T021556Z-DSH.md)
- `20261010T023121Z-DSH` → [`worklog/20261010T023121Z-DSH.md`](worklog/20261010T023121Z-DSH.md)
- `20261010T023924Z-DSH` → [`worklog/20261010T023924Z-DSH.md`](worklog/20261010T023924Z-DSH.md)
- `20261010T032446Z-DSH` → [`worklog/20261010T032446Z-DSH.md`](worklog/20261010T032446Z-DSH.md)
- `20261010T034239Z-DSH` → [`worklog/20261010T034239Z-DSH.md`](worklog/20261010T034239Z-DSH.md)
- `20261010T034450Z-DSH` → [`worklog/20261010T034450Z-DSH.md`](worklog/20261010T034450Z-DSH.md)
- `20261010T034830Z-DSH` → [`worklog/20261010T034830Z-DSH.md`](worklog/20261010T034830Z-DSH.md)
- `20261010T035708Z-DSH` → [`worklog/20261010T035708Z-DSH.md`](worklog/20261010T035708Z-DSH.md)

## 计数

- tasks 9（未完成 2）· decisions 13（未闭环 4）· worklog 41 · phase 文件 2
- 云端原始存量：`archive/cloud_2026-10-09/`（只读留档，勿改）
