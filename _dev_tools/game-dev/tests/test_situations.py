# -*- coding: utf-8 -*-
"""局势投影层（core/situations.py）回归测试 —— 对应《宋祚局势系统实施规范》§11.2。

覆盖：
① 只读性（深度快照）；② 投影可解释性（在 items 或在 NON_PROJECTED_SOURCES）；
③ 缺失维度为 None（不顶替）；④ 排序稳定；⑤ 脏数据隔离与消毒；
⑥ **POP 维度**：legacy(0–1)/focus(0–100) 量纲换算、同事件因 POP 结构差异得到不同 severity、
   `pop_highlights` 如实反映最窘/最丰阶级。
"""
import json
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.situations import (  # noqa: E402
    NON_PROJECTED_SOURCES, SNAPSHOT_METRICS, build_situation_readout,
)
from core.situation_metrics import METRICS, build_metric_snapshot  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402
from content.data import PREFECTURE_LIST  # noqa: E402


def _state():
    s = GameState("史实")
    init_legacies(s)                      # 帝国修正（开局 5 项）
    return s


def _deep_snapshot(s):
    """只读性判据：州县（含全部 POP 与 clerks_detail）、军政真账、派系、长期项三表、
    事件与日志、国家级账本。"""
    return (
        json.dumps(s.prefectures, sort_keys=True, ensure_ascii=False, default=str),
        json.dumps([vars(u) for u in getattr(s, "army_units", []) or []],
                   sort_keys=True, ensure_ascii=False, default=str),
        json.dumps(getattr(s, "factions", {}), sort_keys=True, ensure_ascii=False, default=str),
        json.dumps(getattr(s, "legacies", {}), sort_keys=True, ensure_ascii=False, default=str),
        json.dumps(getattr(s, "active_focus", None), sort_keys=True, ensure_ascii=False, default=str),
        json.dumps(getattr(s, "longterm_effects", []), sort_keys=True, ensure_ascii=False, default=str),
        json.dumps(getattr(s, "active_events", []), sort_keys=True, ensure_ascii=False, default=str),
        json.dumps(getattr(s, "event_history", []), sort_keys=True, ensure_ascii=False, default=str),
        json.dumps(getattr(s, "settlement_log", []), sort_keys=True, ensure_ascii=False, default=str),
        json.dumps(getattr(s, "active_decrees", []), sort_keys=True, ensure_ascii=False, default=str),
        json.dumps(getattr(s, "posts_quota", None), ensure_ascii=False, default=str),
        s.treasury, s.imperial_treasury, s.granary, s.prestige,
    )


# ---------------------------------------------------------------
# ① 只读性
# ---------------------------------------------------------------
def test_readout_is_readonly():
    s = _state()
    s.active_events = [{"title": "陕西大旱", "message": "赤地千里"}]
    s.active_focus = {"node_key": "kaogong_zaoce", "name": "考功造册", "status": "in_progress",
                      "progress": 40, "total_turns": 6, "elapsed_turns": 2, "cost_per_month": 12000}
    s.longterm_effects = [{"name": "市舶新制", "mode": "ongoing", "duration": 12,
                           "effects": {}, "cost": {"treasury": 5000}}]
    before = _deep_snapshot(s)
    build_situation_readout(s)
    build_situation_readout(s)            # 幂等
    assert _deep_snapshot(s) == before, "局势投影必须只读：不得改动州县/POP/长期项/事件/账本"


