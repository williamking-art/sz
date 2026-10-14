# -*- coding: utf-8 -*-
"""M257 P3 · 诏令复述门与执行台账接线定向回归（已获用户授权，覆盖 typesafe 0.17 闸门）。

测试覆盖：
1. 未指派具体在册大臣的诏令：正常通行，执行后登入 `decree_exec_ledger`（by="朝廷"）；
2. 幂等防重放：已在 `decree_exec_ledger` 中标记 `executed` 的同 `decree_id` 诏令，不重复执行；
3. 指定在册大臣（建档+在朝+有权）：复述门 `confirm_decree` 自动标准复述放行，登入台账（by=大臣名）；
4. 指定在册大臣（已存复述不符）：门禁驳回，不执行效果，台账记 `failed` 并留痕原因；
5. 指定在册大臣（无权/在野）：门禁驳回，不执行效果，台账记 `failed`；
6. 指定在册大臣（权限未定义）：按硬约束挂起（留在 pending，不假装执行）；
7. 密旨通道接线：指定大臣走门禁、未指定通行、防重放生效。
"""
import copy
import random
import pytest

from core import commands
from core.decree_confirm import (
    OUTCOME_EXECUTED,
    OUTCOME_FAILED,
    STATUS_CONFIRMED,
    STATUS_MISMATCH,
    STATUS_UNAUTHORIZED,
    STATUS_UNDEFINED,
    exec_ledger_of,
    execution_of,
    record_recitation,
)
from core.domains.administration import minister_agent as ma
from core.settlement_decree import _settle_decrees


AID_A = "王古"
AID_B = "曾布"


def _state():
    random.seed(20261013)
    s = commands.new_game()
    ma.ensure_actor(s, AID_A, posts=["户部尚书"], authority=0.7)
    s.minister_agents[AID_A]["status"] = ma.MINISTER_STATUS_IN_OFFICE
    return s


def test_unassigned_decree_passes_and_records_ledger(monkeypatch):
    """1. 未指派具体在册大臣的普发诏令：通行并登记至执行台账（by="朝廷"）。"""
    s = _state()
    did = "d_unassigned_001"
    decree = {
        "decree_id": did,
        "title": "普开仓赈济",
        "category": "诏令",
        "is_secret": False,
        "duration": 1,
        "effects": {"treasury": -500},
    }
    s.pending_decrees.append(decree)
    monkeypatch.setattr(random, "random", lambda: 0.0)  # 必过概率检定

    log = []
    _settle_decrees(s, log)

    # 执行台账已记账
    rec = execution_of(s, did)
    assert rec is not None, "未指派诏令执行后应登记执行台账"
    assert rec["outcome"] == OUTCOME_EXECUTED
    assert rec["by"] == "朝廷"
    assert rec["confirm_status"] == STATUS_CONFIRMED
    assert rec["title"] == "普开仓赈济"


def test_idempotent_replay_prevention(monkeypatch):
    """2. 幂等防重放：已执行过的相同 decree_id 不得二次执行。"""
    s = _state()
    did = "d_idem_002"
    decree = {
        "decree_id": did,
        "title": "修筑海塘",
        "category": "诏令",
        "is_secret": False,
        "duration": 1,
        "effects": {"treasury": -1000},
    }
    s.pending_decrees.append(decree)
    monkeypatch.setattr(random, "random", lambda: 0.0)

    # 首次执行
    log1 = []
    _settle_decrees(s, log1)
    rec1 = execution_of(s, did)
    assert rec1 is not None and rec1["outcome"] == OUTCOME_EXECUTED

    # 模拟再次提交同一 decree_id
    decree_dup = copy.deepcopy(decree)
    s.pending_decrees.append(decree_dup)
    log2 = []
    _settle_decrees(s, log2)

    # 第二次应被幂等跳过
    assert any("此前已执行" in msg for msg in log2), f"应拦截重放：{log2}"
    assert not any("[本月] 诏令执行" in msg for msg in log2), "不应重复执行效果"


def test_designated_minister_authorized_passes(monkeypatch):
    """3. 指定在册大臣（在朝且有权）：复述门放行，台账记 by=该大臣。"""
    s = _state()
    did = "d_minister_003"
    decree = {
        "decree_id": did,
        "title": "户部核造版籍",
        "category": "诏令",
        "addressees": [AID_A],
        "is_secret": False,
        "duration": 1,
        "effects": {"prestige": 2},
    }
    s.pending_decrees.append(decree)
    monkeypatch.setattr(random, "random", lambda: 0.0)

    log = []
    _settle_decrees(s, log)

    rec = execution_of(s, did)
    assert rec is not None
    assert rec["outcome"] == OUTCOME_EXECUTED
    assert rec["by"] == AID_A
    assert rec["confirm_status"] == STATUS_CONFIRMED

    # 承办大臣记忆中已留下复述记录
    mem = s.minister_agents[AID_A].get("memory", [])
    assert any("复述" in str(m.get("kind", "")) and did in str(m.get("source", "")) for m in mem), \
        "承办大臣记忆中应留下对应 decree_id 的复述记录"


