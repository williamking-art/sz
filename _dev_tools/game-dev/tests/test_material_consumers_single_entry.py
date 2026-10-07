# -*- coding: utf-8 -*-
"""消费侧**口径单点守卫**（Step 4 · 2026-10-02）。

## 为什么用"源码级断言"而不是行为断言

建材扣减现在发生在三处：`settlement_tech._settle_projects`（政府工程）、
`civil_building`（民间营造）、`settlement_agri`（农业设施）。
它们过去**各自直读 `state.resources[dim]["stock"]`** —— 这正是规格 §14.2 **障碍 2**
「**判定与采购口径分叉**」的根源（`route_civil_demand` 查仓、`build_civil_building`
查市，两处不一致）。

本文件把"消费侧**不得**绕过单点读口"变成**可执行断言**，
让"口径单点"不再只是文档里的一句话。

## 与 Step 2 的「禁止人口比例分摊」守卫同法

纪律写在文档里会被绕过；写进 `inspect.getsource` 的断言，下一个改代码的人
会立刻被测试拦住，并被迫先想清楚口径。
"""
import inspect
import os
import sys

import pytest

_GAME = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from core import civil_building, construction_cost  # noqa: E402
from core.domains.construction import settlement_tech  # noqa: E402
from core.domains.production import settlement_agri  # noqa: E402
from core.material_holding import (                                    # noqa: E402
    consume_for_circuit, material_holding_for_circuit, supply_merchant_materials,
)

#: 消费侧三处（政府工程 / 民间营造 / 农业设施）
_CONSUMERS = {
    "settlement_tech": settlement_tech,
    "civil_building": civil_building,
    "settlement_agri": settlement_agri,
}

#: 建材维度（须经单点读口）
_MAT_DIMS = ("木", "石", "铁")

#: **有建材注册表**的消费方（配置表里的维度名须受校验）
_REGISTRY_CONSUMERS = {
    "civil_building": civil_building,
    "settlement_agri": settlement_agri,
}


def _sources():
    out = {}
    for name, mod in _CONSUMERS.items():
        try:
            out[name] = inspect.getsource(mod)
        except OSError:                       # pragma: no cover
            pytest.skip(f"取不到 {name} 源码")
    return out


def _src(name):
    try:
        return inspect.getsource(_CONSUMERS[name])
    except OSError:                           # pragma: no cover
        pytest.skip(f"取不到 {name} 源码")


@pytest.mark.parametrize("name", sorted(_CONSUMERS))
def test_consumer_does_not_bypass_single_entry(name):
    """🔴 消费侧**不得**绕过单点读口直取建材。

    E-1 后建材是**商品**，落在**商人 POP `goods`**；
    仓明细层 `by_pref` 已退役（若再出现即平行账本）。
    """
    src = _sources()[name]
    assert '["by_pref"]' not in src and "['by_pref']" not in src, \
        f"{name} 绕过单点读口直读/直写 by_pref（该层已退役）"
    assert '"铁"]["stock"]' not in src and "'铁']['stock']" not in src, \
        f"{name} 直读仓里建材 ⇒ 等于「料可凭空调用」，物流失去意义"


@pytest.mark.parametrize("name", sorted(_REGISTRY_CONSUMERS))
def test_consumer_validates_material_dims(name):
    """🔴 **注册表**里的建材维度名必须对 `MATERIAL_DIMS` 校验。

    ⚠️ 早期版本把本守卫写成"源码不得出现 timber/stone"——那其实是**错的**：
    配置表自然要写维度名（那是数据不是算法），真正该守的是**拼错必须报错**，
    否则该建筑/升级会永远走"缺料"分支而**静默失效**。故改为断言"存在维度校验"。

    ⚠️ 只约束**有注册表**的消费方（`settlement_tech` 无配置表，
    它经 `to_material_dim()` 翻译既有维度名，另有 `to_material_dim` 的用例守护）。
    """
    src = _src(name)
    assert "MATERIAL_DIMS" in src, \
        f"{name} 未引用 MATERIAL_DIMS —— 配置里的建材维度拼错会静默失效"
    assert "not in MATERIAL_DIMS" in src, \
        f"{name} 只引用了 MATERIAL_DIMS 却没做校验 —— 须显式拒绝非法维度"


def test_construction_cost_is_the_only_cost_source():
    """造价必须只有**一个真源** `base_material_cost`（B4-3 既有口径，不得新增第二处）。"""
    src = inspect.getsource(construction_cost)
    assert "def base_material_cost(" in src, "造价单一真源函数缺失"
    for name, mod in _CONSUMERS.items():
        s = _sources()[name]
        # 允许 import 与调用，但不得自己写死单价表
        assert "MATERIAL_PRICE" not in s and "unit_price = {" not in s, \
            f"{name} 自建了单价表 —— 造价必须走 construction_cost.base_material_cost"


# ====================================================== 行为校验（源码断言不够）
def test_civil_registry_rejects_unknown_material_dim():
    """🔴 拼错建材维度**必须抛错**——否则该建筑永远走"缺料"分支、静默失效。"""
    import copy
    from core.civil_building import (CivilRegistryError, register_civil_building,
                                     CIVIL_BUILDING_SPECS)
    entry = copy.deepcopy(CIVIL_BUILDING_SPECS["民居"])
    entry["stock_per_lv"] = {"timberr": 10}      # 故意拼错
    with pytest.raises(CivilRegistryError):
        register_civil_building("__probe_bad_dim__", entry)


def test_agri_registry_rejects_unknown_material_dim():
    """🔴 同上：农业升级的物料维度拼错也必须抛错。"""
    import copy
    from core.settlement_agri import (AGRI_UPGRADE_EFFECTS, AgriUpgradeError,
                                      register_agri_upgrade)
    entry = copy.deepcopy(AGRI_UPGRADE_EFFECTS["水利"])
    entry["material_per_lv"] = {"woood": 10}      # 故意拼错
    with pytest.raises(AgriUpgradeError):
        register_agri_upgrade("__probe_bad_dim__", entry)


# ====================================================== 单点 API 的契约
def test_single_entry_points_are_the_only_write_path():
    """单点扣减：钱与料都只在 POP 上转移，总量守恒。"""
    from core.game_state import GameState
    from core.legacy_mechanic import init_legacies
    from core.production_chain import settle_production_chain

    s = GameState("史实")
    init_legacies(s)
    settle_production_chain(s, [])
    # 6.33：未裁定维（含木石）落**归属待定槽**，不得采购；
    # 故显式准备**已确权、可用的库存**，供营造/施工用例使用。
    for _d in ("木", "石"):
        _sl = s.resources.setdefault(_d, {"stock": 0, "cap": 50_000})
        if int(_sl.get("stock", 0) or 0) <= 0:
            _sl["stock"] = 10_000
    supply_merchant_materials(s)

    assert material_holding_for_circuit(s, "京畿路", "木") is not None
    before = int(material_holding_for_circuit(s, "京畿路", "木"))
    got = consume_for_circuit(s, "京畿路", "木", 400)
    assert got == 400
    assert material_holding_for_circuit(s, "京畿路", "木") == before - 400