# ---------------------------------------------------------------
# ② 可解释性 + ③ 缺失值语义
# ---------------------------------------------------------------
def test_items_are_explainable_and_missing_fields_are_none():
    s = _state()
    s.active_events = [{"title": "陕西大旱", "message": ""}]
    s.active_focus = {"node_key": "k", "name": "国策甲", "status": "in_progress",
                      "progress": 30, "total_turns": 6, "elapsed_turns": 1, "cost_per_month": 9000}
    s.longterm_effects = [{"name": "长期诏甲", "mode": "ongoing", "duration": 3,
                           "effects": {}, "cost": {"treasury": 100}}]
    out = build_situation_readout(s)
    items = out["items"]
    assert items, "应至少投影出帝修/国策/长期诏/事件"

    sources = {r["source"] for r in items}
    assert sources >= {"legacy", "focus", "free_effect", "event"}
    # 可解释性：不投影的来源必须在代码常量里且有理有据
    for src, reason in NON_PROJECTED_SOURCES.items():
        assert reason, f"{src} 的不投影理由不得为空"

    by_src = {r["source"]: r for r in items}
    # 长期诏无进度 → None（不是 0）
    assert by_src["free_effect"]["bar_value"] is None
    # 事件无进度、无持续代价
    assert by_src["event"]["bar_value"] is None
    assert by_src["event"]["ongoing_text"] is None
    # 禁止语义顶替：focus 的推进成本不得写成持续代价
    assert by_src["focus"]["ongoing_text"] is None
    assert "月耗" in (by_src["focus"]["progress_text"] or "")
    # 帝修：clear_desc → 解除文案（不是"达成条件"）
    leg = by_src["legacy"]
    assert leg["resolve_condition_text"] is None or leg["resolve_condition_text"].startswith("解除")
    assert leg["fail_condition_text"] is None


def test_legacy_and_focus_progress_dimensions():
    """量纲：legacy.progress 是 0–1，focus.progress 是 0–100——换算不得混用。"""
    s = _state()
    key = next(iter(s.legacies))
    s.legacies[key]["progress"] = 0.5            # 50%
    s.active_focus = {"node_key": "k", "name": "国策甲", "status": "in_progress",
                      "progress": 50, "total_turns": 6, "elapsed_turns": 3, "cost_per_month": 1}
    out = build_situation_readout(s)
    by_src = {r["source"]: r for r in out["items"]}
    assert by_src["legacy"]["bar_value"] == 50, "0.5 应换算为 50，而不是 0 或 50.0"
    assert by_src["focus"]["bar_value"] == 50, "0–100 不得再乘 100"


# ---------------------------------------------------------------
# ④ 排序
# ---------------------------------------------------------------
def test_sort_is_stable_and_explainable():
    s = _state()
    s.active_events = [{"title": "陕西大旱", "message": ""}]
    out = build_situation_readout(s)
    sev = [(-r["severity"], r["id"]) for r in out["items"]]
    assert sev == sorted(sev), "应为 severity 降序 + id 升序的稳定排序"


# ---------------------------------------------------------------
# ⑤ 消毒
# ---------------------------------------------------------------
def test_dirty_data_is_isolated_not_fatal():
    s = _state()
    s.legacies["broken"] = "not-a-dict"          # 脏条目
    s.longterm_effects = ["not-a-dict"]          # 脏条目
    s.active_events = [42]                       # 脏条目
    out = build_situation_readout(s)
    assert out["readout_status"] == "partial"
    assert out["readout_errors"], "脏数据必须留下 readout_errors"
    assert isinstance(out["items"], list)        # 面板不崩
    text = json.dumps(out, ensure_ascii=False, allow_nan=False)
    assert "Infinity" not in text and "NaN" not in text


def _by_source(out, src):
    """按来源取项（**不得**用 items[0]：帝修 severity 常高于事件，排序会变）。"""
    return next(r for r in out["items"] if r["source"] == src)


# ---------------------------------------------------------------
# ⑥ POP 维度（宋祚核心：各省 POP 结构不同）
# ---------------------------------------------------------------
def test_event_severity_reflects_pop_structure():
    """同一事件：某路最窘阶级越穷，severity 越高（各省 POP 不同 → 结果不同）。"""
    s = _state()
    route = "陕西路"
    assert route in PREFECTURE_LIST
    s.active_events = [{"title": f"{route}大旱", "message": ""}]
    # 先构造「人均齐平」的 POP 结构（各阶级人均 10 贯）→ 经济落差为 0
    for cls, pop in s.prefectures[route]["pops"].items():
        pop["size"] = max(1, int(pop.get("size") or 0))
        pop["wealth"] = pop["size"] * 10
    first = _by_source(build_situation_readout(s), "event")["severity"]

    # 制造 POP 内部极端落差：把该路"兵"户财富清零（规模不变）
    s.prefectures[route]["pops"]["兵"]["wealth"] = 0
    second = _by_source(build_situation_readout(s), "event")["severity"]
    assert second >= first, "最窘阶级更穷时，严重度不应下降"
    assert second > first, "POP 落差扩大应抬升严重度（体现各省 POP 差异）"


