# -*- coding: utf-8 -*-
"""天道决策日志**离线回测器**契约（`core/ai/tiandao_backtest.py`）。

覆盖（任务 B 的验收清单）：
1. `brier`：完全正确 / 恒定 0.5 / 空输入 ⇒ `None`；
2. `reliability_bins`：手工可算的例子验算 ECE（算式见用例注释），空箱不计入；
3. `hit_rate`：gate 与 choose 两种口径；
4. `monotonic_check`：单调 / 非单调 / 单点（`None` 而非 `True`）；
5. `summarize`：无标签时**不得**给 Brier 数字；有标签时数值可复算；
6. CLI：存在的存档 ⇒ 0；不存在的路径 ⇒ 2。

纪律：本文件只用**合成记录 + 合成标签**，不 new_game、不写存档目录；
CLI 用例的输入写在 `tmp_path`。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "game"))

import core.ai.tiandao_backtest as bt  # noqa: E402

# ── 合成记录工厂（schema 与写入端 tiandao_decision.decide_and_log 一致）──────
def _rec(turn, objective, verdict, probability, defined=True, cached=False):
    return {"turn": turn, "objective": objective, "verdict": verdict,
            "probability": probability, "defined": defined,
            "provider": "tiandao_local", "seed": turn, "cached": cached,
            "facts_digest": None}


# ══════════════════════════════════════════════════════════════════════════
# 1) Brier
# ══════════════════════════════════════════════════════════════════════════
def test_brier_perfect_and_uninformative_and_empty():
    # 完全正确 ⇒ 0.0；两张 0.5 一正一负 ⇒ 0.25；空输入 ⇒ None（不是 0）
    assert bt.brier([(0.0, False), (1.0, True)]) == 0.0
    assert bt.brier([(0.5, True), (0.5, False)]) == 0.25
    assert bt.brier([]) is None
    assert bt.brier(None) is None


def test_brier_ignores_unusable_entries_instead_of_counting_them_as_zero():
    # 越界概率 / 缺 outcome 的条目一律剔除；只剩 1 条有效 ⇒ 按 1 条算
    assert bt.brier([(1.5, True), (0.0, None), (0.3, True)]) == pytest.approx(0.49, abs=1e-9)


# ══════════════════════════════════════════════════════════════════════════
# 2) 可靠性分箱 + ECE
# ══════════════════════════════════════════════════════════════════════════
def test_reliability_bins_ece_hand_computed():
    """手工算例（bins=10）：

    组 A：3 条 p=0.9，outcome = [T, T, F] ⇒ mean_p = 0.9，hit_rate = 2/3，
          gap = 0.9 − 2/3 = 0.233333…（落在 [0.9, 1.0) 末箱附近的第 9 箱）
    组 B：2 条 p=0.3，outcome = [F, F]     ⇒ mean_p = 0.3，hit_rate = 0，
          gap = 0.3 − 0 = 0.3

    ECE = Σ (n_i / N) · |gap_i|
        = (3/5)·0.233333… + (2/5)·0.3
        = 0.14            + 0.12
        = 0.26
    """
    records = ([_rec(i, "g", True, 0.9) for i in range(3)]
               + [_rec(10 + i, "g", False, 0.3) for i in range(2)])
    outcomes = {("g", 0): True, ("g", 1): True, ("g", 2): False,
                ("g", 10): False, ("g", 11): False}

    rel = bt.reliability_bins(records, outcomes, bins=10)
    assert rel["n"] == 5
    assert rel["ece"] == pytest.approx(0.26, abs=1e-9)

    # 空箱不计入：只有两个非空箱，且每个箱 n > 0
    assert len(rel["bins"]) == 2
    assert all(b["n"] > 0 for b in rel["bins"])
    hi_bin = rel["bins"][-1]
    assert hi_bin["lo"] == 0.9 and hi_bin["hi"] == 1.0
    assert hi_bin["mean_p"] == pytest.approx(0.9, abs=1e-9)
    assert hi_bin["hit_rate"] == pytest.approx(2 / 3, abs=1e-6)
    assert hi_bin["gap"] == pytest.approx(0.9 - 2 / 3, abs=1e-6)

    lo_bin = rel["bins"][0]
    assert lo_bin["mean_p"] == pytest.approx(0.3, abs=1e-9)
    assert lo_bin["hit_rate"] == 0.0
    assert lo_bin["gap"] == pytest.approx(0.3, abs=1e-9)


def test_reliability_bins_without_labels_returns_none_not_zero():
    rel = bt.reliability_bins([_rec(0, "g", True, 0.8)], None)
    assert rel["ece"] is None and rel["ece_reason"]
    assert rel["bins"] == [] and rel["n"] == 0


# ══════════════════════════════════════════════════════════════════════════
# 3) 命中率（gate / choose 两种口径）
# ══════════════════════════════════════════════════════════════════════════
def test_hit_rate_gate_and_choose_are_counted_separately():
    records = [
        _rec(0, "g", True, 0.7),                      # gate 命中
        _rec(1, "g", False, 0.3),                     # gate 命中
        _rec(2, "g", False, None, defined=False),     # undefined ⇒ 不参与
        _rec(10, "c", "moderate", 0.8),               # choose 命中（argmax=moderate）
        _rec(11, "c", "strict", 0.4),                 # choose 未命中（argmax=lenient）
    ]
    outcomes = {
        ("g", 0): True,
        ("g", 1): False,
        ("c", 10): {"strict": 0.1, "moderate": 0.8, "lenient": 0.1},
        ("c", 11): {"strict": 0.3, "moderate": 0.3, "lenient": 0.4},
    }

    hr = bt.hit_rate(records, outcomes)
    assert hr["n"] == 4 and hr["gate_n"] == 2 and hr["choose_n"] == 2
    assert hr["hits"] == 3
    assert hr["rate"] == pytest.approx(0.75, abs=1e-9)
    # fail-closed 的 False 不算预测 ⇒ 必须报出来，而不是悄悄充数
    assert hr["skipped_undefined"] == 1


def test_hit_rate_without_labels_rate_is_none():
    hr = bt.hit_rate([_rec(0, "g", True, 0.7)], None)
    assert hr["n"] == 0 and hr["hits"] == 0
    assert hr["rate"] is None and hr["reason"]


# ══════════════════════════════════════════════════════════════════════════
# 4) 单调性
# ══════════════════════════════════════════════════════════════════════════
def test_monotonic_up_allows_ties():
    # 概率并列不算违反（非严格单调）
    chk = bt.monotonic_check([(0.1, 0.2), (0.2, 0.5), (0.3, 0.5)])
    assert chk["monotonic"] is True and chk["direction"] == "up"
    assert chk["violations"] == []


def test_monotonic_down():
    chk = bt.monotonic_check([(0.1, 0.9), (0.2, 0.4), (0.4, 0.1)])
    assert chk["monotonic"] is True and chk["direction"] == "down"


def test_monotonic_driver_ties_are_not_compared():
    # 同一驱动值下概率可任意（并列允许），不参与比较
    chk = bt.monotonic_check([(1.0, 0.9), (1.0, 0.1), (2.0, 0.9)])
    assert chk["monotonic"] is True and chk["direction"] == "up"


def test_monotonic_non_monotone_reports_violations():
    chk = bt.monotonic_check([(0.1, 0.9), (0.2, 0.2), (0.3, 0.8)])
    assert chk["monotonic"] is False
    assert chk["direction"] is None
    assert chk["violations"], "非单调必须给出违反序对，不能只给 False"
    for i, j in chk["violations"]:
        assert i < j


def test_monotonic_single_point_and_empty_are_unknown():
    assert bt.monotonic_check([(1.0, 0.5)])["monotonic"] is None
    assert bt.monotonic_check([])["monotonic"] is None
    assert bt.monotonic_check([(1.0, 0.5)])["direction"] is None


def test_expected_direction_only_audited_ones_are_known():
    up = bt.expected_direction("waive_arrears", "unrest")
    assert up["status"] == "audited" and up["direction"] == "up"
    down = bt.expected_direction("granary_corruption", "integrity")
    assert down["status"] == "audited" and down["direction"] == "down"
    # 未登记方向 ⇒ unknown（不许凭空发明）
    unknown = bt.expected_direction("tax_stance", "unrest")
    assert unknown["status"] == "unknown" and unknown["direction"] is None

    # 与实测方向对照：符合 ⇒ True；未登记 ⇒ None（不是 False）
    ok = bt.check_expected_direction("waive_arrears", "unrest",
                                     [(1.0, 0.2), (2.0, 0.5), (3.0, 0.9)])
    assert ok["agrees"] is True
    bad = bt.check_expected_direction("waive_arrears", "unrest",
                                      [(1.0, 0.9), (2.0, 0.5), (3.0, 0.2)])
    assert bad["agrees"] is False
    na = bt.check_expected_direction("tax_stance", "unrest", [(1.0, 0.2), (2.0, 0.9)])
    assert na["agrees"] is None


# ══════════════════════════════════════════════════════════════════════════
# 5) 汇总
# ══════════════════════════════════════════════════════════════════════════
def test_summarize_without_labels_never_reports_brier_numbers():
    records = [_rec(0, "g", True, 0.8), _rec(1, "g", False, 0.2),
               _rec(2, "c", "moderate", 0.6)]
    rep = bt.summarize(records)

    assert rep["distribution_only"] is True
    assert rep["records"] == 3
    assert rep["labels_provided"] is False
    for obj, entry in rep["objectives"].items():
        # 🔴 无标签时**不得**出现任何 Brier/ECE/命中率数字
        assert entry["brier"] is None, obj
        assert entry["ece"] is None, obj
        assert entry["hit_rate"] is None, obj
        assert entry["brier_reason"] and entry["ece_reason"], obj
        # 分布与覆盖率仍必须有
        assert entry["probability"]["n"] >= 1, obj
        assert entry["defined_n"] >= 1, obj
        assert entry["probability_histogram"], obj


def test_summarize_with_labels_matches_hand_computation():
    # 4 条 gate：p = 0.9/0.8/0.2/0.1，真值 = T/T/F/F
    records = [_rec(0, "g", True, 0.9), _rec(1, "g", True, 0.8),
               _rec(2, "g", False, 0.2), _rec(3, "g", False, 0.1)]
    labels = [{"objective": "g", "turn": i, "outcome": v}
              for i, v in enumerate([True, True, False, False])]
    rep = bt.summarize(records, labels)

    entry = rep["objectives"]["g"]
    assert rep["labels_provided"] is True and rep["distribution_only"] is False
    assert rep["labels_matched"] == 4 and rep["label_coverage"] == 1.0

    # Brier = mean((0.1)^2, (0.2)^2, (0.2)^2, (0.1)^2) = mean(0.01,0.04,0.04,0.01) = 0.025
    assert entry["brier"] == pytest.approx(0.025, abs=1e-9)
    # 4 条都命中 ⇒ 1.0
    assert entry["hit_rate"]["rate"] == pytest.approx(1.0, abs=1e-9)
    # ECE = 每箱 1 条：|0.9-1| + |0.8-1| + |0.2-0| + |0.1-0| = 0.1+0.2+0.2+0.1 = 0.6 ⇒ /4 = 0.15
    assert entry["ece"] == pytest.approx(0.15, abs=1e-9)


def test_summarize_partial_labels_reports_coverage_and_keeps_metrics_honest():
    records = [_rec(0, "g", True, 0.9), _rec(1, "g", False, 0.4)]
    labels = [{"objective": "g", "turn": 0, "outcome": True},
              {"objective": "g", "turn": 99, "outcome": True}]  # 99 在记录里不存在
    rep = bt.summarize(records, labels)

    entry = rep["objectives"]["g"]
    assert rep["label_coverage"] == 0.5
    assert entry["labels_matched"] == 1
    assert entry["brier"] == pytest.approx(0.01, abs=1e-9)   # 只用被标签覆盖的那 1 条
    assert rep["unmatched_labels"] == [{"objective": "g", "turn": 99}]


def test_summarize_duplicate_labels_are_reported_not_silently_overwritten():
    records = [_rec(0, "g", True, 0.5)]
    labels = [{"objective": "g", "turn": 0, "outcome": True},
              {"objective": "g", "turn": 0, "outcome": False}]
    rep = bt.summarize(records, labels)
    assert rep["duplicate_labels"] == [{"objective": "g", "turn": 0}]
    # 保留第一条（outcome=True）⇒ Brier = (0.5-1)^2 = 0.25
    assert rep["objectives"]["g"]["brier"] == pytest.approx(0.25, abs=1e-9)


# ══════════════════════════════════════════════════════════════════════════
# 6) 读档与 CLI
# ══════════════════════════════════════════════════════════════════════════
def test_load_log_accepts_both_nestings(tmp_path):
    row = _rec(0, "g", True, 0.6)
    p_flat = tmp_path / "flat.json"
    p_flat.write_text(json.dumps({"decision_log": [row]}, ensure_ascii=False), encoding="utf-8")
    p_nested = tmp_path / "nested.json"
    p_nested.write_text(json.dumps({"data": {"decision_log": [row]}}, ensure_ascii=False),
                        encoding="utf-8")

    assert bt.load_log(str(p_flat)) == [row]
    assert bt.load_log(str(p_nested)) == [row]


def test_load_log_missing_key_raises_backtest_error(tmp_path):
    p = tmp_path / "old_save.json"
    p.write_text(json.dumps({"turn": 3}), encoding="utf-8")
    with pytest.raises(bt.BacktestError):
        bt.load_log(str(p))


def test_cli_returns_zero_on_existing_save_and_two_on_missing(tmp_path, capsys):
    save = tmp_path / "save.json"
    save.write_text(json.dumps({"decision_log": [_rec(0, "g", True, 0.7)]},
                               ensure_ascii=False), encoding="utf-8")

    assert bt.main([str(save)]) == 0
    assert "回测" in capsys.readouterr().out

    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps(
        {"labels": [{"objective": "g", "turn": 0, "outcome": True}]},
        ensure_ascii=False), encoding="utf-8")
    assert bt.main([str(save), "--labels", str(labels), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["labels_provided"] is True
    assert report["objectives"]["g"]["brier"] == pytest.approx(0.09, abs=1e-9)

    missing = tmp_path / "does_not_exist.json"
    assert bt.main([str(missing)]) == 2
    assert "无法回测" in capsys.readouterr().err


def test_cli_rejects_save_without_decision_log(tmp_path, capsys):
    save = tmp_path / "no_log.json"
    save.write_text(json.dumps({"turn": 1}), encoding="utf-8")
    assert bt.main([str(save)]) == 2
    assert "decision_log" in capsys.readouterr().err


def test_cli_hardens_stdio_so_cp936_console_does_not_crash(tmp_path, monkeypatch, capsys):
    """CLI 必须把 stdio 切到 UTF-8：Windows 中文控制台（cp936）下报告含 `⇒` 会
    UnicodeEncodeError ⇒ 进程以退出码 1 崩掉，而契约只允许 0/2。

    实测背景（2026-10-21 集成复验）：subprocess 未加 `-X utf8` 时，真实存档 + `--json`
    确实崩在 main()。本用例锁死"加固被调用"，并验证 reconfigure 缺失时**不得**抛。
    """
    calls = []

    class _FakeStream:
        def reconfigure(self, **kw):
            calls.append(kw)

    monkeypatch.setattr(bt.sys, "stdout", _FakeStream())
    monkeypatch.setattr(bt.sys, "stderr", _FakeStream())
    bt._harden_stdio()
    assert calls and all(k.get("encoding") == "utf-8" for k in calls)
    assert all(k.get("errors") == "replace" for k in calls)

    # 旧运行时没有 reconfigure ⇒ 静默跳过，不得抛
    class _NoReconfigure:
        pass

    monkeypatch.setattr(bt.sys, "stdout", _NoReconfigure())
    monkeypatch.setattr(bt.sys, "stderr", _NoReconfigure())
    bt._harden_stdio()

    save = tmp_path / "save.json"
    save.write_text(json.dumps({"decision_log": [_rec(0, "g", True, 0.7)]},
                               ensure_ascii=False), encoding="utf-8")
    monkeypatch.undo()
    assert bt.main([str(save), "--json"]) == 0


def test_monotonic_truncation_contract():
    """截断契约：违反再多也只保留 MAX_VIOLATIONS 条，且 truncated=True（计数为真实值）。"""
    # 交替抬升/压低 ⇒ 两个方向都大量违反
    series = [(float(i), 0.9 if i % 2 == 0 else 0.1)
              for i in range(2 * bt.MAX_VIOLATIONS + 50)]
    chk = bt.monotonic_check(series)
    assert chk["monotonic"] is False
    assert chk["truncated"] is True
    assert len(chk["violations"]) <= bt.MAX_VIOLATIONS
    assert chk["violations_up"] >= len(chk["violations"])
    assert chk["violations_down"] >= 1


def test_monotonic_driver_ties_use_group_extremes():
    """驱动值并列时按**组极值**判：组内 0.9 与 0.1 都不许越过下一组。"""
    chk = bt.monotonic_check([(1.0, 0.9), (1.0, 0.1), (2.0, 0.5)])
    assert chk["monotonic"] is False, "组 max 0.9 > 下组 min 0.5 ⇒ 非降不成立；反向也不成立"
    assert chk["violations"], "非单调必须给出违反序对"
    # 完全并列的驱动值 ⇒ 无方向
    chk2 = bt.monotonic_check([(1.0, 0.9), (1.0, 0.1), (1.0, 0.5)])
    assert chk2["monotonic"] is True and chk2["direction"] is None
