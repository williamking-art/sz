# -*- coding: utf-8 -*-
"""前端常量口径单点守卫（审查 D1，2026-10-01）。

背景：`PersonalPanel` / `MilitaryPanel` 曾各自**复制** core 的常量字面量
（`IMPERIAL_RISK_PROB` / `IMPERIAL_ROUTE_DISTANCE` / `IMPERIAL_DISTANCE_MONTHS` /
 `IMPERIAL_EFFECT_DIM` / `EQUIP_KEYS`），并**重实现** `imperial_distance()`。
当时数值恰好一致，但 core 改一次 UI 就静默说谎，且注释还指向已删的 Tk 文件
（`game/ui/panels_economy.py`、`panels_military.py`）。

现改为导出面单点供给（`export_constants.py` → `constants.json`），本测试守三件事：
 ① `constants.json` 含上述 5 键，且与 core 常量**逐值一致**（重新导出后比对）；
 ② 前端**不得再出现**这些字面量副本（源码级断言：只允许经 `constants` 读取）；
 ③ 不得引用已删的 Tk 路径（`game/ui/...`、`panels_economy.py`、`panels_military.py`）。
"""
import json
import os
import re

import pytest

_GAME_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
_FE = os.path.join(_GAME_ROOT, "frontend", "src", "renderer")
_CONST_JSON = os.path.join(_FE, "data", "constants.json")

if _GAME_ROOT not in os.sys.path:
    os.sys.path.insert(0, _GAME_ROOT)


def _constants() -> dict:
    with open(_CONST_JSON, encoding="utf-8") as f:
        return json.load(f)


def _panel_src(name: str) -> str:
    with open(os.path.join(_FE, "panels", name), encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- ① 导出面一致
def test_constants_json_has_d1_keys():
    """① 导出面须含 D1 的 5 个键（缺一即前端又会去复制）。"""
    c = _constants()
    for key in ("imperial_risk_prob", "imperial_route_distance",
                "imperial_distance_months", "imperial_effect_dim", "equip_keys"):
        assert key in c, f"constants.json 缺 {key}（前端将被迫复制字面量）"


def test_constants_json_matches_core_values():
    """①① 导出值必须与 core 常量**逐值一致**（否则等于换了个地方漂移）。"""
    from content.data_imperial import (IMPERIAL_DISTANCE_MONTHS, IMPERIAL_EFFECT_DIM,
                                       IMPERIAL_RISK_PROB, IMPERIAL_ROUTE_DISTANCE)
    from core.army_models import EQUIP_KEYS
    c = _constants()
    assert c["imperial_risk_prob"] == dict(IMPERIAL_RISK_PROB)
    assert c["imperial_distance_months"] == dict(IMPERIAL_DISTANCE_MONTHS)
    assert c["imperial_effect_dim"] == dict(IMPERIAL_EFFECT_DIM)
    assert c["imperial_route_distance"] == {k: list(v) for k, v in IMPERIAL_ROUTE_DISTANCE.items()}
    assert c["equip_keys"] == list(EQUIP_KEYS)


def test_export_constants_is_idempotent():
    """①② 导出面与仓库内 constants.json 必须一致（证明 json 与导出面同步）。

    2026-10-03 修正两处：
    - 原实现直接 subprocess 跑导出脚本，而脚本无条件覆写**仓库内被跟踪的**
      frontend/src/renderer/data/constants.json —— 只读回归却改了工作区，
      且失败时原值已被覆盖、无法回看。现改为导出到临时目录再比对。
    - 原用环境里的 `python`（不是当前解释器），换机器/换 venv 就跑不通；改用 sys.executable。
    """
    import subprocess
    import sys
    import tempfile
    committed = open(_CONST_JSON, encoding="utf-8").read()
    with tempfile.TemporaryDirectory() as td:
        tmp_out = os.path.join(td, "constants.json")
        subprocess.run([sys.executable, "export_constants.py", tmp_out], cwd=_GAME_ROOT,
                       capture_output=True, check=True)
        generated = open(tmp_out, encoding="utf-8").read()
    assert generated == committed, "constants.json 与 export_constants.py 不同步（需重跑导出）"


# ---------------------------------------------------------------- ② 前端不再复制
def test_personal_panel_has_no_literal_constant_copies():
    """② PersonalPanel 不得再硬编码风险概率/距离表字面量。"""
    src = _panel_src("PersonalPanel.tsx")
    assert not re.search(r"\{\s*低:\s*0\.0?2", src), "风险概率字面量副本仍在"
    assert not re.search(r"\[\s*\"近\"\s*,\s*\[\s*\"开封\"", src), "距离关键词表副本仍在"
    assert not re.search(r"\{\s*近:\s*0\s*,\s*中:\s*1\s*,\s*远:\s*2\s*\}", src), "距离月数字面量副本仍在"
    assert "constants.imperial_risk_prob" in src, "应改读 constants.json"
    assert "constants.imperial_route_distance" in src
    assert "constants.imperial_distance_months" in src
    assert "constants.imperial_effect_dim" in src


def test_military_panel_equip_keys_from_constants():
    """② MilitaryPanel 的装备键名改读导出面（计量词属 UI，保留本地）。"""
    src = _panel_src("MilitaryPanel.tsx")
    assert not re.search(r"\[\s*\"枪刀\"\s*,\s*\"件\"", src), "装备键名字面量副本仍在"
    assert "constants.equip_keys" in src


def test_frontend_imperial_distance_matches_core():
    """②① 前端 `imperialDistance` 与后端 `imperial_distance()` 判据一致（同源数据+同逻辑）。"""
    from content.data_imperial import IMPERIAL_ROUTE_DISTANCE, imperial_distance
    table = {k: list(v) for k, v in IMPERIAL_ROUTE_DISTANCE.items()}
    for target in ("两浙路", "开封府", "京西南路", "秦凤路", "不存在的路"):
        # 复刻前端实现：按导出表顺序做关键词包含匹配，未命中默认「中」
        got = "中"
        for dist, kws in table.items():
            if any(k in target for k in kws):
                got = dist
                break
        assert got == imperial_distance(target), f"{target} 前端/后端距离档不一致"


# ---------------------------------------------------------------- ③ 不引死路径
@pytest.mark.parametrize("panel", [
    "PersonalPanel.tsx", "MilitaryPanel.tsx", "ProvinceMilitaryPanel.tsx",
    "TodoPanel.tsx", "PopPanel.tsx",
])
def test_no_dead_tk_path_references(panel):
    """③ 注释不得再指向已删的 Tk 旧页（否则误导后续维护者去找不存在的文件）。"""
    src = _panel_src(panel)
    for dead in ("game/ui/panels_economy.py", "panels_military.py", "panels_economy.py"):
        assert dead not in src, f"{panel} 仍引用已删除的 {dead}"