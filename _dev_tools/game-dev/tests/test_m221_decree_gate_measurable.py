# -*- coding: utf-8 -*-
"""M221 P3 批 5：复述门**可测用例**（不依赖官员建档；**不接主链**）。

依据：用户 2026-10-08 裁决 3（暂不接主链；受命承办者承办前复述；AI 只出候选）+ 批 5。
⚠️ 本批**只覆盖不依赖官员运行态的部分**（M220 实测：`confirm_decree` 在**比对之前**先做
`can_act` 与受命人校验 ⇒ 未建档者会**提前 return**，比对不发生）。
⇒ 「一致⇒放行 / 不符⇒拒 / 未复述⇒拒 / 防伪」四条**须先造官员运行态**，属**另批**。
"""

import copy

from core import commands
from core import decree_confirm as dc


def _decree():
    return {"decree_id": "TEST-D1", "title": "开仓赈济", "body": "诏京畿路开常平仓赈济",
            "visibility": "公", "addressees": ["司马光"]}


def _state():
    import random
    random.seed(20261013)
    return commands.new_game()


# ---------------------------------------------------------------- 比对层（不依赖授权）

def test_compare_positive_is_ok_and_lists_empty():
    """正：`compose_recitation(canonical)` 与原旨一致 ⇒ `ok=True` 且三列表空。"""
    canon = dc.canonical_decree(_decree())
    rec = dc.compose_recitation(canon)
    assert isinstance(rec, dict) and "elements" not in rec          # 形状：扁平 {元素→值}
    cmp = dc.compare_recitation(canon, rec)
    assert cmp["ok"] is True, cmp
    assert cmp["mismatched"] == [] and cmp["missing"] == [] and cmp["unsupported"] == []


def test_compare_negative_detects_mismatch():
    """负：改坏一个元素 ⇒ `ok=False` 且 `mismatched` 含被改键（不静默通过）。"""
    canon = dc.canonical_decree(_decree())
    rec = copy.deepcopy(dc.compose_recitation(canon))
    assert "body" in rec, rec
    rec["body"] = "（被改坏的内容）"
    cmp = dc.compare_recitation(canon, rec)
    assert cmp["ok"] is False and "body" in cmp["mismatched"], cmp


def test_compare_missing_and_unsupported_are_reported():
    """严格性：漏项 ⇒ `missing`；塞口径不认的键 ⇒ `unsupported`（**不静默忽略**）。"""
    canon = dc.canonical_decree(_decree())
    rec = copy.deepcopy(dc.compose_recitation(canon))
    rec.pop("title", None)                                     # 漏项
    rec["野键"] = "x"                                          # 不认的键
    cmp = dc.compare_recitation(canon, rec)
    assert cmp["ok"] is False
    assert ("title" in cmp["missing"]) or cmp["missing"], cmp
    assert "野键" in cmp["unsupported"], cmp


# ---------------------------------------------------------------- 门前置（不依赖建档）

def test_gate_unknown_actor_is_unauthorized_withheld():
    """门·未建档者：`can_act` 不过 ⇒ **UNAUTHORIZED + withheld + 未复述**（权限屏障如实）。"""
    s = _state()
    d = _decree()
    out = dc.confirm_decree(s, d["decree_id"], "路人甲", decree=d)
    assert out["authorized"] is False
    assert out["withheld"] is True
    assert out["recited"] is False
    assert out["status"] == dc.STATUS_UNAUTHORIZED
    assert out["in_roster"] is False


def test_gate_unknown_decree_is_undefined_not_pass():
    """门·未知旨：查不到原文 ⇒ `defined=False` / `unknown_decree`（**缺失≠0**）。"""
    s = _state()
    out = dc.confirm_decree(s, "NOT-EXIST-D999", "路人甲")
    assert out["defined"] is False
    assert out["reason"] == "unknown_decree"
    assert out["status"] == dc.STATUS_UNDEFINED


# ---------------------------------------------------------------- 拒绝式

def test_free_text_recitation_is_rejected():
    """拒绝式：自由文本不得当复述 ⇒ `ValueError`。"""
    s = _state()
    d = _decree()
    try:
        dc.confirm_decree(s, d["decree_id"], "路人甲", decree=d, recitation="臣已复述")
    except ValueError:
        return
    raise AssertionError("自由文本复述应被拒绝式挡回（ValueError）")
