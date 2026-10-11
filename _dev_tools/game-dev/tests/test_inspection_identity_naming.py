# -*- coding: utf-8 -*-
"""M36《称谓与制度》契约回归：**技术层 `inspection_*` 不动，内容层按朝代映射**。

用户裁定（2026-10-11）：故事背景为**宋**，宋制**无**「巡按」（那是明代巡按御史）；
宋代对应体系＝**御史台**（中央监察）＋**监司**（转运使／提点刑狱／提举常平）＋**差遣**（出使形式）。
同一套接口可复用于明（巡按御史）／清（巡察·钦差）——**只换 identity，不换技术层**。

纪律：内容层（日志／读数／提示词）**不得**出现「巡按」二字；技术层模块名保持 `inspection_*`。
"""
import os
import sys

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import (INSPECTION_IDENTITY,  # noqa: E402
                          INSPECTION_IDENTITY_DEFAULT_ERA, INSPECTION_KINDS)
from core.commands import new_game  # noqa: E402
from core.inspection import (enqueue_inspection, file_inspection_report,  # noqa: E402
                             inspection_identity, inspection_readout, inspection_tick)


def _seed(s, route, n=4):
    pool = s.prefectures[route]["pops"]["官僚"]
    move = min(int(n), int(pool.get("on_post", 0) or 0))
    pool["on_post"] = int(pool.get("on_post", 0) or 0) - move
    pool["waiting"] = int(pool.get("waiting", 0) or 0) + move
    return route


# ---------------------------------------------------------------- 身份映射

def test_song_identity_has_no_ming_term():
    """宋档：用**察访／差遣**，且**不得**含「巡按」二字（明制）。"""
    prof = inspection_identity()
    assert prof["era"] == "宋" == INSPECTION_IDENTITY_DEFAULT_ERA, "本游背景＝北宋"
    assert prof["term"] == "察访" and prof["dispatch"] == "差遣"
    for key in ("term", "dispatch", "agency"):
        assert "巡按" not in str(prof[key]), f"{key} 不得含明制称谓"
    for a in prof["actors"]:
        assert "巡按" not in a
    assert "御史台" in prof["agency"] and "监司" in prof["agency"]
    assert set(prof["actors"]) >= {"察访官", "监司官", "御史"}
    # 明/清档案保留（同接口复用）
    assert INSPECTION_IDENTITY["明"]["term"] == "巡按"
    assert INSPECTION_IDENTITY["清"]["term"] == "巡察"


def test_task_office_mapping_covers_all_kinds():
    """任务→主管机构映射（宋）：首批三类＋暂缓类（查刑狱→提刑司）均须有落点。"""
    task_office = inspection_identity()["task_office"]
    assert set(INSPECTION_KINDS) <= set(task_office)
    assert "提点刑狱" in task_office["查刑狱"], "查刑狱归提刑司"
    assert "转运" in task_office["查赋"]
    assert "御史台" in task_office["查吏治"]


def test_identity_readout_is_readonly_and_exposed():
    """identity 只读：进出读数不改状态；`inspection_readout()['identity']` 可见。"""
    s = new_game()
    rk = _seed(s, next(iter(s.prefectures)))
    tid = enqueue_inspection(s, rk, "查粮")["task"]["id"]
    s.year, s.month = 990, 3
    inspection_tick(s)
    file_inspection_report(s, tid, summary="回报")
    before = (dict(s.inspection_feedback["observables"]), len(s.inspection_tasks))
    ro = inspection_readout(s)
    assert ro["identity"]["term"] == "察访"
    assert ro["identity"]["era_requested"] == "宋"
    assert inspection_identity(s, era="明")["term"] == "巡按", "显式传明制应得明制称谓"
    assert inspection_identity(s, era="不存在的朝代")["era"] == "宋", "未知朝代回落默认"
    after = (dict(s.inspection_feedback["observables"]), len(s.inspection_tasks))
    assert before == after, "称谓读数不得有副作用"


# ---------------------------------------------------------------- 内容层语汇守卫

def test_game_logs_speak_song_vocabulary():
    """日志前缀：`[察访]`；玩家可见文本**不得**出现「巡按」。"""
    s = new_game()
    rk = _seed(s, next(iter(s.prefectures)))
    log = []
    r = enqueue_inspection(s, rk, "查赋", secret=True, log=log)
    assert r["ok"]
    s.year, s.month = 990, 3
    inspection_tick(s, log)
    file_inspection_report(s, r["task"]["id"], summary="回报", log=log)
    joined = "\n".join(log)
    assert "[察访]" in joined and "差遣" in joined and "密访" in joined
    assert "巡按" not in joined
    assert "奏报" in joined


def _code_only(src):
    """剥掉文档串与注释（散文里说明"宋无巡按"是**规范说明**，不算制度名误用）。"""
    import re
    src = re.sub(r'"""(?:.|\n)*?"""', "", src)
    src = re.sub(r"'''(?:.|\n)*?'''", "", src)
    return "\n".join(ln.split("#")[0] for ln in src.splitlines())


def test_source_guard_no_ming_term_in_content_layer():
    """源码守卫：`core/inspection.py` 的**可执行代码**不得出现「巡按」；规范说明须在文档串中。"""
    with open(os.path.join(_GAME_ROOT, "core", "inspection.py"), "r", encoding="utf-8") as f:
        src = f.read()
    assert "巡按" not in _code_only(src), "宋制内容层不得出现明制称谓"
    # 规范声明必须可发现（避免后来者又把明制词写回来）
    assert "称谓规范" in src and "宋制**无**" in src, "模块文档须保留称谓规范声明"
    # 明制称谓**只**允许在朝代映射档案里出现
    with open(os.path.join(_GAME_ROOT, "content", "data_constants.py"), "r",
              encoding="utf-8") as g:
        const_src = g.read()
    assert '"明": {"era": "明", "term": "巡按"' in const_src, "明档保留（同接口复用）"


def test_identity_used_by_finance_readout():
    """读数出口：`finance_readout()['inspection']['identity']`（UI/AI 按本朝语汇说话）。"""
    s = new_game()
    ident = s.finance_readout()["inspection"]["identity"]
    assert ident["term"] == "察访" and ident["dispatch"] == "差遣"
    assert "note" in ident and "御史台" in ident["note"] and "差遣" in ident["note"]
    assert "巡按" not in ident["note"], "本朝用语不得出现明制称谓"
