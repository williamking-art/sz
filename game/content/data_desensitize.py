# -*- coding: utf-8 -*-
"""宋祚 · 数值脱敏辅助函数族。

拆分自 content/data.py：皇威/到账/满意度/国库/交子/钱荒/太仓/米价/漕运/人才/科技 定性描述。
被 data.py re-export 保持调用兼容。
"""
def desensitize_prestige(value: int) -> str:
    """皇威数值→脱敏描述"""
    if value <= 25: return "皇威扫地"
    if value <= 40: return "皇威不振"
    if value <= 60: return "皇威平平"
    if value <= 80: return "皇威尚隆"
    return "皇威鼎盛"

def desensitize_arrival(rate: float) -> str:
    """到账率→脱敏描述"""
    if rate <= 0.2: return "十不存二"
    if rate <= 0.4: return "不足五成"
    if rate <= 0.6: return "六成上下"
    if rate <= 0.8: return "十之七八"
    return "几近全数"

def desensitize_satisfaction(value: int) -> str:
    """满意度→脱敏描述"""
    if value <= 20: return "怨声载道"
    if value <= 40: return "颇有微词"
    if value <= 60: return "大体认可"
    if value <= 80: return "心悦诚服"
    return "感恩戴德"

def desensitize_treasury(amount: int) -> str:
    """国库→脱敏描述"""
    if amount <= 0: return "库空如洗"
    if amount <= 2000000: return "入不敷出"
    if amount <= 5000000: return "略有结余"
    if amount <= 10000000: return "国库充盈"
    return "富甲天下"

def desensitize_trust(value: int) -> str:
    if value <= 20: return "交子几不可信"
    if value <= 40: return "商民疑之"
    if value <= 60: return "信用尚稳"
    return "远近信行"

def desensitize_shortage(rate: float) -> str:
    if rate <= 0.1: return "泉货流转"
    if rate <= 0.3: return "钱荒渐显"
    if rate <= 0.6: return "钱荒严重"
    return "几乎无钱可用"

def desensitize_granary(amount: float, cap: float = 1500) -> str:
    """太仓虚实（定性）：用于奏报与 AI 认知层，绝不下放精确存粮数。"""
    if cap <= 0:
        cap = 1500
    r = amount / cap
    if r >= 0.75: return "太仓丰盈，粟积如丘"
    if r >= 0.5:  return "仓储殷实，足以支国用"
    if r >= 0.25: return "仓廪见绌，宜促漕运"
    if r > 0:     return "太仓空虚，几无隔宿之粮"
    return "太仓告罄，京畿乏食"

def desensitize_price(price: float) -> str:
    """米价定性：用于趋势读数与 AI 认知层。"""
    if price >= 2.0: return "米珠薪桂，民不堪命"
    if price >= 1.5: return "米价腾涌，市井骚然"
    if price >= 1.1: return "米价偏高，小民艰食"
    if price <= 0.6: return "谷贱伤农，丰年反困"
    if price <= 0.8: return "米价低平，农人或困"
    return "米价适中，市侩安和"

def desensitize_canal(block: int) -> str:
    """漕运通滞定性。"""
    if block >= 70: return "漕路断绝，纲船难通"
    if block >= 40: return "漕运受阻，输粟不畅"
    if block >= 15: return "漕途多阻，转运维艰"
    return "漕运通畅，转输无滞"

def desensitize_talent(value: int) -> str:
    if value <= 20: return "人才凋零"
    if value <= 50: return "人才平平"
    if value <= 80: return "人才颇盛"
    return "人才辈出"

def desensitize_tech(value: int) -> str:
    if value <= 20: return "技艺粗疏"
    if value <= 50: return "技艺尚可"
    if value <= 80: return "百工精进"
    return "巧夺天工"
