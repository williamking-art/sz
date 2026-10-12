# foundation/ledger — 权威账本层

> POP / 钱粮 / 物料的**真账**与唯一读写入口。迁移状态总表见 [../README.md](../README.md) §一。
> 本文件只记**本子包内的模块职责与不可绕过的纪律**。

## 在整条依赖链的位置

```
业务域 (domains/*)  →  账本 (ledger)  →  状态结构
```

**所有 POP / 钱 / 粮的写入必须经过本层。** 绕过桥接的直写会被
`test_route_pops_readonly_guard.py` 当场炸掉（路级 `pops` 已由只读守卫强制）。

## 模块（9 个：8 个由 `git mv` 迁入 + 1 个 2026-10-13 新建）

> 行数为 2026-10-11 实测快照（会随提交变化，仅作量级参考，不作为判据）。

| 模块 | 行 | 职责 |
|---|---:|---|
| `pop_bridge.py` | 805 | 🔴 **州府级 POP 基座 + 读写桥**（2026-10-04 用户裁定**方案乙**：POP 实体下沉州府级）。真账在 `prefectures[路]["seats"][治所]["pops"][类]`；含只读守卫 `install_all_guards`/`uninstall_all_guards`/`pops_guard_violations` |
| `material_holding.py` | 907 | **账本接口层**。物料/商品单点访问层——遍历 `goods` 键会把州府桶当商品维参与算术，**唯一安全判据是 `commodity_dims`** |
| `money.py` | 762 | 货币口径 M0/M1/M2/M3 与月度对账（**只读视图**） |
| `pop_structure.py` | 359 | POP 职位子池与丁口维度（B1a，2026-09-27 用户口径） |
| `prefecture_entity.py` | 239 | 州府实体层（P0/A2 · 2026-10-02） |
| `grain_bridge.py` | 128 | 🔴 **G-3 读写桥**：`pops[].grain` ⇄ `goods[治所][米]` 的**单点过渡层** |
| `occupation.py` | 111 | 🔴 **M35-C 职业人口单点**（2026-10-11 并入）：职业计数住**挂靠桶子池**（`HOST_POOL`，如 `官僚.runner_count`），**不新增 POP、不新增粮桶**；所有"人口粮需／饥饿判断／粮仓需求／购粮能力"一律经本模块取值 |
| `grain_ledger.py` | 99 | 🔴 **G-3 迁移基座**：把 `pops[].grain` 迁入 `goods[治所][米/麦]`（裁定 H·甲） |
| `local_treasury_bridge.py` | 307 | 🔴 **地方府库（`local_treasury`）下沉桥**（M37，2026-10-13 **新建**、非迁移）。真账在 `prefectures[路]["seats"][治所]["local_treasury"]`，路级降为 **Σ 派生镜像**；含聚合（未下沉⇒`None`）· 对账 `survey_local_treasury` · 写桥 `local_treasury_set/add`（未下沉⇒`None` 回落）· **治所级精确写** `seat_local_treasury_set` + `seat_local_treasury_writable`。⚠️ **别与中央 `state.treasury` 混淆**（两者不同账户） |

## 🔴 不可绕过的纪律

1. **POP 写入必须走 `pop_bridge`**；真账落**州府**，路级 `pops` 降为**只读派生聚合**（Σ 治所）。
   任何写路级 `pops` 的行为都构成「与 POP 平行的账本」。
2. **`grain_bridge` 的四个函数都支持可选 `state`**：给了就委派 `pop_bridge`（写入下沉州府），
   没给则沿用旧载体。🔴 **改调用点时务必传 `state`**，否则会继续写路级、造成分叉
   （§6.18 有三处漏网实例）。
3. **均值类字段**（`MEAN_FIELDS`，如识字率）是比率，拆分/聚合都**不可求和**（复制 + 按 size 加权）。
4. **`sync_route_pops` 是「合并」而非「替换」**，否则抹掉 `estate`/`officials` 等不参与拆分的字段。
5. 存量**读取**仍走路级 `pops`（约 210 处）——**这是刻意保留**：镜像是 `seats` 的纯函数，
   重写读取对正确性零收益、风险极高。
6. 🔴 **地方府库（`local_treasury`）写入必须走 `local_treasury_bridge`**；真账在**治所**、路级是 Σ 派生镜像。
   ⚠️ **"开闸"必须与"全部写点走桥"同批**——实测（2026-10-13，跑结算步骤 × 3 轮）：
   ① 只下沉不桥任何写点 ⇒ **第 1 轮起 20/20 路镜像漂移**（治所冻结在开局值）；
   ② 只桥账户层、留 5 处绕过账户层的直写 ⇒ **2× 冲账**；
   ③ 七处全桥 ⇒ **0 失配**。
   七处写点：账户层 `local:<路>` setter · `settlement_common`（平籴/粜粮）· `settlement_finance`
   （留州份额／必要支出优先层）· `commands_decree`（州郡赈济）；旧档 `setdefault` 由 `load_game` 顺序覆盖。
   账户 id 三段式 **`local:<路>:<治所>`** = 治所级**精确**写（不重分摊）；
   **未下沉路／治所不存在一律不可写**（否则划转静默无效、调用方仍记"已入库"＝销毁钱）。
