# -*- coding: utf-8 -*-
"""B5-4 · 口谕复述确认 ＋ 同旨补录 的定向回归（规格 `market-civilian-economy`）

锁定《建议》§7 的 B5 验收断言与任务书 B5-4 三条要求：

| 要求 | 用例 |
|---|---|
| ① 口谕须有**复述确认**，不是直接执行 | `test_no_recitation_is_not_confirmation` / `test_confirmed_requires_recitation_not_just_authority` |
| ② 同一 `decree_id` **不重复执行**（补录/重下/重试） | `test_same_decree_id_backfilled_twice_executes_once` 等 4 例 |
| ③ 复述与原旨**不符须暴露**，不得静默通过 | `test_mismatch_names_the_diverging_element` 等 4 例 |
| 四态语义 | `test_four_states_are_reachable_and_distinct` |
| **未授权者不能确认** | `test_unauthorized_cannot_confirm` / `test_non_addressee_cannot_confirm` |
| 缺失 ≠ 0 ≠ False（不回落假装成功） | `test_missing_readings_stay_undefined_not_success` |
| 拒绝式（非法输入） | `test_invalid_inputs_are_rejected` |
| **读数不改 state** ＋ **不新增 `state.*`** | `test_readonly_calls_do_not_touch_state` / `test_no_parallel_state_ledger` |
| 跨回合/读档后幂等仍在 | `test_idempotency_survives_save_load` |
| 逐人隔离（复述不串人） | `test_recitation_is_per_person_not_shared` |
| 不碰钱粮人口（POP 挂载律） | `test_backfill_without_executor_moves_no_money_or_people` |
"""
import copy
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.ministers.data import MINISTERS  # noqa: E402
from core.decree_confirm import (  # noqa: E402
    DECREE_CONFIRM_SCHEMA_VERSION, ELEMENTS, LEDGER_STAT_KEY, MEMORY_KIND_RECITE,
    OUTCOME_EXECUTED, OUTCOME_FAILED, OUTCOME_REGISTERED_ONLY, OUTCOMES,
    RECITE_SOURCE_PREFIX, STATUS_CONFIRMED, STATUS_MISMATCH, STATUS_UNAUTHORIZED,
    STATUS_UNDEFINED, STATUSES, addressees_of, backfill_candidates, backfill_decree,
    canonical_decree, compare_recitation, compose_recitation, confirm_decree,
    decree_digest, decree_id_of, decree_of, execution_of, exec_ledger_of,
    latest_recitation, recitations_of, recite_source, record_recitation, render_recitation,
)
from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402
from core.minister_agent import MINISTER_STATUS_OUT, can_act, ensure_actor, recall  # noqa: E402

# 两名在册官员（复用 `MINISTERS`，不另造人物表）
MIN_A = "王古"      # 户部尚书
MIN_B = "陈瓘"      # 右司谏
MIN_C = "曾布"      # 权谋/善变（用于"权限未定义"）

DID = "d_kouyu_0001"
DECREE = {
    "decree_id": DID,
    "title": "括民苍生",
    "desc": "发内帑三十万缗，以赈京东、河北流民。",
    "category": "口谕",
    "is_secret": False,
    "is_direct": True,
    "effects": {"treasury": 300000, "population_satisfaction": -3},
    "target": MIN_A,
}
BODY = DECREE["desc"]


def _state():
    s = GameState("史实")
    init_legacies(s)
    ensure_actor(s, MIN_A, posts=["户部尚书"], authority=0.7)
    ensure_actor(s, MIN_B, posts=["右司谏"], authority=0.6)
    return s


def _pending_secret(s):
    """把一道密旨放进既有队列（模拟 `issue_secret_decree` 的落点）。"""
    d = dict(DECREE)
    d["is_secret"] = True
    d["category"] = "密旨"
    s.pending_secret_decrees.append(d)
    return d


def _counter():
    box = {"n": 0}

    def _run(_state, _decree):
        box["n"] += 1
        return f"执行第 {box['n']} 次"
    return box, _run


