# -*- coding: utf-8 -*-
"""第二十二包回归：开 `core/workflows/`（`evaluation`，§7「基础或应用支持域（逐项定）」）。

本包是**流程编排层的第一份实现**（阶段 0 建包以来该目录一直是空骨架）。

 ① 桩面逐字等于迁移前冻结的 `dir()` 快照（10 个非 dunder 名，含 3 个从 `content.data`
    转引的常量绑定与 2 个 `_` 私有名）；
 ② 逐名从实现转发且同一对象，桩内不许自带实现；迁移前**没有** `__all__`，桩也不许"补一个"；
 ③ 桩不是行为开关 + 全测试目录禁止把旧桩当 patch 提供方（AST 别名解析）——
    本批实测就抓到一处：`test_turn_lifecycle.py` 打桩 `core.evaluation.check_game_over`，
    而消费者的延迟导入已改指新路径 ⇒ patch 会**静默失效**（用例照绿却什么都没注入）；
 ④ 🔴 **落层判据**（本包真正争议的地方）：新落点只允许向下依赖
    `content.*` 与 `core.domains.*`，禁止 `application` / `backend` / `ui` / `ai` / `memory`
    与 `core` 平铺模块 ⇒ 原先 `evaluation → army_models` 这条"平铺 core 引业务域"的
    可疑边，落进流程编排层后方向才成立；
 ⑤ 真实数据通道非空且**开局基线数字**锁死（七维、总分、结局档位）；
 ⑥ 两套防线阈值语义**不得合并**（退位=任一边防空虚且无年份约束 / 京城陷落=指定线+年≥1126）。

⑤⑥ 的数字全部来自 2026-10-09 实测（`_scratch/b22_measure.py`），**先量后写**。
"""
import ast
import importlib
import io
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

BASE = os.path.dirname(_GAME_ROOT)
OLD = "core.evaluation"
NEW = "core.workflows.evaluation"
IMPL_REL = "core/workflows/evaluation.py"

# 迁移前 dir() 冻结（_scratch/b22_surface.json，18 名去 8 个 dunder）
FROZEN_SURFACE = frozenset({
    "END_YEAR", "EVAL_OUTCOMES", "EVAL_WEIGHTS",
    "_DEF_GARRISON_SCORE_BASE", "_garrison_breached", "_get_outcome_desc",
    "check_abdication", "check_game_over", "check_reach_end_year", "evaluate_game",
})


def _impl():
    return importlib.import_module(NEW)


def _non_dunder(mod):
    return {n for n in dir(mod) if not (n.startswith("__") and n.endswith("__"))}


def _iter_py(root):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in fn:
            if f.endswith(".py"):
                yield os.path.join(dp, f)


# ── ①-② 桩面 / 转发 / 同一性 ──────────────────────────────────────
def test_stub_surface_equals_frozen_snapshot():
    surface = _non_dunder(importlib.import_module(OLD))
    assert surface == FROZEN_SURFACE, (
        "公开面漂移 缺=%s 多=%s" % (sorted(FROZEN_SURFACE - surface),
                                    sorted(surface - FROZEN_SURFACE)))


def test_every_name_forwards_to_same_object():
    path = os.path.join(_GAME_ROOT, *OLD.split(".")) + ".py"
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    home = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            for a in n.names:
                home[a.name] = n.module
    assert not [getattr(x, "name", "?") for x in tree.body
                if isinstance(x, (ast.FunctionDef, ast.ClassDef, ast.Assign))], \
        "桩内自带实现（第二份真相）"
    impl = _impl()
    for name in _non_dunder(importlib.import_module(OLD)):
        assert home.get(name) == NEW, f"{OLD}.{name} 应由 {NEW} 转发，实际 {home.get(name)}"
        assert getattr(importlib.import_module(OLD), name) is getattr(impl, name)


def test_no_dunder_all_on_either_side():
    """迁移前该模块**没有** `__all__`（`from core.evaluation import *` 给全部公开名）。

    桩若"顺手补一个"就等于悄悄收窄旧路径的星号公开面，所以两侧都必须没有。
    """
    assert not hasattr(_impl(), "__all__"), "实现侧被加了 __all__，公开面口径变了"
    assert not hasattr(importlib.import_module(OLD), "__all__"), "桩侧多出 __all__"


