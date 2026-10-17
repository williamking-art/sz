# -*- coding: utf-8 -*-
"""M34-③ AI 奏报接线（V1.3 §6 发现链二级"怀疑"）：

`record_suspicion` 唯一写入点（过滤/去重/容量）／**呈请**与**召对**两处接线／
窗口过滤／月报「度支录」臣工风闻／存档往返。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'game'))

from core.audit_case import (discovery_readout, record_suspicion,
                             scan_fiscal_suspicion)
from core.commands import audience_dialogue_apply, new_game
from core.monthly_gazette import build_monthly_gazette
from content.data import FIN_SUSPICION_CAP, FIN_SUSPICION_WINDOW_TURNS


def test_scan_and_record_filters_dedups_caps():
    s = new_game()
    assert scan_fiscal_suspicion("今日天气甚好") is None
    assert scan_fiscal_suspicion("账目不清") == "账目"
    assert record_suspicion(s, "今日天气甚好", source="召对", minister="陈瓘") is None
    r1 = record_suspicion(s, "臣闻某路火耗过重", source="召对", minister="陈瓘")
    assert r1 and r1["keyword"] == "火耗" and r1["turn"] == s.turn
    # 去重（同源＋同人＋同文）
    assert record_suspicion(s, "臣闻某路火耗过重", source="召对", minister="陈瓘") is None
    # 容量上限（超限丢最旧）
    for i in range(20):
        record_suspicion(s, f"第{i}奏：某路亏空甚巨", source="呈请", minister=f"臣{i}")
    assert len(s.discovery_suspicions) == FIN_SUSPICION_CAP


def test_enqueue_ai_action_records_suspicion_only_for_fiscal():
    s = new_game()
    s.enqueue_ai_action("propose_governance", "请核诸路火耗",
                        "诸路火耗过重，请遣官勾校", {}, proposer="陈瓘")
    assert any(x.get("source") == "呈请" and x.get("minister") == "陈瓘"
               for x in s.discovery_suspicions)
    # 非财政类呈请不入
    s2 = new_game()
    s2.enqueue_ai_action("secret_order", "整军", "请阅兵练卒", {}, proposer="种师道")
    assert s2.discovery_suspicions == []


def test_audience_dialogue_apply_records_suspicion():
    s = new_game()
    audience_dialogue_apply(s, "陈瓘", {"reply": "臣闻两浙路火耗奇重，账目恐有不实，请陛下察之。"})
    assert any(x.get("source") == "召对" for x in s.discovery_suspicions)
    assert discovery_readout(s)["level"] >= 2


def test_suspicion_window_excludes_old():
    s = new_game()
    record_suspicion(s, "某路亏空", source="召对", minister="陈瓘", turn=0)
    s.turn = FIN_SUSPICION_WINDOW_TURNS + 1        # 超出窗口 → 不计入"当前怀疑"
    assert discovery_readout(s)["suspicions"] == []
    assert discovery_readout(s)["level"] < 2
    s.turn = FIN_SUSPICION_WINDOW_TURNS            # 窗口内
    assert len(discovery_readout(s)["suspicions"]) == 1


def test_gazette_shows_minister_wind_line():
    s = new_game()
    record_suspicion(s, "臣闻某路火耗过重", source="召对", minister="陈瓘")
    g = build_monthly_gazette(s, year=1102, month=5)
    fin = next(c for c in g["chapters"] if c["title"] == "度支录")
    text = "\n".join(fin["lines"])
    assert "臣工风闻" in text and "陈瓘" in text


def test_suspicions_roundtrip_and_defaults():
    from core.save_load import load_game, save_game
    s = new_game()
    record_suspicion(s, "臣闻某路火耗过重", source="召对", minister="陈瓘")
    assert save_game(s, 9) is True
    s2 = load_game(9)
    assert s2 is not None
    assert any(x.get("minister") == "陈瓘" for x in s2.discovery_suspicions)
    assert new_game().discovery_suspicions == []