def test_pop_highlights_present_for_region_event():
    s = _state()
    route = "陕西路"
    s.active_events = [{"title": f"{route}大旱", "message": ""}]
    row = _by_source(build_situation_readout(s), "event")
    assert row["region_hint"] == route
    hl = row["pop_highlights"]
    assert hl and len(hl) == 2, "应给出最窘/最丰两行"
    assert any("最窘" in x for x in hl) and any("最丰" in x for x in hl)


def test_pop_highlights_none_when_no_region():
    s = _state()
    s.active_events = [{"title": "天有异象", "message": ""}]
    row = _by_source(build_situation_readout(s), "event")
    assert row["region_hint"] is None
    assert row["pop_highlights"] is None, "无关联地区时不得编造 POP 摘要"


def test_metric_snapshot_covers_all_routes_and_classes():
    """快照须覆盖 20 路 × 6 类 POP（宋祚每路 POP 不同，不得只取省均值）。"""
    s = _state()
    snap, errors = build_metric_snapshot(s, SNAPSHOT_METRICS)
    assert not errors, f"开局不应有缺失：{errors[:3]}"
    wpc = snap["metrics"]["pop.wealth_per_capita"]
    size = snap["metrics"]["pop.size"]
    assert len(size) == len(PREFECTURE_LIST) * 6
    # 各省结果确实不同（否则 POP 维度形同虚设）
    values = [v for v in wpc.values() if v is not None]
    assert len(set(round(float(v), 3) for v in values)) > 1, "各路 POP 人均财富应有差异"


def test_unregistered_metric_is_rejected():
    s = _state()
    snap, errors = build_metric_snapshot(s, ["not.a.metric"])
    assert any("未注册" in e for e in errors)
    assert "not.a.metric" not in snap["metrics"]


def test_registry_declares_required_fields():
    """注册表须声明参数类型/返回类型/必填/缺失策略（规范 §3.2）。"""
    for key, spec in METRICS.items():
        assert spec.return_type, key
        assert spec.missing_policy, key
        assert isinstance(spec.required_arg, bool), key


def test_readout_performance_gate():
    """规范 §11.3 性能门禁：20 路、≤12 条局势时 `build_situation_readout` P95 < 50ms。"""
    import statistics
    import time

    s = _state()
    s.active_events = [{"title": f"{n}大旱", "message": ""}
                       for n in ("河北路", "陕西路", "两浙路", "京东东路", "河东路")]
    s.longterm_effects = [{"name": f"长期诏{i}", "mode": "ongoing", "duration": 12,
                           "effects": {}, "cost": {"treasury": 5000}} for i in range(5)]
    s.active_focus = {"node_key": "k", "name": "考功造册", "status": "in_progress",
                      "progress": 40, "total_turns": 6, "cost_per_month": 12000}
    build_situation_readout(s)                      # 预热（含首次 import 与缓存）
    samples = []
    for _ in range(30):
        t0 = time.perf_counter()
        out = build_situation_readout(s)
        samples.append((time.perf_counter() - t0) * 1000)
    assert len(out["items"]) >= 12, "应有 ≥12 条（5 帝修 + 5 长期诏 + 1 国策 + 5 事件）"
    samples.sort()
    p95 = samples[int(len(samples) * 0.95) - 1]
    assert p95 < 50.0, f"P95={p95:.1f}ms 超出门禁 50ms（中位 {statistics.median(samples):.1f}ms）"


