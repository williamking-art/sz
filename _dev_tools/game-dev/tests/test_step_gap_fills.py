# -*- coding: utf-8 -*-
"""结算步体检补测：`legacy_mechanic` / `focus_mechanic` / `institution` 的**未测分支**。

覆盖率实测（2026-09-18，443 例全跑）暴露的缺口：
  · `core/legacy_mechanic.py` 覆盖 **23.8%**（帝国修正效果与消除条件几乎未测）
  · `core/focus_mechanic.py` 覆盖 69.5%（`_apply_branch_effect` 缺 10/17、`cancel_focus`/`unlock_focus`/`focus_summary` 未测）
  · `core/institution.py` 覆盖 80.5%（`apply_reform` 的异常/非数值分支未测）

本文件只补**有行为价值**的分支，不追覆盖率数字。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core import institution as inst  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core import legacy_mechanic as lm  # noqa: E402
from core import focus_mechanic as fm  # noqa: E402


# ---------------------------------------------------------------- legacy_mechanic
def test_legacy_effects_do_not_corrupt_cumulative_statistics():
    """帝国修正是**纯叙事标签**：不得改累计收支统计（否则面板/AI 拿到注水数字）。

    缺陷（2026-09-18 结算步专项检查）：冗官冗费/隐田蔽课/辽夏边患原实现分别
    `total_expenditure += 20000` / `total_income -= 15000` / `total_expenditure += 30000`
    —— 一分钱没动却污染统计量，与项目自身在 `focus_mechanic` 的 B7 修复同类。
    """
    s = GameState("史实")
    lm.init_legacies(s)
    inc0 = int(s.statistics.get("total_income", 0))
    exp0 = int(s.statistics.get("total_expenditure", 0))
    tre0 = s.treasury
    log = []
    lm.settle_legacies(s, log)
    assert int(s.statistics.get("total_income", 0)) == inc0, "帝国修正污染了累计收入统计"
    assert int(s.statistics.get("total_expenditure", 0)) == exp0, "帝国修正污染了累计支出统计"
    # 辽夏边患/冗官冗费不再凭空扣国库（真实成本由军俸/官俸承担）
    assert s.treasury == tre0, "帝国修正不应直接改国库（成本在子系统中）"


def test_legacy_effect_handlers_are_noop_on_numbers_but_log():
    """三个"标签型"修正：只写日志、不改数值；而真效果型（新党/花石纲）仍改民心。"""
    s = GameState("史实")
    log = []
    lm._eff_redundant_officials(s, log)
    lm._eff_hidden_land(s, log)
    lm._eff_liao_xia_border(s, log)
    assert len(log) == 3, "标签型修正必须留下叙事日志（否则玩家看不到历史包袱）"
    for k in ("total_income", "total_expenditure"):
        assert s.statistics.get(k, 0) == 0, f"{k} 被标签型修正改动"

    mood0 = s.population_satisfaction
    lm._eff_new_fund(s, [])
    assert s.population_satisfaction == max(0, mood0 - 1), "新党专权应真实损民心"


def test_legacy_clear_conditions_and_progress():
    """消除条件判定：满足则标记 cleared，并从 active 列表移出。"""
    s = GameState("史实")
    lm.init_legacies(s)
    assert len(lm.active_legacies(s)) == len(lm.LEGACY_DEFS)
    assert lm.cleared_legacies(s) == []
    # 冗官冗费消除条件 = 变法节流已施行
    s.waste_reform["active"] = True
    log = []
    lm.settle_legacies(s, log)
    cleared = {x["key"] for x in lm.cleared_legacies(s)}
    assert "redundant_officials" in cleared, "满足消除条件后未标记清除"
    assert "redundant_officials" not in {x["key"] for x in lm.active_legacies(s)}


# ---------------------------------------------------------------- focus_mechanic
def test_focus_start_progress_complete_and_unlock():
    """国策全生命周期：立案 → 推进（扣度支）→ 满期大成 → 解锁记录。"""
    s = GameState("史实")
    s.treasury = 5_000_000
    ok = fm.start_focus(s, "govern", "g1_centralize")
    assert ok.get("ok"), f"立案失败：{ok}"
    spec = fm.FOCUS_TREE["govern"]["nodes"]["g1_centralize"]
    for _ in range(int(spec["duration"])):
        fm.settle_focus(s, [])
    node = s.focus_tree["govern"]["nodes"]["g1_centralize"]
    assert node.get("unlocked"), "满期后未解锁"
    assert s.active_focus is None, "大成后应清空在办国策"


def test_focus_cancel_refunds_nothing_but_clears():
    """取消国策：清空在办且不推进进度（不退还已支度支）。"""
    s = GameState("史实")
    s.treasury = 5_000_000
    fm.start_focus(s, "govern", "g1_centralize")
    fm.settle_focus(s, [])              # 推进 1 月
    prog = s.active_focus.get("elapsed_turns")
    res = fm.cancel_focus(s)
    assert s.active_focus is None, "取消后仍在办"
    assert prog >= 1 and res is not None


def test_focus_locked_and_invalid_targets_rejected():
    """非法分支/节点应被拒绝（不静默立案）。"""
    s = GameState("史实")
    assert not fm.start_focus(s, "不存在的分支", "x").get("ok")
    assert not fm.start_focus(s, "govern", "不存在的节点").get("ok")


def test_focus_branch_effects_touch_real_fields():
    """已解锁大策的分支效果必须落在**真实字段**（不是假效果）。"""
    from core.focus_mechanic import _apply_branch_effect
    s = GameState("史实")
    s.waste_reform = {"active": False, "savings": 0}
    fort0 = next(iter(s.defense_lines.values()))["fortification"]
    _apply_branch_effect(s, [], "govern", "x", {})
    assert int(s.waste_reform["savings"]) == 5000, "政务分支未提升真实节流额度"
    _apply_branch_effect(s, [], "military", "x", {})
    assert next(iter(s.defense_lines.values()))["fortification"] == min(100, fort0 + 1)
    tech0 = s.tech["level"]
    _apply_branch_effect(s, [], "science", "x", {})
    assert s.tech["level"] == min(100, tech0 + 1)
    hid0 = s.land.get("hidden_rate", 0.35)
    _apply_branch_effect(s, [], "tax", "x", {})
    assert s.land["hidden_rate"] == max(0.05, hid0 - 0.01)


def test_focus_summary_shape():
    """国策读数面：`focus_summary` 返回可序列化摘要（面板用）。"""
    s = GameState("史实")
    fm.start_focus(s, "govern", "g1_centralize")
    summ = fm.focus_summary(s)
    assert isinstance(summ, dict) and summ, "focus_summary 应返回非空摘要"


# ---------------------------------------------------------------- institution
def test_institution_apply_reform_rejects_bad_entries_per_item():
    """逐项拒绝：未知键 / 非数值 → 该项拒绝，其余照常落地（不整单回滚）。"""
    s = GameState("史实")
    base = inst.get(s, "rank_up_mult")
    log = inst.apply_reform(s, {
        "不存在的参数": 1.0,        # 未知键 → 拒绝
        "rank_up_mult": "-中",      # 合法档位词 → 落地
    })
    assert any("不在白名单" in x for x in log), "未知键未被拒绝"
    assert inst.get(s, "rank_up_mult") < base, "合法项未落地"
    # 值既非数字也非可解析档位词 → 该项拒绝
    log2 = inst.apply_reform(s, {"yinben_mult": []})
    assert any("须为数字或档位词" in x for x in log2), "非法值类型未被拒绝"


def test_institution_get_falls_back_on_corrupt_state():
    """参数表被外部写坏（非 dict / 非数值）时，`get` 必须回退默认值而不抛。"""
    s = GameState("史实")
    s.institution_params = "坏值"
    assert inst.get(s, "clerk_pay_mult") == 1.0
    s.institution_params = {"clerk_pay_mult": "坏值"}
    assert inst.get(s, "clerk_pay_mult") == 1.0
    assert inst.get(s, "完全未知的键", fallback=0.7) == 0.7


# ================================================================
# 资金"无对手方"风险点（测试体检伴随发现的一整类：账本镜像覆盖了步骤，
# 但**没有任何用例造出触发状态** → 步骤内的钱路从未被执行，"镜像覆盖 ≠ 路径覆盖"）
# ================================================================
def _pop_wealth(s):
    return sum(int(pp.get("wealth", 0) or 0)
               for p in s.prefectures.values() for pp in p["pops"].values())


def test_project_coin_is_conserving_transfer():
    """工程款（`cost_coin`）必须守恒：国库照扣，但钱进民间 POP → `ΔM_ALL == 0`。

    缺陷：原为裸 `state.treasury -= coin_need`（实测单项工程 500,000 贯 → ΔM_ALL = −500,000）。
    该路径此前**无任何用例触发**（回放里 `state.projects` 恒空），故躲过了全部账本断言。
    """
    from core import money as _money
    from core.settlement_steps import _settle_projects

    s = GameState("史实")
    s.treasury = 5_000_000
    s.resources.setdefault("铁", {"stock": 10_000, "cap": 100_000})
    s.projects["p1"] = {
        "name": "测试工程", "progress": 90, "speed": 20, "done": False,
        "cost_material": {"铁": 100}, "cost_coin": 500_000,
        "output": {"granary_cap_add": 100_000},
    }
    w0, m0, tre0 = _pop_wealth(s), _money.m_all(s), s.treasury
    _settle_projects(s, [])

    assert s.projects["p1"]["done"] is True, "工程未推进完工（用例前提）"
    assert tre0 - s.treasury == 500_000, "财政成本丢失（国库未扣）"
    assert _pop_wealth(s) - w0 == 500_000, "工程款未回流民间（无对手方销毁）"
    assert _money.m_all(s) - m0 == 0, "工程款破坏了货币守恒"
    assert s.resources["铁"]["stock"] == 9_900, "材料未扣"


def test_emperor_action_cost_is_conserving_transfer():
    """皇帝个人行动的度支必须守恒（宫廷支出回流民间）。

    缺陷：原为裸扣 `change_treasury(-paid)` —— 皇帝挥霍的钱凭空消失。
    用「宫里·公开·宴游享乐」（base_cost 80,000，fund=treasury）驱动。
    """
    from core import money as _money
    from core.settlement_steps import _settle_emperor_personal

    s = GameState("史实")
    s.treasury = 5_000_000
    s.imperial_action = {"location": "宫里", "mode": "公开", "action": "宴游享乐"}
    w0, m0, tre0 = _pop_wealth(s), _money.m_all(s), s.treasury
    _settle_emperor_personal(s, [])

    assert tre0 - s.treasury == 80_000, f"行动度支未按 base_cost 扣除：{tre0 - s.treasury}"
    assert _pop_wealth(s) - w0 == 80_000, "行动度支未回流民间（无对手方销毁）"
    assert _money.m_all(s) - m0 == 0, "行动度支破坏了货币守恒"


def test_treaty_dowry_registered_as_external_outflow():
    """和亲嫁妆是**外流**（钱离开宋境）：内帑扣减 + 必须登记为 `burn`。

    缺陷：`state.imperial_treasury -= dowry` 未登记 → 月度对账会把它报成"未解释残差"。
    """
    from core.diplomacy_treaty import apply_treaty
    from core.money import take_flow

    s = GameState("史实")
    s.imperial_treasury = 5_000_000
    _ = take_flow(s)                       # 清空既有台账，隔离本次
    imp0 = s.imperial_treasury
    res = apply_treaty(s, "辽", "和亲", {"tier": "中"}, year=s.year, month=s.month)

    assert res.get("ok"), f"和亲未成立：{res}"
    _spent = imp0 - s.imperial_treasury
    assert _spent > 0, "嫁妆未从内帑支出"
    flow = take_flow(s)
    assert flow.get("burned", 0) == _spent, \
        f"嫁妆未登记为外流（burn）：登记 {flow.get('burned')} vs 实支 {_spent}"
    assert any("嫁妆" in n for n in flow.get("notes", [])), "外流台账缺少嫁妆备注"


def test_state_grain_trade_conserves_both_ledgers():
    """政府粮食交易必须**钱粮双向守恒**（买/卖两条路）。

    这是 `settlement_steps.py` 中覆盖最差的函数（体检时 70/72 语句未覆盖）——
    它同时动国库、太仓与民间六类 POP 的钱粮，一旦破守恒就是双向漏账。
    """
    from core.settlement_steps import _state_grain_trade

    for direction in ("buy", "sell"):
        s = GameState("史实")
        s.treasury = 3_000_000
        s.granary = 5_000_000
        # sell 需要民间有钱；buy 需要民间有粮
        for p in s.prefectures.values():
            for pp in p["pops"].values():
                pp["wealth"] = max(int(pp.get("wealth", 0) or 0), 100_000)
                pp["grain"] = max(int(pp.get("grain", 0) or 0), 100_000)
        m0 = sum(int(pp.get("wealth", 0) or 0) for p in s.prefectures.values()
                 for pp in p["pops"].values()) + s.treasury
        g0 = sum(int(pp.get("grain", 0) or 0) for p in s.prefectures.values()
                 for pp in p["pops"].values()) + s.granary
        got_g, got_m = _state_grain_trade(s, 10_000, direction, 1.0, [], "测试")
        m1 = sum(int(pp.get("wealth", 0) or 0) for p in s.prefectures.values()
                 for pp in p["pops"].values()) + s.treasury
        g1 = sum(int(pp.get("grain", 0) or 0) for p in s.prefectures.values()
                 for pp in p["pops"].values()) + s.granary
        assert got_g > 0 and got_m > 0, f"{direction} 未成交（用例前提不成立）"
        assert m1 - m0 == 0, f"{direction} 钱账本不守恒：{m1 - m0:+,}"
        assert g1 - g0 == 0, f"{direction} 粮账本不守恒：{g1 - g0:+,}"
        assert s.treasury >= 0 and s.granary >= 0, f"{direction} 出现负数余额"


def test_state_grain_trade_respects_caps():
    """买/卖的**硬上限**：钱只花到国库/买方可支付力为止，粮不超仓容、不超民间存粮。"""
    from core.settlement_steps import _state_grain_trade

    # buy：国库很穷 → 只买得起一点点，且不穿底
    s = GameState("史实")
    s.treasury = 1_000
    for p in s.prefectures.values():
        for pp in p["pops"].values():
            pp["grain"] = 10_000
    got_g, got_m = _state_grain_trade(s, 10_000_000, "buy", 1.0, [], "测试")
    assert got_m <= 1_000, f"买入超国库可付额：付 {got_m}"
    assert s.treasury >= 0, "买入把国库扣成负数"
    assert got_g == got_m, "粮钱未按价对应"
    # 且不超太仓余量
    s2 = GameState("史实")
    s2.treasury = 10_000_000
    s2.granary = s2.granary_cap - 100          # 几乎满仓
    for p in s2.prefectures.values():
        for pp in p["pops"].values():
            pp["grain"] = 1_000_000
    g2, m2 = _state_grain_trade(s2, 10_000_000, "buy", 1.0, [], "测试")
    assert g2 <= 100, f"买入超太仓余量：{g2}"
    assert s2.granary <= s2.granary_cap, "太仓超容"

    # sell：民间很穷 → 卖不出多少（不把买家扣成负）
    s3 = GameState("史实")
    s3.granary = 1_000_000
    s3.treasury = 0
    for p in s3.prefectures.values():
        for pp in p["pops"].values():
            pp["wealth"] = 500
    g3, m3 = _state_grain_trade(s3, 10_000_000, "sell", 1.0, [], "测试")
    assert m3 <= 500 * sum(len(p["pops"]) for p in s3.prefectures.values()) + 10
    assert s3.treasury >= 0
    for p in s3.prefectures.values():
        for pp in p["pops"].values():
            assert int(pp.get("wealth", 0) or 0) >= 0, "卖出把民间财富扣成负数"
