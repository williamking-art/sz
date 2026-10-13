# -*- coding: utf-8 -*-
"""M59 盲区补齐哨兵：**读档往返** + **长局 M50 影响面**。

M57 的家族哨兵只覆盖 `run_monthly_settlement`，并如实写明两个盲区：
① **读档往返（`load_game` → 迁移）路径未覆盖**（AGENTS.md 记过「存档往返即下沉」的陷阱）；
② **后端动作路径未覆盖**（本批仍不做，属下一批）。
本文件把 ① 补上，并顺带把 **M50「拒绝产出」的影响面**量化成可执行断言。
"""

import random

from core import commands
from core.foundation.ledger import pop_bridge as pb

SEED = 20261013
SLOT = 91                      # 隔离槽（>5 供测试）


def _cleanup_slot():
    try:
        from core.save_load import _slot_path
        p = _slot_path(SLOT)
        if getattr(p, "exists", lambda: False)():
            p.unlink()
    except Exception:                                       # noqa: BLE001
        pass


def test_save_load_roundtrip_then_guard_sentinel():
    """存→读之后：下沉不变量仍成立，且**再跑短哨兵 0 违规、trace 明细为空**。"""
    import core.settlement as S
    from core.save_load import load_game, save_game

    random.seed(SEED)
    s = commands.new_game()
    for _ in range(3):
        S.run_monthly_settlement(s)
    assert save_game(s, slot=SLOT), "存档失败"
    s2 = load_game(slot=SLOT)
    assert s2 is not None, "读档失败"

    # ① 下沉不变量：20/20 路有 seats；路级镜像 == Σ治所（逐字段）
    assert len(s2.prefectures) == 20
    for route, pdata in s2.prefectures.items():
        assert isinstance(pdata.get("seats"), dict) and pdata["seats"], f"{route} 无 seats"
        assert not pb.assert_pops_consistent(pdata), \
            f"{route} 路级镜像与 Σ治所失配：{pb.assert_pops_consistent(pdata)[:5]}"

    # ② 读档后再跑短哨兵（守卫 + trace）：**0 违规、0 明细**
    assert pb.install_all_guards(s2) == 20, "守卫未装上（读档后应为 20 路）"
    pb.reset_pops_guard()
    pb._GUARD_TRACE = True
    for _ in range(3):
        S.run_monthly_settlement(s2)
    details = pb.pops_guard_violation_details()
    writers = {f"{d.get('function')} @ {str(d.get('file')).split(chr(92))[-1]}:{d.get('line')}"
               for d in details}
    assert pb.pops_guard_violations() == [], f"读档后出现直写：{writers}"
    assert details == [], f"读档后 trace 明细非空：{writers}"
    # ③ 迁移对账读数：字段失配必须为空
    survey = pb.survey_pops(s2)
    assert survey.get("字段失配") == [], f"读档往返后字段失配：{survey.get('字段失配')[:5]}"
    _cleanup_slot()


def test_long_run_has_no_job_track_config_fallback():
    """M50 影响面（长局）：**不应出现「缺政权专档 ⇒ 回落 default」**。

    若本用例红 ⇒ 说明某些政权在长局里**长期靠外挂 `default` 跑**，
    此时正确处置是**补齐专档**（而不是 `M50` 里那条更严的「拒绝产出」，
    拒绝会把它们的产出直接归零）。读数口：`building_jobs.job_track_config_fallbacks()`。
    """
    import core.settlement as S
    from core import building_jobs as bj

    bj._CONFIG_FALLBACKS.clear()
    random.seed(SEED)
    s = commands.new_game()
    for _ in range(12):
        S.run_monthly_settlement(s)
    recs = bj.job_track_config_fallbacks()
    regimes = {}
    for r in recs:
        regimes[r.get("rtype")] = regimes.get(r.get("rtype"), 0) + 1
    assert recs == [], f"长局出现「缺专档回落 default」：{regimes}"