# ======================================================== 复用名册
def test_reuses_existing_roster_and_adds_no_new_person_state():
    """复用 `content.ministers.data.MINISTERS`（43 名），不另造人物表。"""
    assert len(MINISTERS) == 43
    s = _state()
    before = set(vars(s))
    out = confirm_decree(s, DID, MIN_A, decree=DECREE)
    assert out["in_roster"] is True
    assert set(vars(s)) == before, "确认流程冒出了新的 state 属性"
    assert set(s.minister_agents) == {MIN_A, MIN_B}, "凭空多出了人物"


# ======================================================== ① 先复述，后承办
def test_no_recitation_is_not_confirmation():
    """没复述 → `undefined`，**不是** `confirmed`（缺失≠确认）。"""
    s = _state()
    out = confirm_decree(s, DID, MIN_A, decree=DECREE)
    assert out["status"] == STATUS_UNDEFINED
    assert out["reason"] == "not_recited"
    assert out["authorized"] is True and out["can_act"]["ok"] is True
    assert out["recited"] is False and out["recorded"] is False
    # 未确认时台账里不应有任何"已执行"痕迹
    assert execution_of(s, DID) is None
    # 读数仍给出"一份正确复述该是什么样"，供调用方照此落记
    assert out["suggested_recitation"] == compose_recitation(canonical_decree(DECREE))


def test_confirmed_requires_recitation_not_just_authority():
    """有权无复述仍不得承办——复述是硬门槛，不因"他有权限"而放行。"""
    s = _state()
    assert can_act(s, MIN_A)["ok"] is True
    out = confirm_decree(s, DID, MIN_A, decree=DECREE)
    assert out["status"] != STATUS_CONFIRMED


def test_recitation_is_recorded_and_replayable_next_turn():
    """确认后复述记录可查，且下一回合再确认仍是 `confirmed`（不重复写）。"""
    s = _state()
    first = confirm_decree(s, DID, MIN_A, decree=DECREE, record=True)
    assert first["status"] == STATUS_CONFIRMED
    assert first["recorded"] is True and first["recited"] is True

    s.turn = 9
    again = confirm_decree(s, DID, MIN_A, decree=DECREE, record=True)
    assert again["status"] == STATUS_CONFIRMED
    assert again["recorded"] is False, "已有复述记录又被写了一遍"
    assert len(recitations_of(s, DID, MIN_A)) == 1
    assert again["recitation_turn"] == 0

    rows = recitations_of(s, DID, MIN_A)
    assert rows[0]["source"] == recite_source(DID) == RECITE_SOURCE_PREFIX + DID + "·复述"
    assert rows[0]["kind"] == MEMORY_KIND_RECITE
    assert rows[0]["elements"]["title"] == DECREE["title"]
    assert rows[0]["readable"].startswith("〔复述〕")
    assert latest_recitation(s, DID, MIN_B) is None


# ======================================================== 四态
def test_four_states_are_reachable_and_distinct():
    """四态互斥且穷尽：同一接口能给出全部四态，不会把缺失混成成功。"""
    s = _state()
    seen = {}

    # confirmed
    seen["confirmed"] = confirm_decree(s, DID, MIN_A, decree=DECREE, record=True)["status"]
    # mismatch
    seen["mismatch"] = confirm_decree(
        s, "d_2", MIN_A, decree={"decree_id": "d_2", "title": "括民苍生", "desc": "发内帑三十万缗"},
        recitation={"title": "括民苍生", "body": "发内帑三百万缗"}, record=False)["status"]
    # unauthorized
    ensure_actor(s, "蔡京", authority=0.0)
    seen["unauthorized"] = confirm_decree(s, "d_3", "蔡京", decree={"decree_id": "d_3"})["status"]
    # undefined
    seen["undefined"] = confirm_decree(s, "d_4", MIN_A, decree={"decree_id": "d_4"})["status"]

    assert set(seen) == set(STATUSES), seen
    assert len(set(seen.values())) == 4, seen
    assert all(v in STATUSES for v in seen.values())


