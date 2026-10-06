# 🔴 落地受阻记录：新局即建 `seats`（2026-10-05）

> 用户裁定「**继续**」后执行《州府级真账总批计划》**批次 3** 的第一步（新局即建 `seats`）。
> **功能成功，但全量回归失败 ⇒ 已回退。** 本文如实记录。

---

## 一、改动（已回退，补丁存 `_scratch/seats_init.patch`）

`core/game_state.py` `__init__` 末尾（**所有 POP 写入之后**）：

```python
self.seats_initialized: int = 0
self.seats_split_errors: list = []
from core.pop_bridge import split_pops_to_seats
for _route, _pdata in self.prefectures.items():
    self.seats_initialized += int(split_pops_to_seats(_pdata, _route) or 0)
```

**位置依据**：在兵额回填/识字率/财富注资/家产切片/隐户/农职位与丁口子池**之后** ——
避免「拆完又被路级写回」的分叉。

## 二、✅ 功能验证**成功**

```
seats_initialized   = 117
seats_split_errors = []      # **零失败**
departments_all     = {ok: True, seats_covered: 117}  entities = 234

京畿路|开封府  民间营造  owner=pop       craftsmen=255,191
京畿路|开封府  官有营造  owner=local_gov  craftsmen=1,875,525
```

⇒ **117 治所 × 2 部门 = 234 个州府级实体**，与 `prefecture_entity` 的 117 治所一致。

## 三、🔴 全量回归：**EXIT=1，15 失败**

### 3.1 属「**设计已变更**」的 2 项（可预期，需改测试）

| 测试 | 断言 |
|---|---|
| `test_pop_bridge_mirror.py::test_aggregate_is_none_when_not_sunk` | 断言新局 `aggregate()` 返回 `None`（**即「未下沉」）**|
| `test_pop_seat_split.py::test_aggregate_returns_none_when_not_sunk` | 同上 |

⇒ 🔴 **这两项直接编码了旧意图「新局不下沉」** —— 与本次裁定**正面冲突**。
⇒ 落地时**必须同步改这两项**（改断言为「已下沉」），否则无法通过。

### 3.2 🔴 **未查明**的 13 项（真实风险）

| 文件 | 失败数 |
|---|---|
| `test_officialdom.py` | **5** |
| `test_pop_identity.py` | 2 |
| `test_step_gap_fills.py` | 2 |
| `test_tuning_fixes.py` | 1 |
| `test_pop_flow_wealth.py` | 1 |
| （另 `test_officialdom` 内含轨迹测试）| |

⚠️ **未逐条诊断**（预算所限，已回退保树）。**猜测**（**未经证实，不作为结论**）：
新局下沉后**路级 `pops` 变为只读派生**，而既有部分代码/测试仍**期望路级可直写或聚合为 `None`**。

### 3.3 附带发现：**测试耗时约翻倍**

| 轮次 | 耗时 |
|---|---|
| 回退前（无 seats）| 约 5–6 分钟 |
| 下沉后（有 seats）| **约 12 分钟**（python CPU 598s）|

⇒ **性能是真实代价**：新局下沉后每次 POP 写入都过桥接到治所。
⇒ 落地时须评估性能预算（§6.1「测试规模/跑法变化」也需回填）。

## 四、当前状态

| 项 | 状态 |
|---|---|
| 工作树 | ✅ **干净**（HEAD = `1c7e43f924`，该提交全量 EXIT=0）|
| 补丁 | ✅ 保留于 `_scratch/seats_init.patch`（3,704 字节）|
| `construction_shadow` | ✅ 不受影响（`departments_all` 对无 `seats` 的旧档返回 `no_seats`，**行为未变**）|

## 五、🔴 落地前必须先做的事

| # | 事项 |
|---|---|
| 1 | **诊断 13 项失败**（尤其 `officialdom` 5 项）—— 判定是「代码需适配」还是「设计冲突」|
| 2 | **改写 2 项 `not_sunk` 测试**为「已下沉」口径 |
| 3 | 评估**性能翻倍**是否可接受，或需优化桥接 |
| 4 | 按结论决定：全量适配 / 分路分批下沉 / 暂缓 |

## 六、本文性质

**受阻记录 + 事实清单**，**未落代码**（已回退）。

最后更新：2026-10-05