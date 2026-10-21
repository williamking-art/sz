# -*- coding: utf-8 -*-
"""内核基础包（P0 地基）。

| 文件 | 职责 |
|---|---|
| `pack.py` | 读取/校验 `content/packs/<id>/manifest.json`；不触碰 GameState |
| `calendar.py` | 年/月/年号/相对年份/周期；只读计算 |
| `objectives.py` | 显式目标注册表（gate/choose/score/dice） |
| `decision.py` | DecisionRequest/Result/Service 契约；不写 state、不联网 |
"""
