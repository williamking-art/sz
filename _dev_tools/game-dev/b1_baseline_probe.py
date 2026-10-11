# -*- coding: utf-8 -*-
"""B-1 golden 产出探针（`_dev_tools/game-dev/b1_baseline_probe.py`）。

用途：为 `tests/b1_field_registry_golden.py` 产出**迁移前实现**的实跑冻结数据。
配套测试：`tests/test_field_registry_parity.py`（L1/L1.5/L2/L3）。

🔴 **安全性要点（本探针最容易毁掉 golden 的地方）**
    B-1b 之后，`game/engine/state_applier.py` 里的六套字面量**已被删除**（改为从
    `field_registry` 导入）。若照旧从**工作树**提取，会得到**空集合**并把 golden 写坏。
    因此本探针：
      ① 六集合一律用 `git show <rev>:game/engine/state_applier.py` 从**修订**提取，不读工作树；
      ② `--emit` 前做 **fail-closed 守卫**：工作树的 state_applier 必须与该修订**逐字节相同**，
         否则拒绝写出（除非显式 `--force`，那通常意味着你做错了）。
    ⇒ 要重新产出 golden，请先 `git worktree add <tmp> <rev>` 在**基线修订**上运行本脚本。

用法
----
    # 只采集并打印摘要（不写文件；可在任意树/任意修订上跑）
    python _dev_tools/game-dev/b1_baseline_probe.py --rev f6d2dad6139febf40e6ee9271a19a5d312d1671e

    # 在基线 worktree 上重新产出 golden
    python _dev_tools/game-dev/b1_baseline_probe.py --rev <基线rev> --emit

退出码：0 成功；1 = 守卫拒绝或用法错（`SystemExit`，并打印正确做法）。
"""
from __future__ import annotations

import ast
import io
import json
import os
import pprint
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))          # _dev_tools/game-dev
SZ = os.path.normpath(os.path.join(_HERE, "..", ".."))      # 仓库根
GAME = os.path.join(SZ, "game")
STATE_APPLIER_REL = "game/engine/state_applier.py"
STATE_APPLIER = os.path.join(GAME, "engine", "state_applier.py")
GOLDEN_OUT = os.path.join(_HERE, "tests", "b1_field_registry_golden.py")

DEFAULT_REV = "f6d2dad6139febf40e6ee9271a19a5d312d1671e"    # B-1 之前的基准修订

sys.path.insert(0, GAME)

from core.game_state import GameState  # noqa: E402
import engine.state_applier as sa  # noqa: E402

VIEWS = ["VALID_PATHS", "NON_NEG_PREFIXES", "MONEY_PATHS", "GRAIN_PATHS",
         "RANGE_100_FIELDS", "CLAMP_01_FIELDS"]


def show(tag, obj):
    print("%s %s" % (tag, json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)))


