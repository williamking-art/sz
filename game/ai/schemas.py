# -*- coding: utf-8 -*-
"""宋祚 · AI 输出契约 JSON Schema 注册表（A1：jsonschema 结构层）

定位：业务 validator（client.py 各契约内联闭包）之前的**结构层**。
- schema 只声明"业务 validator 必然硬性要求的字段"（类型/必填/枚举），
  additionalProperties 一律放开——结构层只会拒绝业务层也会拒绝的输出，
  不引入新的误杀面；价值在于：结构错误有**精确路径与原因**，可回喂修复。
- jsonschema 未安装 → schema_check 直接放行（True, ""），行为与旧版一致；
  业务 validator 仍是最终防线（归一化/白名单/档位封顶不受影响）。
- 注册表按契约方法名（AIClient 的方法名）查表；未注册的契约自动跳过。

纪律（言枢密席位）：schema 与 validator 的字段口径必须共同评审——
schema 比 validator 宽是安全的（只多放行），比 validator 严则必须同步收窄 validator。
"""
from __future__ import annotations

try:  # 可选依赖（game/requirements-extras.txt）；缺失时结构层放行、业务 validator 兜底
    import jsonschema as _jsonschema
except Exception:  # noqa: BLE001 — 可选依赖缺失不是错误
    _jsonschema = None

#: 结构校验是否真的启用（R-N-4：显式状态，不再"静默两分支"）。
HAS_JSONSCHEMA = _jsonschema is not None

__all__ = ["SCHEMAS", "schema_for", "schema_check", "schema_status", "HAS_JSONSCHEMA"]

# 结构层注册表：契约方法名 → JSON Schema（Draft 2020-12 子集，jsonschema 库兼容）
SCHEMAS: dict = {
    # 召对回奏：reply 必填字符串；mood 必填（业务层再归一到 7 档）
    "dialogue": {
        "type": "object",
        "required": ["reply", "mood"],
        "properties": {
            "reply": {"type": "string"},
            "mood": {"type": "string"},
            "intent_hint": {"type": "string"},
        },
        "additionalProperties": True,
    },
    # 御前献策：advice 必填字符串
    "advice": {
        "type": "object",
        "required": ["advice"],
        "properties": {"advice": {"type": "string"}},
        "additionalProperties": True,
    },
    # 自由拟旨解析：category/exec_mode/title 必填；exec_mode 闭集
    "parse_decree": {
        "type": "object",
        "required": ["category", "exec_mode", "title"],
        "properties": {
            "category": {"type": "string"},
            "exec_mode": {"type": "string", "enum": ["instant", "longterm"]},
            "title": {"type": "string"},
            "body": {"type": "string"},
            "params": {"type": "object"},
            "narrative": {"type": "string"},
        },
        "additionalProperties": True,
    },
    # 月报：report 必填非空（业务层再查空串）；scenes 可选数组
    "monthly_report": {
        "type": "object",
        "required": ["report"],
        "properties": {
            "report": {"type": "string"},
            "scenes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["text"],
                    "properties": {"scene": {"type": "string"}, "text": {"type": "string"}},
                    "additionalProperties": True,
                },
            },
        },
        "additionalProperties": True,
    },
    # 事件叙事：narrative 必填；severity_hint 闭集（轻/中/重）
    "event_narrative": {
        "type": "object",
        "required": ["narrative", "severity_hint"],
        "properties": {
            "narrative": {"type": "string"},
            "severity_hint": {"type": "string", "enum": ["轻", "中", "重"]},
            "scenes": {"type": "array"},
        },
        "additionalProperties": True,
    },
}


def schema_for(contract: str):
    """按契约方法名取 schema；未注册返回 None（调用方跳过结构层）。"""
    return SCHEMAS.get(contract)


def schema_status() -> dict:
    """结构层状态（R-N-4）：是否启用、已注册契约数、覆盖说明。

    面板/自检用它显式区分「结构校验已启用」与「可选依赖缺失 ⇒ 恒放行」，
    不再靠调用方猜。注册表覆盖是**有意子集**（当前 5 个：dialogue/advice/
    parse_decree/monthly_report/event_narrative）；未注册契约由业务 validator 兜底。
    """
    return {
        "enabled": HAS_JSONSCHEMA,
        "registered": len(SCHEMAS),
        "contracts": sorted(SCHEMAS),
        "coverage_note": "有意子集：仅注册字段明确/最常出错的 5 个契约；未注册由业务 validator 兜底",
    }


def schema_check(contract: str, obj) -> tuple:
    """结构校验。返回 (ok, err)。

    - 未注册 schema / obj 非字典 / jsonschema 未安装 / 校验器自身异常 → (True, "") 放行；
      业务 validator 仍兜底，绝不因可选依赖缺失而改变既有行为。
    - 校验失败 → (False, "字段路径: 原因")，供 _postprocess 回喂修复。
    """
    schema = SCHEMAS.get(contract)
    if schema is None or not isinstance(obj, dict):
        return True, ""
    if _jsonschema is None:
        return True, ""
    try:
        _jsonschema.validate(obj, schema)
        return True, ""
    except _jsonschema.ValidationError as e:  # type: ignore[attr-defined]
        path = "/".join(str(p) for p in e.absolute_path) or "(root)"
        return False, f"{path}: {e.message}"
    except Exception:
        # schema 自身写错等异常：不阻断业务（放行，交业务 validator）
        return True, ""
