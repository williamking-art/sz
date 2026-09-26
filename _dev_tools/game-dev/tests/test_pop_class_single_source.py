# -*- coding: utf-8 -*-
"""口径单一化守卫：六类 POP 清单 + 官俸权数（2026-09-27 清理）。

背景（《POP机制现状_2026-09-27》§6.3 / §6.9）：同一事实曾**三处并行定义**——

  ① 六类 POP 清单：
     - `content/data.py` 的 `GRAIN_CONSUME_PER_CAPITA`（**权威**，被 faction_basis /
       situation_metrics / situations / region_brief / settlement_* 消费）；
     - `content/data_constants.py` 的 `POP_TYPES`（重复定义，**已删**）；
     - `core/situation_metrics.py` 的 `POP_SENTIMENT_CHANNELS`（派生，须与权威恒等）。
  ② 官俸权数：`content/data_constants.py` 的 `WAITING_PAY_RATIO` / `SINECURE_PAY_RATIO`
     （**权威**）；而 `core/officialdom.py` 模块注释与《宋代官制与三冗设计.md》曾写死
     0.5 / 0.5（与代码不符，**已改为引用常量名**）。

本文件把「权威值 + 三处恒等 + 注释/文档不得写死数字」钉成用例：
**数值一旦改动，必须显式改本测试**——否则文档与注释会再次漂移。
"""
import os
import re
import sys

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME_ROOT not in sys.path:
    sys.path.insert(0, _GAME_ROOT)

from content.data import GRAIN_CONSUME_PER_CAPITA  # noqa: E402
from content.data_constants import (  # noqa: E402
    SINECURE_PAY_RATIO, WAITING_PAY_RATIO,
)
from core.situation_metrics import POP_SENTIMENT_CHANNELS  # noqa: E402

# 六类 POP 的**权威清单（含键序）**——只此一处期望值，改动即需显式改本文件
POP_SIX = ("农", "士绅", "工匠", "商人", "官僚", "兵")

_DESIGN_DOC = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "game-docs", "docs", "宋代官制与三冗设计.md"))


def _code_lines(text):
    """产出 `(行号, 去掉注释与 docstring 后的代码)` —— 用于"只查代码引用"。"""
    text = re.sub(r'"""(?:.|\n)*?"""', "", text)
    text = re.sub(r"'''(?:.|\n)*?'''", "", text)
    for i, line in enumerate(text.splitlines(), 1):
        yield i, line.split("#")[0]


# ---------------------------------------------------------------- ① 六类 POP
def test_authoritative_pop_list_is_exactly_six_in_order():
    """权威清单 = `GRAIN_CONSUME_PER_CAPITA` 的键序（唯一事实源）。"""
    assert tuple(GRAIN_CONSUME_PER_CAPITA) == POP_SIX, (
        "六类 POP 权威清单已变：content/data.py::GRAIN_CONSUME_PER_CAPITA "
        f"= {tuple(GRAIN_CONSUME_PER_CAPITA)!r}，期望 {POP_SIX!r}。"
        "若确为有意变更，请同步 POP_SENTIMENT_CHANNELS 与本测试。"
    )


def test_sentiment_channels_match_authoritative_list():
    """心气通道表与权威清单恒等（既不多也不少、键序一致）。"""
    assert tuple(POP_SENTIMENT_CHANNELS) == tuple(GRAIN_CONSUME_PER_CAPITA), (
        "POP_SENTIMENT_CHANNELS 与 GRAIN_CONSUME_PER_CAPITA 不一致："
        f"{tuple(POP_SENTIMENT_CHANNELS)!r} vs {tuple(GRAIN_CONSUME_PER_CAPITA)!r}"
    )
    assert set(POP_SENTIMENT_CHANNELS) == set(POP_SIX)


