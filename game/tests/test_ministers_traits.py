# -*- coding: utf-8 -*-
"""A3 派单回归测试：大臣特质表 / 离任影响表 / apply_minister_departure 基本行为。"""
import os
import sys

import pytest

_GAME_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.ministers.data import (  # noqa: E402
    TRAITS, DEPARTURE_RULES, traits_of, departure_effects, MINISTERS,
)
from core.game_state import GameState  # noqa: E402


def _new_state():
    return GameState("史实")


# ------------------------------------------------------------
# 1) 只读函数基本行为
# ------------------------------------------------------------
def test_traits_of_and_departure_effects():
    # 标注大臣：蔡京 = 聚敛/变法/才艺（素材 2.2 代表）
    assert traits_of("蔡京") == ["聚敛", "变法", "才艺"]
    # 未标注大臣：留空列表（不臆造，待考据单补齐）
    assert traits_of("岳飞") == []
    # 未知大臣安全失败
    assert traits_of("不存在的人") == []
    # 全部 43 人都有 trait_ids 字段且引用 TRAITS 键（含 talent 才艺）
    for name, fig in MINISTERS.items():
        assert "trait_ids" in fig, f"{name} 缺 trait_ids"
        for tid in fig["trait_ids"]:
            assert tid in TRAITS, f"{name} 引用了未知特质 {tid}"
    # 离任规则：6 原因齐全，档位词合法
    assert set(DEPARTURE_RULES) == {"贬黜", "致仕", "病故", "战殁", "处死", "乞休"}
    r = departure_effects("贬黜")
    assert r["prestige"] == "-微" and r["faction_satisfaction"] == "-小"
    # 未知原因安全失败
    assert departure_effects("流放") == {}


# ------------------------------------------------------------
# 2) apply_minister_departure 基本行为（清岗/状态/档位影响/记忆）
# ------------------------------------------------------------
def test_apply_minister_departure_basic():
    from core.commands import apply_minister_departure
    s = _new_state()
    # 贬黜韩忠彦（尚书省·尚书左仆射 holder；旧党）
    p0 = s.prestige
    old_sat0 = s.factions["旧党"]["satisfaction"]
    log = apply_minister_departure(s, "韩忠彦", "贬黜")
    # ① 清岗（权限跟机构不跟人，仅清 holder）
    assert s.central_orgs["尚书省"]["holders"]["尚书左仆射"] == ""
    # ② 状态
    assert s.minister_status("韩忠彦") == "dismissed"
    assert s.is_minister_available("韩忠彦") is False
    # ③ 档位影响：prestige -微（tier_to_value 4×0.25=1）、旧党 -小（3×0.5→2）
    assert s.prestige == max(0, min(100, p0 - 1))
    assert s.factions["旧党"]["satisfaction"] == max(0, min(100, old_sat0 - 2))
    # ④ 记忆留痕
    assert "贬黜" in s.minister_memory["韩忠彦"][-1]
    assert log[0] == "[离任] 韩忠彦 贬黜"


def test_apply_minister_departure_war_death_special():
    from core.commands import apply_minister_departure
    s = _new_state()
    # 战殁种师道（西军集团·军略名将）：西军满意度 大降 + 边境士气 小降
    xj0 = s.factions["西军集团"]["satisfaction"]
    line = next(iter(s.defense_lines.values()))
    fort0 = line["fortification"]
    log = apply_minister_departure(s, "种师道", "战殁")
    assert s.minister_status("种师道") == "dead"
    assert s.factions["西军集团"]["satisfaction"] < xj0  # 派系 大降（基础 + 名将修饰）
    assert line["fortification"] < fort0                  # 边境士气 小降（defense_bonus）
    assert any("边境士气" in l for l in log)
