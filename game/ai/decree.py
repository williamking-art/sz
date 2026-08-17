# -*- coding: utf-8 -*-
"""统一拟旨解析：圣旨 / 密旨 都由玩家自由拟定，交由 AI 推演判定。

- 类别：fixed_tech / fixed_finance / fixed_army / fixed_construction（走规则程序）
        其余为 free_edict（自由推演）
- 执行时机：instant（即时）/ longterm（长期，月度推进核销）

全程依赖 AI，无离线兜底。AI 不可用时返回带 `_error` 标记的结构，由 UI 提示配置。
"""
from ai.client import AIClient, _fallback_parse  # 复用既有 AI 客户端与离线兜底


def parse_decree(text: str, state_summary: str = "", is_secret: bool = False) -> dict:
    """解析一道拟旨，返回结构化结果。"""
    client = AIClient.load_saved()
    if client is None:
        # 复用 client 的统一离线兜底（同 schema 的 _error 标记，不伪造文本）
        return _fallback_parse(text, is_secret)
    return client.parse_decree(text, state_summary, is_secret=is_secret)
