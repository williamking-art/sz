# -*- coding: utf-8 -*-
"""宋祚 · 本地语义嵌入后端（B2：ONNX Runtime + bge-small-zh-v1.5，可选层）

用途（沈舶司/言枢密席位）：
1) **语义防复读**：升级 client.py 的字面复读检测（SequenceMatcher>0.6）——
   换皮复读（同义改写）字面相似度低但语义相同，语义阈值 0.92 才拦截；
2) **大臣记忆检索**：memory/ 对话库的语义查询（配合 ai/vector_store.py）；
3) **设定 RAG**：35+ 大臣档案/24 项事权的语义检索（后续扩展）。

模型：BAAI/bge-small-zh-v1.5 的 ONNX 版（约 90MB，512 维，CLS 池化 + L2 归一）。
放置位置：assets/models/bge-small-zh-v1.5/{model.onnx, tokenizer.json}
（用 ai/model_setup.py 一键下载）。

降级纪律：onnxruntime/tokenizers 未安装或模型缺失 → available()=False，
所有函数安全返回 None/False，调用方回落字面检测——**绝不影响游戏**。
"""
from __future__ import annotations

import os
import sys
import threading

__all__ = ["available", "embed", "cosine", "semantic_repetition_hit",
           "MODEL_DIR", "EMBED_DIM"]

MODEL_DIR_NAME = os.path.join("assets", "models", "bge-small-zh-v1.5")
EMBED_DIM = 512
_MAX_INPUTS = 512          # bge 上下文上限（token）
_REPETITION_THRESHOLD = 0.92  # 语义复读阈值（字面 0.6 抓不到的换皮复读）

_lock = threading.Lock()
_backend = None            # (session, tokenizer) 缓存
_probe_done = False


def model_dir() -> str:
    """模型目录（frozen 时用 exe 所在目录，与 backend.client._app_root 同约定）。"""
    try:
        if getattr(sys, "frozen", False):
            root = os.path.dirname(sys.executable)
        else:
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(root, MODEL_DIR_NAME)
    except Exception:
        return MODEL_DIR_NAME


def _deps_ok() -> bool:
    try:
        import onnxruntime  # noqa: F401
        import tokenizers  # noqa: F401
        return True
    except Exception:
        return False


def _files_ok() -> bool:
    d = model_dir()
    return (os.path.isfile(os.path.join(d, "model.onnx"))
            and os.path.isfile(os.path.join(d, "tokenizer.json")))


def available() -> bool:
    """语义后端是否可用（依赖 + 模型文件齐备）。"""
    return _deps_ok() and _files_ok()


def _get_backend():
    """懒加载 ONNX 会话与分词器（进程级单例，线程安全）。"""
    global _backend, _probe_done
    if _probe_done:
        return _backend
    with _lock:
        if _probe_done:
            return _backend
        _probe_done = True
        if not available():
            return None
        try:
            import onnxruntime
            from tokenizers import Tokenizer
            d = model_dir()
            so = onnxruntime.SessionOptions()
            so.intra_op_num_threads = 1   # 桌面游戏：省 CPU，嵌入是低频操作
            so.inter_op_num_threads = 1
            sess = onnxruntime.InferenceSession(
                os.path.join(d, "model.onnx"), sess_options=so,
                providers=["CPUExecutionProvider"])
            tok = Tokenizer.from_file(os.path.join(d, "tokenizer.json"))
            tok.enable_truncation(max_length=_MAX_INPUTS)
            _backend = (sess, tok)
        except Exception:
            _backend = None
    return _backend


def _cls_pool(logits, attention) -> list:
    """bge 家族：[CLS]（首 token）池化 + L2 归一。"""
    vec = logits[:, 0]
    norm = (vec * vec).sum(axis=1) ** 0.5
    norm[norm == 0] = 1.0
    return (vec / norm[:, None]).tolist()


def embed(texts) -> list:
    """批量嵌入。返回 [[float]*512, ...]；后端不可用返回 None。"""
    be = _get_backend()
    if be is None or not texts:
        return None
    sess, tok = be
    try:
        import numpy as np
        texts = [str(t or "")[:2000] for t in texts]
        enc = tok.encode_batch(texts)
        ids = [e.ids for e in enc]
        attn = [e.attention_mask for e in enc]
        max_len = max(len(x) for x in ids)
        pad_id = tok.token_to_id("[PAD]") or 0
        input_ids = np.array([x + [pad_id] * (max_len - len(x)) for x in ids], dtype=np.int64)
        attention = np.array([x + [0] * (max_len - len(x)) for x in attn], dtype=np.int64)
        feed = {}
        for inp in sess.get_inputs():
            name = inp.name
            if "input_ids" in name:
                feed[name] = input_ids
            elif "attention_mask" in name:
                feed[name] = attention
            elif "token_type_ids" in name:
                feed[name] = np.zeros_like(input_ids)
        out = sess.run(None, feed)[0]  # (batch, seq, hidden)
        return _cls_pool(out, attention)
    except Exception:
        return None


def cosine(a, b) -> float:
    """余弦相似度（numpy 优先，纯 Python 兜底）。"""
    try:
        import numpy as np
        va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
        na, nb = float((va * va).sum() ** 0.5), float((vb * vb).sum() ** 0.5)
        if na == 0 or nb == 0:
            return 0.0
        return float((va * vb).sum() / (na * nb))
    except Exception:
        try:
            na = sum(x * x for x in a) ** 0.5
            nb = sum(x * x for x in b) ** 0.5
            if na == 0 or nb == 0:
                return 0.0
            return sum(x * y for x, y in zip(a, b)) / (na * nb)
        except Exception:
            return 0.0


def semantic_repetition_hit(text: str, prev_texts, threshold: float = _REPETITION_THRESHOLD) -> bool:
    """语义复读判定：text 与任一 prev 语义相似度超阈值 → True。

    后端不可用 → False（调用方回落字面检测，行为与旧版一致）。
    """
    be = _get_backend()
    if be is None or not text or not prev_texts:
        return False
    try:
        vecs = embed([text] + [str(p or "") for p in prev_texts])
        if not vecs:
            return False
        v0 = vecs[0]
        return any(cosine(v0, v) >= threshold for v in vecs[1:])
    except Exception:
        return False
