# -*- coding: utf-8 -*-
"""M50 岗位轨「缺政权专档 ⇒ 回落 default」**去静默** —— 定向回归。

锁定：① 有专档 ⇒ 用它、**不记回落**；② 无专档 ⇒ **仍产同样的量**（本批不动数值）但
**记一次回落**（计数 + 结构化留痕）；③ `rtype=""` 也记（不可静默）；④ 记录可被读取。
"""

import copy

import pytest

from core import building_jobs as bj

CFG = {
    "PER_WORKER_OUTPUT": {
        "default": {"桑麻田": {"麻": 0.08, "丝": 0.03}},
        "党项蕃国": {"桑麻田": {"麻": 0.10, "丝": 0.04}},
    },
    "LV_OUTPUT_BONUS": 0.05,
    "RAW_DIMS": ["麻", "丝"],
}


@pytest.fixture(autouse=True)
def _clean():
    bj._CONFIG_FALLBACKS.clear()
    yield
    bj._CONFIG_FALLBACKS.clear()


def test_regime_entry_used_without_fallback_record():
    res = {}
    out = bj.produce_job_track({"农": {"size": 100}}, {"桑麻田": 1}, CFG, "党项蕃国",
                               staffed={"桑麻田": 100}, resources=res)
    assert out == {"麻": 10, "丝": 4}                 # 专档：0.10 / 0.04
    assert bj.job_track_config_fallbacks() == []      # 有专档 ⇒ 不记回落


def test_missing_regime_falls_back_but_is_recorded_not_silent():
    res = {}
    out = bj.produce_job_track({"农": {"size": 100}}, {"桑麻田": 1}, CFG, "宋",
                               staffed={"桑麻田": 100}, resources=res)
    # 🔴 数值仍走 default（本批不动数值，避免把未登记政权产出归零）
    assert out == {"麻": 8, "丝": 3}
    recs = bj.job_track_config_fallbacks()
    assert len(recs) == 1 and recs[0]["rtype"] == "宋"
    assert "missing_regime_entry" in recs[0]["reason"]


def test_empty_rtype_is_also_recorded():
    bj.produce_job_track({"农": {"size": 10}}, {"桑麻田": 1}, CFG, "",
                         staffed={"桑麻田": 10}, resources={})
    recs = bj.job_track_config_fallbacks()
    assert len(recs) == 1 and recs[0]["rtype"] == ""


def test_fallback_record_is_a_copy():
    bj.produce_job_track({"农": {"size": 10}}, {"桑麻田": 1}, CFG, "宋",
                         staffed={"桑麻田": 10}, resources={})
    snapshot = bj.job_track_config_fallbacks()
    snapshot.append({"rtype": "污染"})
    assert len(bj.job_track_config_fallbacks()) == 1     # 外部改动不污染内部记录


def test_cfg_is_not_mutated():
    cfg = copy.deepcopy(CFG)
    bj.produce_job_track({"农": {"size": 10}}, {"桑麻田": 1}, cfg, "宋",
                         staffed={"桑麻田": 10}, resources={})
    assert cfg == CFG
