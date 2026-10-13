# -*- coding: utf-8 -*-
"""M63 商品/物料存量州府化 —— 前置取证模块的定向回归。

锁定：① **台账不腐烂**——`DIRECT_WRITE_SITES` 里每个 `(file, marker)` 都必须在源码里逐字存在；
② `stock_summary` 缺失≠0（不可读 ⇒ `total=None` + reason；`cap` 缺 ⇒ 列入清单）；
③ `mediation_status` 在 applier 不可导入时**不臆断**（报 reason）；
④ **零写入**。
"""

import copy
import types

from core.domains.economy import resource_stock_survey as rss


# ------------------------------------------------------------------ ① 台账存在性（防腐烂）
def test_write_site_ledger_markers_still_exist():
    """台账里每个写点都必须在源码里存在——否则说明写点已挪/已改，台账必须同步。"""
    import os

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "game"))
    missing = []
    for site in rss.direct_write_sites():
        path = os.path.join(root, site["file"])
        if not os.path.exists(path):
            missing.append(f"文件不存在：{site['file']}")
            continue
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        if site["marker"] not in src:
            missing.append(f"marker 消失：{site['file']} :: {site['marker'][:60]}")
    assert missing == [], ("写点台账已过期（请同步 DIRECT_WRITE_SITES）：\n  " + "\n  ".join(missing))


def test_ledger_shape():
    sites = rss.direct_write_sites()
    assert len(sites) >= 10
    for s in sites:
        assert set(s) == {"file", "marker", "direction", "note", "bridged", "bridgeable"}
        assert s["file"].startswith("core/") and s["marker"] and s["direction"]
        # **不可桥必须有原因**（写在该点 note 里）——不然就是"偷懒不桥"
        if not s["bridgeable"]:
            assert ("无路" in s["note"]) or ("外邦" in s["note"]), s


def test_all_bridgeable_sites_are_bridged_and_workstream_closed():
    """M72 收口判据：**可桥的全部已桥**（`closed=True`），不可桥的都有原因。"""
    cov = rss.bridge_coverage()
    assert cov["bridgeable"] == 4 and cov["bridged"] == 4
    assert cov["bridgeable_pending"] == 0 and cov["closed"] is True
    assert cov["not_bridgeable"] == 7
    # 可桥的必须真的接了桥
    import os
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "game"))
    for s in rss.direct_write_sites():
        if not s["bridgeable"]:
            continue
        with open(os.path.join(root, s["file"]), encoding="utf-8") as fh:
            assert "resource_stock_bridge" in fh.read(), f"{s['file']} 可桥却没接桥"


def test_bridge_coverage_is_asserted_not_claimed():
    """覆盖率**可断言**：`bridgeable` 的点，其文件里必须**真的**出现桥调用。"""
    import os

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "game"))
    cov = rss.bridge_coverage()
    assert cov["total"] == len(rss.DIRECT_WRITE_SITES)
    assert cov["bridgeable"] + cov["not_bridgeable"] == cov["total"]
    for s in rss.direct_write_sites():
        if not s["bridgeable"]:
            continue
        with open(os.path.join(root, s["file"]), encoding="utf-8") as fh:
            src = fh.read()
        assert "resource_stock_bridge" in src, f"{s['file']} 标了 bridgeable 但没接桥"


# ------------------------------------------------------------------ ② 存量读数
def test_stock_summary_reports_missing_without_zero():
    st = types.SimpleNamespace(resources=None)
    rep = rss.stock_summary(st)
    assert rep["readable"] is False and rep["total"] is None and "缺失≠0" in rep["reason"]

    st2 = types.SimpleNamespace(resources={"木": {"stock": 10, "cap": 100},
                                           "石": {"stock": 5}})
    rep2 = rss.stock_summary(st2)
    assert rep2["readable"] is True and rep2["total"] == 15
    assert rep2["dims"]["木"] == {"stock": 10, "cap": 100}
    assert rep2["cap_missing_dims"] == ["石"]                 # cap 缺 ⇒ 列入，不臆造

    st3 = types.SimpleNamespace(resources={"木": {"stock": None, "cap": 1}})
    rep3 = rss.stock_summary(st3)
    assert rep3["total"] is None                              # 任一项不可读 ⇒ 合计 None
    assert rep3["dims"]["木"]["stock"] is None


# ------------------------------------------------------------------ ③ 中介探针
def test_mediation_status_is_honest():
    rep = rss.mediation_status()
    assert "applier_available" in rep and "rules_hit" in rep
    if not rep["applier_available"]:
        assert rep["reason"]                                     # 不可用 ⇒ 给 reason，不臆断
    else:
        assert rep["rules_hit"] or rep["reason"]


# ------------------------------------------------------------------ ④ 只读
def test_survey_is_readonly():
    st = types.SimpleNamespace(resources={"木": {"stock": 1, "cap": 2}})
    before = copy.deepcopy(st.__dict__)
    rss.stock_summary(st)
    rss.mediation_status()
    rss.direct_write_sites()
    assert copy.deepcopy(st.__dict__) == before
