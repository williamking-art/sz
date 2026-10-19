# -*- coding: utf-8 -*-
"""M3a：弹劾闭环（JEV 裁 B：中枢大臣 + 联名弹章）。"""
import copy

from core import commands
from core import impeachment
from core.commands_decree import accept_memorial, dismiss_memorial


def _state():
    return commands.new_game()


def _memo(**kw):
    m = {
        "kind": "impeachment", "memorial_id": "m1", "title": "弹章",
        "target": "邓洵武", "target_kind": "central",
        "accusers": ["李清臣", "陈次升"],
        "trigger_fact": "擅权铨选",
        "severity": 0.8,
        "evidence_refs": [{"kind": "audit", "id": "a1", "verified": True}],
    }
    m.update(kw)
    return m


def _open(s, memo=None):
    s.memorials = [memo or _memo()]
    return accept_memorial(s, 0)


def test_missing_fields_does_not_open_case():
    s = _state()
    s.memorials = [_memo(trigger_fact="")]
    out = accept_memorial(s, 0)
    assert out["ok"] is False
    assert s.impeachments == {}
    assert len(s.memorials) == 1


def test_joint_impeachment_opens_case_without_dismissal():
    s = _state()
    out = _open(s)
    assert out["ok"] is True
    case = s.impeachments[out["case_id"]]
    assert case["status"] == "investigating"
    assert case["accusers"] == ["李清臣", "陈次升"]
    assert s.central_orgs["吏部"]["holders"]["吏部尚书"] == "邓洵武"


def test_supported_evidence_rules_dismiss_but_does_not_dismiss_yet():
    s = _state()
    cid = _open(s)["case_id"]
    res = impeachment.review_case(s, cid)
    case = res["case"]
    assert case["fact_finding"] == "supported"
    assert case["institutional_ruling"] == "dismiss"
    assert case["status"] == "awaiting_disposal"
    assert s.central_orgs["吏部"]["holders"]["吏部尚书"] == "邓洵武"


def test_force_dismiss_keeps_fact_finding_and_clears_holder():
    s = _state()
    cid = _open(s)["case_id"]
    impeachment.review_case(s, cid)
    fact = s.impeachments[cid]["fact_finding"]
    out = impeachment.dispose_case(s, cid, "force_dismiss")
    assert out["dismissed"] is True
    assert s.impeachments[cid]["fact_finding"] == fact
    assert s.central_orgs["吏部"]["holders"]["吏部尚书"] == ""
    assert s.minister_status("邓洵武") == "dismissed"


def test_unsupported_evidence_acquits():
    s = _state()
    cid = _open(s, _memo(evidence_refs=[{"id": "a1", "verified": False}]))["case_id"]
    case = impeachment.review_case(s, cid)["case"]
    assert case["fact_finding"] == "unsupported"
    assert case["institutional_ruling"] == "acquit"


def test_unknown_evidence_retries():
    s = _state()
    cid = _open(s, _memo(evidence_refs=[]))["case_id"]
    case = impeachment.review_case(s, cid)["case"]
    assert case["fact_finding"] == "unknown"
    assert case["institutional_ruling"] == "retry"
    assert case["status"] == "investigating"


def test_same_case_is_idempotent():
    s = _state()
    cid = _open(s)["case_id"]
    again = _open(s, _memo(memorial_id="m1"))
    assert again.get("case_id") == cid
    assert len(s.impeachments) == 1


def test_leave_in_does_not_open_case():
    s = _state()
    s.memorials = [_memo()]
    dismiss_memorial(s, 0)
    assert s.impeachments == {}


def test_dispose_is_idempotent():
    s = _state()
    cid = _open(s)["case_id"]
    impeachment.review_case(s, cid)
    impeachment.dispose_case(s, cid, "force_dismiss")
    before = copy.deepcopy(s.impeachments[cid])
    again = impeachment.dispose_case(s, cid, "force_dismiss")
    assert again.get("duplicate") is True
    assert s.impeachments[cid] == before


def test_impeachments_are_json_roundtrip_safe():
    import json
    s = _state()
    _open(s)
    blob = json.dumps(s.impeachments, ensure_ascii=False)
    assert json.loads(blob) == s.impeachments

