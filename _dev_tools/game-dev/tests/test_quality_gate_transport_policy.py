# -*- coding: utf-8 -*-
"""质量放行门 · 交通政策白名单与 AI 快照（G-3 P5d，2026-10-18）。

背景：用户质疑「怎么会没开海呢」暴露「开关定义但无写入者」缺陷。
本门钉住：
1. 政策**默认值**（open_sea=True 史实开海）可读；
2. `set_transport_policy` **白名单 + 取值校验**（未知键/非法值进 rejected，不静默忽略）；
3. 事件/政令能真正拨开关（`transport_policy` effect → 海运立刻关闭）；
4. `transport_snapshot` **区间化**（不吐精密数值，守审查 P0-2）；
5. 反例自证：非法键必须被拒、合法键必须写入。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.transport import (  # noqa: E402
    TRANSPORT_POLICY_DEFAULTS, TRANSPORT_POLICY_KEYS, set_transport_policy,
    transport_capability, transport_policy, transport_snapshot)


def _state():
    from core.commands import new_game

    return new_game()


def test_policy_defaults_are_open_sea():
    s = _state()
    pol = transport_policy(s)
    assert set(pol) == set(TRANSPORT_POLICY_KEYS), pol
    assert pol["open_sea"] is True, "史实开海：默认必须为 True"
    assert pol == {**TRANSPORT_POLICY_DEFAULTS, **{}}, pol


def test_setter_rejects_unknown_key_and_bad_value():
    s = _state()
    r = set_transport_policy(s, open_sea=False, 瞎写=1)
    assert r["applied"] == {"open_sea": False}
    assert r["rejected"].get("瞎写") == "unknown_key"
    r2 = set_transport_policy(s, mode_pref="飞运")
    assert "bad_value" in str(r2["rejected"].get("mode_pref")), r2
    assert transport_policy(s)["mode_pref"] == TRANSPORT_POLICY_DEFAULTS["mode_pref"], \
        "非法值不得落库"


def test_closing_sea_affects_capability():
    s = _state()
    ok = transport_capability(s, "两浙路|台州", "福建路|福州", "sea")
    assert ok["ok"], ok
    set_transport_policy(s, open_sea=False)
    off = transport_capability(s, "两浙路|台州", "福建路|福州", "sea")
    assert not off["ok"] and off["reason"] == "sea_closed_by_policy", off


def test_event_effect_can_flip_switch():
    """政令/事件必须真能拨开关（此前只产出文本 ⇒ 永远关着）。"""
    from core.events import apply_event_choice

    s = _state()
    ev = {"choices": [{"text": "禁海", "effects": {"transport_policy": {"open_sea": False}}}]}
    log = apply_event_choice(s, ev, 0)
    assert any("交通政策" in line for line in log), log
    assert transport_policy(s)["open_sea"] is False
    assert transport_capability(s, "两浙路|台州", "福建路|福州", "sea")["reason"] == "sea_closed_by_policy"


def test_snapshot_is_intervalized():
    s = _state()
    snap = transport_snapshot(s)
    assert set(snap) >= {"barges", "canal", "in_transit", "policy", "note"}
    for key in ("barges", "canal", "in_transit_batches"):
        val = snap[key]
        assert isinstance(val, str) and not any(ch.isdigit() for ch in val), \
            f"{key} 必须是档位词（不吐精密数值）：{val!r}"
    assert snap["in_transit"] in ("有", "无")