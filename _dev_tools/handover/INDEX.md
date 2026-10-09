# 交接索引 · 宋祚（本机交接层）

> 由 `python _dev_tools/handover.py summary` 生成，**请勿手改**；
> 生成时间：2026-10-09T08:07:30Z · 协议见 [`README.md`](README.md) · 停用说明见 [`NOTICE.md`](NOTICE.md)

## 各 agent 当前阶段

- **DSH**（updatedAt=2026-10-08）：M25 裁定全部落地（隐户初始化移出 GameState + 动态蓝图迁应用层 + 失败分级）；POP 真账州府级下沉完成（新局+子池）；肉改商品。本会话累计 20 提交。
- **Qoder**（updatedAt=2026-10-09T07:48:30Z）：交接通道迁移完成：CloudBase MCP 停用，改用仓库内本机交接层 _dev_tools/handover/（用户裁定，登记 decisions/LOCAL-HANDOVER）。

## 任务板（未完成）

- `M24-leaf-candidates` 第二十二包候选：自实测真叶子清单挑一个 ｜status=**pending**｜claimedBy=（未认领）
- `M25-blocked-writesites` 11 个写站点裁定（①依赖注入 vs ②横向域依赖） ｜status=**open-registered**｜claimedBy=DSH
- `M30-rebind-cache-debt` 销账：material_tech / settlement_agri 的 _ALIAS_INDEX 是 global 重绑型惰性缓存 ⇒ 旧 ｜status=**open-registered**｜claimedBy=（未认领）

## 待裁 / 未闭环决策

- `5d-身份子池` [open] 身份子池与宗族 clan 是否下沉州府级
- `A-粮价` [open] 旧粮价是否与全局人口解耦
- `C-invest` [recommended-no] invest_decide 回报来源守恒
- `D-复述门` [open] 复述门『复述的产生方』补不补
- `G-4-holder` [open] 原料付款人由实际持有人/供给链位置决定
- `G-4-owner` [open] G-4 工坊营运资金：owner 归属与账内出资
- `MIG-COMPAT-RETENTION` [待裁定] 迁移期兼容入口(core/* 旧路径转发桩)保留多久；是否列为稳定公共 API
- `POP-faction` [design-done] POP 增派系子池（与阶层分离）
- `家计-五等` [needs-impact-report] 家计五等阈值取值 + 三税三基改造

## 最近 8 条工作日志

- `20261009T022127.427Z-DSH` → [`worklog/20261009T022127.427Z-DSH.md`](worklog/20261009T022127.427Z-DSH.md)
- `20261009T023042.408Z-DSH` → [`worklog/20261009T023042.408Z-DSH.md`](worklog/20261009T023042.408Z-DSH.md)
- `20261009T023659.335Z-DSH` → [`worklog/20261009T023659.335Z-DSH.md`](worklog/20261009T023659.335Z-DSH.md)
- `20261009T025304.919Z-DSH` → [`worklog/20261009T025304.919Z-DSH.md`](worklog/20261009T025304.919Z-DSH.md)
- `20261009T031448.660Z-Qoder` → [`worklog/20261009T031448.660Z-Qoder.md`](worklog/20261009T031448.660Z-Qoder.md)
- `20261009T072619Z-Qoder` → [`worklog/20261009T072619Z-Qoder.md`](worklog/20261009T072619Z-Qoder.md)
- `20261009T074830Z-Qoder` → [`worklog/20261009T074830Z-Qoder.md`](worklog/20261009T074830Z-Qoder.md)
- `20261009T080639Z-Qoder` → [`worklog/20261009T080639Z-Qoder.md`](worklog/20261009T080639Z-Qoder.md)

## 计数

- tasks 9（未完成 3）· decisions 13（未闭环 9）· worklog 23 · phase 文件 2
- 云端原始存量：`archive/cloud_2026-10-09/`（只读留档，勿改）
