# -*- coding: utf-8 -*-
"""M66 作坊货主登记（产权落点）—— 定向回归。

锁定：划分规则**有据可查**（逐类型给依据）· **不臆造**（未登记类型 / 判不出路 ⇒ `defined=False`）·
**幂等且不覆盖**既有 `owner`/`owner_ref` · 词表复用既有形式（`local:<路>` / `pop:<路>:商人`）·
**零数值变化**（只写 `workshops[wid]` 的三个字段）· 真实新局 **107 座全部登记、0 未定义**。
"""

import copy
import types

from core.domains.economy import workshop_owner as wo


def _state(workshops=None, routes=("京畿路",)):
    st = types.SimpleNamespace()
    st.workshops = workshops if workshops is not None else {}
    st.prefectures = {r: {"name": r, "seats": {"%s|首府" % r: {"pops": {}}}} for r in routes}
    return st


# ------------------------------------------------------------------ ① 规则与解析
def test_rules_are_evidence_based():
    assert set(wo.OWNER_BY_TYPE) >= {"酒坊", "畜栏", "麻坊", "丝坊"}
    for wtype, (_kind, _own, basis) in wo.OWNER_BY_TYPE.items():
        assert basis, f"{wtype} 缺依据"
    assert wo.OWNER_BY_TYPE["酒坊"][1] == "官营"
    assert wo.OWNER_BY_TYPE["畜栏"][1] == "民营"
    # M67 补漏：配方面实有 6 型 ⇒ 规则表必须**全覆盖**（否则将来建坊会 owner-undefined）
    from content.data_constants import WORKSHOP_RECIPES
    missing = set(WORKSHOP_RECIPES) - set(wo.OWNER_BY_TYPE)
    assert missing == set(), f"配方面有而规则表缺：{missing}"
    assert wo.OWNER_BY_TYPE["造纸坊"][1] == "民营"
    assert wo.OWNER_BY_TYPE["糖坊"][1] == "民营"


def test_owner_for_uses_existing_vocabulary():
    st = _state()
    r = wo.owner_for(st, "酒坊_京畿路_1")
    assert r["defined"] is True and r["owner"] == "local:京畿路" and r["owner_kind"] == "local"
    m = wo.owner_for(st, "麻坊_京畿路_2")
    assert m["owner"] == "pop:京畿路:商人" and m["owner_kind"] == "pop:商人"


def test_owner_for_refuses_to_guess():
    st = _state()
    r = wo.owner_for(st, "无名坊_京畿路_1")
    assert r["defined"] is False and "未登记归属规则" in r["reason"]
    r2 = wo.owner_for(st, "酒坊_不存在的路_1")
    assert r2["defined"] is False and "判不出所属路" in r2["reason"]
    assert wo.owner_for(st, 123)["defined"] is False


# ------------------------------------------------------------------ ② 幂等且不覆盖
def test_assign_is_idempotent_and_never_overwrites():
    st = _state({"酒坊_京畿路_1": {"name": "酒坊", "active": True},
                 "麻坊_京畿路_2": {"name": "麻坊", "active": True}})
    rep = wo.assign_owners(st)
    assert rep["assigned"] == 2 and rep["kept"] == 0
    assert st.workshops["酒坊_京畿路_1"]["owner"] == "local:京畿路"
    # 再跑一次 ⇒ 全部 kept（幂等）
    assert wo.assign_owners(st)["assigned"] == 0
    # 人为改一个既有值 ⇒ **不得被覆盖**
    st.workshops["酒坊_京畿路_1"]["owner"] = "imperial"
    wo.assign_owners(st)
    assert st.workshops["酒坊_京畿路_1"]["owner"] == "imperial"


def test_unknown_type_is_skipped_not_guessed():
    st = _state({"怪坊_京畿路_1": {"name": "怪坊"}})
    rep = wo.assign_owners(st)
    assert rep["assigned"] == 0 and rep["undefined"] == 1
    assert "owner" not in st.workshops["怪坊_京畿路_1"]        # 不写假货主


# ------------------------------------------------------------------ ③ 零数值变化
def test_only_three_fields_are_added():
    ws = {"酒坊_京畿路_1": {"name": "酒坊", "active": True, "yield": 5, "recipe": {"grain_feed": 1}}}
    st = _state(ws)
    before = copy.deepcopy(st.workshops)
    tres_before = getattr(st, "treasury", None)
    wo.assign_owners(st)
    row = st.workshops["酒坊_京畿路_1"]
    assert set(row) - set(before["酒坊_京畿路_1"]) == {"owner", "owner_kind", "owner_reason"}
    for k in before["酒坊_京畿路_1"]:                         # 既有字段逐字不变
        assert row[k] == before["酒坊_京畿路_1"][k]
    assert getattr(st, "treasury", None) == tres_before        # 钱未动


# ------------------------------------------------------------------ ④ 真实新局
def test_real_new_game_all_workshops_get_owner():
    """真实新局：**接线（`init_workshop_owners`）已生效** ⇒ 107 座全部有货主、0 未定义。

    ⚠️ 注意区分：`workshop_fund_shadow` 的 **`shadow_ready` 仍为 0** —— 因为影子还要求
    **工资单点**（作坊维度无权威条目，见 M49/M51）；本用例只断言 **`undefined_no_owner == 0`**
    （即「货主」这一维度的 blocker 已解除），**不谎报**整座作坊已 ready。
    """
    from core import commands
    s = commands.new_game()
    rep = wo.assign_owners(s)
    # 新局已在 init 里登记 ⇒ 这里应为 kept（幂等），不是 assigned
    assert rep["kept"] == 107 and rep["assigned"] == 0 and rep["undefined"] == 0, rep
    cov = wo.survey_owner_assignment(s)
    assert cov["with_owner"] == 107 and cov["missing"] == 0 and cov["undefined_rule"] == 0
    assert set(cov["by_kind"]) == {"local", "pop:商人"}
    assert cov["by_kind"]["local"] == 40 and cov["by_kind"]["pop:商人"] == 67  # 2×20 酒坊 / 其余

    # 🔴 影子读数：货主维度归零（**解除 M51 的 owner blocker**）
    from core.domains.economy import workshop_fund_shadow as wfs
    rep2 = wfs.survey_workshop_fund_shadow(s)
    assert rep2["undefined_no_owner"] == 0, rep2
    assert rep2["shadow_ready"] == 0, "工资口径未定前不应有 shadow_ready（如实）"
