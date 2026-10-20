# -*- coding: utf-8 -*-
"""质量放行门 · 圣旨核销闭环（2026-10-20）。

用户裁定：「每一份圣旨都要能被核销，哪怕是中旨这种，只是落地效果的区别而已」。

钉住：
1. 队列中每道旨（含中旨/密旨/口谕）超期后必有台账条目（可核销）；
2. **中旨也核销**，但 `landed` = 0.75 < 普通诏令 1.0（落地效果区别）；
3. 未超期的保留（`kept`），不提前误核销；
4. 幂等：已核销的旨意**绝不改写**（重复 sweep 不改条目）；
5. 已执行（executed）的旨意不会被兜底覆盖为 failed；
6. `closure_status.dangling` 核销后归零；
7. 缺 id 的旨意会被补 `decree_id`（不产生无名悬挂）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

from core.decree_confirm import OUTCOME_EXECUTED, exec_ledger_of, record_execution  # noqa: E402
from core.domains.politics.edict_closure import (  # noqa: E402
    ZHONGZHI_LANDING, closure_status, is_zhongzhi, landing_effect, sweep_edict_closure)


class _S:
    def __init__(self, decrees, turn=10):
        self.turn = turn
        self.pending_decrees = list(decrees)
        self.pending_secret_decrees = []
        self.active_decrees = []
        self.statistics = {}


def test_zhongzhi_detection():
    assert is_zhongzhi({"category": "中旨"})
    assert is_zhongzhi({"delivery": "御笔直发"})
    assert not is_zhongzhi({"category": "诏令"})
    assert landing_effect({"category": "中旨"}) == ZHONGZHI_LANDING
    assert landing_effect({"category": "诏令"}) == 1.0


def test_stale_edicts_are_closed_with_landed():
    s = _S([{"title": "加薪诏", "turn_issued": 1},
            {"title": "御笔加赏", "category": "中旨", "turn_issued": 1}])
    out = sweep_edict_closure(s, stale_turns=3, turn=10)
    assert out["closed_count"] == 2, out
    led = exec_ledger_of(s)
    zz = next(e for e in led.values() if e["title"] == "御笔加赏")
    pt = next(e for e in led.values() if e["title"] == "加薪诏")
    assert zz["landed"] == ZHONGZHI_LANDING and zz["zhongzhi"] is True
    assert pt["landed"] == 1.0 and pt["zhongzhi"] is False


def test_fresh_edicts_are_kept():
    s = _S([{"title": "新旨", "turn_issued": 9}])
    out = sweep_edict_closure(s, stale_turns=3, turn=10)
    assert out["closed_count"] == 0 and out["kept_count"] == 1
    assert closure_status(s)["dangling_count"] == 1


def test_sweep_is_idempotent_and_never_overwrites():
    s = _S([{"title": "旧旨", "turn_issued": 1}])
    sweep_edict_closure(s, stale_turns=3, turn=10)
    first = dict(exec_ledger_of(s)["d1"]) if "d1" in exec_ledger_of(s) else list(exec_ledger_of(s).values())[0]
    out2 = sweep_edict_closure(s, stale_turns=3, turn=11)
    assert out2["closed_count"] == 0
    again = list(exec_ledger_of(s).values())[0]
    assert again["turn"] == first["turn"] and again.get("outcome") == first.get("outcome")


def test_executed_edict_not_overwritten():
    s = _S([{"title": "已办", "decree_id": "d9-1", "turn_issued": 1}])
    record_execution(s, "d9-1", outcome=OUTCOME_EXECUTED, turn=2, landed=1.0)
    out = sweep_edict_closure(s, stale_turns=3, turn=10)
    assert out["closed_count"] == 0
    assert exec_ledger_of(s)["d9-1"]["outcome"] == OUTCOME_EXECUTED


def test_dangling_zero_after_sweep():
    s = _S([{"title": "甲", "turn_issued": 1}, {"title": "乙", "category": "中旨", "turn_issued": 1}])
    assert closure_status(s)["dangling_count"] == 2
    sweep_edict_closure(s, stale_turns=3, turn=10)
    assert closure_status(s)["dangling_count"] == 0


def test_missing_id_gets_assignee():
    s = _S([{"title": "无名旨", "turn_issued": 1}])
    out = sweep_edict_closure(s, stale_turns=3, turn=10)
    assert out["closed_count"] == 1
    assert s.pending_decrees[0].get("decree_id"), "缺失 id 必须补齐（不产生无名悬挂）"

def test_undated_decree_is_kept_not_closed():
    """颁布回合未知（未决/挂起，如受命人权限未定）⇒ 不兜底核销。"""
    s = _S([{"title": "待定事务", "decree_id": "d_undef_x", "effects": {}}])
    out = sweep_edict_closure(s, stale_turns=3, turn=10)
    assert out["closed_count"] == 0
    assert out["kept_count"] == 1
    assert any("挂起" in (k.get("reason") or "") for k in out["kept"])