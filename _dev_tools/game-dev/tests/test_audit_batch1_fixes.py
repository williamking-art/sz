# -*- coding: utf-8 -*-
"""批次 1 回归：M1 / M3 / M4 / M5 / M6 / M7 / M9（2026-10-01 全审落地）。

每条用例对应一个已修缺陷，含**守恒/脱敏**断言（POP 挂载律 + 铁律「隐藏值不外泄」）。
"""
import json
import math
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.game_state import GameState            # noqa: E402
from core.legacy_mechanic import init_legacies     # noqa: E402
from core import money as M                       # noqa: E402
from core import save_load as SL                  # noqa: E402
from core import settlement as S                  # noqa: E402
from core.faction_split import split_of           # noqa: E402


@pytest.fixture()
def state():
    s = GameState("史实")
    init_legacies(s)
    return s


# ---------------------------------------------------------------- M1 存粮守恒
def test_m1_tax_grain_only_actual_goes_to_storage(state):
    """M1：本色征粮只把**实征**记入 `storage`，仓中无粮时不得凭空增仓。

    旧实现 `_nong["grain"] = max(0, grain - _st)` 后仍 `storage += _st + _gt`
    → 缺口部分变成等额仓粮（实测 +899,480 石/月）。

    直接调 `_settle_land_local`：避免整月流水里「先收成、后征税」把缺口补掉，
    从而无法确定性地触发征不足的分支。
    """
    from core.settlement_econ import _settle_land_local
    p = next(iter(state.prefectures.values()))
    nong = p["pops"]["农"]
    nong["grain"] = 0# 存粮清零 → 本色田赋实征必为 0
    p["self_farm_land"] = 0        # 无自耕田 → 无应征
    storage_before = int(p.get("storage", 0) or 0)
    log = []
    _settle_land_local(state, log)
    storage_after = int(p.get("storage", 0) or 0)
    assert storage_after == storage_before, "存粮为 0 时不得有任何粮入廪（凭空增仓）"
    assert int(nong["grain"]) == 0


def test_m1_storage_never_exceeds_tax_collected(state):
    """M1 强化：`_st/_gt` 名义值不得原样进 `storage`（征不足时 storage 增量 < 名义税）。"""
    # 把所有路农存粮清零 → 实征必为 0 → storage 不应因田赋而增长
    for pref in state.prefectures.values():
        for cls in ("农", "士绅"):
            if cls in pref.get("pops", {}):
                pref["pops"][cls]["grain"] = 0
    before = sum(int(p.get("storage", 0) or 0) for p in state.prefectures.values())
    S.run_monthly_settlement(state)
    after = sum(int(p.get("storage", 0) or 0) for p in state.prefectures.values())
    # 存粮为 0 时，田赋这一路不应有任何实征入仓
    assert after - before <= 0


# ---------------------------------------------------------------- M3 转账不毁钱
def test_m3_transfer_to_missing_pop_returns_zero_and_keeps_money(state):
    """M3：目标 POP 不存在时**不动 src** 并返回 0（旧实现销毁钱却返回 moved）。"""
    road = next(iter(state.prefectures))
    before_treasury = int(state.treasury)
    moved = state.transfer_money("treasury", f"pop:{road}:不存在的阶层", 100_000)
    assert moved == 0
    assert int(state.treasury) == before_treasury, "目标不可写时国库不得被扣款"


def test_m3_transfer_normal_path_still_works(state):
    """M3 反向：目标存在时照常划转（不因加固而退化）。"""
    road = next(iter(state.prefectures))
    key = f"pop:{road}:农"
    before_tre = int(state.treasury)
    before_pop = int(state.prefectures[road]["pops"]["农"]["wealth"])
    moved = state.transfer_money("treasury", key, 1_000)
    assert moved == 1_000
    assert int(state.treasury) == before_tre - 1_000
    assert int(state.prefectures[road]["pops"]["农"]["wealth"]) == before_pop + 1_000


def test_m3_transfer_to_missing_road(state):
    """M3：路不存在同样不得毁钱。"""
    before = int(state.treasury)
    assert state.transfer_money("treasury", "pop:不存在的路:农", 50_000) == 0
    assert int(state.treasury) == before


# ---------------------------------------------------------------- M4 非有限值
def test_m4_normalize_drops_nonfinite_and_bool():
    """M4：AI 拟旨 effects 归一必须丢弃 NaN/±Inf/布尔。"""
    from ai.client_utils import _normalize_decree_effects
    assert _normalize_decree_effects({"commerce_tax": float("nan")}) is None
    assert _normalize_decree_effects({"commerce_tax": float("inf")}) is None
    assert _normalize_decree_effects({"commerce_tax": float("-inf")}) is None
    assert _normalize_decree_effects({"commerce_tax": True}) is None
    # 正常值与数字串仍应通过（不因加固而退化）
    assert _normalize_decree_effects({"commerce_tax": 0.13}) == {"commerce_tax": 0.13}
    assert _normalize_decree_effects({"commerce_tax": "0.13"}) == {"commerce_tax": 0.13}


