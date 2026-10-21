# domains/transport — 交通与物流

> **2026-10-21 重写**：本包不再是空骨架。真实实现仍在 `core/transport.py`（约 1400 行，尚未 `git mv` 进本目录）；
> 本 README 记录**当前事实**与接线位置；迁移时以符号调用图为准，不得按本文件路径直接搬家。

## 1. 它负责什么

- **可达性与耗时**：`is_adjacent` / `route_path` / `route_days` / `transit_km` / `transit_days` /
  `carrier_days`（路网图来自 `content` 的州府/路网数据；海运另有 `sea_lanes_graph` / `sea_route`）。
- **运力派生与占用**：`transport_capacity`（载具上限 × 人力上限 × 可用率，标 bottleneck）/
  `transport_remaining` / `transport_consume` / `transport_used`。
- **发运与排队**：`transport_ship_or_queue`（能运多少运多少，余量入 `state.transport_queue`，不拒办）/
  `transport_queue` / `transport_flush_queue`。
- **月重置**：`transport_reset_month`（清空本月货/客两本 `transport_used`，队列保留）。
- **季节/政策/成本**：`route_season`、`transport_policy`、`transport_fee`、`hire_private`（和雇）、
  `impress_private`（强征）。
- **在途资产**：`dispatch` / `arrive_due` / `in_transit` / `transit_by_seat` / `transit_report`；
  钱作为 cargo 走 `foundation/ledger/money_transport.py`（与实体运输分开记账）。
- **效果注册表**：`register_transport_effect_provider/key` 与 `transport_effects`（科技/诏令修正运力）。
- **读数**：`transport_capability` / `available_modes` / `connectivity_report` / `transport_links` /
  `transport_snapshot`（只读；缺失一律 `None`/reason，不回落 0）。

## 2. 接线（谁在调用）

| 调用方 | 用途 |
|---|---|
| `core/commands.py::settle_local` → `run_monthly_settlement` | **回合初**先 `transport_reset_month`，再 `transport_flush_queue` 续发上月超限队列（R-N-3，2026-10-20）；续发量记 `statistics["transport_queue_flushed"]`，日志写「[运输] 续发…」 |
| `core/domains/economy/trade_legs.py` | 外贸货腿用 `transport_ship_or_queue` 占运力并记流水（`queued_stone`） |
| `core/settlement_econ.py` / 市场/调拨 | 本地成交与跨所调拨按 `transport_consume` 占运力 |
| `core/design/...`（读数/影子） | 只读 `transport_remaining`/`in_transit`/`available_modes`，**不得**据此回写 |
| `core/foundation/ledger/money_transport.py` | 钱银在途：`dispatch_money`/`arrive_money_due`（与货物在途分开） |

**纪律**：运力是**派生量**，不是账本；`transport_used` 只是本月占用，跨月必须由 `transport_reset_month`
重置（否则历史占用会永久吃光运力——2026-10-20 实测过的 bug）。

## 3. 队列语义（R-N-3 后）

- 队列条目：`{mode, qty, kind, payload}`；`state.transport_queue` / `state.transport_used` 均为**瞬态**
  （`save_load` 不序列化，读档后为空）——`transport_reset_month` 只重置本月占用，队列保留待续发。
- `transport_ship_or_queue`：先 `transport_consume`；不足部分按 `TRANSPORT_QUEUE_MAX_STONE` 入队，
  超上限部分丢弃并累计 `statistics["transport_queue_dropped"]` + WARNING（上限缺失/非正 ⇒ 不限制并 WARNING）。
  返回 `{ok, shipped, queued, dropped, remaining, status}`，`status ∈ shipped/partial/queued/dropped/none`。
- `transport_flush_queue(dispatcher=None)`：FIFO 续发；无 `dispatcher` 时**只做运力账**；
  回调失败会把额度退回并保留条目；容量不足的条目原样留队。
- 坏条目（qty 非数值 / 非 dict / payload 非 dict）在入队统计与续发时**丢弃 + WARNING**，不崩溃、不按 0 低估占用。
- 相关统计键：`transport_queue_dropped`（累计丢弃石数）、`transport_queue_flushed`（累计续发石数）。

## 4. 边界

- 向下依赖 `foundation`（账本/状态）与 `content`（数据）；**不得反向导入** `workflows`/UI 或上层应用。
- 机制间协作经显式接口；不跨域读写私有结构。
- 读数是只读投影，**不得成为结算算法权威**。
- `ROAD_QUALITY` 当前为空（不臆造史料，见 `docs/游戏机制说明.md:206`）；真实路况接入前，
  可达性按几何/路网默认值计算。

## 5. 迁移状态

- **未迁移**：实现仍全部在 `core/transport.py`；本目录只有本 README。
- 迁移前置：先补/核对符号调用图（`transport.py` 被 settlement、trade、market、money_transport 等多处引用），
  再分批 `git mv`；**不得**在迁移中改运力公式或结算顺序。
- 参考：`docs/底层经济闭环与全息真账机制规范_2026-10-17.md`（交通在途/四仓位）、
  `specs/transport/`（可航性/下沉设计稿）。