def test_designated_minister_diverging_recitation_is_rejected(monkeypatch):
    """4. 指定在册大臣已存复述与原旨不符：门禁驳回，不执行效果，台账记 failed。"""
    s = _state()
    did = "d_diverge_004"
    decree = {
        "decree_id": did,
        "title": "核定两税额",
        "body": "减两税一成以恤民力",
        "category": "诏令",
        "addressees": [AID_A],
        "is_secret": False,
        "duration": 1,
        "effects": {"treasury": -200},
    }
    # 事先由该官员写入一份篡改/不符的复述
    bad_elements = {
        "title": "核定两税额",
        "body": "增两税三成以充内帑",  # 篡改正文
        "delivery": "诏令",
        "visibility": "公",
        "addressees": [AID_A],
        "effects": {"treasury": 500},
    }
    record_recitation(s, did, AID_A, bad_elements, turn=s.turn)

    s.pending_decrees.append(decree)
    monkeypatch.setattr(random, "random", lambda: 0.0)

    log = []
    _settle_decrees(s, log)

    # 效果不应执行
    assert any("复述与原旨不符" in msg for msg in log), f"应报告不符原因：{log}"
    rec = execution_of(s, did)
    assert rec is not None
    assert rec["outcome"] == OUTCOME_FAILED
    assert rec["confirm_status"] == STATUS_MISMATCH


def test_designated_minister_unauthorized_is_rejected(monkeypatch):
    """5. 指定在册大臣无权承办（authority=0 或在野）：门禁驳回。"""
    s = _state()
    ma.ensure_actor(s, AID_B, posts=["中书舍人"], authority=0.0)  # authority=0 无权
    s.minister_agents[AID_B]["status"] = ma.MINISTER_STATUS_IN_OFFICE

    did = "d_unauth_005"
    decree = {
        "decree_id": did,
        "title": "中书核文",
        "addressees": [AID_B],
        "category": "诏令",
        "is_secret": False,
        "duration": 1,
        "effects": {},
    }
    s.pending_decrees.append(decree)
    monkeypatch.setattr(random, "random", lambda: 0.0)

    log = []
    _settle_decrees(s, log)

    assert any("无权承办" in msg for msg in log), f"应报告无权原因：{log}"
    rec = execution_of(s, did)
    assert rec is not None
    assert rec["outcome"] == OUTCOME_FAILED
    assert rec["confirm_status"] == STATUS_UNAUTHORIZED


def test_designated_minister_authority_undefined_is_suspended():
    """6. 指定在册大臣权限未定义（authority=None）：按硬约束挂起，留在待办。"""
    s = _state()
    ma.ensure_actor(s, AID_B, posts=["中书舍人"], authority=None)  # authority 未定义

    did = "d_undef_006"
    decree = {
        "decree_id": did,
        "title": "待定事务",
        "addressees": [AID_B],
        "category": "诏令",
        "is_secret": False,
        "duration": 1,
        "effects": {},
    }
    s.pending_decrees.append(decree)

    log = []
    _settle_decrees(s, log)

    # 未决诏令应被挂起，仍在 pending_decrees 中
    assert any("挂起" in msg and "复述确认未决" in msg for msg in log), f"应挂起：{log}"
    assert any(d.get("decree_id") == did for d in s.pending_decrees), "未决诏令应留在 pending_decrees"
    assert execution_of(s, did) is None, "未决诏令不应记已完成台账"


def test_secret_decree_wiring_and_idempotency(monkeypatch):
    """7. 密旨通道接线：指定大臣复述校验与幂等防重放均生效。"""
    s = _state()
    did = "d_sec_007"
    decree = {
        "decree_id": did,
        "title": "密访度支",
        "category": "密旨",
        "addressees": [AID_A],
        "is_secret": True,
        "duration": 1,
        "effects": {},
    }
    s.pending_secret_decrees.append(decree)
    monkeypatch.setattr(random, "random", lambda: 0.0)

    log1 = []
    _settle_decrees(s, log1)
    rec1 = execution_of(s, did)
    assert rec1 is not None and rec1["outcome"] == OUTCOME_EXECUTED
    assert rec1["by"] == AID_A

    # 重放下达同一密旨
    s.pending_secret_decrees.append(copy.deepcopy(decree))
    log2 = []
    _settle_decrees(s, log2)
    assert any("此前已执行" in msg for msg in log2), f"密旨应防重放：{log2}"
