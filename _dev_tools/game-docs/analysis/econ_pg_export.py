# -*- coding: utf-8 -*-
"""经济指标月度导出（供落 PostgreSQL 做 SQL 对账/趋势分析）。

设计原则：
- **只读游戏、只写 JSON**：不修改任何游戏代码，也不含任何数据库凭据；
  入库由外部步骤完成（见 docs/开发服务器与回归测试说明.md §8.9）。
- 推进方式与项目测试**完全同源**：`core.settlement.run_monthly_settlement(state, seed_offset)`
  + 每月注入 `state._economy_ai`（照 `_dev_tools/game-dev/tests/test_officialdom.py:41-45` 的 `_run`）。
  ⚠️ 反例（本脚本初版踩过）：用 `core.commands.advance_month` + `settle_turn` 组合**不会推进状态** ——
  240 行输出逐行完全相同（年份恒 1101-1），且 `residual` 等字段全空。判定"回放是否真的在跑"
  的第一条准则：**首行与末行必须不同**。
- 货币侧取 `core/money.py` 的 `snapshot()`（账户 + M0/M1/M2/M3 口径）
  与 `state.money_audit`（月度对账残差），财政侧取 `finance_readout()`。

用法（用本机 venv 的 python）：
    cd <repo>/_dev_tools/game-docs/analysis
    python econ_pg_export.py            # 默认 240 月
    python econ_pg_export.py 60         # 指定月数
输出：
    econ_monthly.json   {"meta": {...}, "rows": [每月一行, ...]}
"""
import sys
import os
import json
import random

_HERE = os.path.dirname(os.path.abspath(__file__))

# 定位游戏根（与 tests/ 相同的相对层级：../../.. + game）
_GAME_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

# 历史遗留：core/settlement.py 缺 from typing import Any，不改源码，注入 builtins 绕过
import builtins  # noqa: E402
if not hasattr(builtins, "Any"):
    builtins.Any = object()

from core.game_state import GameState                        # noqa: E402
from core.settlement import run_monthly_settlement           # noqa: E402
from core import money as money_mod                          # noqa: E402

# 与 test_officialdom.py 同源的确定性经济侧 AI 桩
_ECO = {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中",
        "窖银": "小", "城市化": "中", "回乡": "无", "科举": "中"}

SEED = 7


def _num(v, default=None):
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _snapshot_row(i, state, err, log_tail):
    """每月一行：货币口径 + 财政 + 民生 + 对账残差。"""
    row = {
        "idx": i,
        "turn": getattr(state, "turn", None),
        "year": getattr(state, "year", None),
        "month": getattr(state, "month", None),
    }
    if err:
        row["error"] = err[:300]
    if log_tail:
        row["log_tail"] = " | ".join(log_tail)[:500]

    # --- 货币账户与 M 口径 ---
    try:
        snap = money_mod.snapshot(state) or {}
    except Exception as exc:
        snap = {}
        row["snapshot_error"] = f"{type(exc).__name__}: {exc}"
    for k in (
        "pop_wealth", "estate_wealth", "treasury", "imperial", "local_treasury",
        "payraise_budget", "invest_principal", "hoard", "estate_hoard",
        "melt_pool", "bank_reserve", "silver_stock",
        "M_ALL", "m0", "m1_full", "m1_working", "m2", "m3",
        "jiaozi_eff", "copper_share",
    ):
        if k in snap:
            row[k] = _num(snap.get(k))

    # --- 月度对账（残差）---
    audit = getattr(state, "money_audit", None) or {}
    recent = audit.get("recent") or []
    if recent:
        last = recent[-1] or {}
        row["residual"] = _num(last.get("residual"))
        row["d_mall"] = _num(last.get("d_mall"))
        row["external_in"] = _num(last.get("external_in"))
        row["burned"] = _num(last.get("burned"))
    row["cum_residual"] = _num(audit.get("cum_residual"))

    # --- 财政读数 ---
    try:
        fin = state.finance_readout() or {}
    except Exception as exc:
        fin = {}
        row["finance_error"] = f"{type(exc).__name__}: {exc}"
    for k in (
        "monthly_in", "expenditure", "army_cash", "official_cash", "clerk_cash",
        "corruption_ded", "cash_out", "sui_gong", "total_out", "net",
        "imperial_treasury", "granary", "granary_cap", "rate",
    ):
        if k in fin:
            row[k] = _num(fin.get(k))

    # --- 民生 / 物价 / 存量（兜底直取 GameState）---
    row["treasury"] = _num(getattr(state, "treasury", None), row.get("treasury"))
    row["imperial_treasury"] = _num(getattr(state, "imperial_treasury", None),
                                    row.get("imperial_treasury"))
    row["granary"] = _num(getattr(state, "granary", None), row.get("granary"))
    row["grain_price"] = _num(getattr(state, "grain_price", None))
    row["price_level"] = _num(getattr(state, "price_level", None))
    row["coin_shortage"] = _num(getattr(state, "coin_shortage", None))
    row["money_supply"] = _num(getattr(state, "money_supply", None))
    row["population"] = _num(getattr(state, "population", None))
    row["satisfaction"] = _num(getattr(state, "population_satisfaction", None))
    ref = getattr(state, "refugees", None)
    if ref is None:
        ref = getattr(state, "refugee_count", None)
    row["refugees"] = _num(ref)
    jz = getattr(state, "jiaozi", None)
    row["jiaozi_issued"] = _num(jz.get("issued")) if isinstance(jz, dict) else None
    return row


def main():
    months = 240
    if len(sys.argv) > 1:
        try:
            months = int(sys.argv[1])
        except ValueError:
            pass

    random.seed(2026)
    state = GameState("史实")

    rows = []
    for i in range(months):
        state._economy_ai = _ECO
        err = None
        log_tail = []
        try:
            log = run_monthly_settlement(state, seed_offset=SEED)
            for line in (log or []):
                if isinstance(line, str) and any(
                        k in line for k in ("[财政]", "[民生]", "[岁币]", "[军粮]")):
                    log_tail.append(line)
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            print(f"[WARN] 第 {i + 1} 月结算异常：{err}", file=sys.stderr)
        row = _snapshot_row(i, state, err, log_tail[-4:])
        rows.append(row)
        if (i + 1) % 12 == 0:
            print(f"  ... {i + 1}/{months} 月  {row.get('year')}-{row.get('month')}"
                  f"  国库={row.get('treasury')}  太仓={row.get('granary')}"
                  f"  M2={row.get('m2')}  残差={row.get('residual')}")

    # 自检：回放是否真的推进（首末行必须不同）
    moved = bool(rows) and (rows[0] != rows[-1])
    print(f"[SELF-CHECK] 首末行是否不同（回放确实推进）= {moved}")

    out = {
        "meta": {
            "months": months,
            "seed": 2026,
            "seed_offset": SEED,
            "mode": "史实",
            "generated_by": "econ_pg_export.py",
            "pipeline": "core.settlement.run_monthly_settlement + state._economy_ai",
            "advanced": moved,
            "start_year": rows[0]["year"] if rows else None,
            "end_year": rows[-1]["year"] if rows else None,
        },
        "rows": rows,
    }
    path = os.path.join(_HERE, "econ_monthly.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"已写出 {path}（{len(rows)} 行，advanced={moved}）")


if __name__ == "__main__":
    main()