# ---------------------------------------------------------------
# ⑦ POP 的**非经济**维度：六类各自有通道，不得只集中在官吏兵
# ---------------------------------------------------------------
def test_six_pop_channels_are_declared():
    """六类 POP 每类都要有非经济通道（代码事实表），且 primary 必须是已注册 metric。"""
    from content.data import GRAIN_CONSUME_PER_CAPITA
    from core.situation_metrics import CLERK_SENTIMENT_CHANNELS, POP_SENTIMENT_CHANNELS

    assert set(POP_SENTIMENT_CHANNELS) == set(GRAIN_CONSUME_PER_CAPITA), \
        "六类 POP 必须各有非经济通道（农/士绅/工匠/商人/官僚/兵）"
    for cls, ch in POP_SENTIMENT_CHANNELS.items():
        assert ch["primary"] in METRICS, f"{cls} 的 primary 未注册：{ch['primary']}"
        assert ch.get("secondary") in METRICS, f"{cls} 的 secondary 未注册：{ch.get('secondary')}"
        assert ch["source"], cls
        assert ch["label"], cls
    # 吏是**官僚 POP 的子池**，单列而不新开第 7 类 POP
    assert CLERK_SENTIMENT_CHANNELS["primary"] in METRICS
    assert "吏" not in POP_SENTIMENT_CHANNELS


def test_readout_exposes_all_pop_channels():
    s = _state()
    out = build_situation_readout(s)
    pc = out["pop_channels"]
    assert pc, "readout 必须下发 pop_channels"
    nation = pc["nation"]
    for cls in ("农", "士绅", "工匠", "商人", "官僚", "兵", "吏"):
        assert cls in nation, f"nation 截面缺 {cls}"
    assert set(pc["by_route"]) and len(pc["by_route"]) == len(PREFECTURE_LIST)
    for route, row in pc["by_route"].items():
        for cls in ("农", "士绅", "工匠", "商人", "官僚", "兵", "吏"):
            assert cls in row, f"{route} 缺 {cls}"


def test_army_channel_is_computed_and_clamped():
    """兵 POP 的军心通道：士气降/欠饷增 → 督行系数降，且恒在 [FLOOR, 1]。"""
    from core.army_models import ENFORCE_FLOOR, military_channels
    s = _state()
    route = "河北路"
    row = military_channels(s, route)
    assert row is not None, "河北路应有驻军（开局每路禁/厢/乡各一支）"
    first = row["enforcement_mult"]
    assert ENFORCE_FLOOR <= first <= 1.0

    for u in s.army_units:
        if u.station == route:
            u.morale = 0
            u.arrears = 10 ** 7
    second = military_channels(s, route)["enforcement_mult"]
    assert second < first, "军心崩、欠饷重时督行系数必须下降"
    assert second >= ENFORCE_FLOOR


def test_non_economic_channels_raise_event_severity():
    """非经济维度必须能抬升事件严重度：军心降 / 吏怨升 → 同一事件更紧迫。"""
    s = _state()
    route = "河北路"
    s.active_events = [{"title": f"{route}大旱", "message": ""}]
    base = _by_source(build_situation_readout(s), "event")["severity"]

    for u in s.army_units:
        if u.station == route:
            u.morale = 0
    for p in s.prefectures.values():
        p.setdefault("clerks_detail", {})["grievance"] = 90.0
    worse = _by_source(build_situation_readout(s), "event")["severity"]
    assert worse > base, "吏怨与军心恶化后，事件严重度不得持平或下降"


def test_execution_channels_follow_clerks_and_army():
    """执行通道：吏怨/把持上升 → 政令折扣下降；execution_channels 如实下发且不伪造执行率。"""
    s = _state()
    s.active_focus = {"node_key": "k", "name": "国策甲", "status": "in_progress",
                      "progress": 30, "total_turns": 6, "cost_per_month": 1}
    first = _by_source(build_situation_readout(s), "focus")["execution_channels"]
    assert first is not None, "在办大策必须下发执行通道"
    assert "clerks_mult" in first and "military_mult" in first
    assert first["combined_mult"] is not None

    for p in s.prefectures.values():
        p.setdefault("clerks_detail", {})["grip"] = 0.8
        p["clerks_detail"]["grievance"] = 80.0
    second = _by_source(build_situation_readout(s), "focus")["execution_channels"]
    assert second["clerks_mult"] < first["clerks_mult"], "把持度上升必须压低吏治折扣"
    assert second["combined_mult"] < first["combined_mult"]

    # 帝修不是「执行」对象：不得假装有执行度
    leg = [r for r in build_situation_readout(s)["items"] if r["source"] == "legacy"]
    assert leg and all(r["execution_channels"] is None for r in leg)


