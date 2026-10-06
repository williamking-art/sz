# -*- coding: utf-8 -*-
# 迁移期薄转发（兼容层）：实现已迁入 core.foundation.common.errors（第十一包，2026-10-07）。
# 本模块**不复制任何类定义**，仅显式转发；`dir(core.errors)` 公开面与迁移前一致。
"""核心错误类型定义（避免循环导入）。

⚠️ 自第十一包起，`AIRuntimeError` 的实现位置在
`core/foundation/common/errors.py`，本路径只是兼容转发桩——
生产代码请直接引用新路径；旧路径继续供历史 import 与测试使用。
"""
from core.foundation.common.errors import AIRuntimeError  # noqa: F401
