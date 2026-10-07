# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：新实现已迁入 core.domains.politics.legacy_mechanic
# 不复制实现；新模块不得导入本薄转发。
from core.domains.politics.legacy_mechanic import (
    LEGACY_DEFS, _clear_hidden_land, _clear_huashigang,
    _clear_liao_xia_border, _clear_new_party, _clear_redundant_officials,
    _eff_hidden_land, _eff_huashigang, _eff_liao_xia_border,
    _eff_new_fund, _eff_redundant_officials, _estimate_progress,
    _num, active_legacies, annotations,
    cleared_legacies, init_legacies, settle_legacies,
)

__all__ = ['LEGACY_DEFS', '_clear_hidden_land', '_clear_huashigang', '_clear_liao_xia_border', '_clear_new_party', '_clear_redundant_officials', '_eff_hidden_land', '_eff_huashigang', '_eff_liao_xia_border', '_eff_new_fund', '_eff_redundant_officials', '_estimate_progress', '_num', 'active_legacies', 'annotations', 'cleared_legacies', 'init_legacies', 'settle_legacies']