def test_m4_apply_decree_effect_survives_nan(state):
    """M4：结算侧兜底 —— 直接注入 NaN/Inf 不得抛异常、不得改税率。"""
    from core.settlement_decree import _apply_decree_effect
    log = []
    before_tax = float(state.commerce_tax_rate)
    _apply_decree_effect(state, {"title": "脏诏令", "effects": {
        "commerce_tax": float("nan"), "treasury": float("inf"),
        "prestige": float("nan"), "population_satisfaction": float("inf"),
    }}, log)
    assert float(state.commerce_tax_rate) == before_tax, "NaN 不得把税率钳到边界"
    assert any("非有限值" in m or "非数值" in m for m in log), "丢弃须留日志"


def test_m4_apply_decree_effect_booleans_dropped(state):
    """M4：布尔不得被当作 1/0 的数值效果。"""
    from core.settlement_decree import _apply_decree_effect
    before_tre = int(state.treasury)
    _apply_decree_effect(state, {"title": "布尔诏令", "effects": {"treasury": True}}, [])
    assert int(state.treasury) == before_tre


# ---------------------------------------------------------------- M5 台账闭合
def test_m5_levy_registered_in_money_flow(state):
    """M5：枢密征发军资必须登记台账，否则对账残差把登记 bug 误报成造币。"""
    from core import settlement_military as SM
    from core.settlement_common import _P1_LEVY_COST
    levy_cost = int(_P1_LEVY_COST.get("大", 100_000))
    state._military_ai = {"levy": "大", "army": "无", "train": "无", "att": "无"}
    state.treasury = 50_000_000
    M.audit_step(state)
    before_tre = int(state.treasury)
    log = []
    SM._settle_military_diplomacy(state, log)
    # 前置：确认征发分支真的走了（否则下面的残差断言是空转）
    assert before_tre - int(state.treasury) == levy_cost, "征发军资未发生，用例空转"
    rec = M.audit_step(state)
    resid = rec.get("residual")
    assert resid is None or abs(float(resid)) < 1.0, f"征发后残差应为 0，实得 {resid}"
    assert int(rec.get("burned") or 0) >= levy_cost, "军资支出应计入 burned（真实离账）"


def test_m5_long_run_residual_zero(state):
    """M5 端到端：连跑 12 月，货币对账残差恒 0（回归前 M5 单独造成 −200,000/月）。"""
    M.audit_step(state)
    for _ in range(12):
        S.run_monthly_settlement(state)
        rec = M.audit_step(state)
        resid = rec.get("residual")
        assert resid is None or abs(float(resid)) < 1.0, f"月度残差非零：{resid}"


# ---------------------------------------------------------------- M6/M7 存档往返
@pytest.fixture()
def tmp_save_dir(tmp_path, monkeypatch):
    # 第七包起 `_slot_path` 住在 `core.foundation.persistence.slots`，它读的是**那个模块**的
    # 模块级 `SAVE_DIR`；只 patch `core.save_load` 已不再决定落盘目录（全量实测红过 3 例）。
    monkeypatch.setattr(SL, "SAVE_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr("core.foundation.persistence.slots.SAVE_DIR", str(tmp_path),
                        raising=False)
    return str(tmp_path)


def test_m6_resources_roundtrip(tmp_save_dir, state):
    """M6：`resources` 存档写了就必须读得回（旧实现只重建默认骨架，数值归零）。"""
    state.resources["盐"] = {"stock": 424_242, "cap": 50_000}
    assert SL.save_game(state, 1)
    loaded = SL.load_game(1)
    assert loaded is not None
    assert int(loaded.resources["盐"]["stock"]) == 424_242
    assert int(loaded.resources["盐"]["cap"]) == 50_000


def test_m6_resources_bad_shape_falls_back(tmp_save_dir, state):
    """M6：坏结构不得炸档，按缺省补齐（缺失≠0 但结构坏=不可用）。"""
    assert SL.save_game(state, 2)
    path = os.path.join(tmp_save_dir, "slot_2.json")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    raw["resources"] = {"盐": "不是字典"}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False)
    loaded = SL.load_game(2)
    assert loaded is not None
    assert isinstance(loaded.resources.get("盐"), dict)
    assert "stock" in loaded.resources["盐"]


