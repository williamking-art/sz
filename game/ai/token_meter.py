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

__all__ = ["estimate_tokens", "estimate_messages_tokens", "tiktoken_available",
           "TOKEN_GROUPS", "TOKEN_GROUP_ORDER", "token_group_of", "grouped_meter_rows"]


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


# ============================================================
# Token 计量表（展示层分组聚合）——Tk/Web 共用单一映射源
#   （原实现位于 ui/panels_meta.py；Tk 废弃后迁至本模块，由 HTTP /api/meter 下发）
# ============================================================
TOKEN_GROUPS = {
    "召对·AI": {"dialogue"},
    "拟旨": {"polish_decree", "draft_decree", "parse_decree"},
    "会签": {"council_review"},
    "推演": {"economy_decide", "diplomacy_decide", "military_decide", "relief_decide",
             "finance_decide", "treasury_decide", "granary_decide", "faction_decide",
             "land_local_decide", "era_decide", "invest_decide", "free_effect_decide",
             "survey_settle", "decree_execute_decide", "emperor_personal_decide",
             "hidden_state_decide", "build_new_branch_decide", "research_decide"},
    "月报叙事": {"monthly_report", "event_narrative", "advice", "final_eval"},
}
TOKEN_GROUP_ORDER = ("拟旨", "会签", "推演", "月报叙事")


def token_group_of(method: str) -> str:
    """契约方法名 → 显示分组（未命中归「其它」）。"""
    for grp, methods in TOKEN_GROUPS.items():
        if method in methods:
            return grp
    return "其它"


def grouped_meter_rows(client, dialogue_stats=None) -> list:
    """组装 Token 计量表行（含召对命中行与合计行）。

    数据源：client.meter_summary()（按契约方法分桶）+ dialogue_stats
    （召对预过滤/缓存命中与 AI 调用次数）。
    返回 [{type, calls, prompt, completion, hit}, ...]，末行为「合计」
    （hit 列填召对省调率文本）。
    """
    st = dialogue_stats if isinstance(dialogue_stats, dict) else {}
    pre = int(st.get("prefilter_hits", 0) or 0)
    ch = int(st.get("cache_hits", 0) or 0)
    ai_calls = int(st.get("ai_calls", 0) or 0)
    rows = [
        {"type": "召对·预过滤命中", "calls": pre, "prompt": 0, "completion": 0, "hit": pre},
        {"type": "召对·缓存命中", "calls": ch, "prompt": 0, "completion": 0, "hit": ch},
    ]
    meter = {}
    try:
        meter = client.meter_summary() if client is not None else {}
    except Exception:
        meter = {}
    by = (meter or {}).get("by_method", {}) or {}
    groups = {}
    for m, b in by.items():
        g = groups.setdefault(token_group_of(m),
                              {"calls": 0, "prompt": 0, "completion": 0})
        g["calls"] += int(b.get("calls", 0) or 0)
        g["prompt"] += int(b.get("prompt", 0) or 0)
        g["completion"] += int(b.get("completion", 0) or 0)
    # 召对·AI：次数以 _dialogue_stats.ai_calls 为准（token 取 dialogue 分桶）
    d = groups.pop("召对·AI", {"calls": 0, "prompt": 0, "completion": 0})
    rows.append({"type": "召对·AI", "calls": ai_calls,
                 "prompt": d["prompt"], "completion": d["completion"], "hit": 0})
    for grp in TOKEN_GROUP_ORDER:
        g = groups.pop(grp, {"calls": 0, "prompt": 0, "completion": 0})
        rows.append({"type": grp, "calls": g["calls"], "prompt": g["prompt"],
                     "completion": g["completion"], "hit": 0})
    if groups:
        rows.append({
            "type": "其它",
            "calls": sum(g["calls"] for g in groups.values()),
            "prompt": sum(g["prompt"] for g in groups.values()),
            "completion": sum(g["completion"] for g in groups.values()),
            "hit": 0,
        })
    total = (meter or {}).get("total", {}) or {}
    hit_all = pre + ch
    call_all = hit_all + ai_calls
    rate = (hit_all / call_all * 100) if call_all else 0.0
    rows.append({"type": "合计", "calls": int(total.get("calls", 0) or 0),
                 "prompt": int(total.get("prompt", 0) or 0),
                 "completion": int(total.get("completion", 0) or 0),
                 "hit": f"{rate:.0f}%（召对）"})
    return rows
