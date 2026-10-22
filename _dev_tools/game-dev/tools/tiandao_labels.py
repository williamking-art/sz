# -*- coding: utf-8 -*-
"""回测标签生成器（**离线工具**，2026-10-22）。

为什么是工具而不是 `core/ai` 模块
---------------------------------
它要驱动月结算（`core.settlement`）、建新局/读档（`core.commands` / `application.load_game`），
而 `core/ai` **不得反向依赖**这些层（`test_architecture_import_guard` 的 R2/R3，且明确要求
"现在就该改代码，不要往 _FROZEN_UPLINK 加行"）。所以：判定与度量的**纯逻辑**留在
`game/core/ai/tiandao_labels.py`，本文件只做**接线 + CLI**。

用法（在 `game/` 目录，或把 `game/` 放进 PYTHONPATH）::

    python _dev_tools/game-dev/tools/tiandao_labels.py --months 12 --out labels.json
    python _dev_tools/game-dev/tools/tiandao_labels.py --save <save.json> --months 6 --json

产出直接喂回测器::

    python -m core.ai.tiandao_backtest <save.json> --labels labels.json

⚠️ 是**代理真值**（"事后哪种做法让国计民生更好"）：能度量校准与排序，不证明因果；
覆盖率天然有限（互有胜负的月份不出标签），回测器的 `label_coverage` 会如实报。
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

# 允许从仓库任意目录直接跑：把 game/ 加进搜索路径
_GAME = Path(__file__).resolve().parents[3] / "game"
if str(_GAME) not in sys.path:
    sys.path.insert(0, str(_GAME))

from core.ai.tiandao_labels import (  # noqa: E402
    METRIC_NAMES, LabelError, extract_labels, frozen_observe,
)

log = logging.getLogger(__name__)

DEFAULT_SEED = 20261021
DEFAULT_MONTHS = 12


def run_month(state: Any, record: Mapping[str, Any], seed: int) -> Any:
    """冻结观测、固定种子，推进一个月（供 `extract_labels` 注入）。"""
    from core.settlement import run_monthly_settlement

    state._tiandao_observe = dict(record)
    random.seed(seed)
    with frozen_observe():
        run_monthly_settlement(state)
    return state


def observe_monthly(state: Any) -> Mapping[str, Any]:
    """本月自然观测副本（与游戏内月结 Step 0 同源）。"""
    from core.ai.tiandao_facade import TianDaoFacade

    return TianDaoFacade.observe_monthly(state)


def make_state(save_path: Optional[str] = None):
    """造一局新游戏，或从存档读回。"""
    if save_path:
        from application.load_game import load_game

        state = load_game(save_path)
        if state is None:
            raise LabelError("读档失败：%s" % save_path)
        return state
    from core.commands import new_game

    return new_game("史实")


def build_labels(months: int = DEFAULT_MONTHS, *, save_path: Optional[str] = None,
                 seed: int = DEFAULT_SEED,
                 objectives: Optional[Sequence[str]] = None):
    """生成标签（`extract_labels` 的接线封装）。"""
    return extract_labels(
        months,
        make_state=lambda: make_state(save_path),
        observe_monthly=observe_monthly,
        run_month=run_month,
        seed=seed,
        objectives=objectives,
        source=save_path or "new_game('史实')",
    )


def _harden_stdio() -> None:
    """Windows 管道下 cp936 遇 `⇒`/`≥` 会 UnicodeEncodeError（实测）——统一切 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: Optional[Sequence[str]] = None) -> int:
    _harden_stdio()
    parser = argparse.ArgumentParser(
        prog="tiandao_labels.py",
        description="反事实回放生成回测标签（帕累托支配；离线工具，不进结算链）")
    parser.add_argument("--months", type=int, default=DEFAULT_MONTHS, help="推进月数（默认 12）")
    parser.add_argument("--save", default=None, help="从存档起算（默认 new_game）")
    parser.add_argument("--out", default=None, help="标签写到此 JSON（缺省只打印摘要）")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG 种子")
    parser.add_argument("--json", action="store_true", help="摘要以 JSON 打印")
    args = parser.parse_args(argv)

    try:
        result = build_labels(args.months, save_path=args.save, seed=args.seed)
    except LabelError as exc:
        print("标签生成失败：%s" % exc, file=sys.stderr)
        return 2
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("已写出 %d 条标签 → %s" % (len(result["labels"]), args.out))
    if args.json:
        print(json.dumps(result["meta"], ensure_ascii=False, indent=2))
    else:
        by_obj = {}
        for row in result["labels"]:
            by_obj[row["objective"]] = by_obj.get(row["objective"], 0) + 1
        print("标签 %d 条 / 跳过 %d 条（%d 个月）"
              % (len(result["labels"]), result["meta"]["skipped_count"], args.months))
        for obj in sorted(by_obj):
            print("  %-22s %d" % (obj, by_obj[obj]))
        for obj in sorted({s["objective"] for s in result["meta"]["skipped"]}):
            print("  （跳过）%-16s %s" % (obj, next(
                s["reason"] for s in result["meta"]["skipped"] if s["objective"] == obj)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