def test_transferred_constants_are_content_objects():
    """三个常量是**同一个对象**（不是复制值）——改 content 表时旧路径必须同步看到。"""
    import content.data as cd
    impl, stub = _impl(), importlib.import_module(OLD)
    assert stub.END_YEAR is impl.END_YEAR is cd.END_YEAR
    assert stub.EVAL_WEIGHTS is impl.EVAL_WEIGHTS is cd.EVAL_WEIGHTS
    assert stub.EVAL_OUTCOMES is impl.EVAL_OUTCOMES is cd.EVAL_OUTCOMES


# ── ③ 桩不是行为开关 / 禁止把旧桩当 patch 提供方 ──────────────────
def test_stub_is_not_a_behavior_switch(monkeypatch):
    stub, impl = importlib.import_module(OLD), _impl()
    orig = impl.check_game_over
    monkeypatch.setattr(stub, "check_game_over", lambda _s: False)
    try:
        assert impl.check_game_over is orig, "改桩不该改到实现"
    finally:
        monkeypatch.undo()
    assert impl.check_game_over is orig


def test_no_test_patches_the_old_evaluation_stub():
    """旧桩只保名字；打在桩上的 patch 对消费者**静默无效** ⇒ 一律禁止。"""
    tests = os.path.join(BASE, "_dev_tools", "game-dev", "tests")
    offenders = []
    for path in _iter_py(tests):
        try:
            tree = ast.parse(io.open(path, encoding="utf-8", errors="replace").read())
        except SyntaxError:
            continue
        aliases = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    if a.name == OLD:
                        aliases.add(a.asname or a.name.split(".")[-1])
            elif isinstance(n, ast.ImportFrom) and (n.module or "") == "core":
                for a in n.names:
                    if a.name == "evaluation":
                        aliases.add(a.asname or a.name)
        for n in ast.walk(tree):
            if (isinstance(n, ast.Call) and getattr(n.func, "attr", "") in ("setattr", "delattr")
                    and n.args and isinstance(n.args[0], ast.Name) and n.args[0].id in aliases):
                offenders.append("%s:%d" % (os.path.relpath(path, BASE).replace(os.sep, "/"),
                                            n.lineno))
    assert not offenders, "旧桩被当 patch 提供方：\n" + "\n".join(offenders)


# ── ④ 落层判据：流程编排层只许向下 ────────────────────────────────
# 允许：`content.*`（数据层）、`core.domains.*`（业务机制层）、stdlib。
# 禁止：`application`/`backend`/`ui`/`ai`/`memory`/`engine`（上层），
#       以及 `core.<平铺模块>`（同层平铺互引，正是本包要消掉的那类边）。
_CORE_SUBPACKAGES = ("core.domains.", "core.foundation.", "core.workflows.", "core.settlement.")
_UPPER_ROOTS = ("application", "backend", "ui", "ai", "memory", "engine")


