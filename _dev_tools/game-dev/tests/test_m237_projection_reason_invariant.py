# -*- coding: utf-8 -*-
"""M237 P2 可解释性**不变量**守卫：`undefined ⇒ reason` 必非空（建筑与作坊两侧、全字段）。

动因：M236 发现 `level` 在 `defined=False` 时 `reason` **恒为 None**（14 字段中唯一无理由者）
⇒ 「**无 reason 的 undefined**」使『语义不存在』与『可读但取不到』**不可区分**，是可解释性缺口。
修法：补 `level` 的 reason（M237）。**本用例把该不变量钉死**，防回归。
"""

import random

from core import commands
from core.domains.economy import entity_projection as ep


def _state():
    random.seed(20261013)
    return commands.new_game()


def test_building_undefined_always_carries_reason():
    s = _state()
    for route, p in s.prefectures.items():
        seats = p.get("seats") or {}
        for seat, srow in list(seats.items())[:2]:                     # 抽样：每路前 2 治所
            blds = (srow or {}).get("buildings") or {}
            for name in list(blds)[:3]:
                rep = ep.project_building(s, route, seat, name)
                for k in ep.FIELDS:
                    f = (rep.get("fields") or {}).get(k) or {}
                    if not f.get("defined"):
                        assert f.get("reason"), (route, seat, name, k, f)


def test_workshop_undefined_always_carries_reason():
    s = _state()
    for wid in list(s.workshops)[:12]:
        rep = ep.project_workshop(s, wid)
        for k in ep.FIELDS:
            f = (rep.get("fields") or {}).get(k) or {}
            if not f.get("defined"):
                assert f.get("reason"), (wid, k, f)


def test_level_of_scalar_building_has_reason_when_undefined():
    """定点回归：`level` 未定义时**必须有 reason**（M237 修的那一处）。"""
    s = _state()
    for route, p in s.prefectures.items():
        for seat, srow in list((p.get("seats") or {}).items())[:1]:
            for name in list(((srow or {}).get("buildings") or {}))[:1]:
                lv = (ep.project_building(s, route, seat, name).get("fields") or {}).get("level") or {}
                if not lv.get("defined"):
                    assert lv.get("reason"), (route, seat, name, lv)
