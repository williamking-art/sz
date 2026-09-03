# -*- coding: utf-8 -*-
"""宋祚 · token 计量（A3：tiktoken 可选层）

职责：
- 端点**未返回 usage** 时，按消息内容估算 prompt/completion tokens，
  让 token_usage 计量表（含分桶）在任意端点下都有数可看；
- 提供独立估算函数，供成本预算/上下文窗口决策复用。

精度策略：
1) tiktoken 可用 → 按模型族选编码（gpt-4o/o200k_base，其余 cl100k_base），
   中文为近似（BPE 对中文非字级），但远优于纯字数启发；
2) tiktoken 未安装 → 字符启发：CJK ≈ 1.05 token/字，其余 ≈ /3.8。
估算值在 usage 中标记 estimated=True，与端点真值区分，绝不冒充精确值。

纪律：本模块只读不写状态；任何异常由调用方静默（计量失败不影响游戏）。
"""
from __future__ import annotations

__all__ = ["estimate_tokens", "estimate_messages_tokens", "tiktoken_available"]


def tiktoken_available() -> bool:
    try:
        import tiktoken  # noqa: F401
        return True
    except Exception:
        return False


def _encoding(model: str = ""):
    """按模型族选 tiktoken 编码；失败回落 cl100k_base；再失败返回 None。"""
    try:
        import tiktoken
        m = (model or "").lower()
        if "o200k" in m or "gpt-4o" in m or "gpt-4.1" in m:
            try:
                return tiktoken.encoding_for_model("gpt-4o")
            except Exception:
                pass
        try:
            return tiktoken.encoding_for_model(model) if model else None
        except Exception:
            return None
    except Exception:
        return None


def _heuristic(text: str) -> int:
    """无 tiktoken 时的字符启发：CJK≈1.05/字，其余≈/3.8。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff"
              or "\u3400" <= ch <= "\u4dbf" or "\uf900" <= ch <= "\ufaff")
    other = len(text) - cjk
    return max(1, int(cjk * 1.05 + other / 3.8) + 1)


def estimate_tokens(text: str, model: str = "") -> int:
    """估算一段文本的 token 数（tiktoken 优先，启发式兜底）。"""
    if not text:
        return 0
    enc = _encoding(model)
    if enc is not None:
        try:
            return len(enc.encode(text, disallowed_special=()))
        except Exception:
            pass
    return _heuristic(text)


def estimate_messages_tokens(messages, out_text: str = "", model: str = "") -> tuple:
    """估算一次调用的 (prompt_tokens, completion_tokens)。

    messages: OpenAI 格式 [{"role","content"},...]（含 system/user/assistant/tool）。
    out_text: 模型将/已返回的补全文（计 completion）。
    """
    prompt = 0
    try:
        for m in messages or []:
            if isinstance(m, dict):
                prompt += estimate_tokens(str(m.get("content", "")), model) + 4  # 每条消息开销
    except Exception:
        pass
    return prompt, estimate_tokens(out_text, model)
