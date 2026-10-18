# -*- coding: utf-8 -*-
"""质量放行门 · 商品单点访问层（B-2c）。

对应设计：`B2_守卫与质量放行门_设计与取证_2026-10-12.md` §4 B-2c。

门要回答的问题：**"还有没有绕过 `material_holding` 单点访问层、把商品当算术量（或直写镜像）的地方"**。

## 取证结论（2026-10-18 实测）

静态：`goods` 直写共 16 处，全部落在可解释的范围：

| 范围 | 理由 |
|---|---|
| `material_holding.py` / `pop_bridge.py` | 单点访问层与账本桥**本体** |
| `production_chain.py::settle_production_chain` | 仅补容器，随后走 `pop_goods_add`（M43/M44 已修） |
| `save_load.py::_load_with_data` | 旧档兼容补字段 |
| `settlement_econ.py::_ext_econ_phases` | **外邦**（辽/西夏/大理）省域 POP，**没有治所下沉层**，故无桥可走 |
| `settlement_granary.py::_settle_granary` | **未下沉兜底**：先调 `pop_goods_decay` 桥，桥返回空才走旧写法（M43 注记） |

运行时：3 个月后 **822 个 goods 字典**，全为扁平数值键；**州府桶 0 个**、非法值 0 个。
裸遍历（`for k in goods` / `.keys()`）**0 处**。

因此本门是**棘轮**：不允许出现"新的文件/新的函数"直写 goods；允许范围内按文件+函数登记，抗行号漂移。
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

GAME_ROOT = Path(__file__).resolve().parents[3] / "game"
sys.path.insert(0, str(GAME_ROOT))

#: 允许直写 goods 的**文件**（层本体/桥/容器初始化/旧档兼容）
ALLOWED_FILES = {
    "core/foundation/ledger/material_holding.py",
    "core/foundation/ledger/pop_bridge.py",
    "core/domains/production/production_chain.py",
    "core/save_load.py",
}

#: 允许直写 goods 的**函数级**例外（文件, 函数名）→ 理由
ALLOWED_SCOPES = {
    ("core/settlement_econ.py", "_ext_econ_phases"):
        "外邦省域 POP 无治所下沉层，无桥可走；非宋境账本",
    ("core/settlement_granary.py", "_settle_granary"):
        "未下沉兜底：先走 pop_goods_decay 桥，桥返回空才走旧写法",
}

SKIP_DIRS = {"node_modules", "__pycache__", ".venv", ".git"}


def _goods_writes(tree) -> list[tuple[int, str]]:
    """→ [(行号, 所属函数名)]：赋值目标链里出现 ['goods'] 即算直写。"""
    fns = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]

    def enclosing(line: int) -> str:
        hit = [f for f in fns if f.lineno <= line <= (f.end_lineno or f.lineno)]
        hit.sort(key=lambda f: -f.lineno)
        return hit[0].name if hit else "<module>"

    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        hit = False
        for t in node.targets:
            if isinstance(t, ast.Attribute) and t.attr == "goods":
                hit = True
            cur = t
            while isinstance(cur, ast.Subscript):
                if isinstance(cur.slice, ast.Constant) and cur.slice.value == "goods":
                    hit = True
                    break
                cur = cur.value
        if hit:
            out.append((node.lineno, enclosing(node.lineno)))
    return out


def _goods_iterations(tree) -> list[int]:
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        it = node.iter
        hit = False
        if isinstance(it, ast.Subscript) and isinstance(it.slice, ast.Constant) and it.slice.value == "goods":
            hit = True
        elif isinstance(it, ast.Attribute) and it.attr == "goods":
            hit = True
        elif isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) \
                and it.func.attr in ("get", "keys", "items", "values"):
            hit = any(isinstance(a, ast.Constant) and a.value == "goods" for a in it.args)
        if hit:
            out.append(node.lineno)
    return out


def _scan():
    writes, iterates = [], []
    for base, dirs, files in os.walk(GAME_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = Path(base) / fn
            rel = p.relative_to(GAME_ROOT).as_posix()
            try:
                tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"), filename=str(p))
            except SyntaxError:
                continue
            for line, scope in _goods_writes(tree):
                writes.append((rel, scope, line))
            for line in _goods_iterations(tree):
                iterates.append((rel, line))
    return writes, iterates


def test_scanner_detects_synthetic_violation():
    """反例（注入即红）：判据必须能抓出两种写法，否则"0 违规"是假绿。"""
    tree = ast.parse(
        "def f(p):\n"
        "    p['goods'] = {}\n"
        "    p['goods']['米'] = 1\n"
        "    for k in p['goods']:\n"
        "        pass\n"
    )
    writes = _goods_writes(tree)
    iters = _goods_iterations(tree)
    assert len(writes) >= 2, f"未识别直写（含链式写法）：{writes}"
    assert iters, "未识别裸遍历"


def test_no_unregistered_goods_writers():
    """棘轮：直写 goods 只允许既有文件/函数，新增即红（必须评审并登记理由）。"""
    writes, _ = _scan()
    bad = [w for w in writes if not (w[0] in ALLOWED_FILES or (w[0], w[1]) in ALLOWED_SCOPES)]
    assert not bad, (
        "出现未登记的 goods 直写（应改走 material_holding 单点访问层）："
        f"{bad[:8]}"
    )


def test_allowed_scopes_are_not_stale():
    """例外登记必须仍然命中真实代码（防"登记了但代码已改"的假豁免）。"""
    writes, _ = _scan()
    present = {(f, s) for f, s, _ in writes}
    stale = sorted(k for k in ALLOWED_SCOPES if k not in present)
    assert not stale, f"例外登记已失效（代码不再直写或函数已改名）：{stale}"


def test_no_bare_iteration_over_goods():
    """禁止裸遍历 goods（会把州府桶当商品维参与算术；唯一安全判据是 commodity_dims）。"""
    _, iterates = _scan()
    assert not iterates, f"发现裸遍历 goods 的写法：{iterates[:8]}"


def test_goods_values_are_flat_numbers_or_seat_buckets():
    """运行时：goods 的值只能是数值（商品维）或 dict（州府桶）；桶键必须是真实治所。"""
    from core.commands import new_game, settle_local

    state = new_game()
    for _ in range(3):
        settle_local(state)

    checked = buckets = 0
    problems = []
    for route, pdata in (state.prefectures or {}).items():
        seats = (pdata or {}).get("seats") or {}
        seat_ids = set(seats)
        pools = []
        for sip, srow in seats.items():
            for cls, row in (((srow or {}).get("pops")) or {}).items():
                if isinstance(row, dict):
                    pools.append((f"seat:{sip}/{cls}", row.get("goods"), None))
        for cls, row in (((pdata or {}).get("pops")) or {}).items():
            if isinstance(row, dict):
                pools.append((f"route:{route}/{cls}", row.get("goods"), seat_ids))
        for ctx, goods, allowed_bucket_keys in pools:
            if not isinstance(goods, dict):
                continue
            checked += 1
            for k, v in goods.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    continue
                if isinstance(v, dict):
                    buckets += 1
                    if allowed_bucket_keys is not None and k not in allowed_bucket_keys:
                        problems.append((ctx, k, "桶键不是本路治所"))
                    continue
                problems.append((ctx, k, f"非法值 {type(v).__name__}"))
    assert checked > 0, "没有检查到 goods 字典，门是空转"
    assert not problems, f"goods 出现非法形态（会把桶/非法值当商品维）：{problems[:6]}"


def test_commodity_dims_really_excludes_buckets():
    """判据本身非空转：州府桶（dict 值）与布尔值都不得被认成商品维。"""
    from core.domains.economy.material_trade_ops import commodity_dims

    goods = {"米": 3, "盐": 7.5, "某路|某州": {"米": 2}, "坏值": True}
    dims = commodity_dims(goods)
    assert "米" in dims and "盐" in dims
    assert "某路|某州" not in dims, "州府桶被当成了商品维"
    assert "坏值" not in dims, "布尔值不得作为商品维"
