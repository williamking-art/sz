# -*- coding: utf-8 -*-
"""I 首批（Jev A 0.967）：科技扩展提案只读校验骨架。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))


def _valid() -> dict:
    return {
        "proposal_id": "p1",
        "source": {"kind": "ai_innovation", "reference": "test"},
        "technology_extension": {
            "dimension": {"id": "new_dim", "name": "新维度"},
            "nodes": [
                {"id": "n1", "name": "节点1", "prerequisites": [], "research": {"cost": 100, "duration_months": 3}},
                {"id": "n2", "name": "节点2", "prerequisites": ["n1"], "effect_refs": ["yield_mult"]},
            ],
        },
        "blueprint_proposals": [
            {"kind": "new", "blueprint_id": "bp1", "definition": {"name": "x"}},
            {"kind": "upgrade", "blueprint_id": "bp2", "from_version": 1, "to_version": 2, "definition": {}},
        ],
    }


def test_valid_proposal_passes():
    from core.domains.economy.tech_extension_proposal import validate_tech_extension_proposal

    rep = validate_tech_extension_proposal(_valid())
    assert rep["ok"] is True, rep["errors"]
    assert rep["node_ids"] == ["n1", "n2"]
    assert rep["read_only"] is True


def test_duplicate_and_existing_id_rejected():
    from core.domains.economy.tech_extension_proposal import validate_tech_extension_proposal

    p = _valid()
    p["technology_extension"]["nodes"].append({"id": "n1", "name": "dup"})
    rep = validate_tech_extension_proposal(p)
    assert rep["ok"] is False and any("重复" in e for e in rep["errors"])
    rep2 = validate_tech_extension_proposal(_valid(), existing_ids=["n1"])
    assert rep2["ok"] is False and any("已发布" in e for e in rep2["errors"])


def test_missing_prereq_and_cycle_rejected():
    from core.domains.economy.tech_extension_proposal import validate_tech_extension_proposal

    p = _valid()
    p["technology_extension"]["nodes"][0]["prerequisites"] = ["ghost"]
    rep = validate_tech_extension_proposal(p)
    assert any("不存在" in e for e in rep["errors"])
    p2 = _valid()
    p2["technology_extension"]["nodes"][0]["prerequisites"] = ["n2"]
    rep2 = validate_tech_extension_proposal(p2)
    assert any("成环" in e for e in rep2["errors"])


def test_bad_blueprint_upgrade_rejected_and_unknown_warns():
    from core.domains.economy.tech_extension_proposal import validate_tech_extension_proposal

    p = _valid()
    p["blueprint_proposals"][1]["to_version"] = 1
    p["unknown_top"] = 1
    rep = validate_tech_extension_proposal(p)
    assert any("to_version" in e for e in rep["errors"])
    assert any("未知顶层字段" in w for w in rep["warnings"])


def test_missing_dimension_and_nodes_rejected():
    from core.domains.economy.tech_extension_proposal import validate_tech_extension_proposal

    rep = validate_tech_extension_proposal({})
    assert rep["ok"] is False
    assert any("technology_extension" in e for e in rep["errors"])