def test_mismatch_names_the_diverging_element():
    """复述与原旨不符 → 逐项暴露差在哪（原值 / 复述值 / 原因），不静默通过。"""
    s = _state()
    out = confirm_decree(s, DID, MIN_A, decree=DECREE,
                         recitation={"title": "括民苍生", "body": "发内帑三百万缗"})
    assert out["status"] == STATUS_MISMATCH
    assert out["mismatched"] == ["body"]
    assert out["missing"], "其余应有要素被当作已复述"
    row = {r["key"]: r for r in out["elements"]}["body"]
    assert row["ok"] is False
    assert row["expected"] == BODY
    assert row["recited"] == "发内帑三百万缗"
    assert "不符" in row["note"]
    assert "不符" in out["message"]


def test_empty_recitation_is_not_treated_as_agreement():
    """空复述 ≠ "无异议"：所有应有要素进 `missing` → `mismatch`。"""
    s = _state()
    out = confirm_decree(s, DID, MIN_A, decree=DECREE, recitation={})
    assert out["status"] == STATUS_MISMATCH
    assert sorted(out["missing"]) == sorted(ELEMENTS)
    assert out["mismatched"] == [] and out["unsupported"] == []


def test_reciting_something_the_decree_never_said_is_a_mismatch():
    """复述出原旨没有的要素 → `unsupported`（杜撰也算不符）。"""
    s = _state()
    d = {"decree_id": "d_5", "title": "减两税", "effects": {"treasury": 100}}
    out = confirm_decree(s, "d_5", MIN_A, decree=d,
                         recitation={"title": "减两税", "effects": {"treasury": 100},
                                     "delivery": "口谕"})
    assert out["status"] == STATUS_MISMATCH
    assert out["unsupported"] == ["delivery"]


def test_effects_compare_normalizes_numbers_but_not_values():
    """`300000` 与 `300000.0` 视为一致；`300000` 与 `300001` 必须判不符。"""
    d = {"decree_id": "d_6", "title": "发帑", "effects": {"treasury": 300000}}
    ok = confirm_decree(_state(), "d_6", MIN_A, decree=d,
                        recitation={"title": "发帑", "effects": {"treasury": 300000.0}})
    assert ok["status"] == STATUS_CONFIRMED
    bad = confirm_decree(_state(), "d_6", MIN_A, decree=d,
                         recitation={"title": "发帑", "effects": {"treasury": 300001}})
    assert bad["status"] == STATUS_MISMATCH and bad["mismatched"] == ["effects"]


# ======================================================== 未授权者
def test_unauthorized_cannot_confirm():
    """无权者：离任者、权限为 0 者、名册外之人 → `unauthorized`，且**拿不到原旨内容**。"""
    s = _state()
    s.minister_agents[MIN_B]["authority"] = 0.0
    out0 = confirm_decree(s, DID, MIN_B, decree=DECREE)
    assert out0["status"] == STATUS_UNAUTHORIZED
    assert out0["reason"] == "no_authority"
    assert out0["authorized"] is False
    assert out0["withheld"] is True and out0["elements"] == [], "未授权者读到了原旨要素"
    assert out0["suggested_recitation"] is None

    s.minister_agents[MIN_B]["authority"] = 0.6
    s.minister_agents[MIN_B]["status"] = MINISTER_STATUS_OUT
    out1 = confirm_decree(s, DID, MIN_B, decree=DECREE)
    assert out1["status"] == STATUS_UNAUTHORIZED and out1["reason"] == "not_in_office"

    out2 = confirm_decree(s, DID, "查无此人", decree=DECREE)
    assert out2["status"] == STATUS_UNAUTHORIZED and out2["reason"] == "unknown_actor"


def test_non_addressee_cannot_confirm():
    """原旨点名的受命人之外的人，即便有权限也不得代为确认。"""
    s = _state()
    out = confirm_decree(s, DID, MIN_B, decree=DECREE)
    assert out["addressee_declared"] is True
    assert out["is_addressee"] is False
    assert out["status"] == STATUS_UNAUTHORIZED and out["reason"] == "not_addressee"
    assert out["elements"] == [] and out["withheld"] is True


def test_unauthorized_person_cannot_backfill_either():
    """未授权者连补录的资格也没有：台账不占位、不执行。"""
    s = _state()
    box, run = _counter()
    out = backfill_decree(s, DECREE, MIN_B, executor=run)
    assert out["applied"] is False
    assert out["blocked_by"] == STATUS_UNAUTHORIZED
    assert out["outcome"] is None and box["n"] == 0
    assert execution_of(s, DID) is None


