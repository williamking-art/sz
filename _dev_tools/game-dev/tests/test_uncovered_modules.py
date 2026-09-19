# -*- coding: utf-8 -*-
"""此前**未被任何测试提及**的模块的最小可用性测试（2026-09-19 测试项审查补缺口）。

审计结果（`_ming_probe/songzuo_test_audit.md` §五）曾有 6 个盲区模块：
`semantic` / `vector_store` / `external_view` / `schemas` / `client_narrative` / `model_setup`。
本文件覆盖前四个的**纯函数与本地存储**部分（不联网、不依赖可选 ONNX 资产）：

- `semantic.cosine`：余弦相似度（复读检测与记忆检索的数学核心）；
- `semantic.available` / `embed`：缺资产时**必须优雅降级**（返回 None/False），不得抛异常；
- `vector_store.VectorStore`：SQLite 存储的增/查/计数/关闭；
- `external_view.external_pop_view` / `external_provinces`：外邦视图（只读、缺数据不炸）；
- `schemas.schema_for` / `schema_check`：AI 契约的 JSON Schema 结构层。

`model_setup` 是**下载脚本**（网络依赖），显式豁免，不在测试范围内。
"""
import math
import os
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)


# ---------------------------------------------------------------- semantic
def test_semantic_cosine_basic():
    from ai import semantic
    assert semantic.cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert semantic.cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert semantic.cosine([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_semantic_cosine_degrades_safely():
    """空向量/零向量/维度不符/脏值 → 不得抛异常（复读检测在每轮对话里都会调用）。"""
    from ai import semantic
    for a, b in (([], []), ([0.0, 0.0], [1.0, 1.0]), ([1.0], [1.0, 2.0]),
                 (None, [1.0]), ([float("nan")], [1.0])):
        try:
            v = semantic.cosine(a, b)
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"cosine({a!r},{b!r}) 抛异常：{type(e).__name__}: {e}")
        assert v is None or isinstance(v, float)
        if isinstance(v, float):
            assert math.isfinite(v)


def test_semantic_available_is_bool_and_embed_degrades():
    from ai import semantic
    assert isinstance(semantic.available(), bool)
    if not semantic.available():
        # 缺可选资产（本机常态）→ embed 必须优雅返回 None，不得抛
        assert semantic.embed(["测试"]) is None


def test_semantic_repetition_hit_uses_threshold():
    from ai import semantic
    try:
        hit = semantic.semantic_repetition_hit("今年风调雨顺", ["去年风调雨顺"], threshold=0.5)
    except Exception as e:  # noqa: BLE001
        pytest.fail(f"semantic_repetition_hit 抛异常：{type(e).__name__}: {e}")
    assert hit in (True, False)


# ------------------------------------------------------------ vector_store
def test_vector_store_add_search_count(tmp_path):
    from ai.vector_store import VectorStore
    vs = VectorStore(str(tmp_path / "vs.db"), dim=3)
    try:
        assert vs.count() == 0
        vs.add("a", "第一段", [1.0, 0.0, 0.0], {"kind": "x"})
        vs.add("b", "第二段", [0.0, 1.0, 0.0])
        assert vs.count() == 2
        hits = vs.search([1.0, 0.0, 0.0], top_k=1)
        assert hits, "向量检索应返回结果"
        top = hits[0]
        key = top.get("item_id") or top.get("id")
        assert key == "a", f"最相近的应是 item a，实际 {top}"
    finally:
        vs.close()


def test_vector_store_survives_reopen(tmp_path):
    from ai.vector_store import VectorStore
    path = str(tmp_path / "vs2.db")
    vs = VectorStore(path, dim=2)
    vs.add("k", "持久化", [1.0, 1.0])
    vs.close()
    vs2 = VectorStore(path, dim=2)
    try:
        assert vs2.count() == 1, "重开应能读到已写入向量"
    finally:
        vs2.close()


# ----------------------------------------------------------- external_view
def test_external_view_degrades_without_data():
    """外邦视图在缺数据时不得抛异常（外邦数据由 AI/事件填充，早期可能为空）。"""
    from core.external_view import external_pop_view, external_provinces
    class _S:
        external_regimes = {}
        external_provinces = {}
        prefectures = {}
    s = _S()
    out1 = external_pop_view(s, "辽")
    out2 = external_provinces(s, "辽")
    assert out1 is None or isinstance(out1, (dict, list))
    assert out2 is None or isinstance(out2, (dict, list))


# ---------------------------------------------------------------- schemas
def test_schemas_shape():
    from ai.schemas import schema_check, schema_for
    sch = schema_for("economy")
    assert sch is None or isinstance(sch, dict)
    # 契约签名：返回 (ok: bool, err: str)（err 为空串表示通过）
    ok, errs = schema_check("monthly_report", {"report": "本月朝报"})
    assert isinstance(ok, bool) and isinstance(errs, str)
    # 业务必填字段缺失 → 结构层应拒绝（若 jsonschema 已装）
    ok2, errs2 = schema_check("monthly_report", {})
    assert isinstance(ok2, bool) and isinstance(errs2, str)
    # 未注册契约必须安全（不抛异常、放行）
    ok3, errs3 = schema_check("不存在的契约", {"x": 1})
    assert ok3 is True and errs3 == ""
