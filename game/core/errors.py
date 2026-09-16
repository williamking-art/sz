"""核心错误类型定义（避免循环导入）。

本模块只定义异常类，不导入任何业务模块，供 core / ai / ui 各层共享。
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