# ======================================================== 缺失 ≠ 0 ≠ False
def test_missing_readings_stay_undefined_not_success():
    """原旨查不到 / 权限未定义 / 尚未复述 → 都是 `undefined`，都不是成功。"""
    s = _state()
    # ① 原旨查不到：不凭空造旨
    miss = confirm_decree(s, "查无此旨", MIN_A)
    assert miss["status"] == STATUS_UNDEFINED and miss["reason"] == "unknown_decree"
    assert miss["defined"] is False and "decree" in miss["undefined_basis"]
    assert miss["elements"] == [] and miss["digest"] is None
    # ② 权限未定义：既不按有权、也不按无权
    ensure_actor(s, MIN_C)          # authority 未给
    und = confirm_decree(s, DID, MIN_C, decree=DECREE)
    assert und["status"] == STATUS_UNDEFINED and und["reason"] == "authority_undefined"
    assert und["authorized"] is None, "未定义被擅自判成了有权或无权"
    assert "authority" in und["undefined_basis"]
    # ③ 复述记录读不出要素：报"读不出"，不按"复述过"放行
    confirm_decree(s, DID, MIN_A, decree=DECREE, record=True)
    s.minister_agents[MIN_A]["memory"][-1]["text"] = "〔复述〕被人抹掉了结构"
    bad = confirm_decree(s, DID, MIN_A, decree=DECREE)
    assert bad["status"] == STATUS_UNDEFINED and bad["reason"] == "recitation_unreadable"
    assert bad["recited"] is True
    assert execution_of(s, DID) is None


def test_missing_execution_record_is_none_not_empty_shell():
    """未执行过 → `None`（不是空 dict、不是 False）。"""
    s = _state()
    assert execution_of(s, DID) is None
    assert exec_ledger_of(s) == {}


def test_replay_reports_missing_digest_as_none_not_false():
    """旧档条目没有指纹时 → `digest_changed=None`（读数缺失，不谎报"内容没变"）。"""
    s = _state()
    backfill_decree(s, DECREE, MIN_A)
    s.statistics[LEDGER_STAT_KEY][DID].pop("digest")
    out = backfill_decree(s, DECREE, MIN_A)
    assert out["replay"] is True
    assert out["digest_changed"] is None


# ======================================================== ② 同一 decree_id 不重复执行
def test_same_decree_id_backfilled_twice_executes_once():
    """**幂等主断言**：同一 `decree_id` 补录两次，执行器只被调一次。"""
    s = _state()
    box, run = _counter()
    one = backfill_decree(s, DECREE, MIN_A, executor=run)
    assert one["applied"] is True
    assert one["outcome"] == OUTCOME_EXECUTED
    assert one["replay"] is False and one["idempotent"] is False
    assert box["n"] == 1

    two = backfill_decree(s, DECREE, MIN_A, executor=run)
    assert two["applied"] is False, "同一 decree_id 补录第二次仍然生效了"
    assert two["replay"] is True and two["idempotent"] is True
    assert box["n"] == 1, "执行器被调了第二次"
    # 如实回报首次结果，不重算、不改写
    assert two["outcome"] == one["outcome"] == OUTCOME_EXECUTED
    assert two["first"]["turn"] == one["first"]["turn"]
    assert two["first"]["by"] == MIN_A
    assert two["first"]["digest"] == one["first"]["digest"]
    assert two["digest_changed"] is False
    assert execution_of(s, DID)["schema_version"] == DECREE_CONFIRM_SCHEMA_VERSION


def test_repeated_backfill_five_times_still_executes_once():
    """连补五次（含重试）也只生效一次。"""
    s = _state()
    box, run = _counter()
    outs = [backfill_decree(s, DECREE, MIN_A, executor=run) for _ in range(5)]
    assert box["n"] == 1
    assert [o["applied"] for o in outs] == [True, False, False, False, False]
    assert all(o["replay"] is False if i == 0 else o["replay"] is True
               for i, o in enumerate(outs))
    assert execution_of(s, DID)["outcome"] == OUTCOME_EXECUTED


