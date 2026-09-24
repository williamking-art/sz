# -*- coding: utf-8 -*-
"""`audio/` 与 `telemetry/` 冒烟测试（第四轮全审 R4-5：两模块此前零测试）。

定位：只锁**对外契约与不变量**，不测内部实现细节——
- `audio/manifest.py`：槽位清单结构合法、键唯一、分类口径单一源、`audio_class_for` 回落；
- `telemetry/store.py`：写入/读回闭环、失败静默（连接为 None 时不上抛）、默认关闭。

遥测库一律用 tmp_path 显式建库（不依赖 SAVE_DIR，也不碰 `get_store()` 的进程级单例，
除非用例自己复位它）。
"""
import os

import pytest

from audio.manifest import (
    AUDIO_SLOTS, AudioSlot, EVENT_AUDIO_CLASS, audio_class_for, register_slot,
)
import telemetry.store as ts


# ════════════════════════════════════════════
# audio / manifest
# ════════════════════════════════════════════

def test_audio_slots_非空且键唯一():
    assert AUDIO_SLOTS, "音频槽位清单不应为空"
    keys = [s.key for s in AUDIO_SLOTS]
    assert len(keys) == len(set(keys)), f"槽位键重复：{keys}"


def test_audio_slots_分类与音量档位合法():
    allowed = {"bgm", "sfx", "voice"}
    for s in AUDIO_SLOTS:
        assert isinstance(s, AudioSlot)
        assert s.category in allowed, f"{s.key} 分类非法：{s.category}"
        assert s.trigger, f"{s.key} 缺触发点描述（触发点是接线依据）"
        assert 0.0 <= s.volume_bias <= 1.0, f"{s.key} 音量档位越界：{s.volume_bias}"


def test_bgm_槽位必须循环():
    for s in AUDIO_SLOTS:
        if s.category == "bgm":
            assert s.loop is True, f"背景乐 {s.key} 未标 loop"


def test_未落位资源不得标记_ready():
    """`ready` 是「是否已生成并落位」；file 为空即尚未落地，两者不得矛盾。"""
    for s in AUDIO_SLOTS:
        if not s.file:
            assert s.ready is False, f"{s.key} 无文件却标记 ready"


def test_event_audio_class_取值收敛():
    allowed = {"urgent", "auspicious", "normal"}
    for eid, cls in EVENT_AUDIO_CLASS.items():
        assert cls in allowed, f"{eid} 的音效分类非法：{cls}"


def test_audio_class_for_已知与未知回落():
    assert audio_class_for("huanghe_flood") == "urgent"
    assert audio_class_for("xiangrui") == "auspicious"
    # 未知事件回落 default（朝务/一般），不得抛 KeyError
    assert audio_class_for("zzqqxx_不存在的事件") == "normal"
    assert audio_class_for("zzqqxx_不存在的事件", default="urgent") == "urgent"


def test_register_slot_可追加并复原():
    before = len(AUDIO_SLOTS)
    extra = AudioSlot("test_tmp_slot", "sfx", trigger="测试用临时槽位")
    register_slot(extra)
    try:
        assert len(AUDIO_SLOTS) == before + 1
        assert AUDIO_SLOTS[-1].key == "test_tmp_slot"
    finally:
        AUDIO_SLOTS.remove(extra)
    assert len(AUDIO_SLOTS) == before, "测试结束未复原，会污染其它用例"


# ════════════════════════════════════════════
# telemetry / store
# ════════════════════════════════════════════

@pytest.fixture
def store(tmp_path):
    s = ts.TelemetryStore(path=str(tmp_path / "t.db"))
    try:
        yield s
    finally:
        s.close()


def test_telemetry_写入与读回闭环(store):
    assert store.record_ai_call("economy_decide", prompt_tokens=120, completion_tokens=30)
    assert store.record_monthly(3, {"treasury": 12345, "grain": 999})
    assert store.record_event(3, "huanghe_flood", {"choice": "赈济"})

    s = store.summary()
    assert s["ai_calls"] == 1
    assert s["prompt_tokens"] == 120 and s["completion_tokens"] == 30
    assert s["monthly_records"] == 1 and s["event_records"] == 1
    # 按方法分桶（计量面板的数据源）
    assert s["by_method"] and s["by_method"][0]["method"] == "economy_decide"

    series = store.monthly_series()
    assert len(series) == 1 and series[0]["turn"] == 3
    assert series[0]["treasury"] == 12345, "月度快照的键值应原样读回"


def test_telemetry_monthly_series_按回合升序(store):
    for turn in (5, 1, 3):
        assert store.record_monthly(turn, {"turn": turn})
    assert [r["turn"] for r in store.monthly_series()] == [1, 3, 5]


def test_telemetry_超长字段被截断而不报错(store):
    """method 截 40 字、event name 截 60 字——截断是契约的一部分（防表膨胀）。"""
    assert store.record_ai_call("x" * 500)
    assert store.record_event(1, "y" * 500)
    s = store.summary()
    assert s["ai_calls"] == 1
    rows = store._conn.execute("SELECT length(method) FROM ai_calls").fetchone()
    assert rows[0] == 40


def test_telemetry_关闭连接后写入返回False且不上抛(store):
    """失败静默是硬契约：遥测任何异常都不得影响游戏。"""
    store.close()
    assert store.record_ai_call("x") is False
    assert store.record_monthly(1, {}) is False
    assert store.record_event(1, "x") is False
    assert store.summary() == {}
    assert store.monthly_series() == []


def test_telemetry_入库路径不存在时静默降级(tmp_path):
    """目录不可建 → _open 失败把 _conn 置 None，所有方法返回 False 而不炸。"""
    bad = str(tmp_path / "no_such_dir" / "deep" / "t.db")
    # Windows/Linux 下 makedirs 会创建父目录，故用「把文件路径当目录」制造必然失败
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file", encoding="utf-8")
    s = ts.TelemetryStore(path=str(blocker / "t.db"))
    assert s._conn is None
    assert s.record_ai_call("x") is False
    assert s.summary() == {}


def test_telemetry_默认关闭(monkeypatch):
    monkeypatch.delenv("SONGZUO_TELEMETRY", raising=False)
    assert ts.enabled() is False


def test_telemetry_get_store_单例与开关(monkeypatch, tmp_path):
    monkeypatch.setenv("SONGZUO_TELEMETRY", "1")
    monkeypatch.setattr(ts, "_store", None)
    import content.data as cd
    monkeypatch.setattr(cd, "SAVE_DIR", str(tmp_path))
    try:
        a = ts.get_store()
        assert a is not None
        assert ts.get_store() is a, "启用时应返回同一进程级单例"
        assert os.path.isdir(str(tmp_path))
    finally:
        a.close()
        monkeypatch.setattr(ts, "_store", None)

    monkeypatch.setenv("SONGZUO_TELEMETRY", "0")
    assert ts.get_store() is None