def test_pop_types_is_gone_and_must_not_come_back():
    """`POP_TYPES` 已删除；既不许作为属性复活，也不许在 game/ 源码里重新出现。"""
    import content.data as _cd
    import content.data_constants as _cc

    assert not hasattr(_cd, "POP_TYPES"), (
        "content.data 又出现 POP_TYPES —— 六类清单的权威源是 "
        "content/data.py::GRAIN_CONSUME_PER_CAPITA，不要重新导出。"
    )
    assert not hasattr(_cc, "POP_TYPES"), (
        "content.data_constants 又出现 POP_TYPES —— 该表已被 GRAIN_CONSUME_PER_CAPITA "
        "取代（且本模块不能 import content.data，无法派生），请直接使用权威表。"
    )

    # 只扫**代码行**（注释/docstring 里说明"POP_TYPES 已删除"不算消费者）
    hits = []
    for root, dirs, files in os.walk(_GAME_ROOT):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".pytest_cache")]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
            for i, line in _code_lines(text):
                if "POP_TYPES" in line:
                    hits.append(f"{os.path.relpath(path, _GAME_ROOT)}:{i}: {line.strip()}")
    assert not hits, (
        "`game/` 源码中仍有 POP_TYPES 代码引用（同一事实的第三处定义）：\n  "
        + "\n  ".join(hits)
    )


# ---------------------------------------------------------------- ② 官俸权数
def test_official_pay_ratios_are_pinned():
    """官俸付款权数（待阙/祠禄）**钉住数值**——改动必须显式改本测试。

    权威源：`content/data_constants.py`；消费点：`core/officialdom.route_pay_units`。
    """
    assert WAITING_PAY_RATIO == 0.35, f"待阙俸率变了：{WAITING_PAY_RATIO!r}（期望 0.35）"
    assert SINECURE_PAY_RATIO == 0.4, f"祠禄折俸变了：{SINECURE_PAY_RATIO!r}（期望 0.4）"


def test_officialdom_module_docstring_cites_constants_not_numbers():
    """模块注释只许引用常量名，不许写死权数（防止注释再次漂移成 0.5/0.5）。"""
    import core.officialdom as _od

    doc = _od.__doc__ or ""
    for name in ("WAITING_PAY_RATIO", "SINECURE_PAY_RATIO"):
        assert name in doc, f"officialdom 模块注释未引用 {name}（应引用而非写死数字）"
    assert "0.5" not in doc, (
        "officialdom 模块注释又写死了权数 0.5 —— 请改为引用 "
        "`WAITING_PAY_RATIO` / `SINECURE_PAY_RATIO`（数值以 data_constants 为权威）。"
    )
    # 函数级 docstring 同样只引用常量名
    fn_doc = _od.route_pay_units.__doc__ or ""
    assert "WAITING_PAY_RATIO" in fn_doc and "SINECURE_PAY_RATIO" in fn_doc


def test_design_doc_pay_ratios_match_code():
    """官制设计文档里以 `X=数值` **陈述当前取值**的地方，必须与代码一致。

    例外：同句带「若」的假设句（如"若用户认为应更史实，改 `WAITING_PAY_RATIO = 0.0`"）
    不是对当前取值的陈述，跳过。
    """
    if not os.path.isfile(_DESIGN_DOC):
        pytest.skip(f"设计文档不在预期位置：{_DESIGN_DOC}")
    with open(_DESIGN_DOC, encoding="utf-8") as fh:
        text = fh.read()

    expect = {"WAITING_PAY_RATIO": WAITING_PAY_RATIO,
              "SINECURE_PAY_RATIO": SINECURE_PAY_RATIO}
    pattern = re.compile(r"(WAITING_PAY_RATIO|SINECURE_PAY_RATIO)\s*=\s*([0-9.]+)")
    seen = {name: [] for name in expect}
    for lineno, line in enumerate(text.splitlines(), 1):
        for name, raw in pattern.findall(line):
            if "若" in line:          # 假设句，非当前取值
                continue
            seen[name].append((lineno, raw))
            assert float(raw) == expect[name], (
                f"设计文档 :{lineno} 写 `{name}={raw}`，与代码 {expect[name]} 不一致 —— "
                "数值以 game/content/data_constants.py 为权威。"
            )
    for name, value in expect.items():
        assert seen[name], (
            f"设计文档未以 `{name}={value}` 形式同步当前取值 —— "
            "权威在 game/content/data_constants.py，文档须随之一致。"
        )