def test_new_home_dependency_direction():
    tree = ast.parse(io.open(os.path.join(_GAME_ROOT, *IMPL_REL.split("/")),
                             encoding="utf-8").read())
    offenders = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods = [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            mods = [n.module or ""] if n.level == 0 else ["<相对导入>"]
        else:
            continue
        for m in mods:
            top = m.split(".")[0]
            if top in _UPPER_ROOTS:
                offenders.append("%s:%d %s（引上层）" % (IMPL_REL, n.lineno, m))
            elif top == "core" and not m.startswith(_CORE_SUBPACKAGES):
                offenders.append("%s:%d %s（引 core 平铺）" % (IMPL_REL, n.lineno, m))
            elif top not in ("content", "core"):
                offenders.append("%s:%d %s（stdlib/第三方，允许）" % (IMPL_REL, n.lineno, m))
    offenders = [o for o in offenders if "允许" not in o]
    assert not offenders, f"新落点依赖方向违例：{offenders}"
    # 反向哨兵：本模块**确实**有那两条边，扫描不是空跑
    src_mods = []
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            src_mods.append(n.module or "")
    assert "content.data" in src_mods, "content.data 边消失 ⇒ 扫描口径变了"
    assert "core.domains.military.army_models" in src_mods, (
        "army_models 边消失 ⇒ 武功维取用口径变了，本包的落层论证需重判")


# ── ⑤ 真实通道非空 + 开局基线 ────────────────────────────────────
def test_fresh_game_baseline_numbers():
    from core.game_state import GameState
    impl = _impl()
    s = GameState("史实")
    r = impl.evaluate_game(s)
    assert sorted(r["scores"]) == sorted(
        ["文治", "武功", "民生", "财政", "艺术造诣", "声望", "百姓口碑"]), sorted(r["scores"])
    # 先量后写：2026-10-09 新局实测
    assert round(r["scores"]["文治"], 3) == 53.6, r["scores"]
    assert round(r["scores"]["武功"], 3) == 32.396, r["scores"]
    assert r["scores"]["财政"] == 50 and r["scores"]["民生"] == 55
    assert r["total"] == 56.8 and r["outcome"] == "治平", r
    assert r["description"], "结局描述空 ⇒ 档位文案表与 EVAL_OUTCOMES 脱节"
    assert len(r["scores"]) == len(impl.EVAL_WEIGHTS) == 7
    # 新局不得判成已结束
    assert impl.check_game_over(s) is False and s.game_over is False
    assert impl.check_abdication(s) == (False, "")
    assert impl.check_reach_end_year(s) == (False, "")


def test_wu_score_uses_real_army_channel_not_sum():
    """`武功` 走 `army_models.army_power` 的**均值折算**（本模块唯一一条跨层取用）。

    若那条延迟导入断链被 try/except 吞掉，`powers` 会退化成 `[0]` ⇒ 分数明显掉档。
    """
    from core.game_state import GameState
    impl = _impl()
    s = GameState("史实")
    wu = impl.evaluate_game(s)["scores"]["武功"]
    assert wu > 0, "武功为 0 ⇒ army_power 通道没吃到真实部队"
    s2 = GameState("史实")
    s2.army_units = []
    wu_empty = impl.evaluate_game(s2)["scores"]["武功"]
    assert wu_empty < wu, (wu_empty, wu)


def test_abdication_needs_two_reasons():
    from core.game_state import GameState
    impl = _impl()
    s = GameState("史实")
    s.population_satisfaction = 19
    assert impl.check_abdication(s) == (False, ""), "单条理由不该触发退位"
    s.prestige, s.emperor_health = 20, 29
    hit, reason = impl.check_abdication(s)
    assert hit is True and reason == "民怨沸腾、皇威扫地龙体不支", reason


# ── ⑥ 两套防线阈值语义不得合并 ───────────────────────────────────
def test_two_defense_threshold_semantics_stay_distinct():
    from core.game_state import GameState
    impl = _impl()
    s = GameState("史实")
    line = "内线_东京城防"
    assert s.defense_lines[line]["garrison"] == 70_000
    assert impl._garrison_breached(s, 10, line) is False
    s.defense_lines[line]["garrison"] = 5
    assert impl._garrison_breached(s, 10, line) is True
    # 不存在的防线：`.get(name, {})` 后 `garrison` 缺省 **100**（不是 0）⇒ 不判破
    assert impl._garrison_breached(s, 10, "不存在的线") is False
    # line_name=None 走"任一边防空虚"分支（退位用），与指定线分支阈值口径不同
    s2 = GameState("史实")
    s2.defense_lines["北线_陕西"]["garrison"] = 7
    assert impl._garrison_breached(s2, 20) is True


def test_capital_fall_requires_year_gate():
    from core.game_state import GameState
    import content.data as cd
    impl = _impl()
    s = GameState("史实")
    s.year = 1125
    s.defense_lines["内线_东京城防"]["garrison"] = 5
    assert impl.check_game_over(s) is False, "1126 年前不该判京城陷落"
    s.year = 1127
    assert impl.check_game_over(s) is True
    assert "京城陷落" in s.game_result, s.game_result
    s3 = GameState("史实")
    s3.year = cd.END_YEAR
    assert impl.check_game_over(s3) is True and "收束之年" in s3.game_result, s3.game_result