def git(*args):
    r = subprocess.run(["git", "-C", SZ] + list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit("git %s 失败：%s" % (" ".join(args), r.stderr.strip()))
    return r.stdout


def old_collections(rev):
    """从**修订**提取迁移前六集合字面量（逐字，含顺序）。**不读工作树。**"""
    src = git("show", "%s:%s" % (rev, STATE_APPLIER_REL))
    tree = ast.parse(src)
    out = {}
    for node in tree.body:
        tgt, val = None, None
        if isinstance(node, ast.Assign):
            tgt = [t.id for t in node.targets if isinstance(t, ast.Name)]
            val = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            tgt = [node.target.id]
            val = node.value
        if tgt and isinstance(val, ast.List):
            for n in tgt:
                if n in VIEWS:
                    out[n] = [e.value for e in val.elts]
    missing = [v for v in VIEWS if v not in out]
    if missing:
        raise SystemExit(
            "修订 %s 里找不到这些集合字面量：%s\n"
            "（若该修订已做过 B-1b，字面量已删除 ⇒ 请改用 B-1 之前的修订，"
            "或在基线 worktree 上运行。）" % (rev, missing))
    return out


def worktree_matches_rev(rev):
    cur = io.open(STATE_APPLIER, encoding="utf-8").read()
    return cur == git("show", "%s:%s" % (rev, STATE_APPLIER_REL))


def canon(state):
    return {
        "treasury": state.treasury,
        "imperial_treasury": state.imperial_treasury,
        "granary": state.granary,
        "prestige": state.prestige,
        "population_satisfaction": state.population_satisfaction,
    }


def build_scenarios(road, fac):
    return [
        ("S1_set_single", [("a", [{"path": "prestige", "op": "set", "value": 50, "reason": "r1"}])]),
        ("S2_pair_money_closed", [("a", [
            {"path": "treasury", "op": "add", "value": -1000, "reason": "税征"},
            {"path": "prefectures.%s.pops.商人.wealth" % road, "op": "add", "value": 1000, "reason": "税征"},
        ])]),
        ("S3_single_sided_fix", [("a", [
            {"path": "treasury", "op": "add", "value": 5000, "reason": "市舶税入账"}])]),
        ("S4_single_sided_no_keyword", [("a", [
            {"path": "treasury", "op": "add", "value": -100, "reason": "无关键词单边"}])]),
        ("S5_underflow", [("a", [
            {"path": "treasury", "op": "add", "value": -9000000000, "reason": "穿底探针"},
            {"path": "prefectures.%s.pops.士绅.wealth" % road, "op": "add", "value": 9000000000, "reason": "穿底探针"},
        ])]),
        ("S6_nonconserved_underflow", [("a", [
            {"path": "prefectures.%s.refugees" % road, "op": "add", "value": -999999, "reason": "流民安置"}])]),
        ("S7_wildcard_fix_prorate", [("a", [
            {"path": "treasury", "op": "add", "value": 1234, "reason": "市舶税"}])]),
        ("S8_multi_agent_merge", [
            ("a1", [{"path": "treasury", "op": "add", "value": 10, "reason": "a1"},
                    {"path": "granary", "op": "set", "value": 7, "reason": "a1"}]),
            ("a2", [{"path": "treasury", "op": "add", "value": 20, "reason": "a2"},
                    {"path": "granary", "op": "set", "value": 9, "reason": "a2"}]),
        ]),
        ("S9_cascade_noop", [("a", [
            {"path": "prefectures.%s.pops.农.wealth" % road, "op": "add", "value": 1, "reason": "cascade 探针"},
            {"path": "prefectures.%s.pops.农.grain" % road, "op": "add", "value": -1, "reason": "cascade 探针"},
            {"path": "prefectures.%s.pops.士绅.grain" % road, "op": "add", "value": 1, "reason": "cascade 探针"},
        ])]),
        ("S10_push_numeric", [("a", [{"path": "prestige", "op": "push", "value": 5, "reason": "push 探针"}])]),
        ("S11_range100_set_over", [("a", [
            {"path": "prestige", "op": "set", "value": 200, "reason": "越界 set"}])]),
        ("S12_range100_add_negative", [("a", [
            {"path": "population_satisfaction", "op": "add", "value": -5, "reason": "负增量"}])]),
        ("S13_era_state_prefix", [("a", [
            {"path": "era_state.art", "op": "add", "value": 3, "reason": "前缀通道探针"}])]),
        ("S14_pop_class7_rejected", [("a", [
            {"path": "prefectures.%s.pops.吏.wealth" % road, "op": "add", "value": 1, "reason": "第7类探针"}])]),
        ("S15_money_missing_source_hard_reject", [("a", [
            {"path": "prefectures.%s.pops.农.wealth" % road, "op": "add", "value": 777, "reason": "孤立入账"}])]),
    ]


def build_sample_paths(road, fac):
    return [
        "treasury", "imperial_treasury", "granary", "granary_cap", "granary.x", "granary_",
        "prestige", "payraise_budget", "population_satisfaction", "art_mastery",
        "era_state", "era_state.", "era_state.art",
        "land.hidden_rate", "land.hidden_households",
        "waste_reform.active", "waste_reform.savings",
        "prefectures.%s.mood" % road, "prefectures.%s.govern" % road,
        "prefectures.%s.unrest" % road, "prefectures.%s.grain" % road,
        "prefectures.%s.storage" % road, "prefectures.%s.refugees" % road,
        "prefectures.%s.public_support" % road, "prefectures.%s.gentry_resistance" % road,
        "prefectures.%s.city_defense" % road, "prefectures.%s.controlled_by" % road,
        "prefectures.%s.mood.extra" % road, "prefectures.mood",
        "prefectures.*.mood", "prefectures.%s" % road,
        "prefectures.%s.pops.农.wealth" % road, "prefectures.%s.pops.农.grain" % road,
        "prefectures.%s.pops.士绅.wealth" % road, "prefectures.%s.pops.士绅.grain" % road,
        "prefectures.%s.pops.工匠.wealth" % road, "prefectures.%s.pops.商人.wealth" % road,
        "prefectures.%s.pops.官僚.wealth" % road, "prefectures.%s.pops.兵.wealth" % road,
        "prefectures.%s.pops.吏.wealth" % road, "prefectures.*.pops.*.wealth",
        "prefectures.*.pops.*.grain", "prefectures.%s.pops.*.wealth" % road,
        "factions.%s.satisfaction" % fac, "factions.%s.influence" % fac,
        "factions.%s.power" % fac, "factions.*.satisfaction",
        "defense_lines.*.fortification", "defense_lines.*.garrison",
        "legacies.*.active", "legacies.*.progress",
        "Treasury", "", ".", "treasury.", "treasury ", "  ", "a..b",
        "focus.*.unlocked", "focus.*.power_level",
        None, 42, ["treasury"], {"path": "treasury"},
    ]


def predicates(p):
    out = {}
    for name, fn in (("path_ok", sa._path_ok), ("non_neg", sa._is_non_neg),
                     ("range100", sa._is_range100), ("clamp01", sa._is_clamp01)):
        try:
            out[name] = fn(p)
        except Exception as e:  # noqa: BLE001
            out[name] = "EXC:%s" % type(e).__name__
    try:
        out["group"] = sa._group_of(p) if isinstance(p, str) else "N/A"
    except Exception as e:  # noqa: BLE001
        out["group"] = "EXC:%s" % type(e).__name__
    return out


def main():
    argv = sys.argv[1:]
    emit = "--emit" in argv
    force = "--force" in argv
    rev = DEFAULT_REV
    if "--rev" in argv:
        rev = argv[argv.index("--rev") + 1]
    rev_full = git("rev-parse", rev).strip()

    print("=== [0] 修订与守卫 ===")
    show("REV", rev_full)
    matches = worktree_matches_rev(rev_full)
    show("WORKTREE_MATCHES_REV", matches)
    if emit and not matches and not force:
        raise SystemExit(
            "拒绝写出 golden：工作树的 %s 与修订 %s 不同。\n"
            "本探针的**行为**采集跑的是已安装模块，只有在基线树上才等于迁移前实现。\n"
            "正确做法：git worktree add <tmp> %s && 在 <tmp> 内运行本脚本。\n"
            "（确实清楚风险时用 --force，但那通常意味着你在把 golden 写坏。）"
            % (STATE_APPLIER_REL, rev_full, rev_full))

    old = old_collections(rev_full)
    print("=== [1] 六集合（取自修订，非工作树）===")
    for k in VIEWS:
        show("OLD_COUNT %s" % k, len(old[k]))

    print("=== [2] 确定性 ===")
    a, b = GameState("史实"), GameState("史实")
    show("DETERMINISTIC_TOPLEVEL", canon(a) == canon(b))
    show("DETERMINISTIC_PREFECTURES",
         json.dumps(a.prefectures, ensure_ascii=False, sort_keys=True, default=str)
         == json.dumps(b.prefectures, ensure_ascii=False, sort_keys=True, default=str))
    roads = sorted(a.prefectures.keys())
    facs = sorted(getattr(a, "factions", {}).keys())
    road = roads[0]
    fac = facs[0] if facs else None
    show("ROAD_COUNT", len(roads))
    show("ROAD_FIRST", road)
    show("FACTION_FIRST", fac)

    print("=== [3] 回滚场景（实跑）===")
    s = GameState("史实")
    sa.reset_change_log()
    before = canon(s)
    log_before = len(sa.CHANGE_LOG)
    changes = [
        {"path": "treasury", "op": "add", "value": -100, "reason": "回滚探针：钱组出腿"},
        {"path": "imperial_treasury", "op": "add", "value": 100, "reason": "回滚探针：钱组入腿"},
        {"path": "prefectures.%s.mood" % "不存在的路ZZZ", "op": "add", "value": 1,
         "reason": "回滚探针：中间层缺失"},
    ]
    exc_type = exc_msg = None
    result = None
    try:
        result = sa.applier_pipeline(s, [("probe", changes)])
    except Exception as e:  # noqa: BLE001
        exc_type, exc_msg = type(e).__name__, str(e)
    after = canon(s)
    rollback = {
        "exception_type": exc_type,
        "exception_msg": exc_msg,
        "returned": None if result is None else {
            "applied_paths": [x["path"] for x in result.get("applied", [])],
            "rejected": result.get("rejected"),
            "conservation_failed": result.get("conservation_failed"),
        },
        "state_before": before,
        "state_after": after,
        "state_restored": before == after,
        "field_diff": {k: [before[k], after[k]] for k in before if before[k] != after[k]},
        "changelog_before": log_before,
        "changelog_after": len(sa.CHANGE_LOG),
    }
    show("ROLLBACK", rollback)

    print("=== [4] 15 场景 pipeline ===")
    pipeline = {}
    for name, raw in build_scenarios(road, fac):
        st = GameState("史实")
        sa.reset_change_log()
        b4 = canon(st)
        res, ex = None, None
        try:
            res = sa.applier_pipeline(st, raw)
        except Exception as e:  # noqa: BLE001
            ex = "%s: %s" % (type(e).__name__, e)
        aft = canon(st)
        pipeline[name] = {
            "exception": ex,
            "applied": None if res is None else [[x["path"], x["old"], x["new"]] for x in res["applied"]],
            "rejected": None if res is None else res["rejected"],
            "conservation_failed": None if res is None else res.get("conservation_failed"),
            "changelog": len(sa.CHANGE_LOG),
            "state_delta": {k: [b4[k], aft[k]] for k in b4 if b4[k] != aft[k]},
        }
        show("SCEN %-36s" % name, pipeline[name])

    print("=== [5] 谓词样本 ===")
    sample = build_sample_paths(road, fac)
    pred = [(p, predicates(p)) for p in sample]
    show("SAMPLE_COUNT", len(sample))
    show("DISTINCT_PREDICATE_RESULTS", len(Counter(tuple(sorted(d.items())) for _, d in pred)))

    if emit:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        body = io.StringIO()
        body.write("# -*- coding: utf-8 -*-\n")
        body.write('"""B-1 golden：**迁移前实现**的实跑冻结数据（勿手改）。\n\n')
        body.write("来源：commit %s（B-1 之前的基准修订）\n" % rev_full)
        body.write("产出：`_dev_tools/game-dev/b1_baseline_probe.py --rev %s --emit`，"
                   "生成时间 %s\n" % (rev_full[:12], now))
        body.write("用途：`test_field_registry_parity.py` 的 L1/L2/L3 期望值。\n")
        body.write("纪律：期望值必须来自实跑；不得用未验证的预期替换本文件；\n")
        body.write("      重新产出请在**基线修订的 worktree** 上运行（探针含 fail-closed 守卫）。\n")
        body.write('"""\n\n')
        body.write("GOLDEN_SOURCE = {\n 'commit': %r,\n 'generated_at': %r,\n"
                   " 'probe': '_dev_tools/game-dev/b1_baseline_probe.py',\n"
                   " 'worktree_matches_rev': %r,\n}\n\n" % (rev_full, now, matches))
        body.write("SIX_COLLECTIONS_OLD = ")
        body.write(pprint.pformat(old, width=110, sort_dicts=False))
        body.write("\n\nSAMPLE_PATHS = ")
        body.write(pprint.pformat(sample, width=110, sort_dicts=False))
        body.write("\n\nPREDICATE_GOLDEN = ")
        body.write(pprint.pformat(pred, width=110, sort_dicts=False))
        body.write("\n\nPIPELINE_GOLDEN = ")
        body.write(pprint.pformat(pipeline, width=110, sort_dicts=False))
        body.write("\n\nROLLBACK_GOLDEN = ")
        body.write(pprint.pformat(rollback, width=110, sort_dicts=False))
        body.write("\n\nCONTEXT = {'road': %r, 'faction': %r, 'missing_road': '不存在的路ZZZ'}\n"
                   % (road, fac))
        io.open(GOLDEN_OUT, "w", encoding="utf-8", newline="\n").write(body.getvalue())
        show("EMITTED", GOLDEN_OUT)


if __name__ == "__main__":
    main()
