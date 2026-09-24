# -*- coding: utf-8 -*-
"""假 AI 后端（测试替身，不联网；沈舶司范式）：供 free_effect/强制 AI 契约的无网络测试，
与玩家真实 AI 严格隔离（仅 tests/ 使用）。

导入统一用：`from tests.fake_ai_backend import FakeAIClient`
（conftest 已把 `_dev_tools` 根加入 sys.path，`tests` 为 namespace 包）。

**契约字段对齐提醒**：`economy_decide` 默认值必须含金融 5 字段
（jiaozi_trust/shortage/maritime/bank/price_trend）——R3-14 拒绝式后，
缺字段会被真 validate 整单拒绝；本替身绕过 validate，但默认值仍应完整，
避免测试里手动补字段时漏项。
"""


class FakeAIClient:
    """替身 AI：按注入的契约/推演结果返回，绝不联网。

    未实现的方法请在测试里 subclass 覆盖（保持本类精简）。
    """

    def __init__(self, free_effect_contract=None, economy=None):
        self.available = True
        self._contract = free_effect_contract
        self._economy = economy

    def free_effect_decide(self, posture, title="", body=""):
        if self._contract is None:
            return {"_error": "AI_CONTRACT_FAILED"}
        return dict(self._contract)

    def economy_decide(self, posture, state=None):
        if self._economy is None:
            # 完整 12 字段（含金融 5 字段），与 AIClient.economy_decide 契约对齐
            return {
                "景气": "中", "士绅": "观望", "士绅力度": "中", "生产": "中",
                "窖银": "无", "城市化": "无", "回乡": "无", "科举": "无",
                "jiaozi_trust": "稳", "shortage": "平", "maritime": "平",
                "bank": "稳", "price_trend": "平",
            }
        return dict(self._economy)

    def monthly_report(self, year, month, era_name, posture):
        return {"report": f"〔{era_name}〕{year}年{month}月，四海承平，百司奏对如仪。"}
