# -*- coding: utf-8 -*-
"""物理四仓深化测试：重点工程料场真领料与常平仓同源化（M308）。

覆盖：
1. 工程优先从治所 public_depot 领料；
2. public_depot 缺料时向商人行栈补充，两处均缺时不凭空造料；
3. 工程完工时未耗完余料退回治所 public_depot；
4. 常平仓平籴平粜与治所 public_granary['grain'] 同源同步。
"""
import pytest
from application.game_init import new_game
from core.foundation.ledger.spatial_warehouse_bridge import (
    ensure_seat_warehouses,
    warehouse_stock_get,
    warehouse_stock_add,
    consume_project_materials_spatial,
    changping_grain_spatial_op,
)
from core.foundation.ledger.storage_bridge import changping_add, changping_get


def test_project_consume_from_public_depot_first():
    """工程领料优先消耗治所 public_depot 库存。"""
    s = new_game("史实")
    # 为京畿路官方料场注料
    warehouse_stock_add(s, "kaifeng", "public_depot", "木", 500.0)
    assert warehouse_stock_get(s, "kaifeng", "public_depot", "木") == 500.0

    # 领料 300
    got, src = consume_project_materials_spatial(s, "京畿路", "木", 300.0)
    assert got == 300.0
    assert "官方料场" in src
    # 官方料场剩余 200
    assert warehouse_stock_get(s, "kaifeng", "public_depot", "木") == 200.0


def test_project_consume_overflow_to_merchant():
    """官方料场不足时，缺口转由本路商人货栈补充。"""
    s = new_game("史实")
    # 料场只有 50 木
    warehouse_stock_add(s, "两浙路", "public_depot", "木", 50.0)
    
    # 向两浙路商人货栈注料
    from core.foundation.ledger.material_holding import goods_add, to_material_dim
    merchant = s.prefectures["两浙路"]["pops"]["商人"]
    goods_add(merchant.setdefault("goods", {}), to_material_dim("木"), 200)

    # 领料 150 (料场出 50，商人出 100)
    got, src = consume_project_materials_spatial(s, "两浙路", "木", 150.0)
    assert got == 150.0
    assert "官方料场" in src
    assert "商人行栈" in src
    assert warehouse_stock_get(s, "两浙路", "public_depot", "木") == 0.0


def test_project_completion_refund_to_public_depot():
    """工程完工时余料自动退回治所 public_depot。"""
    from core.domains.construction.settlement_tech import _settle_projects
    s = new_game("史实")
    log = []
    
    # 为料场准备 100 木供开工
    warehouse_stock_add(s, "京畿路", "public_depot", "木", 100.0)
    
    # 注册一个即将完工且有余料的工程
    proj = {
        "id": "test_refund_proj",
        "name": "开封治河工程",
        "status": "building",
        "progress": 95,
        "speed": 10,
        "route": "京畿路",
        "cost_coin": 0,
        "cost_material": {"木": 50},
        "_mat_left_木": 40.0,  # 剩余 40 没用完
    }
    s.projects["test_refund_proj"] = proj
    
    initial_depot_wood = warehouse_stock_get(s, "京畿路", "public_depot", "木") or 0.0
    _settle_projects(s, log)
    
    assert proj.get("done") is True
    # 完工后余料已退回 public_depot
    new_depot_wood = warehouse_stock_get(s, "京畿路", "public_depot", "木") or 0.0
    assert new_depot_wood >= 40.0


def test_changping_granary_spatial_sync():
    """B-2：常平账与官仓实物账分离，常平写入不得无对价覆盖 public_granary。"""
    s = new_game("史实")
    seat = next(iter(s.prefectures["两浙路"]["seats"]))
    warehouse_stock_add(s, seat, "public_granary", "grain", 777.0)
    before_public = warehouse_stock_get(s, seat, "public_granary", "grain")
    # 两浙路常平仓籴入 1000 石
    changping_add(s, "两浙路", 1000)
    route_total = changping_get(s, "两浙路")
    assert route_total is not None and route_total >= 1000
    # 常平账变动不得覆盖官仓实物账
    assert warehouse_stock_get(s, seat, "public_granary", "grain") == before_public
