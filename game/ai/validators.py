# -*- coding: utf-8 -*-
"""宋祚 · 契约校验共享辅助（从 ai/client.py 拆出）。

存放各契约域 Mixin 共用的纯函数/常量：档位白名单、朝局摘要归一、
推演 state 脱敏注入、叙事失败分级降级。

契约内联 validate 闭包仍留在各方法体内（inspect.getsource 契约测试
要求方法源码内可见 return None / 拒绝式逻辑；且多数闭包捕获局部变量，
不宜提纯）。
"""
import json

# 档位白名单（7 档：无/微/小/中/大/巨/极）；validator 用 normalize_tier 归一丰富表达
#
# 【缺字段处置策略（审查 B6 考证，勿再误读为「白送收益」）】本层对「缺字段/非法值」
# 分两类处理，规则一致、**从无例外**：
#   ① 类型/枚举字段（etype、agreement、target、stance、node、lineage、fund、position…）
#      → `return None` / `continue`，即**拒绝式**，整份契约作废或该项丢弃；
#   ② 强度/档位字段（tier、effect_tier、sat、inf、priority、cost_tier、probability、
#      inflow/outflow…、sui_gong/alliance）→ **向下降级**填默认值，取值一律 中/小/微
#      或「不变」，**绝无一处落到 大/巨/极**（全库反查确认）。
# 故缺字段只可能少拿、不可能多拿；且和亲/盟约/纳贡/战争等**高代价**协议在档位非法时
# 直接 `return None`（见 diplomacy_dialogue.validate），因和亲出内帑嫁妆、战争抬入侵
# 意愿，不容猜档。策略取向：宁可少给（不阻断整局），绝不因 AI 漏字段而多给。
_TIERS7 = ("无", "微", "小", "中", "大", "巨", "极")



def _summary_text(state_summary) -> str:
    """朝局摘要入参归一（审查 P0-1/P0-2 修复）：

    - str：原样（调用方已脱敏，如 state.posture / desensitize_for_ai 文本）；
    - dict（get_state_summary 全量，含国库/派系/兵力精确真值）：先经
      desensitize_state 区间化+定性化，再序列化——杜绝把精确真值直拼进 prompt
      造成脱敏四层失效，同时消灭 'dict' 拼接崩溃；
    - None/未知：返回空串。
    """
    if isinstance(state_summary, str):
        return state_summary
    if state_summary is None:
        return ""
    if isinstance(state_summary, dict):
        try:
            from ai.desensitize import desensitize_state
            ds = desensitize_state(state_summary)
            return json.dumps(ds, ensure_ascii=False, indent=1)
        except Exception:
            pass
    try:
        return json.dumps(state_summary, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(state_summary)


def _decide_state_text(state) -> str:
    """任一 *_decide 的 state 直读注入统一改经此脱敏（审查 P0-2）：

    只把 GameState 变成「区间/滞后/定性」文本，绝不写精确国库/太仓/派系/流民。
    """
    if state is None:
        return ""
    try:
        from ai.desensitize import desensitize_for_ai
        return desensitize_for_ai(state)
    except Exception:
        return _summary_text(getattr(state, "get_state_summary", lambda: {})())


def _narrative_fallback(kind, minister_name=""):
    """AI 失败分级降级（落地改进 4 + T8 完整模板库）：**叙事类**失败 → 本地模板兜底
    （本地组装，非 AI 伪造，明确标注由程序代拟）；**推演类**（economy/military/
    era 等）失败仍拒绝式（AIRuntimeError/None，必须 AI）。

    模板库见 ai/narrative_fallback.py（多句式轮换 + 事件分档 + 结构化真值组装）。
    """
    from ai import narrative_fallback
    from ai.client_utils import _ai_unavailable
    if kind == "report":
        return narrative_fallback.fallback_report()
    if kind == "dialogue":
        return narrative_fallback.fallback_dialogue(minister_name)
    if kind == "narrative":
        return narrative_fallback.fallback_narrative()
    if kind == "advice":
        return narrative_fallback.fallback_advice()
    if kind == "event":
        return narrative_fallback.fallback_event()
    if kind == "eval":
        return narrative_fallback.fallback_eval()
    return _ai_unavailable(kind)

