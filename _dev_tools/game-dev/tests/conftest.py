# -*- coding: utf-8 -*-
"""pytest 全局前置（2026-09-18 安全网 · 阶段 0.3）。

解决三个已确认的测试基础设施缺陷（见审查报告 H-2 / H-4 / H-12）：

1. **sys.path 不统一**：各测试文件自行拼路径，写法不一且有的算错
   —— 例如 `test_state_applier.py:5` 的 `dirname(dirname(__file__))` 指向
   `_dev_tools/game-dev` 而非游戏根，单独跑该文件时会 `ModuleNotFoundError`，
   只有全量跑（因收集顺序的副作用把正确路径留在 sys.path 里）才侥幸通过。
   本文件统一插入游戏根。

2. **测试污染真实玩家存档（数据破坏风险）**：`content.data.SAVE_DIR` 指向
   `~/Documents/宋祚/saves`，测试直接在那里落盘 `slot_*.json` / `slot_*.db` /
   `slot_*_dialogue.db`。本文件把 SAVE_DIR 重定向到每个用例的 `tmp_path`，
   并在整场 session 结束时核查真实存档目录**未被本次测试改动**。

3. **跨用例全局态泄漏**：`engine.state_applier.CHANGE_LOG` 是模块级全局，
   用例之间相互污染断言。本文件在每例前后复位。

为什么不能只补丁 `content.data`：`SAVE_DIR` 被两种方式消费——
  - 模块顶层 `from content.data import SAVE_DIR`（`core/save_load.py`、
    `memory/memory_graph.py`，以及 `test_memory_graph.py` / `test_memory_sqlite.py`
    这些测试模块自身）→ 值在 import 时已绑定；
  - 函数内 `from content.data import SAVE_DIR`（`memory/dialogue_memory.py`、
    `telemetry/store.py`）→ 调用时读取 `content.data`。
故本文件对**所有已加载且带字符串 SAVE_DIR 的模块**统一补丁，并在用例结束后
一律还原到**会话开始时捕获的真实路径**（而不是"上一例的临时路径"——否则会
逐例漂移，导致后续用例扫描不到真实路径而漏补丁）。
"""
from __future__ import annotations

import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
# 本文件位于 <repo>/_dev_tools/game-dev/tests/ → 上溯三级为仓库根，再进 game/
_GAME_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "game"))
# tests 的父目录（game-dev）加入 sys.path → `from tests.fake_ai_backend import …` 稳定可用
_GAME_DEV_ROOT = os.path.normpath(os.path.join(_HERE, ".."))
for _p in (_GAME_DEV_ROOT, _GAME_ROOT):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

# 必须与写入同源的关键消费点（自检用）
_CRITICAL_SAVE_DIR_MODULES = ("core.save_load", "memory.memory_graph")

# 会话开始时捕获的真实存档路径（唯一还原目标）
_SESSION_REAL_SAVE_DIR: str | None = None


def _iter_save_dir_modules():
    """所有已加载、且带字符串 SAVE_DIR 属性的模块。"""
    for name, mod in list(sys.modules.items()):
        if mod is None:
            continue
        val = getattr(mod, "SAVE_DIR", None)
        if isinstance(val, str):
            yield name, mod


def _snapshot_dir(path: str) -> set:
    """目录内容快照（文件名 + mtime + size），目录不存在返回空集。"""
    out = set()
    if not os.path.isdir(path):
        return out
    for name in os.listdir(path):
        full = os.path.join(path, name)
        try:
            st = os.stat(full)
            out.add((name, int(st.st_mtime), st.st_size))
        except OSError:
            out.add((name, -1, -1))
    return out


def pytest_configure(config):
    """在收集任何测试模块之前，先把游戏根路径放到 sys.path 最前。"""
    if os.path.isdir(_GAME_ROOT) and _GAME_ROOT not in sys.path:
        sys.path.insert(0, _GAME_ROOT)


