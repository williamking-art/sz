# -*- coding: utf-8 -*-
"""假 AI 后端（测试替身，不联网；沈舶司范式）：供 free_effect/强制 AI 契约的无网络测试，
与玩家真实 AI 严格隔离（仅 tests/ 使用）。"""


class FakeAIClient:
    """替身 AI：按注入的契约/推演结果返回，绝不联网。"""

    def __init__(self, free_effect_contract=None, economy=None):
        self.available = True
        self._contract = free_effect_contract
        self._economy = economy

    def free_effect_decide(self, posture, title="", body=""):
        if self._contract is None:
            return {"_error": "AI_CONTRACT_FAILED"}
        return dict(self._contract)

    def economy_decide(self, posture):
        if self._economy is None:
            return {"景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中",
                    "窖银": "无", "城市化": "无", "回乡": "无", "科举": "无"}
        return dict(self._economy)

    def monthly_report(self, year, month, era_name, posture):
        return {"report": f"〔{era_name}〕{year}年{month}月，四海承平，百司奏对如仪。"}