# ---------------------------------------------------------------
# ⑧ 利益集团 ⊆ POP 阶级（不是与 POP 并列的独立实体）
# ---------------------------------------------------------------
def test_every_faction_declares_pop_subset():
    """每个集团都必须声明 POP 基本盘与**子集**关系（subset_of ⊆ pop_classes）。"""
    from content.data import FACTION_NAMES, FACTION_POP_BASIS
    from core.faction_basis import POP_CLASS_NAMES, SUBSET_KINDS, validate_faction_basis

    for name in FACTION_NAMES:
        spec = FACTION_POP_BASIS.get(name)
        assert spec is not None, f"{name} 未声明 POP 基本盘"
        assert not validate_faction_basis(name, spec), \
            f"{name} 归属声明非法：{validate_faction_basis(name, spec)}"
        assert set(spec["subset_of"]) <= set(spec["pop_classes"])
        assert set(spec["subset_of"]) <= set(POP_CLASS_NAMES)
        assert spec["subset_kind"] in SUBSET_KINDS


def test_missing_pop_basis_is_rejected():
    """没有 POP 基本盘的集团不予登记（否则回到「无源影响力」）。"""
    from core.faction_basis import validate_faction_basis
    assert validate_faction_basis("野党", None)
    assert validate_faction_basis("野党", {"pop_classes": ["官僚"]})          # 缺 subset_of/kind
    assert validate_faction_basis("野党", {"pop_classes": ["兵"], "subset_of": ["士绅"],
                                           "subset_kind": "national"})        # 子集不在母集内
    ok = {"pop_classes": ["兵"], "subset_of": ["兵"], "subset_kind": "route",
          "routes": ["陕西路"]}
    assert not validate_faction_basis("西军", ok)


def test_jungong_is_subset_of_soldier_and_official_pop():
    """军功集团 = 兵与官僚 POP 的边域**子集**（含以军功晋身的文官）。

    2026-09-19 口径调整（用户定稿）：「西军集团」更名「军功集团」，基盘由
    纯兵 POP 扩为 **兵 + 边路官僚**——军功补官、军前参议、经略安抚等文官因此可入；
    兵系仍只来自兵 POP（不得因此新开兵额账本）。展示仍须给母集占比，不得并列。
    """
    from core.faction_basis import build_faction_channels
    s = _state()
    fc = build_faction_channels(s)
    assert fc["declared"], fc["basis_errors"]
    xijun = fc["factions"]["西军集团"]
    b = xijun["basis_readout"]
    assert b["subset_of"] == ["兵", "官僚"] and b["subset_kind"] == "faction"
    assert b["troops"] > 0
    assert b["parent_pop_size"] > b["pop_size"], "西军只是兵 POP 的一部分"
    assert 0 < b["share"] < 1
    assert "兵" in b["subset_note"] and "%" in b["subset_note"]


def test_readout_exposes_faction_channels_and_emerging():
    """readout 必须下发 faction_channels；在场改革催生的新集团必须带 pop_basis 且合法。"""
    s = _state()
    s.longterm_effects = [{"name": "方田均税", "mode": "ongoing", "duration": 12,
                           "effects": {"land_survey": 0.05}, "cost": {}}]
    out = build_situation_readout(s)
    fc = out["faction_channels"]
    assert fc["factions"], "必须逐派下发 POP 基本盘读数"
    emerging = fc["emerging"]
    assert emerging and emerging[0]["reform"] == "land_survey"
    for item in emerging:
        for f in item["emergent"]:
            assert f["pop_basis"], "新集团必须带 pop_basis（POP 归属声明）"
            assert not f["basis_errors"], f["basis_errors"]
    # 改革受益/受损必须落在具体 POP 类上（不写空话）
    assert emerging[0]["gain"] and emerging[0]["lose"]