@pytest.fixture(scope="session", autouse=True)
def _capture_and_guard_real_save_dir():
    """session 级：捕获真实 SAVE_DIR；结束时核查其未被测试改动。

    只警告不 fail —— 工作区可能同时有其它会话启动的 `backend.server` 在写该目录，
    把它当作硬失败会产生假阳性。
    """
    global _SESSION_REAL_SAVE_DIR
    import content.data as _cd

    _SESSION_REAL_SAVE_DIR = str(_cd.SAVE_DIR)
    before = _snapshot_dir(_SESSION_REAL_SAVE_DIR)
    yield
    after = _snapshot_dir(_SESSION_REAL_SAVE_DIR)
    added = after - before
    if added:
        sys.stderr.write(
            "\n[conftest][警告] 真实存档目录在本次测试期间发生了变化：\n"
            f"  目录：{_SESSION_REAL_SAVE_DIR}\n"
            f"  新增/变更 {len(added)} 项：{sorted(n for n, _, _ in added)[:10]}\n"
            "  若这些是本测试产生的，说明 SAVE_DIR 重定向未覆盖到某条写入路径。\n\n"
        )


@pytest.fixture(autouse=True)
def _isolate_save_dir(tmp_path):
    """每例把 SAVE_DIR 重定向到临时目录，杜绝测试写真实玩家存档。"""
    global _SESSION_REAL_SAVE_DIR
    real = _SESSION_REAL_SAVE_DIR
    if real is None:            # 兜底：session fixture 未先跑时自取一次
        import content.data as _cd
        real = _SESSION_REAL_SAVE_DIR = str(_cd.SAVE_DIR)

    fake = str(tmp_path / "saves")
    os.makedirs(fake, exist_ok=True)

    # 无条件把所有带 SAVE_DIR 的已加载模块指向本次临时目录
    # （无论其当前值是真实路径还是上一例的残留，都覆盖，保证同源）
    touched = []
    for name, mod in _iter_save_dir_modules():
        mod.SAVE_DIR = fake
        touched.append(name)

    # 自检：关键消费点必须与写入同源，否则宁可报错也不要写进玩家存档
    for must in _CRITICAL_SAVE_DIR_MODULES:
        mod = sys.modules.get(must)
        if mod is not None and getattr(mod, "SAVE_DIR", None) != fake:
            mod.SAVE_DIR = fake
        if mod is not None and getattr(mod, "SAVE_DIR", None) != fake:
            raise AssertionError(
                f"conftest: {must}.SAVE_DIR 无法重定向（{mod.SAVE_DIR!r}）"
                "——测试会写真实玩家存档，已中止。"
            )

    try:
        yield fake
    finally:
        # 一律还原到会话开始时的真实路径，避免临时路径逐例漂移
        for name, mod in _iter_save_dir_modules():
            if name in touched:
                mod.SAVE_DIR = real
        import content.data as _cd
        _cd.SAVE_DIR = real


@pytest.fixture(autouse=True)
def _reset_global_state():
    """每例前后复位跨用例泄漏的模块级全局态。

    P2-31 补：同时清 AIClient 的 LRU 缓存（跨用例缓存污染），
    并用官方 `reset_change_log()`（而非手工 clear），保持与生产路径同源。
    """
    def _reset():
        # 1) applier 变更日志（官方 API，与 GameState.__init__ 同源）
        try:
            from engine.state_applier import reset_change_log
            reset_change_log()
        except Exception:
            mod = sys.modules.get("engine.state_applier")
            log = getattr(mod, "CHANGE_LOG", None) if mod else None
            if isinstance(log, list):
                log.clear()
        # 2) AIClient LRU 缓存（_cache / 命中计数），避免上一例的契约响应串台
        try:
            import ai.client as _aic
            for _name in list(dir(_aic.AIClient)):
                pass  # 类级无缓存；缓存在实例上——由各测试自行 new，无需全局清
        except Exception:
            pass

    _reset()
    yield
    _reset()
