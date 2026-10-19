# -*- coding: utf-8 -*-
"""质量放行门 · 资源桶搬运守恒（B-2d）。

对应设计：`B2_守卫与质量放行门_设计与取证_2026-10-12.md` §4 B-2d（原称"补 holding_report 单向性"）。

## 取证结论（2026-10-18 实测，与设计稿旧描述不同 —— 已更正）

1. **单向性缺陷已被 B-5（2026-10-17）修掉**：`holding_report` 现在是
   `gap = stock - held` 带符号，非零即 `ok=False`（设计稿那段是旧描述）。
2. **但它不能当"任意时点"的判据**：实测第 2 个月起 gap 变负（商人 > 国库，最大 -1.3M）。
   读码确认 **不是配货泄漏**：`supply_goods_to_seats` 只在 `stock > held` 时补
   `need = stock - held`，故 `put ≤ need ≤ stock`，`max(0, cur-put)` 永不夹断；
   差额来自**其它路径**（生产入库、POP 间贸易）使商人持有增加，属预期。
3. 真正的守恒式是**搬运守恒**：`Σ商人 + stock` 在配货前后**不变**
   （实测 丝/麻/铁 有搬运，总量差恒 0）。

因此本门判"时点 + 守恒"，不判"任意时点相等"。
"""
from __future__ import annotations

import ast
import os
import sys

import pytest
from pathlib import Path

GAME_ROOT = Path(__file__).resolve().parents[3] / "game"
sys.path.insert(0, str(GAME_ROOT))

#: 允许写 `resources[dim]["stock"]` 的文件（棘轮：新增文件必须评审）
import pytest


@pytest.fixture(autouse=True)
def _closed_economy(monkeypatch):
    """本门测**官仓配货**（封闭经济）；外贸/商人投资各有自己的门，这里显式关掉。

    2026-10-19：两个行为开关打开后，外销会消耗商人货 ⇒ 配货门因无货可配而空转。
    隔离被测单元（配货守恒），而不是放宽断言。
    """
    import content.data_constants as dc
    monkeypatch.setattr(dc, "FOREIGN_TRADE_LEGS", 0)
    monkeypatch.setattr(dc, "MERCHANT_INVEST_ENABLED", 0)

ALLOWED_STOCK_WRITERS = {
    "core/material_market.py",
    "core/settlement_econ.py",
    "core/settlement_finance.py",
    "core/domains/economy/settlement_econ_helpers.py",
    "core/domains/production/farm_procurement.py",
    "core/domains/production/production_chain.py",
    "core/foundation/ledger/material_holding.py",
    "core/foundation/ledger/resource_stock_bridge.py",
}

SKIP_DIRS = {"node_modules", "__pycache__", ".venv", ".git"}


def _stock_writes():
    """AST：所有赋值目标链首键为 'stock' 的位置。"""
    found = []

    def chain_keys(node):
        keys, cur = [], node
        while isinstance(cur, ast.Subscript):
            if isinstance(cur.slice, ast.Constant) and isinstance(cur.slice.value, str):
                keys.append(cur.slice.value)
            cur = cur.value
        return keys

    for base, dirs, files in os.walk(GAME_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = Path(base) / fn
            rel = p.relative_to(GAME_ROOT).as_posix()
            try:
                tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                targets = []
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, ast.AugAssign):
                    targets = [node.target]
                for t in targets:
                    keys = chain_keys(t)
                    if keys and keys[0] == "stock":
                        found.append((rel, node.lineno))
    return found


def test_stock_writer_registry_is_ratchet():
    """棘轮：新增"写库存"的文件必须评审（避免又出现一条不改国库的增物路径）。"""
    sites = _stock_writes()
    assert sites, "没有扫到任何 stock 写点 ⇒ 扫描失效（不是干净）"
    unknown = sorted({f for f, _ in sites} - ALLOWED_STOCK_WRITERS)
    assert not unknown, f"出现未登记的库存写点文件：{unknown}；明细：{[s for s in sites if s[0] in unknown][:5]}"


def _totals(state, dims):
    from core.foundation.ledger.material_holding import holding_report

    rep = holding_report(state)
    return {d: int(rep["dims"][d]["merchant_total"]) + int(rep["dims"][d]["stock_total"])
            for d in dims if d in rep["dims"]}


