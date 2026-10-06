# 🔴 甲方案批次 3 诊断结果：`seats` 下沉的**根因已查明**（2026-10-05）

> 用户裁定：「**不用在意旧档，这是开发阶段**」⇒ 解除迁移/兼容约束，重上批次 3。
> 本文记录**首次真正诊断**的结果（此前只看过失败**名字**，没看过**原因**）。

---

## 一、功能面**完全正常**

```
seats_initialized = 117   errors = []
route 京畿路 has seats = True
seat keys = ['京畿路|开封府', '京畿路|郑州', ...]
seat pops = ['兵', '农', '商人', '士绅', '官僚', '工匠']
农 subpools = [ding, goods, grain, hidden, kou, literacy, size, wealth,
              佃农, 富农, 欠税, 自耕农]
```

⇒ **拆分本身没问题**：117 治所、6 类 POP 齐全、农的 12 个子池齐全。

## 二、🔴 根因：**钱写在派生镜像上，真账收不到**

### 2.1 失败现象（实测）

```
test_pop_flow_wealth.py:63
  AssertionError: 钱流失衡：Σ … and 14808 = int(14808)
```

⇒ 是**钱账本失衡**，不是 POP 结构问题。

### 2.2 机制

`game_state.transfer_money` 的 `_write`：

```python
if _pop_add(self, pp, "wealth", _nw - int(pp.get("wealth", 0) or 0)) is None:
    pp["wealth"] = _nw          # ← 兜底**直写路级 pops**
```

路级 `pops` 下沉后是**只读派生镜像**（守卫维护）⇒ `_pop_add` 返回 `None`
⇒ **走进兜底分支** ⇒ 钱被写进**派生副本** ⇒
**治所真账 `seats[*]["pops"][*]["wealth"]` 从未收到** ⇒ **钱凭空消失**。

⇒ 这就是 **18 项失败的共同根因**（`officialdom` 10 · `pop_identity` 3 ·
`step_gap_fills` 2 · `tuning_fixes` 1 · `pop_flow_wealth` 1 · `not_sunk` 2）。

## 三、正确改法

```python
# 兜底分支**不得**直写路级 pops；应委派**桥接**（写入下沉州府）
if _pop_add(self, pp, "wealth", delta) is None:
    pp["wealth"] = _nw        # ❌ 写派生副本 → 钱丢
    # ✅ 应改为：走 pop_bridge / grain_bridge（传 state），使写入落到治所真账
```

⚠️ **注意**：这与 AGENTS.md §3-1 记的**同类漏网**完全一致 ——
`grain_bridge` 的函数都支持**可选 `state`**：**给了就委派桥接**，没给就沿用旧载体。
**`_write` 的兜底分支正是「没给 state」的等价物**。

## 四、影响面（修复需动的点）

| # | 项 | 难度 |
|---|---|---|
| 1 | `_write` 兜底改走桥接（**核心**）| 中 |
| 2 | 排查其余「直写路级 pops」的兜底分支 | 中 |
| 3 | 2 项 `not_sunk` 测试改断言（**旧意图已作废**，用户已明确）| 低 |
| 4 | 修复后重跑全量 + **钱账本恒等式断言** | 低 |

## 五、本轮状态

| 项 | 状态 |
|---|---|
| `seats` 下沉补丁 | ❌ **已回退**（保树绿）|
| **根因** | ✅ **已查明**（本文件）|
| 修复 | ⏸ 下一轮 |

最后更新：2026-10-05