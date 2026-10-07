# -*- coding: utf-8 -*-
"""第二十包回归：开 `domains/culture/`（`literacy`，§7 教育与礼仪）。

结构类（①-④）与第十九包同型，语义类（⑤-⑧）是识字率特有的口径，全部**先实测再写**：
 ① 桩面逐字等于迁移前冻结的 `dir()` 快照（27 个非 dunder 名）；
 ② 逐名从实现转发且同一对象，桩内不许自带实现；
 ③ 🔴 `POP_LITERACY_BASE`（模块级可变 dict）与 `log`（logger 对象）只能有一份；
 ④ 🔴 logger 名仍是 `"literacy"`——M2 可观测性用例按 logger 名过滤，改名等于弄丢对外可见面；
 ⑤ 全国/逐路识字率是**按 size 加权**的比率，**绝不可求和**（`pop_bridge.MEAN_FIELDS` 同源口径）；
 ⑥ 缺失就是缺失：读不到一律 `None`，不回落 0（根 AGENTS §3-3）；
 ⑦ `init_literacy` 幂等：已补齐时补 0 处，清空后补齐 120 处（实测值）；
 ⑧ `settle_literacy` 是**唯一写入点**：实测新局开局即稳定点（`init_literacy` 补的是目标值），
    故整步结算**一个字段都不该动**（含 `literacy` 本身），派生值 `state.literacy` 保持 8.41。
    POP 挂载律要求它只写 `pops.*.literacy`，不得碰 size/wealth/grain 等真账字段。
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
OLD = "core.literacy"
NEW = "core.domains.culture.literacy"

# 迁移前用 dir() 冻结的公开面（_scratch/b19_surface_literacy.json，37 名去 10 个 dunder）
FROZEN_SURFACE = frozenset({
    "Any", "Dict", "Optional", "Tuple", "annotations", "logging", "log",
    "_num", "_clamp", "_CLASSES", "_region_mod",
    "POP_LITERACY_BASE", "LITERACY_FLOOR", "LITERACY_CAP", "LITERACY_CONVERGE",
    "MOD_BASE", "MOD_SUPPORT_W", "MOD_UNREST_W", "MOD_ART_W", "MOD_LO", "MOD_HI",
    "literacy_target", "pop_literacy", "route_literacy", "national_literacy",
    "init_literacy", "settle_literacy",
})

IMPL_REL = "core/domains/culture/literacy.py"


def _impl():
    return importlib.import_module(NEW)


def _non_dunder(mod):
    return {n for n in dir(mod) if not (n.startswith("__") and n.endswith("__"))}


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
    local_impl = [getattr(x, "name", "?") for x in tree.body
                  if isinstance(x, (ast.FunctionDef, ast.ClassDef))
                  or (isinstance(x, ast.Assign)
                      and not all(getattr(t, "id", "").startswith("__") for t in x.targets)
                      and x.targets and getattr(x.targets[0], "id", "") != "__all__")]
    assert not local_impl, f"桩内自带实现（第二份真相）：{local_impl}"
    impl = _impl()
    for name in _non_dunder(importlib.import_module(OLD)):
        assert home.get(name) == NEW, f"{OLD}.{name} 应由 {NEW} 转发，实际 {home.get(name)}"
        assert getattr(importlib.import_module(OLD), name) is getattr(impl, name)


def test___all__is_a_verbatim_copy_not_a_regeneration():
    """`__all__` 在桩里是**原样拷贝**（内容相等，但按定义是两份 list）。

    写成断言是为了：以后若有人改成重生成，公开面会被悄悄扩大；若有人删掉它，
    `dir()` 仍相等但 `from core.literacy import *` 的兼容面会变。
    """
    stub, impl = importlib.import_module(OLD), _impl()
    assert stub.__all__ == impl.__all__
    assert stub.__all__ is not impl.__all__
    assert impl.__all__ == ["POP_LITERACY_BASE", "literacy_target", "init_literacy",
                            "settle_literacy", "route_literacy", "national_literacy",
                            "pop_literacy"]


def test_mutable_base_table_and_logger_are_shared():
    impl = _impl()
    stub = importlib.import_module(OLD)
    assert stub.POP_LITERACY_BASE is impl.POP_LITERACY_BASE, (
        "识字基准表出现第二份：改一侧值域另一侧不跟着变，结算与读数会各自漂移")
    assert stub.log is impl.log


def test_logger_name_is_still_literacy():
    """M2 可观测性口径：logger 名不得因迁移而改变。"""
    assert _impl().log.name == "literacy"


def test_stub_is_not_a_behavior_switch(monkeypatch):
    stub, impl = importlib.import_module(OLD), _impl()
    orig = impl.init_literacy

    def _boom(*a, **k):
        raise AssertionError("不该被调到")

    monkeypatch.setattr(stub, "init_literacy", _boom)
    try:
        assert impl.init_literacy is orig, "桩与实现已不是同一对象 ⇒ 桩被写成了第二份实现"
        assert stub.init_literacy is _boom
    finally:
        monkeypatch.undo()
    assert impl.init_literacy is orig


def _iter_py(root):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for f in fn:
            if f.endswith(".py"):
                yield os.path.join(dp, f)


def test_no_test_patches_the_old_literacy_stub():
    """常驻禁令：不许把旧桩 `core.literacy` 当 monkeypatch 的**提供方**。

    本批就有一处（`test_error_observability_settle.py` 注 `init_literacy`），
    消费者改直认真实家之后它必然静默失效 ⇒ 已随批改指实现模块，这条防止它再回来。
    """
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
                        aliases.add((a.asname or a.name.split(".")[-1]))
            elif isinstance(n, ast.ImportFrom) and (n.module or "") == "core":
                for a in n.names:
                    if a.name == "literacy":
                        aliases.add(a.asname or a.name)
        for n in ast.walk(tree):
            if (isinstance(n, ast.Call)
                    and getattr(n.func, "attr", "") in ("setattr", "delattr")
                    and n.args and isinstance(n.args[0], ast.Name)
                    and n.args[0].id in aliases):
                offenders.append("%s:%d" % (os.path.relpath(path, BASE).replace(os.sep, "/"),
                                            n.lineno))
    assert not offenders, "旧桩被当 patch 提供方（注入会静默失效）：\n" + "\n".join(offenders)


# ── 语义类（全部为迁移前实测值） ──────────────────────────────────
def test_national_literacy_is_weighted_average_not_sum():
    from core.game_state import GameState
    impl = _impl()
    s = GameState("史实")
    nat = impl.national_literacy(s)
    assert nat == 8.41, f"实测基线值 8.41，现在 {nat}——结算口径变了，须另立批次"
    num = den = 0.0
    total = 0.0
    for p in s.prefectures.values():
        for row in (p.get("pops") or {}).values():
            if row.get("literacy") is None:
                continue
            size = max(0.0, float(row.get("size") or 0))
            num += float(row["literacy"]) * size
            den += size
            total += float(row["literacy"])
    assert round(num / den, 2) == nat, "全国读数与按 size 加权复算不一致"
    assert total > 10 * nat, (
        "本用例的前提是『求和会翻数量级』；若这条不成立说明 state 结构变了，需重判")
    assert nat <= impl.LITERACY_CAP, "比率被求和了（MEAN_FIELDS 口径破）"


def test_missing_reads_are_none_not_zero():
    """缺失 ≠ 0：读不到必须 None（根 AGENTS §3-3）。"""
    from core.game_state import GameState
    impl = _impl()
    s = GameState("史实")
    cleared = 0
    for p in s.prefectures.values():
        for row in (p.get("pops") or {}).values():
            if "literacy" in row:
                row["literacy"] = None
                cleared += 1
    assert cleared == 120, f"清空了 {cleared} 项，用例前提（120 类 POP 行）需重判"
    assert impl.national_literacy(s) is None
    assert impl.route_literacy(s, list(s.prefectures)[0]) is None
    assert impl.pop_literacy(s, list(s.prefectures)[0], "农") is None
    # 实测既有语义（本批未改）：缺失行在结算时**直接补到目标值**（不缓动），
    # 且这些行不计进 `pops` 计数（`continue` 在 `out["pops"] += 1` 之前）
    out = impl.settle_literacy(s)
    assert out == {"pops": 0, "changed": cleared, "national": 8.41}, out
    assert impl.national_literacy(s) == 8.41
    # 已补齐 ⇒ 幂等：再补一次不该写任何东西
    assert impl.init_literacy(s) == 0
    assert impl.national_literacy(s) == 8.41


def test_init_literacy_is_idempotent():
    from core.game_state import GameState
    impl = _impl()
    s = GameState("史实")
    assert impl.init_literacy(s) == 0, "新局 POP 已带 literacy，幂等补齐不该再写"
    rows = [row for p in s.prefectures.values() for row in (p.get("pops") or {}).values()]
    for row in rows:
        row["literacy"] = None
    assert impl.init_literacy(s) == len(rows) == 120
    assert impl.init_literacy(s) == 0, "第二次补齐不该再写任何东西"
    assert impl.national_literacy(s) == 8.41


def test_settle_only_writes_literacy_fields():
    """唯一写入点：除 `pops.*.literacy` 与派生值 `state.literacy` 外一位都不许动。"""
    from core.game_state import GameState
    impl = _impl()
    s = GameState("史实")
    before = {r: {c: dict(row) for c, row in (p.get("pops") or {}).items()}
              for r, p in s.prefectures.items()}
    out = impl.settle_literacy(s)
    assert out["pops"] == 120 and out["national"] == 8.41, out
    changed = []
    for r, rows in s.prefectures.items():
        for c, row in (rows.get("pops") or {}).items():
            for k, v in before[r][c].items():
                if row.get(k) != v:
                    changed.append((r, c, k, v, row.get(k)))
    assert not changed, (
        "开局即稳定点，本步不该改任何字段（含 literacy）；实际改了：\n%s" % changed[:5])
    assert s.literacy == 8.41


def test_settle_moves_by_converge_rate_only():
    """教育是慢变量：月度只走 6% 差距（缓动，不跳变）。"""
    from core.game_state import GameState
    impl = _impl()
    s = GameState("史实")
    route = list(s.prefectures)[0]
    row = s.prefectures[route]["pops"]["农"]
    cur = float(row["literacy"])
    target = impl.literacy_target(s, route, "农", s.prefectures[route])
    row["literacy"] = cur - 10.0
    impl.settle_literacy(s)
    got = float(row["literacy"])
    expect = round(max(impl.LITERACY_FLOOR, min(impl.LITERACY_CAP,
                   (cur - 10.0) + (target - (cur - 10.0)) * impl.LITERACY_CONVERGE)), 2)
    assert got == expect, (got, expect, cur, target)
    assert got < target, "缓动一步就到位＝跳变，违背『慢变量』设定"


def test_new_home_imports_only_foundation_and_stdlib():
    """新落点：只许 stdlib + `core.foundation.*` 公开名（§6 硬规则1 向下依赖）。"""
    tree = ast.parse(io.open(os.path.join(_GAME_ROOT, *IMPL_REL.split("/")),
                             encoding="utf-8").read())
    offenders, priv = [], []
    for n in ast.walk(tree):
        mods = []
        if isinstance(n, ast.ImportFrom):
            mods = [n.module or ""]
            for a in n.names:
                if (n.module or "").startswith("core.") and a.name.startswith("_") \
                        and not a.asname:
                    priv.append("%s:%d %s ← %s" % (IMPL_REL, n.lineno, n.module, a.name))
        elif isinstance(n, ast.Import):
            mods = [a.name for a in n.names]
        for m in mods:
            if m.startswith("core.") and not m.startswith(("core.foundation.", "core.domains.")):
                offenders.append("%s:%d %s" % (IMPL_REL, n.lineno, m))
    assert not offenders, f"新落点引了 core 平铺/上层模块：{offenders}"
    assert not priv, f"跨模块借用私有符号（§6 规则2）：{priv}"
