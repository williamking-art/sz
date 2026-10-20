# -*- coding: utf-8 -*-
"""跨文件「逐字节相同函数体」守卫（2026-10-20，机制分区下的复用棘轮）。

用户问题：「代码按机制分区，但有些实现功能几乎一致，能否在分区下达成复用？」
答：能——但复用的单位是**语义不变量**，不是代码长相。本守卫只钉最硬的一类：
**两份函数体 AST 完全相等却放在两个文件里**（同一实现两个家）。

规则（棘轮，不是规约）：
- 现有 15 组 / 38 个函数（全部列在 `_BASELINE`）冻结；允许**消失**（归一完成），
  不允许**新增**；
- 新增报错时给出两文件 + 函数名，提示走三条正确通道之一：
  ① 抽到 `core/foundation/`（共享内核）②模板方法/数据表 ③注册/插件反转；
- 只扫 `game/**/*.py`，排除 node_modules/资产/构建产物；不 import game 模块、无第三方依赖。

背景与完整判定表见 `_dev_tools/game-docs/docs/机制分区与复用约定_2026-10-20.md`。
"""
from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_GAME = _REPO / "game"
_SKIP_DIRS = {"__pycache__", "node_modules", "assets", ".git", "out", "dist", "release",
              "vendor", ".venv"}

#: 冻结基线（2026-10-20 实测）：hash → 出现该实现的文件集。
#: 归一时从下表删除；**不要**为「新增重复」往这里加。
_BASELINE = {
    ("a87c31b463aba6d7", ("core/domains/population/settlement_hidden.py", "core/settlement_imperial.py")),
    ("eef8b368b4e5d328", ("core/domains/politics/settlement_imperial.py", "core/settlement_imperial.py")),
    ("802ec6582dc7819e", ("core/domains/politics/settlement_imperial.py", "core/settlement_imperial.py")),
    ("144e9c316f844f25", ("core/domains/population/settlement_hidden.py", "core/settlement_imperial.py")),
    ("08d3620cb794591c", ("core/domains/politics/settlement_imperial.py", "core/settlement_imperial.py")),
    ("358360bc30045c8e", ("core/domains/politics/settlement_imperial.py", "core/settlement_imperial.py")),
    ("80982f10c4855f32", ("core/domains/politics/settlement_imperial.py", "core/settlement_imperial.py")),
    ("9f9649fde2855c93", ("core/construction_cost.py", "core/domains/administration/minister_agent.py",
                          "core/domains/economy/demand.py", "core/domains/economy/market.py",
                          "core/market_price.py", "core/population_readout.py")),
    ("7ac01c887eb34b5e", ("core/faction_ban.py", "core/impeachment.py")),
    ("6bd3bc8b526539d1", ("core/domains/administration/imperial_exam.py",
                          "core/domains/administration/official_appraisal.py")),
    ("e6c7ebc5be219911", ("core/civil_building.py", "core/domains/production/settlement_agri.py")),
    ("5d654c1c059f6e86", ("core/faction_distribution.py", "core/permission_model.py")),
    ("ad65adede7c5d51a", ("core/party_ban_order.py", "core/personnel_order.py")),
    ("df219f7ede9572cd", ("core/domains/economy/canal_bridge.py",
                          "core/foundation/ledger/building_bridge.py",
                          "core/foundation/ledger/local_treasury_bridge.py",
                          "core/foundation/ledger/storage_bridge.py")),
    ("d3e6bde83e1c53dc", ("core/domains/economy/canal_bridge.py",
                          "core/foundation/ledger/building_bridge.py",
                          "core/foundation/ledger/resource_stock_bridge.py",
                          "core/foundation/ledger/storage_bridge.py")),
}


def _iter_py():
    for dirpath, dirnames, filenames in os.walk(_GAME):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                yield Path(dirpath) / fn


def _body_hash(node) -> str:
    body = ast.Module(body=node.body, type_ignores=[])
    dump = ast.dump(body, annotate_fields=True, include_attributes=False)
    return hashlib.sha1(dump.encode("utf-8")).hexdigest()[:16]


def _scan() -> dict:
    """→ {(hash, tuple(sorted(files))): [函数名, ...]}，仅跨文件重复。"""
    groups: dict = {}
    for path in _iter_py():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = path.relative_to(_GAME).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if len(node.body) < 3:      # 太短的三行样板不算
                continue
            h = _body_hash(node)
            groups.setdefault(h, []).append((rel, node.name))

    out = {}
    for h, rows in groups.items():
        files = sorted({r[0] for r in rows})
        if len(files) < 2:
            continue
        out[(h, tuple(files))] = sorted({r[1] for r in rows})
    return out


def test_no_new_cross_file_duplicate_bodies():
    found = _scan()
    new = {k: v for k, v in found.items() if k not in _BASELINE}
    assert not new, (
        "新增跨文件重复实现（同一函数体出现在两个文件）：\n"
        + "\n".join(f"  {names} @ {files}" for (h, files), names in new.items())
        + "\n请走：①抽到 core/foundation（共享内核）②模板方法/数据表 ③注册/插件反转；"
          "不要靠横向 import 兄弟域来复用。"
    )


def test_baseline_entries_are_still_real_or_removed():
    """基线只许变小：若某组已归一，提醒维护者删表（防止表腐化成永久豁免）。"""
    import warnings

    found = _scan()
    stale = [k for k in _BASELINE if k not in found]
    if stale:
        warnings.warn(
            "重复守卫基线里有 %d 组已消失（归一完成）：请从 _BASELINE 删除，"
            "避免守卫退化成永久豁免。示例：%r" % (len(stale), stale[:3]),
            stacklevel=2,
        )
