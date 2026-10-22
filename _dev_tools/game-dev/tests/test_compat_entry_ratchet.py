# -*- coding: utf-8 -*-
"""兼容入口**棘轮**（C4，Jev A 0.828）。

背景：迁移期在 `game/core/` 留了一批「薄转发桩」（旧路径 → 新位置），
`decisions/MIG-COMPAT-RETENTION.json` 裁定 **A=保留到「旧路径 import 归零 + 至少一个大版本发行」+ 加棘轮**。

实测事实（2026-10-22 本机）：
- `game/` 内部对这批桩的 import **已经是 0**；
- 仓库内仍有 `_scratch/*.py`、`dbg*.py` 等**开发脚本**引用它们（不随发行版分发）；
⇒ 本棘轮只锁 **game/ 内部**（发行物）的引用数与桩数：**只减不增**。
  删除窗口 = 下一个大版本发行（本次发行仍保留）。

纪律：新增兼容入口/新增旧路径引用 ⇒ 必须让本测试变红，先问 Jev 再调基线。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]        # tests → game-dev → _dev_tools → sz
GAME = REPO / "game"
BASELINE = Path(__file__).resolve().parent / "testdata" / "compat_entry_baseline.json"

STUB_KEYS = ("兼容", "旧路径", "deprecated", "Deprecated", "别名")


def _scan():
    stubs = []
    for f in GAME.rglob("*.py"):
        rel = f.relative_to(REPO).as_posix()
        if "__pycache__" in rel:
            continue
        txt = f.read_text(encoding="utf-8", errors="replace")
        lines = [l for l in txt.splitlines()
                 if l.strip() and not l.strip().startswith("#")]
        if (len(lines) <= 14
                and re.search(r"^\s*from\s+(core|game|application|engine|ai|content)\.",
                              txt, re.M)
                and any(k in txt for k in STUB_KEYS)):
            stubs.append(rel)
    names = {Path(s).stem for s in stubs}
    internal = 0
    for f in GAME.rglob("*.py"):
        rel = f.relative_to(REPO).as_posix()
        if "__pycache__" in rel or rel in stubs:
            continue
        txt = f.read_text(encoding="utf-8", errors="replace")
        for name in names:
            internal += len(re.findall(
                r"^\s*(?:from\s+core\.%s\s+import|import\s+core\.%s\b)" % (name, name),
                txt, re.M))
    return sorted(stubs), internal


def test_compat_stub_count_does_not_grow():
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    stubs, _internal = _scan()
    assert len(stubs) <= base["stub_count"], (
        "新增兼容桩（薄转发桩）%d > 基线 %d；新增前先问 Jev，确需新增则同步调基线：\n新增=%s"
        % (len(stubs), base["stub_count"],
           sorted(set(stubs) - set(base["stubs"]))))


def test_legacy_imports_inside_game_do_not_grow():
    """发行物（game/）内部对旧路径的 import 数只减不增（当前实测基线为 0）。"""
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    _stubs, internal = _scan()
    assert internal <= base["legacy_import_count"], (
        "game/ 内旧路径 import 增加：%d > 基线 %d —— 请改 import 到新位置"
        % (internal, base["legacy_import_count"]))


def test_baseline_is_self_consistent():
    """基线文件自身要与桩清单一致（防止有人只改计数不改清单）。"""
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert base["stub_count"] == len(base["stubs"])
    for s in base["stubs"]:
        assert (REPO / s).is_file(), "基线里列了不存在的桩：%s" % s
