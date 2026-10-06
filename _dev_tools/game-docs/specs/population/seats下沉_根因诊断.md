# 🔴 甲方案批次 3：**确切根因**（已复现到断言行）

---

## 一、复现的失败断言

```
def test_retirement_keeps_official_subpool_invariants():
    …
    g = p["pops"]["官僚"]
    assert int(g["size"]) == int(g["officials"]) + int(g["clerks"]), f"{name}: 官员子池不符"
E   AssertionError: 京畿路: 官员子池不符
E   assert 16944 == (1851 + 14808)
```

测试自述：「**官员**只改「在地 `size`」，不随迁转；由 `move_pop_people` 同步双改
⇒ **任一边漏改即失败**」。

## 二、🔴 根因：**身份子池不在 `SPLIT_FIELDS`**

```
size       16944   ← 在 SPLIT_FIELDS ⇒ 下沉治所并聚合回来
officials   1851   ← **不在** SPLIT_FIELDS ⇒ 留路级
clerks     14808   ← **不在** SPLIT_FIELDS ⇒ 留路级
```

⇒ 下沉后 `size` 与 `officials`/`clerks` **分叉**：
前者由桥接维护（Σ 治所），后者仍是路级单值 ⇒ **恒等式不成立**。

> ⚠️ **`AGENTS.md §3-1` 早已记录此事**（属已知未完成项）：
> 「`officials`/`clerks`/`on_post`/`waiting`/`sinecure`（身份子池）、
> `clan`（宗族）仍**不在 `SPLIT_FIELDS`**」。
⇒ **本次是它第一次被具体失败暴露出来**。

## 三、排除项（**已实测排除**，不是原因）

| 项 | 实测 | 结论 |
|---|---|---|
| `split_pops_to_seats` 本身 | `seats=117`、`errors=[]`、6 类 POP 齐全、农 12 子池齐全 | ✅ **正常** |
| `pop_bridge.pop_obj_add` 桥接 | `+100 ⇒ 570220`；`Σ seats = 570220 = 路级` | ✅ **正常、且守恒** |
| `transfer_money._write` 兜底 | **未触发**（桥接未返回 None）| ❌ **不是根因** |

⇒ 上一版诊断文档把 `_write` 兜底列为根因，**该判断已被实测推翻**，此处更正。

## 四、正确修法

| # | 项 | 说明 |
|---|---|---|
| 1 | 把 `officials`/`clerks`/`on_post`/`waiting`/`sinecure` 加入 **`SPLIT_FIELDS`** | 它们是**计数**，可求和（同 `size`），**不是** `MEAN_FIELDS` 的比率 |
| 2 | `clan`（宗族）单独判定 | 宗族是**互斥归属**，可能需走 `split_affiliation` 通道而非直接求和 |
| 3 | 2 项 `not_sunk` 测试改断言 | 旧意图「新局不下沉」已作废（用户明确「开发阶段，不必在意旧档」）|
| 4 | 修复后跑**钱账本恒等式** + 全量 | 见 §五 |

## 五、预期影响

`SPLIT_FIELDS` 是**求和拆分**；身份子池若按同一权重拆分，
则治所级恒等式 `Σ治所.size == Σ治所.officials + Σ治所.clerks` 成立，
聚合回路级亦成立 ⇒ `officialdom` 10 项与 `pop_identity` 3 项应一并转绿。

⚠️ **须逐项验证**：身份子池与 `size` 的**权重是否同一套**（治所人口权重），
若 `move_pop_people` 迁转的是**具体治所**而非按比例，则需**按迁转路径**同步拆分。

## 六、本文性质

**根因诊断（已复现到断言行）**，**未改代码**（补丁已回退）。

最后更新：2026-10-05