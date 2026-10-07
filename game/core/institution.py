# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：实现已迁入 core.domains.administration.institution（第十九包，2026-10-07）。
# 公开面上每个名字都从实现模块转发（含 `_` 开头私有名与 typing 绑定名）；
# ⚠️ 桩只保住『名字与对象』：打在桩上的 monkeypatch 不影响消费者，打在桩上的**重绑**也不改变实现侧同名绑定（第十七/十八包教训）。
"""宋祚 · institution（兼容入口）。实现在 `core/domains/administration/institution.py`。"""
from core.domains.administration.institution import (  # noqa: F401
    Any, Dict, INSTITUTION_PARAM_SPEC, TIER_STEP, Tuple, _EXECUTOR_KEYS, _SPEC, _authority_matters_of, _executor_by_org, _executor_by_person, _executor_by_post, _matter_of, _org_table, all_params, apply_reform, changed_count, check_authority, clamp, describe, get, resolve_executor, set_by_delta, set_param,
)
