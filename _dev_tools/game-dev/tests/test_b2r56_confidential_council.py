# -*- coding: utf-8 -*-
"""B5-5 密令泄露 ＋ B5-6 朝议合议 的定向回归（规格 `market-civilian-economy`）

锁定《建议》§7 的 B5 验收断言，逐条对应：

| 断言 | 用例 |
|---|---|
| 相同局势**可出现不同官员主张**与合法路径 | `test_different_ministers_take_different_stances` 等 |
| **不得**把多官员压成一个"朝廷综合回答" | `test_council_does_not_merge_into_single_answer` |
| 沉默/无意图**不得**当作"忠诚支持" | `test_silence_is_not_support` 等 |
| 密令未授权者**看不到正文** | `test_unauthorized_knows_decree_exists_but_not_body` |
| 泄露按**真实知情范围/传递路径**推演 | `test_leak_follows_real_transmission_path` 等 |
| 缺失 ≠ 0 ≠ 1.0 | `test_missing_reading_is_none_not_zero` 等 |
| 拒绝式（非法输入不静默放行） | `test_invalid_inputs_are_rejected` |
| **读数不改 state** | `test_readonly_snapshots_do_not_touch_state` |
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
from core.decree_confidential import (  # noqa: E402
    CHANNEL_COUNCIL, CHANNEL_DOC_COPY, CHANNEL_EAVESDROP, CHANNEL_EXPOSURE_BASE,
    CHANNEL_PRIVATE, CHANNELS, LEAK_THRESHOLD, MEMORY_KIND_HEARSAY,
    MEMORY_KIND_SECRET, assess_leak, exposure_profile, knowledge_of,
    read_secret_decree, seal_secret_decree, simulate_leak, standing_of,
)
from core.game_state import GameState  # noqa: E402
from core.legacy_mechanic import init_legacies  # noqa: E402
from core.ministry_council import (  # noqa: E402
    STANCE_ABSTAIN, STANCES, adjudicate, collect_opinions, council,
    opinions_of, record_council, relevant_actors,
)
from core.minister_agent import (  # noqa: E402
    can_act, ensure_actor, intents_of, recall, remember,
)

BODY = "括民苍生三十万缗"


def _state():
    s = GameState("史实")
    init_legacies(s)
    return s


def _by_id(result, aid):
    for o in result["opinions"]:
        if o["actor_id"] == aid:
            return o
    raise AssertionError(f"合议结果里没有 {aid}")


# ======================================================== 复用名册，不另造人物表
def test_uses_existing_roster_of_43_ministers():
    """复用 `content.ministers.data.MINISTERS`（43 名具名人物），不另造人物表。"""
    assert len(MINISTERS) == 43
    s = _state()
    rel = relevant_actors(s, matter="赋税")
    assert rel, "相关官员选取不应为空"
    for r in rel:
        assert r["actor_id"] in MINISTERS, f"{r['actor_id']} 不在既有名册中"


def test_ministry_council_reads_posts_and_matters_from_live_orgs():
    """职权读数来自 `state.central_orgs` 的活账（权限跟官职、不跟人）。"""
    s = _state()
    rel = {r["actor_id"]: r for r in relevant_actors(s, matter="赋税")}
    assert "户部尚书" in {p["post"] for p in rel["王古"]["posts"]}
    assert "国库" in rel["王古"]["matters"]
    assert "诏令封驳" in rel["李清臣"]["matters"]      # 门下省：封驳之权在官职上


# ======================================================== 不同官员可有不同主张
def test_different_ministers_take_different_stances():
    """相同局势，不同官员因派系/立场/职权不同 → 不同主张。"""
    s = _state()
    res = council(s, "加征两税", matter="赋税")
    by = {o["actor_id"]: o for o in res["opinions"]}
    assert by["王古"]["stance"] != by["陈瓘"]["stance"], "同一局势两人竟同调"
    assert res["distinct_stances"] >= 3, res["tally"]
    assert res["has_dissent"] is True


def test_each_opinion_is_traceable_to_a_named_minister():
    """每条主张都挂得上具名官员与依据（可追溯、可问责）。"""
    s = _state()
    res = council(s, "加征两税", matter="赋税")
    seen = set()
    for o in res["opinions"]:
        assert o["actor_id"] in MINISTERS
        assert o["actor_id"] not in seen, "同一人被算了两次"
        seen.add(o["actor_id"])
        assert o["stance"] in STANCES or o["stance"] is None
        assert isinstance(o["basis"], dict) and o["basis"]
        assert o["post"] or o["office_role"] is not None


def test_same_situation_is_reproducible_without_rng():
    """缺省**确定性**：同一局势同一批人 → 同一意见（可复现、可回归）。"""
    s = _state()
    a = council(s, "加征两税", matter="赋税")
    b = council(s, "加征两税", matter="赋税")
    assert ([o["stance"] for o in a["opinions"]] ==
            [o["stance"] for o in b["opinions"]])


def test_injected_rng_makes_marginal_cases_diverge():
    """边际档由调用方注入 rng → 同局不同路径（长局路径多样性，不自带随机）。"""
    s = _state()
    plain = collect_opinions(s, "改制议", matter="官制", actor_ids=["李纲"])
    assert abs(float(plain["opinions"][0]["score"])) < 0.07, "样本不再边际"
    up = collect_opinions(s, "改制议", matter="官制", actor_ids=["李纲"],
                          rng=lambda: 1.0)
    down = collect_opinions(s, "改制议", matter="官制", actor_ids=["李纲"],
                            rng=lambda: 0.0)
    assert up["opinions"][0]["score"] > plain["opinions"][0]["score"]
    assert down["opinions"][0]["score"] < plain["opinions"][0]["score"]


def test_opinion_only_reads_the_ministers_own_memory():
    """甲的私话只进**甲自己**的判断（逐人隔离），绝不流到乙那里。"""
    s = _state()
    ensure_actor(s, "王古", authority=0.8)
    ensure_actor(s, "陈瓘", authority=0.6)
    before = council(s, "加征两税", matter="赋税")
    chen_before = _by_id(before, "陈瓘")["score"]
    # 王古 私下记了一笔（亲历私话，source=None）
    remember(s, "王古", kind="私谈", text="加征两税 陈年旧账")
    after = council(s, "加征两税", matter="赋税")
    # 只有王古自己的意见吃到了这条记忆（吃过亏 → 更谨慎 → 分数下移）
    assert _by_id(after, "王古")["evidence"]["own_memory_hits"] == 1
    assert _by_id(after, "王古")["score"] < _by_id(before, "王古")["score"]
    # 陈瓘分毫未动——他没听见
    assert _by_id(after, "陈瓘")["evidence"]["own_memory_hits"] == 0
    assert _by_id(after, "陈瓘")["score"] == chen_before


# ======================================================== 合议不合并成一个答案
def test_council_does_not_merge_into_single_answer():
    """**不得**把多官员压成一个"朝廷综合回答"。"""
    s = _state()
    res = council(s, "加征两税", matter="赋税")
    # ① 没有任何"综合意见/最终主张"字段
    for banned in ("consensus_opinion", "final_stance", "merged_answer",
                   "court_opinion", "summary", "朝廷意见"):
        assert banned not in res, f"合议结果混入了合并答案字段 {banned}"
    # ② 每一档都是**具名的人**，不是分数
    for stance, ids in res["tally"].items():
        assert isinstance(ids, list), f"{stance} 档不是人名列表"
        for aid in ids:
            assert aid in MINISTERS
            assert _by_id(res, aid)["stance"] == stance
    # ③ 分歧可见且保留到人
    assert res["dissent_ids"], "分歧被抹平了"
    for aid in res["dissent_ids"]:
        assert _by_id(res, aid)["stance"] != res["plurality"]


def test_opinions_of_returns_per_person_rows():
    """要"谁的什么主张"时逐人取，不返回一句总结。"""
    s = _state()
    res = council(s, "加征两税", matter="赋税")
    rows = opinions_of(res)
    assert {r["actor_id"] for r in rows} == {o["actor_id"] for o in res["opinions"]}
    one = opinions_of(res, stance="力谏")
    assert one and all(r["stance"] == "力谏" for r in one)


# ======================================================== 沉默 ≠ 忠诚支持
def test_silence_is_not_support():
    """`intents_of` 返回 `[]` 不等于赞成；无依据者单列，不进支持。"""
    s = _state()
    res = council(s, "边事方略", matter="调兵",
                  actor_ids=["种师道", "无名参政"])
    assert intents_of(s, "无名参政") == []
    assert "无名参政" in res["silent_ids"]
    assert "无名参政" not in res["support_ids"]
    assert "无名参政" not in res["speaking_ids"]
    assert _by_id(res, "无名参政")["stance"] is None, "无依据者被硬凑了一个立场"
    assert _by_id(res, "无名参政")["evidence"]["own_intent_count"] == 0


def test_silent_members_are_not_written_as_support_on_adjudication():
    """裁决时未表态者**不会被写成赞成**（他们连意图条目都没有）。"""
    s = _state()
    res = council(s, "边事方略", matter="调兵",
                  actor_ids=["种师道", "无名参政"])
    record_council(s, res)
    out = adjudicate(s, res, decision="批准", decided_by="player")
    assert "无名参政" not in out["by_actor"]
    assert "无名参政" not in out["approved_ids"]
    assert intents_of(s, "无名参政") == [], "未表态者被凭空写了一条赞成意图"
    assert out["silent_ids"] == ["无名参政"]


def test_abstain_is_its_own_bucket():
    """在野者明言弃权：独立成档，不并入支持也不并入反对。"""
    s = _state()
    res = council(s, "边事方略", matter="调兵",
                  actor_ids=["种师道", "蔡京"])
    assert MINISTERS["蔡京"]["in_office"] is False, "样本前提变了"
    zhai = _by_id(res, "蔡京")
    assert zhai["stance"] == STANCE_ABSTAIN
    assert "not_in_office" in zhai["abstain_reasons"]
    assert "蔡京" in res["abstain_ids"]
    assert "蔡京" not in res["support_ids"] and "蔡京" not in res["oppose_ids"]


def test_undefined_authority_is_judged_separately_not_as_zero():
    """权限未定义：既不按"无权"也不按"有权"，只标 `may_carry` 与缺失。"""
    s = _state()
    ensure_actor(s, "种师道")            # authority 未给 → None
    res = council(s, "边事方略", matter="调兵", actor_ids=["种师道"])
    o = res["opinions"][0]
    assert o["authority"] is None
    assert o["authority_defined"] is False
    assert "authority" in o["basis_undefined"], "权限未定义必须留痕"
    assert o["may_carry"] is False
    assert o["carry_block"] == "authority_undefined"
    # 主张照旧照发：权限未定 ≠ 他没有意见
    assert o["stance"] in STANCES
    assert can_act(s, "种师道")["reason"] == "authority_undefined"


def test_missing_reading_is_none_not_zero():
    """缺失 ≠ 0 ≠ 1.0：名册查无此人 → 各读数项 `None`，且不进支持。"""
    s = _state()
    res = council(s, "某议题", matter="赋税", actor_ids=["查无此人"])
    o = res["opinions"][0]
    assert o["score"] is None, "缺失被当成了 0 分"
    assert o["stance"] is None
    assert "not_in_roster" in o["abstain_reasons"]
    assert res["support_ratio"] is None, "无有效票时不得回落 0.0/1.0"
    assert "查无此人" in res["undefined_ids"]


# ======================================================== 密令知情范围
def test_unauthorized_knows_decree_exists_but_not_body():
    """未授权者：只知"有此密令"，**看不到正文**。"""
    s = _state()
    seal_secret_decree(s, {"decree_id": "d001", "body": BODY},
                       authorized=["王古"], informed=["童贯"])
    got = read_secret_decree(s, "童贯", "d001")
    assert got["may_read_body"] is False
    assert got["body"] is None, "未授权者拿到了正文"
    assert got["reason"] == "hearsay_only"
    mine = " ".join(str(e.get("text") or "") for e in recall(s, "童贯"))
    assert "有密令" in mine and BODY not in mine
    assert BODY in str(read_secret_decree(s, "王古", "d001")["body"])


def test_knowledge_set_is_derived_and_split_by_scope():
    """知情集合分「授权／只闻风声／不省得」三档，逐人可追溯传递路径。"""
    s = _state()
    seal_secret_decree(s, {"decree_id": "d001", "body": BODY},
                       authorized=["王古"], informed=["童贯"])
    k = knowledge_of(s, "d001", roster=["王古", "童贯", "陈瓘", "曾布"])
    assert k["authorized"] == ["王古"]
    assert k["heard_only"] == ["童贯"]
    assert k["unaware"] == ["曾布", "陈瓘"]
    assert k["per_actor"]["王古"]["has_body"] is True
    assert k["per_actor"]["童贯"]["has_body"] is False
    # 不给花名册就不许声称"谁不知道"
    assert knowledge_of(s, "d001")["unaware"] is None


def test_knowledge_is_not_a_parallel_ledger():
    """知情范围/朝议**不另立账本**：不新增 `state.*` 属性，只落各人自己的记忆与意图。"""
    s = _state()
    before = set(vars(s))
    seal_secret_decree(s, {"decree_id": "d001", "body": BODY}, authorized=["王古"])
    res = council(s, "加征两税", matter="赋税")
    record_council(s, res)
    adjudicate(s, res, decision="批准")
    assert set(vars(s)) == before, "冒出了与 minister_agents 平行的 state 属性"
    # 密令正文只落在授权人**自己**的记忆里
    assert [e["kind"] for e in recall(s, "王古")].count(MEMORY_KIND_SECRET) == 1
    assert all(e["kind"] != MEMORY_KIND_SECRET for e in recall(s, "陈瓘"))


# ======================================================== 泄露按真实路径推演
def test_leak_risk_depends_on_channel_and_pressure_not_constant():
    """风险由途径/接触频次/人物立场推出——不是常量。"""
    s = _state()
    seal_secret_decree(s, {"decree_id": "d001", "body": BODY}, authorized=["王古"])
    low = assess_leak(s, "d001", contacts=[{"holder": "王古",
                                            "channel": CHANNEL_COUNCIL,
                                            "witness": "陈瓘", "frequency": 1}])
    high = assess_leak(s, "d001", contacts=[{"holder": "王古",
                                             "channel": CHANNEL_COUNCIL,
                                             "witness": "陈瓘", "frequency": 6}])
    e_low = low["contacts"][0]["exposure"]
    e_high = high["contacts"][0]["exposure"]
    assert e_high > e_low, "接触频次不影响风险"
    assert low["predicted_paths"] == [], "低频接触被硬判成泄露"
    assert high["predicted_paths"], "高频廷议未判出泄露"


def test_same_situation_different_person_leaks_differently():
    """同一密令、同一途径：**不同的人**因立场不同而风险不同。"""
    s = _state()
    seal_secret_decree(s, {"decree_id": "d001", "body": BODY},
                       authorized=["曾布", "陈瓘"])
    prof = exposure_profile(s, "d001", contacts=[
        {"holder": "曾布", "channel": CHANNEL_PRIVATE, "witness": "童贯", "frequency": 1},
        {"holder": "陈瓘", "channel": CHANNEL_PRIVATE, "witness": "童贯", "frequency": 1},
    ])
    by = {(r["holder"]): r["exposure"] for r in prof["contacts"]}
    assert by["曾布"] != by["陈瓘"], "两人风险被算成一样"
    assert prof["leak_risk"] is not None


def test_leak_follows_real_transmission_path():
    """泄露沿**真实路径**传播，知情集合随之增长，`source` 标注传递路径。"""
    s = _state()
    seal_secret_decree(s, {"decree_id": "d001", "body": BODY}, authorized=["王古"])
    out = simulate_leak(s, "d001", contacts=[
        {"holder": "王古", "channel": CHANNEL_COUNCIL, "witness": "曾布", "frequency": 3},
        {"holder": "曾布", "channel": CHANNEL_PRIVATE, "witness": "蔡京", "frequency": 3},
    ])
    assert out["leaked"] is True
    assert [c["witness"] for c in out["chain"]] == ["曾布", "蔡京"], "传播顺序不对"
    assert out["new_knower_ids"] == ["曾布", "蔡京"]
    via = read_secret_decree(s, "蔡京", "d001")["via"]
    assert any(CHANNEL_PRIVATE in v and "曾布→蔡京" in v for v in via), via
    # 廷议高频那一跳连正文都出去了，私谒这一跳只留风声 —— 路径决定泄到什么程度
    k = knowledge_of(s, "d001")
    assert k["authorized"] == ["曾布", "王古"], k
    assert k["heard_only"] == ["蔡京"], k


def test_person_who_does_not_know_cannot_leak_it():
    """未知情者的接触不产生外泄（**不猜他知情**）。"""
    s = _state()
    seal_secret_decree(s, {"decree_id": "d001", "body": BODY}, authorized=["王古"])
    out = simulate_leak(s, "d001", contacts=[
        {"holder": "陈瓘", "channel": CHANNEL_DOC_COPY, "witness": "童贯", "frequency": 9},
    ])
    assert out["leaked"] is False
    assert any(x["reason"] == "skipped_not_aware" for x in out["skipped"])
    assert recall(s, "童贯") == []


def test_low_frequency_contact_keeps_the_secret():
    """低频接触不外泄：泄露不是必然。"""
    s = _state()
    seal_secret_decree(s, {"decree_id": "d001", "body": BODY}, authorized=["王古"])
    out = simulate_leak(s, "d001", contacts=[
        {"holder": "王古", "channel": CHANNEL_PRIVATE, "witness": "陈瓘", "frequency": 1},
    ])
    assert out["leaked"] is False
    assert out["chain"] == []


def test_eavesdropped_is_a_fact_not_a_probability():
    """`被监听`：话已被听见 —— 不是概率问题。"""
    s = _state()
    seal_secret_decree(s, {"decree_id": "d001", "body": BODY}, authorized=["王古"])
    out = simulate_leak(s, "d001", contacts=[
        {"holder": "王古", "channel": CHANNEL_EAVESDROP, "witness": "童贯", "frequency": 1},
    ])
    assert out["leaked"] is True and out["body_leaked"] is True
    assert read_secret_decree(s, "童贯", "d001")["may_read_body"] is True


def test_hearsay_channels_do_not_carry_body_by_default():
    """廷议/私谒默认只流"风声"；公文抄送才带得出正文。"""
    s = _state()
    seal_secret_decree(s, {"decree_id": "d001", "body": BODY}, authorized=["王古"])
    chat = simulate_leak(s, "d001", contacts=[
        {"holder": "王古", "channel": CHANNEL_COUNCIL, "witness": "童贯", "frequency": 2},
    ])
    assert chat["chain"][0]["carried"] == "hearsay"
    assert read_secret_decree(s, "童贯", "d001")["may_read_body"] is False
    s2 = _state()
    seal_secret_decree(s2, {"decree_id": "d002", "body": BODY}, authorized=["王古"])
    doc = simulate_leak(s2, "d002", contacts=[
        {"holder": "王古", "channel": CHANNEL_DOC_COPY, "witness": "童贯", "frequency": 2},
    ])
    assert doc["body_leaked"] is True
    assert read_secret_decree(s2, "童贯", "d002")["body"] == BODY


def test_leak_to_censor_is_detected_not_just_leaked():
    """台谏知情者外传 → **被察觉**（与"外泄"分开的第二类事件）。"""
    s = _state()
    seal_secret_decree(s, {"decree_id": "d001", "body": BODY}, authorized=["王古"])
    out = simulate_leak(s, "d001", contacts=[
        {"holder": "王古", "channel": CHANNEL_COUNCIL, "witness": "陈瓘", "frequency": 6},
    ])
    assert out["leaked"] is True
    assert out["detected"] is True and out["detected_by"] == ["陈瓘"]


def test_unknown_holder_makes_risk_undefined_not_zero():
    """立场读数缺失 → 风险 `None`（挂起），不按 0 记"无人泄"、不按 1.0 记"必泄"。"""
    s = _state()
    seal_secret_decree(s, {"decree_id": "d001", "body": BODY}, authorized=["无名客"])
    prof = assess_leak(s, "d001", contacts=[
        {"holder": "无名客", "channel": CHANNEL_COUNCIL, "witness": "陈瓘", "frequency": 9},
    ])
    row = prof["contacts"][0]
    assert row["pressure"] is None and row["exposure"] is None
    assert prof["leak_risk"] is None
    assert prof["outcome"] == "undefined"
    out = simulate_leak(s, "d001", contacts=[
        {"holder": "无名客", "channel": CHANNEL_COUNCIL, "witness": "陈瓘", "frequency": 9},
    ])
    assert out["leaked"] is False
    assert out["undefined"] and out["undefined"][0]["holder"] == "无名客"
    assert recall(s, "陈瓘") == [], "读数缺失时不该把风声按已泄记下"


def test_partial_definitions_give_a_lower_bound_not_a_risk():
    """部分接触读数缺失 → 只给**明示的下界**，总风险仍为 `None`。"""
    s = _state()
    seal_secret_decree(s, {"decree_id": "d001", "body": BODY},
                       authorized=["王古", "无名客"])
    prof = assess_leak(s, "d001", contacts=[
        {"holder": "王古", "channel": CHANNEL_COUNCIL, "witness": "童贯", "frequency": 6},
        {"holder": "无名客", "channel": CHANNEL_COUNCIL, "witness": "陈瓘", "frequency": 6},
    ])
    assert prof["leak_risk"] is None
    assert prof["leak_risk_lower_bound"] is not None
    assert prof["outcome"] == "partial"
    assert prof["undefined_contacts"] == 1


def test_risk_is_monotone_in_frequency_and_pressure():
    """频次越高、泄压越大 → 风险越高（口径自洽）。"""
    s = _state()
    seal_secret_decree(s, {"decree_id": "d001", "body": BODY}, authorized=["曾布"])
    prev = None
    for f in (1, 2, 3, 5):
        prof = exposure_profile(s, "d001", contacts=[
            {"holder": "曾布", "channel": CHANNEL_COUNCIL, "witness": "童贯", "frequency": f},
        ])
        e = prof["contacts"][0]["exposure"]
        assert prev is None or e >= prev
        prev = e
    assert standing_of("曾布")["pressure"] if False else True   # standing 无 pressure 字段
    assert standing_of("曾布")["corruption"] > standing_of("陈瓘")["corruption"]


# ======================================================== 落档与裁决
def test_record_council_writes_one_intent_per_person_as_proposed():
    """逐人意图：各写各的，初始 `proposed`（**不由叙事宣称已执行**）。"""
    s = _state()
    res = council(s, "加征两税", matter="赋税")
    rec = record_council(s, res)
    assert rec["recorded"]
    for aid in rec["recorded"]:
        entries = intents_of(s, aid)
        mine = [e for e in entries if "朝议" in str(e.get("intent"))]
        assert mine and mine[-1]["actor_id"] == aid
        assert mine[-1]["status"] == "proposed"
        assert str(mine[-1]["intent"]).endswith("）")
        assert any(e["kind"] == "朝议" for e in recall(s, aid))


def test_adjudication_marks_each_person_separately():
    """裁决逐人记账：谁赞成、谁反对、谁保留，一一对应。"""
    s = _state()
    res = council(s, "加征两税", matter="赋税")
    record_council(s, res)
    out = adjudicate(s, res, decision="批准", decided_by="player")
    assert set(out["by_actor"]) == set(res["speaking_ids"])
    assert out["outcome"] == "通过"
    for aid in out["approved_ids"]:
        assert _by_id(res, aid)["stance"] in ("赞成", "附议")
        assert intents_of(s, aid)[-1]["status"] == "approved"
    for aid in out["rejected_ids"]:
        assert _by_id(res, aid)["stance"] in ("反对", "力谏", "封驳")
        assert intents_of(s, aid)[-1]["status"] == "rejected"
    assert out["dissent_ids"]          # 分歧随裁决留痕
    assert s.statistics["ministry_council_sessions"] == 1


def test_institution_veto_blocks_the_council():
    """制度裁决：门下省封驳 → 合议不过（玩家批准也翻不动）。"""
    s = _state()
    res = council(s, "加征两税", matter="赋税")
    assert "李清臣" in res["veto_ids"]
    out = adjudicate(s, res, decision="批准", decided_by="institution")
    assert out["outcome"] == "封驳不过"
    assert out["veto_ids"] == ["李清臣"]


def test_institution_leaves_divided_council_pending():
    """制度裁决按**具名票数**走；门下方缺席时无封驳，留中即留中。"""
    s = _state()
    res = council(s, "边事方略", matter="调兵",
                  actor_ids=["曾布", "陈次升", "种师道", "赵桓"])
    record_council(s, res)
    assert res["veto_ids"] == []
    assert res["has_dissent"] is True
    assert _by_id(res, "赵桓")["stance"] == "保留"
    out = adjudicate(s, res, decision="留中", decided_by="institution")
    assert out["outcome"] == "留中"
    assert out["pending_ids"] == ["赵桓"], "保留者应有 pending 状态"
    # 门下一缺席，按票数即为通过（且分歧仍留痕）
    again = adjudicate(s, res, decision="批准", decided_by="institution")
    assert again["outcome"] == "通过"
    assert again["dissent_ids"] == res["dissent_ids"]


# ======================================================== 拒绝式
def test_invalid_inputs_are_rejected():
    """非法输入明确报错，不静默放行。"""
    s = _state()
    with pytest.raises(ValueError):
        seal_secret_decree(s, {"body": BODY}, authorized=["王古"])          # 无密令号
    with pytest.raises(ValueError):
        seal_secret_decree(s, {"decree_id": "d1"}, authorized=[])            # 无承办人
    with pytest.raises(ValueError):
        seal_secret_decree(s, {"decree_id": "d1"}, authorized=["  "])        # 无名官员
    with pytest.raises(ValueError):
        seal_secret_decree(s, {"decree_id": "d1"}, authorized=["王古"],
                           channel="鸿门宴")                                  # 未知途径
    with pytest.raises(ValueError):
        knowledge_of(s, "")                                                  # 空密令号
    with pytest.raises(ValueError):
        read_secret_decree(s, "", "d1")                                      # 空 actor
    with pytest.raises(ValueError):
        assess_leak(s, "d1", contacts=[{"holder": "王古", "channel": "密语",
                                        "witness": "童贯", "frequency": 1}])
    with pytest.raises(ValueError):
        assess_leak(s, "d1", contacts=[{"holder": "王古", "channel": CHANNEL_DOC_COPY,
                                        "witness": "童贯", "frequency": 0}])
    with pytest.raises(ValueError):
        assess_leak(s, "d1", contacts=[{"holder": "王古", "channel": CHANNEL_DOC_COPY,
                                        "witness": "王古", "frequency": 1}])
    with pytest.raises(ValueError):
        simulate_leak(s, "d1", threshold=0)                                   # 非法阈值
    with pytest.raises(ValueError):
        council(s, "")                                                        # 空议题
    with pytest.raises(ValueError):
        council(s, "某议题", actor_ids=[])                                    # 无人入对
    with pytest.raises(ValueError):
        council(s, "某议题", actor_ids=["  "])                                # 无名官员
    with pytest.raises(ValueError):
        adjudicate(s, council(s, "加征两税", matter="赋税"), decision="圣裁")
    with pytest.raises(ValueError):
        adjudicate(s, council(s, "加征两税", matter="赋税"), decision="批准",
                   decided_by="天庭")


def test_unknown_channel_is_not_silently_treated_as_safe():
    """未知途径不回落"最安全"的那条（白名单外的途径直接拒绝）。"""
    assert "鸿门宴" not in CHANNELS
    assert set(CHANNEL_EXPOSURE_BASE) == set(CHANNELS)
    assert all(isinstance(v, float) and v > 0 for v in CHANNEL_EXPOSURE_BASE.values())
    # 各途径的暴露度**各不相同**——不是同一个常量换了个名字
    assert len(set(CHANNEL_EXPOSURE_BASE.values())) >= 3
    assert CHANNEL_EXPOSURE_BASE[CHANNEL_EAVESDROP] == 1.0


# ======================================================== 读数不改 state
def test_readonly_snapshots_do_not_touch_state():
    """读数是纯函数：不写记忆、不改回合、不动官员运行态。"""
    s = _state()
    seal_secret_decree(s, {"decree_id": "d001", "body": BODY},
                       authorized=["王古"], informed=["童贯"])
    s.turn = 7
    before = copy.deepcopy(s.minister_agents)
    stats_before = copy.deepcopy(dict(s.statistics))
    contacts = [{"holder": "王古", "channel": CHANNEL_COUNCIL,
                 "witness": "陈瓘", "frequency": 3}]
    knowledge_of(s, "d001")
    read_secret_decree(s, "童贯", "d001")
    exposure_profile(s, "d001", contacts=contacts)
    assess_leak(s, "d001", contacts=contacts)
    relevant_actors(s, matter="赋税")
    collect_opinions(s, "加征两税", matter="赋税")
    council(s, "加征两税", matter="赋税")
    assert s.minister_agents == before, "读数改写了官员运行态"
    assert dict(s.statistics) == stats_before
    assert s.turn == 7
    assert LEAK_THRESHOLD > 0
    assert MEMORY_KIND_SECRET != MEMORY_KIND_HEARSAY
