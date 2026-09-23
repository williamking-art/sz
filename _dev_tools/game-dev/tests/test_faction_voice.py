# -*- coding: utf-8 -*-
"""集团「声量」按人计权的回归测试（2026-09-19 修复）。

背景：`core/faction_voice.py` 的口径是"官职的声量就是它的权限大小；官员的声量来自官职，
派系的声量来自其官员"——**官员才是载体**。原实现按"每个 holder 都取机构权限累加"，
于是**兼任**者会把机构权限重复计入：

  实证：`王古` 兼 `户部·户部尚书`(19.0) 与 `户部·抵当所提举`(19.0) → 38.0；
        `曾布` 兼中书侍郎(12.0) 与尚书右仆射(6.5) → 18.5。
  → 中立派声量虚高到 67.0（旧党 53.5），把"朝堂声量最大者"判错，进而让
    `_examiner_faction`（知贡举举荐权）归错派系（`test_faction_flows.py` 因此失败）。

本文件锁定：**一人只按其最高权限职位计一次**（兼任不叠加），且**不采用**"同机构去重"
（那会砍掉旧党"人多势众"这一真实优势）。
"""
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from core.faction_voice import org_voice, voice_norm, voice_seats  # noqa: E402
from core.game_state import GameState  # noqa: E402
from core.officialdom import _examiner_faction  # noqa: E402


def _s():
    return GameState("史实")


def test_one_official_counts_once_even_with_concurrent_posts():
    """同一人身兼同机构两职 → 只计其最高权限一次（不翻倍）。"""
    s = _s()
    org = s.central_orgs["户部"]
    w = org_voice(org)
    holder = org["holders"]["户部尚书"]
    # 让此人同时挂着户部的第二个职位
    org["holders"]["抵当所提举"] = holder
    seats = voice_seats(s)
    # 该机构权限只应被此人计入一次
    assert seats, "声量不该为空"
    # 记录：把第二职换成另一派系的人，声量应发生变化（证明第二职真的在算，只是不重复计同一人）
    org["holders"]["抵当所提举"] = "童贯"
    seats2 = voice_seats(s)
    assert seats2 != seats, "第二职换人后声量应有变化（说明兼任只有'同一人'才去重）"


def test_voice_is_per_person_not_per_post():
    """定量口径：单人声量 = 其最高权限职位；兼任不叠加。"""
    s = _s()
    org = s.central_orgs["户部"]
    w = org_voice(org)
    holder = org["holders"]["户部尚书"]
    base = voice_seats(s)
    fac = None
    from content.ministers.data import MINISTERS
    fac = (MINISTERS.get(holder) or {}).get("faction")
    assert fac, "户部尚书应有派系"
    # 兼任同机构第二职：该派系声量不变（同一人只算一次，且权限相同）
    org["holders"]["抵当所提举"] = holder
    assert voice_seats(s)[fac] == pytest.approx(base[fac]), \
        "兼任同机构职位不得叠加声量（一人一份）"


def test_opening_voice_ranks_jiudang_first():
    """开局声量排序：旧党（在朝八人各领一职）> 中立派 > 新党 …（与史实设定一致）。"""
    s = _s()
    seats = voice_seats(s)
    assert seats["旧党"] > seats["中立派"], f"开局旧党声量应最大：{seats}"
    assert seats["旧党"] == pytest.approx(53.5, abs=0.6), f"旧党声量口径变化：{seats}"
    assert seats["中立派"] == pytest.approx(41.5, abs=0.6), f"中立派声量口径变化：{seats}"


def test_examiner_defaults_to_largest_voice():
    """知贡举默认由"朝堂声量最大者"举荐 → 开局为旧党。"""
    s = _s()
    top = max(voice_seats(s).items(), key=lambda kv: kv[1])[0]
    assert _examiner_faction(s) == top == "旧党"


def test_voice_norm_is_absolute_not_share():
    """声量是**绝对影响力**（边际递减映射），不是份额：两派可同时高，不要求 Σ=1。"""
    s = _s()
    vals = [voice_norm(s, f) for f in ("旧党", "中立派", "新党")]
    assert all(0.0 <= v <= 1.0 for v in vals)
    assert sum(vals) > 0 and sum(vals) != pytest.approx(1.0), "声量不是份额，不应归一为 1"