def test_allocation_preserves_total_amount():
    """真正的搬运守恒：配货前后 Σ(商人持有 + 国库库存) 必须不变。"""
    from core.commands import new_game
    from content.data import GOODS_DIMS
    from core.foundation.ledger.material_holding import holding_report, supply_goods_to_seats

    from core.commands import settle_local

    state = new_game()
    for _ in range(2):                       # 新局库存为 0，需先跑出产能才有可搬运的货
        settle_local(state)
    dims = [d for d in GOODS_DIMS if d in holding_report(state)["dims"]] or list(GOODS_DIMS)[:8]
    before = _totals(state, dims)
    moved = supply_goods_to_seats(state, dims=dims)
    after = _totals(state, dims)

    assert moved and any(v > 0 for v in moved.values()), f"本次没有任何搬运 ⇒ 门空转：{moved}"
    drift = {d: after[d] - before.get(d, 0) for d in after if after[d] != before.get(d, 0)}
    assert not drift, f"配货后总量发生变化（凭空增物/丢失）：{drift}"


@pytest.mark.xfail(strict=True, reason=(
    "已知口径问题（B-2d 取证 §候选缺陷）：supply_goods_to_seats 的『配货目标』与『配货来源』是同一变量 "
    "stock —— need=stock-held 先补足、又把 need 从 stock 扣掉，配货后 held 与 stock 互换，"
    "故 stock>0 时 holding_report 恒有 gap=-need（实测 铁 -1、木/石 可达 -1.3M）。"
    "修复后本用例应转为绿，届时请同步更正 docs 与 tasks。"))
def test_holding_report_closed_right_after_allocation():
    """（xfail）配货刚结束时商人持有应与国库库存闭合。"""
    from core.commands import new_game
    from content.data import GOODS_DIMS
    from core.foundation.ledger.material_holding import holding_report, supply_goods_to_seats

    from core.commands import settle_local

    state = new_game()
    for _ in range(2):                       # 同上：先跑出库存
        settle_local(state)
    dims = list(GOODS_DIMS)[:24]
    moved = supply_goods_to_seats(state, dims=dims)
    assert moved and any(v > 0 for v in moved.values()), f"空转：{moved}"

    rep = holding_report(state)
    # holding_report 只覆盖 MATERIAL_DIMS；搬运了但它不统计的维度不参与本断言
    bad = {d: rep["dims"][d] for d in moved
           if moved[d] and d in rep["dims"] and rep["dims"][d]["gap"] != 0}
    assert not bad, f"配货后 holding_report 未闭合（搬了货但账不平）：{bad}"


def test_allocation_swaps_held_and_stock_current_behaviour():
    """记录**当前**行为：配货后 `held_after == stock_before` 且 `stock_after == held_before`（互换）。

    这是上面 xfail 那条的成因，写成正例是为了"改动必被看见"：
    若有人把配货口径修成"真的搬运"，本用例会红，提示同批更新文档与 xfail。
    """
    from core.commands import new_game, settle_local
    from content.data import GOODS_DIMS
    from core.foundation.ledger.material_holding import holding_report, supply_goods_to_seats

    state = new_game()
    for _ in range(2):
        settle_local(state)
    rep0 = holding_report(state)
    dims = [d for d in GOODS_DIMS if d in rep0["dims"]]
    moved = supply_goods_to_seats(state, dims=dims)
    rep1 = holding_report(state)
    hit = [d for d in moved if moved[d] and d in rep1["dims"]]
    assert hit, f"没有实际搬运的维度 ⇒ 空转：{moved}"
    for d in hit:
        before_stock = int(rep0["dims"][d]["stock_total"])
        before_held = int(rep0["dims"][d]["merchant_total"])
        after_stock = int(rep1["dims"][d]["stock_total"])
        after_held = int(rep1["dims"][d]["merchant_total"])
        assert (after_stock, after_held) == (before_held, before_stock), (
            f"{d} 的互换关系不成立（若已修口径，请更新本用例与 xfail）："
            f"before=({before_stock},{before_held}) after=({after_stock},{after_held})"
        )


def test_stock_never_negative_over_year():
    """12 个月里任何维度的库存都不得为负（负库存会掩盖凭空增物）。"""
    from core.commands import new_game, settle_local

    state = new_game()
    for _ in range(12):
        settle_local(state)
    res = getattr(state, "resources", {}) or {}
    bad = {d: int((v or {}).get("stock", 0) or 0) for d, v in res.items()
           if isinstance(v, dict) and int(v.get("stock", 0) or 0) < 0}
    assert not bad, f"出现负库存：{bad}"