def test_reissuing_same_id_with_changed_body_still_does_not_execute():
    """**重下旨**：同一 id 内容变了，仍按 id 幂等不重跑，但必须把"内容漂移"报出来。"""
    s = _state()
    box, run = _counter()
    backfill_decree(s, DECREE, MIN_A, executor=run)
    mutated = dict(DECREE, desc="发内帑三百万缗。")
    out = backfill_decree(s, mutated, MIN_A, executor=run)
    assert out["applied"] is False
    assert out["digest_changed"] is True, "同 id 改内容重下没有被报出来"
    assert "内容已变" in out["message"]
    assert box["n"] == 1


def test_claim_is_stamped_before_the_executor_so_a_crash_cannot_double_execute():
    """执行器报错 → 记 `failed` 并**不自动重试**（宁可不重复，不可重复执行）。"""
    s = _state()
    calls = {"n": 0}

    def boom(_s, _d):
        calls["n"] += 1
        raise RuntimeError("太仓不足")

    one = backfill_decree(s, DECREE, MIN_A, executor=boom)
    assert one["applied"] is False
    assert one["outcome"] == OUTCOME_FAILED
    assert execution_of(s, DID)["error"] == "RuntimeError"

    two = backfill_decree(s, DECREE, MIN_A, executor=boom)
    assert two["applied"] is False and two["replay"] is True
    assert two["outcome"] == OUTCOME_FAILED
    assert calls["n"] == 1, "失败后被静默重跑了"
    assert "不重复执行" in two["message"]


def test_mismatch_blocks_and_does_not_occupy_the_id():
    """复述不符 → 不执行**也不记账**；改正复述后同 id 仍可正常执行一次。"""
    s = _state()
    box, run = _counter()
    bad = backfill_decree(s, DECREE, MIN_A, executor=run,
                          recitation={"title": DECREE["title"], "body": "发内帑三百万缗。"})
    assert bad["applied"] is False
    assert bad["blocked_by"] == STATUS_MISMATCH
    assert box["n"] == 0
    assert execution_of(s, DID) is None, "被挡下的补录也占了 id"

    good = backfill_decree(s, DECREE, MIN_A, executor=run,
                           recitation=compose_recitation(canonical_decree(DECREE)))
    assert good["applied"] is True and box["n"] == 1
    # 复述记录里两条都在：错的那条不被抹掉（可查）
    rows = recitations_of(s, DID, MIN_A)
    assert len(rows) == 2
    assert rows[-1]["elements"]["body"] == BODY
    # 第三次仍然不重跑
    assert backfill_decree(s, DECREE, MIN_A, executor=run)["applied"] is False
    assert box["n"] == 1


def test_backfill_candidates_lists_only_decrees_without_a_record():
    """待补录清单：列漏记/漏执行者；补录后自动出列。"""
    s = _state()
    d = _pending_secret(s)
    s.pending_decrees.append({"decree_id": "d_pub_1", "title": "开仓赈济"})
    ids = {c["decree_id"] for c in backfill_candidates(s)}
    assert ids == {DID, "d_pub_1"}
    row = {c["decree_id"]: c for c in backfill_candidates(s)}[DID]
    assert row["queue"] == "pending_secret_decrees"
    assert row["addressees"] == [MIN_A]
    assert row["executed"] is False

    box, run = _counter()
    assert backfill_decree(s, d, MIN_A, executor=run)["applied"] is True
    assert DID not in {c["decree_id"] for c in backfill_candidates(s)}
    assert "d_pub_1" in {c["decree_id"] for c in backfill_candidates(s)}
    assert box["n"] == 1


# ======================================================== 跨回合 / 读档
def test_idempotency_survives_save_load():
    """读档后：复述记录仍在（跨回合可查），台账仍在（**不重复执行**）。"""
    from core.save_load import load_game, save_game
    s = _state()
    box, run = _counter()
    assert backfill_decree(s, DECREE, MIN_A, executor=run)["applied"] is True
    s.turn = 12
    assert save_game(s, 88) is True
    s2 = load_game(88)
    assert s2 is not None
    assert s2.minister_agents[MIN_A]["authority"] == 0.7

    rows = recitations_of(s2, DID, MIN_A)
    assert len(rows) == 1
    assert rows[0]["elements"]["title"] == DECREE["title"]
    assert rows[0]["turn"] == 0, "复述回合没随档保留"

    box2, run2 = _counter()
    out = backfill_decree(s2, DECREE, MIN_A, executor=run2)
    assert out["applied"] is False and out["replay"] is True
    assert out["outcome"] == OUTCOME_EXECUTED
    assert box2["n"] == 0, "读档后同一 decree_id 又执行了一次"

    # 读档后复述仍可确认（不必重新复述）
    assert confirm_decree(s2, DID, MIN_A, decree=DECREE)["status"] == STATUS_CONFIRMED


