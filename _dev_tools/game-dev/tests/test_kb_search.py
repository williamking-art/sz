# -*- coding: utf-8 -*-
"""本地典章知识库（kb_search 工具）测试。

知识库本地化（2026-09-24）：assets/kb/game_kb.sqlite 随游戏分发（只读 FTS5），
游戏内 AI 经第 10 个工具 kb_search 按需检索（「问到才查」，同 query_state 哲学）。
构建脚本：_dev_tools/game-docs/kb/build_kb.py（查询算法两处保持一致）。

覆盖：工具注册（schema/白名单/必填）、查询模块（FTS5 命中 / LIKE 兜底 / 无命中 /
长度截断）、dispatch（命中 / 缺参拒绝 / 库缺失降级 / 白名单闸门）。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_GAME_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

import ai.kb_query as kbq  # noqa: E402
from ai.client_utils import _TOOL_NAMES, _TOOL_SCHEMAS, _tool_dispatch  # noqa: E402


class _FakeState:
    """_tool_dispatch 只读写 minister_memory，普通实例即可。"""


def _call(args, name="kb_search", state=None):
    tc = {"id": "t1", "function": {"name": name, "arguments": args}}
    return _tool_dispatch(state or _FakeState(), [tc], "测试大臣")


# ---------------------------------------------------------------
# 工具注册
# ---------------------------------------------------------------
def test_kb_search_tool_registered():
    """schema 注册 + 白名单 + 必填 query。"""
    sch = next((t for t in _TOOL_SCHEMAS
                if t.get("function", {}).get("name") == "kb_search"), None)
    assert sch is not None, "_TOOL_SCHEMAS 应含 kb_search"
    params = sch["function"]["parameters"]
    assert "query" in params["properties"]
    assert "query" in params["required"]
    assert "kb_search" in _TOOL_NAMES, "kb_search 必须进服务端白名单"


def test_kb_search_is_read_only_tool():
    """kb_search 是只读检索：不得出现在写状态危险名集合（哨兵口径同 test_ai_write_scope）。"""
    forbidden = {"update_state", "set_state", "write_state", "apply_changes"}
    assert not (forbidden & set(_TOOL_NAMES))


# ---------------------------------------------------------------
# 查询模块
# ---------------------------------------------------------------
def test_kb_available():
    """库文件随仓库分发，且本机 SQLite 支持 FTS5 trigram。"""
    assert kbq.kb_available() is True


def test_kb_search_hit_fts():
    """多词查询命中（FTS5 bm25 路径），返回带典章出处前缀。"""
    out = kbq.kb_search("交子 准备金")
    assert out and "【典章·1】" in out
    assert "交子" in out


def test_kb_search_two_char_like_fallback():
    """纯 2 字词（trigram 盲区）走 LIKE 兜底仍能命中。"""
    out = kbq.kb_search("冗兵")
    assert out, "2 字查询不得空返（LIKE 兜底必须生效）"
    assert "冗" in out


def test_kb_search_no_hit_returns_empty():
    assert kbq.kb_search(" zzqqxx 不存在的词 ") == ""


def test_kb_search_result_capped():
    """返回总量受 MAX_RESULT_CHARS 截断（防 token 膨胀）。"""
    out = kbq.kb_search("货币", top_k=5)
    assert len(out) <= kbq.MAX_RESULT_CHARS


# ---------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------
def test_dispatch_kb_search_hit():
    state = _FakeState()
    res = _call({"query": "常平仓"}, state=state)
    assert len(res) == 1
    _cid, text = res[0]
    assert "【典章·1】" in text
    assert "常平仓" in text
    mem = state.minister_memory["测试大臣"]
    assert any("查典章" in m for m in mem)


def test_dispatch_kb_search_topk_clamped():
    """top_k 钳制 1~5；非法值回落 3（拒绝式之外的数值护栏）。"""
    _cid, text = _call({"query": "货币", "top_k": 99})[0]
    assert text.count("【典章·") <= 5
    _cid, text2 = _call({"query": "货币", "top_k": "abc"})[0]
    assert "【典章·1】" in text2


def test_dispatch_kb_search_missing_query_rejected():
    """缺 query 必填 → 拒绝式报错，不落地不检索。"""
    _cid, text = _call({})[0]
    assert "缺参被拒" in text and "query" in text


def test_dispatch_kb_search_degraded_when_unavailable(monkeypatch):
    """库缺失/不可用时给降级话术，绝不抛异常进 AI 管线。"""
    monkeypatch.setattr(kbq, "_available", False)
    _cid, text = _call({"query": "冗官"})[0]
    assert "未查到" in text or "未部署" in text


def test_dispatch_unauthorized_tool_still_rejected():
    """白名单闸门兜底：危险工具名依旧被拒（kb_search 加入后闸门不失效）。"""
    _cid, text = _call({}, name="update_state")[0]
    assert "未授权工具被拒" in text
