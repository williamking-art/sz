# -*- coding: utf-8 -*-
"""宋祚 · 存档槽位机械（从 `core/save_load.py` 原文迁来，零行为变更）。

承架构方案 §4.1：`foundation/persistence/` = 存档读写与版本迁移。本文件只装
**已验证无业务依赖**的槽位定位/列举，`save_game`/`load_game` 仍在 `core/save_load.py`
（它们间接携带 4 条反向边，见 `specs/cross-cutting/存档schema版本消费实况_2026-10-07.md`）。

旧路径兼容：`core.save_load` 显式转发本模块全部符号，`dir()` 公开面与调用方导入不变。
"""
import json
import os

from content.data import SAVE_DIR

#: 槽位约定（勿擅自收窄）：0 = **自动存档槽**（`finish_turn` 每年正月与终局写入，
#: 见 core/commands.py）；1–5 = 玩家可见槽（`get_save_slots` 只列这些）；
#: >5 = 测试/临时槽（多个回归用例刻意用 6/7/8/9/99 做隔离）。
#: 故 save/load **只校验「非负整数」**，不做 1–5 钳制 —— 钳制会打断自动存档并炸掉一批用例。
SLOT_MIN = 0


def _slot_ok(slot) -> bool:
    """槽位合法性：非负整数（HTTP 层的 Pydantic 已挡住类型注入，此处兜住内部调用）。"""
    return isinstance(slot, int) and not isinstance(slot, bool) and slot >= SLOT_MIN


# 迁移注记（2026-10-07 第七包，仅注释、不改函数原文）：下方 docstring 里
# 「刻意留在本模块」指的是**不要抽到 save_load_util**（那时它还在 core 下）。
# 现本模块读的是**本模块级** `SAVE_DIR`：这才是槽位文件的**唯一真开关**。
# ⚠️ 实测教训（本批首跑全量红 3 例）：只 patch `core.save_load.SAVE_DIR` **不再生效**，
# 因为那个名字如今只为维持旧路径 `dir()` 公开面而保留、不驱动任何写入。
# 两道兜底：① conftest 对**所有带字符串 SAVE_DIR 的已加载模块**统一打补丁，并把本模块列入
# `_CRITICAL_SAVE_DIR_MODULES` 同源自检（session 末核查真实 `SAVE_DIR` 未被写过）；
# ② `save_load.save_game` 的建目录改为 `os.path.dirname(_slot_path(slot))`，与写入同源。
def _slot_path(slot: int) -> str:
    """存档槽位文件路径（save/load/slots 三处共用，避免硬编码漂移）。

    刻意留在本模块：读模块级 `SAVE_DIR`，测试 monkeypatch.setattr(save_load, "SAVE_DIR")
    才能重定向；抽到 save_load_util 会让 patch 失效。
    """
    return os.path.join(SAVE_DIR, f"slot_{slot}.json")


def get_save_slots() -> list:
    """获取所有存档槽位信息"""
    slots = []
    for i in range(1, 6):
        path = _slot_path(i)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                # 审查 P2-3 / M13（**反向缺口**）：原只捕获 (OSError, ValueError)。
                # 槽文件内容是**数组/字符串**时 `d.get(...)` 抛 AttributeError **穿透**，
                # 整个槽位列表调用直接 500 —— 一个坏档让玩家连"哪个档坏了"都看不到。
                # 现解析后即校验顶层类型，并入既有损坏槽分支（标 corrupt，不隐藏槽位）。
                if not isinstance(d, dict):
                    raise ValueError(f"顶层非对象（{type(d).__name__}）")
                slots.append({
                    "slot": i,
                    "time": d.get("save_time_str", "未知"),
                    "year": d.get("year", 0),
                    "month": d.get("month", 1),
                    "era": d.get("era_name", ""),
                    "turn": d.get("turn", 0),
                })
            except (OSError, ValueError) as e:
                # 审查 P3：裸 except 会吞掉一切且静默丢槽。改为具名异常 + 记日志 +
                # 显式标记损坏槽（UI 显示「存档损坏」而非误报空槽/槽位消失）。
                import logging as _lg
                _lg.getLogger("save_load").warning("存档槽 %s 读取失败：%s", i, e)
                slots.append({"slot": i, "corrupt": True, "time": "存档损坏",
                              "year": 0, "month": 1, "era": "", "turn": 0})
        else:
            slots.append({"slot": i, "empty": True})
    return slots