# ======================================================== 逐人隔离
def test_recitation_is_per_person_not_shared():
    """甲的复述不是乙亲闻：乙看不到甲的记录，也确认不了。"""
    s = _state()
    # 这道旨未点名受命人（否则乙会先被判 not_addressee），只考"记忆不串人"这一层
    free = {k: v for k, v in DECREE.items() if k != "target"}
    assert confirm_decree(s, DID, MIN_A, decree=free, record=True)["status"] == STATUS_CONFIRMED
    assert recitations_of(s, DID, MIN_B) == []
    assert latest_recitation(s, DID, MIN_B) is None
    assert all(e.get("kind") != MEMORY_KIND_RECITE for e in recall(s, MIN_B))
    out_b = confirm_decree(s, DID, MIN_B, decree=free)
    assert out_b["authorized"] is True, "乙权限足够，应先过权限这一关"
    assert out_b["status"] == STATUS_UNDEFINED and out_b["reason"] == "not_recited"
    assert out_b["suggested_recitation"] is not None, "乙拿不到标准复述就无从开口"


# ======================================================== 读数不改 state
def test_readonly_calls_do_not_touch_state():
    """读数是纯函数：不写记忆、不写台账、不动官员运行态与回合。"""
    s = _state()
    s.turn = 7
    agents_before = copy.deepcopy(s.minister_agents)
    stats_before = copy.deepcopy(dict(s.statistics))

    decree_of(s, DID)
    decree_id_of(DECREE)
    addressees_of(DECREE)
    canon = canonical_decree(DECREE)
    decree_digest(canon)
    compose_recitation(canon)
    render_recitation(canon)
    compare_recitation(canon, canon)
    recitations_of(s, DID, MIN_A)
    latest_recitation(s, DID, MIN_A)
    execution_of(s, DID)
    exec_ledger_of(s)
    backfill_candidates(s)
    confirm_decree(s, DID, MIN_A, decree=DECREE)                     # 未复述 → undefined
    confirm_decree(s, DID, MIN_A, decree=DECREE,                     # 给了复述但不落记
                   recitation=compose_recitation(canon))
    confirm_decree(s, DID, MIN_B, decree=DECREE)                     # 未授权
    confirm_decree(s, "查无此旨", MIN_A)                             # 原旨缺失

    assert s.minister_agents == agents_before, "读数改写了官员运行态"
    assert dict(s.statistics) == stats_before, "读数改写了 statistics"
    assert s.turn == 7


def test_no_parallel_state_ledger():
    """不新增 `state.*` 属性：复述走各人自己的记忆，执行台账挂在既有 `statistics` 下。"""
    s = _state()
    before = set(vars(s))
    box, run = _counter()
    backfill_decree(s, DECREE, MIN_A, executor=run)
    assert set(vars(s)) == before, "冒出了与 minister_agents 平行的 state 属性"
    # 复述只落在本人记忆里（与 B5-5 知情范围同一处，不另立第二本账）
    kinds = [e["kind"] for e in recall(s, MIN_A)]
    assert kinds.count(MEMORY_KIND_RECITE) == 1
    # 执行台账挂在存档白名单内的既有容器上
    assert LEDGER_STAT_KEY in s.statistics
    assert set(exec_ledger_of(s)) == {DID}
    assert box["n"] == 1


