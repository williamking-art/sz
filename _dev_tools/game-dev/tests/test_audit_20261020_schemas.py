# -*- coding: utf-8 -*-
"""R-N-4：AI 契约 JSON Schema 结构层——真实校验（不再"缺依赖恒放行"零覆盖）。

Jev：A 0.441 / B 0.303 / C 0.256（近平手，按 A 执行并留档：
`decisions/JEV-RN4-结构层收口-2026-10-20.json`）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

jsonschema = pytest.importorskip("jsonschema", reason="extras 依赖未装；结构层按设计放行")


def test_structural_layer_rejects_invalid_registered_contract():
    from ai.schemas import schema_check

    ok, err = schema_check("dialogue", {"mood": "平"})   # 缺 reply
    assert ok is False
    assert "reply" in err and "required" in err.lower(), err
    ok2, _ = schema_check("dialogue", {"reply": "臣谨奏", "mood": "平"})
    assert ok2 is True


def test_schema_status_reports_enabled_and_intentional_subset():
    from ai.schemas import HAS_JSONSCHEMA, SCHEMAS, schema_status

    st = schema_status()
    assert st["enabled"] is True and HAS_JSONSCHEMA is True
    assert st["registered"] == len(SCHEMAS) == 5, st
    assert set(st["contracts"]) == {
        "dialogue", "advice", "parse_decree", "monthly_report", "event_narrative"}
    assert "有意子集" in st["coverage_note"]


def test_unregistered_contract_still_passes_structure_layer():
    from ai.schemas import schema_check

    assert schema_check("some_future_decide", {"anything": 1})[0] is True