def test_m7_faction_split_persisted(tmp_save_dir, state):
    """M7：`faction_split` 必须进存档并原样读回（否则读档抹平党争演化）。"""
    for _ in range(4):
        S.run_monthly_settlement(state)
    before = {c: dict(split_of(state, c)) for c in ("兵", "士绅", "商人", "官僚")}
    assert SL.save_game(state, 3)
    path = os.path.join(tmp_save_dir, "slot_3.json")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    assert "faction_split" in raw, "存档字典缺 faction_split 键"
    loaded = SL.load_game(3)
    for cls, exp in before.items():
        got = dict(split_of(loaded, cls))
        assert set(got) == set(exp), f"{cls} 派系键集合不一致"
        for k, v in exp.items():
            assert math.isclose(got[k], v, rel_tol=1e-12, abs_tol=1e-12), f"{cls}.{k} 往返不一致"


def test_m7_strip_keeps_pop_class_layer(state):
    """M7：旧名清洗只清**内层**集团名，不得把外层 POP 阶层键当废弃集团名删掉。"""
    from core.save_load_util import _strip_unknown_faction_keys
    state.faction_split = {"士绅": {"中立派": 0.5, "宦官集团": 0.5}}
    dropped = _strip_unknown_faction_keys(state)
    assert "士绅" in state.faction_split, "外层 POP 阶层键不得被删"
    assert "宦官集团" in dropped, "内层废弃集团名应被清理"
    assert "中立派" in state.faction_split["士绅"], "合法集团名不得被删"


def test_m7_strip_cleans_decree_stances(state):
    """M7：诏令 `faction_stances` 的旧名仍应被清理（该路径原本是对的，别回归）。"""
    from core.save_load_util import _strip_unknown_faction_keys
    state.pending_decrees = [{"title": "旧诏", "faction_stances": {"新党": 1.0, "东南士人": 0.5}}]
    _strip_unknown_faction_keys(state)
    st = state.pending_decrees[0]["faction_stances"]
    assert "新党" in st
    assert "东南士人" not in st


# ---------------------------------------------------------------- M9 脱敏旁路
def _snapshot_with_sentinels():
    """构造带哨兵真值的 state（未清丈）。"""
    from backend.server import _state_to_dict
    s = GameState("史实")
    init_legacies(s)
    mk = next(iter(s.loyalty))
    s.loyalty[mk] = 73.5
    s.corruption[mk] = 0.4213
    road = next(iter(s.prefectures))
    s.prefectures[road]["pops"]["农"]["hidden"] = 123_456
    s.land["hidden_households"] = 123_456 // 4      # 派生镜像（×4 可还原真值）
    s.minister_estate = {mk: {"wealth": 987_654}}
    return s, _state_to_dict(s), road


def test_m9_hidden_households_not_leaked():
    """M9：`land.hidden_households` 是隐户真值的精确派生（×4 可还原），未清丈不得下发。"""
    _s, snap, _road = _snapshot_with_sentinels()
    assert "hidden_households" not in (snap.get("land") or {})


def test_m9_hidden_land_true_value_not_leaked():
    """M9：未清丈路的 `hidden_land`（隐田真值）不得随快照下发。"""
    _s, snap, _road = _snapshot_with_sentinels()
    leaked = [r for r, p in (snap.get("prefectures") or {}).items()
              if isinstance(p, dict) and "hidden_land" in p]
    assert not leaked, f"未清丈仍下发隐田真值：{leaked[:3]}"


def test_m9_true_values_absent_from_payload():
    """M9 端到端：真值与可反推的派生值都不得出现在整份快照 JSON 里。"""
    _s, snap, _road = _snapshot_with_sentinels()
    blob = json.dumps(snap, ensure_ascii=False)
    assert "123456" not in blob
    assert str(123_456 // 4) not in blob
    assert "73.5" not in blob and "0.4213" not in blob
    assert "987654" not in blob


def test_m9_existing_desensitization_intact():
    """M9 回归：既有脱敏（忠诚/贪腐档位化、未清丈农.hidden 剔除）不得被破坏。"""
    _s, snap, road = _snapshot_with_sentinels()
    assert set(snap.get("loyalty", {}).values()) <= {
        "死忠", "忠顺", "恭谨", "敷衍", "离心", "怨望"}
    assert set(snap.get("corruption", {}).values()) <= {
        "巨贪", "贪墨", "平庸", "尚廉", "清廉", "廉洁"}
    assert "hidden" not in (snap["prefectures"][road]["pops"]["农"])
    assert set(snap.get("minister_estate", {}).values()) == {"巨富"}