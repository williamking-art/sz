# -*- coding: utf-8 -*-
"""M126 读数**端点契约**守卫：`collect()` 的载荷必须可 JSON 序列化（零风险，测试only）。

背景：`/api/readouts` 会把 `readout_hub.collect()` 经 `_json_safe` 下发；M125 刚发现
`drill_down` 曾出现"字符串/对象两种形状"（9 个 M54 期读数）⇒ 同类风险的另一半是
**载荷里混入不可序列化对象**（set/tuple/自定义对象）——本用例把它锁死：
① 整体 `json.dumps` 必须成功；② 逐项 `drill_down` 必须是 dict/None；
③ `display` 必须是字符串；④ 不可读项必然是 `"undefined"` + 有 reason（缺失≠0）。
"""

import json

from core import commands
from core.domains.economy import readout_hub as rh


def _months(state, n=3):
    import core.settlement as S
    for _ in range(n):
        S.run_monthly_settlement(state)
    return state


def test_collect_payload_is_json_serializable():
    rep = rh.collect(_months(commands.new_game()))
    payload = json.dumps(rep, ensure_ascii=False)            # 不可序列化 ⇒ 端点会炸
    assert payload and "readouts" in payload
    back = json.loads(payload)
    assert back["frontend_wired"] is False


def test_every_readout_row_matches_endpoint_contract():
    rep = rh.collect(_months(commands.new_game()))
    assert rep["ok_count"] + rep["undefined_count"] == len(rep["readouts"])
    for k, v in rep["readouts"].items():
        assert isinstance(v["display"], str), k
        assert isinstance(v["source"], str) and v["source"], k
        assert isinstance(v["drill_down"], (dict, type(None))), (k, type(v["drill_down"]))
        if v["value"] is None:
            assert v["display"] == "undefined" and v["reason"], k
        else:
            assert v["display"] == str(v["value"]), k
        # drill/source 里不得混入 set/tuple（序列化后形状会变）
        if isinstance(v["drill_down"], dict):
            json.dumps(v["drill_down"], ensure_ascii=False)