def test_backfill_without_executor_moves_no_money_or_people():
    """本模块**不代数值落地**（POP 挂载律：不碰钱粮人口）。"""
    s = _state()
    before = (s.treasury, s.imperial_treasury, s.granary,
              s.population, s.population_satisfaction,
              {k: v["size"] for k, v in s.pops.items()} if isinstance(
                  getattr(s, "pops", None), dict) else None)
    out = backfill_decree(s, DECREE, MIN_A)
    assert out["applied"] is True
    assert out["outcome"] == OUTCOME_REGISTERED_ONLY, "无执行器却谎称已执行"
    assert "既有通道" in (out["first"]["detail"] or "")
    after = (s.treasury, s.imperial_treasury, s.granary,
             s.population, s.population_satisfaction,
             {k: v["size"] for k, v in s.pops.items()} if isinstance(
                 getattr(s, "pops", None), dict) else None)
    assert before == after, "补录顺手动了钱粮或人口"
    assert set(OUTCOMES) == {OUTCOME_EXECUTED, OUTCOME_REGISTERED_ONLY,
                             OUTCOME_FAILED, "claimed"}


# ======================================================== 口径与格式
def test_canonical_decree_covers_exactly_the_six_elements():
    """复述要素就是那六项，键序稳定（口径单点）。"""
    canon = canonical_decree(DECREE)
    assert tuple(canon) == ELEMENTS
    assert canon["title"] == "括民苍生"
    assert canon["body"] == BODY
    assert canon["visibility"] == "公"
    assert canon["delivery"] == "口谕"
    assert canon["addressees"] == [MIN_A]
    assert list(canon["effects"]) == sorted(canon["effects"])
    assert decree_digest(canon) == decree_digest(canonical_decree(dict(DECREE)))
    assert decree_digest(canon) != decree_digest(canonical_decree(dict(DECREE, title="换题")))


def test_secret_decree_in_queue_is_found_and_read_as_secret():
    """密旨同样走复述确认（队列里的原文可被查到，可见性判为「密」）。"""
    s = _state()
    d = _pending_secret(s)
    assert decree_of(s, DID) is d
    assert decree_of(s, "查无此旨") is None
    out = confirm_decree(s, DID, MIN_A, record=True)
    assert out["status"] == STATUS_CONFIRMED
    assert canonical_decree(d)["visibility"] == "密"


def test_zhongzhi_visibility_is_distinct_from_plain_secret():
    """中旨与密旨的可见性要素不同（不被当成同一件事）。"""
    plain = canonical_decree({"decree_id": "z1", "is_secret": True})
    zhong = canonical_decree({"decree_id": "z2", "is_secret": True, "is_zhongzhi": True})
    assert plain["visibility"] == "密" and zhong["visibility"] == "中旨"


# ======================================================== 拒绝式
def test_invalid_inputs_are_rejected():
    """非法输入明确报错，不静默放行。"""
    s = _state()
    with pytest.raises(ValueError):
        confirm_decree(s, "  ", MIN_A, decree=DECREE)                  # 空 decree_id
    with pytest.raises(ValueError):
        confirm_decree(s, DID, "  ", decree=DECREE)                   # 空 actor_id
    with pytest.raises(ValueError):
        confirm_decree(s, DID, MIN_A, decree=DECREE, recitation="我明白了")
    with pytest.raises(ValueError):
        confirm_decree(s, DID, MIN_A, decree=DECREE, record="是")
    with pytest.raises(ValueError):
        confirm_decree(s, DID, MIN_A, decree=["不是对象"])
    with pytest.raises(ValueError):
        compare_recitation(canonical_decree(DECREE), "不是对象")
    with pytest.raises(ValueError):
        record_recitation(s, DID, MIN_A, {"胡说": "八道"})
    with pytest.raises(ValueError):
        record_recitation(s, DID, MIN_A, "不是对象")
    with pytest.raises(ValueError):
        record_recitation(s, "", MIN_A, {"title": "x"})
    with pytest.raises(ValueError):
        backfill_decree(s, DECREE, "")
    with pytest.raises(ValueError):
        backfill_decree(s, {"title": ""}, MIN_A)                      # 无名之旨
    with pytest.raises(ValueError):
        backfill_decree(s, 42, MIN_A)                                 # 类型不对
    with pytest.raises(ValueError):
        backfill_decree(s, DECREE, MIN_A, executor="不是可调用对象")
    # 拒绝之后没留下任何痕迹
    assert execution_of(s, DID) is None
    assert all(e.get("kind") != MEMORY_KIND_RECITE for e in recall(s, MIN_A))
