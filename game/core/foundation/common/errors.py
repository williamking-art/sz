# -*- coding: utf-8 -*-
"""宋祚 · 核心错误类型（第十一包自 `core/errors.py` **原文**迁入）。

承架构方案 §106：`common/` = 真正跨域且无业务归属的基础工具。本模块只定义异常类，
**不导入任何业务模块**，供 core / ai / backend / ui 各层共享。
旧路径兼容：`core.errors` 显式转发本模块全部符号，`dir()` 公开面不变。
"""
class AIRuntimeError(RuntimeError):
    """AI 叙事在运行时发生故障（超时 / 限流 / 报错）。

    核心玩法依赖 AI 介入，因此运行时故障不应被静默吞掉或伪造兜底，
    而应抛出此异常，由上层（GUI / 终端）弹出提醒并停止当前操作。

    审查 P2-43 修复：新增可选 `code`（取 content.data.AI_ERROR_CODES 的 6 码），
    使 AI_TIMEOUT / AI_AUTH_FAILED 等错误码具备真实生产者（此前仅定义无产出），
    上层可据此给出精确诊断而非笼统报错。
    """

    def __init__(self, message: str = "", code: str = ""):
        super().__init__(message)
        self.code = code or ""


class StaleAdvanceError(RuntimeError):
    """回合推进请求**超前**于服务端当前回合（两端漂移）。

    由 `commands.advance_two_phase` 在 `expect_turn > state.turn` 时抛出，
    `backend/server.py` 将其映射为 HTTP 409 + 错误码 `STALE_TURN`，
    避免客户端凭陈旧视图跳过一个月。

    落后（`expect_turn < state.turn`）**不走异常**：按幂等重放返回该回合历史日志
    （重发请求是正常现象，不应报错）。

    接线背景（2026-10-23）：server 侧（`server.py:42/576`）、backend 侧
    （`client.py:189-221`）与定向测试均早已按此契约写好，本类与
    `advance_two_phase`/`settle_local` 的 `expect_turn` 守卫是缺的最后一块——
    缺它时 `import backend.server` 直接 ImportError，整个服务起不来。
    """
