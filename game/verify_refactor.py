# -*- coding: utf-8 -*-
"""军政重构冒烟验证（无 GUI 依赖，直接跑 core 层）。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.game_state import GameState
from content.data import ARMY_UNIT_INIT, UNIT_TIER, CENTRAL_ARSENAL_INIT, TECH_NODES
from ui.panels_military import _army_power, _army_power_total, reorganize_xiang_to_jin
from content.data import _firearm_tier
from core.settlement import run_monthly_settlement

def main():
    s = GameState("史实")
    # 1) 开局兵额 = Σ ARMY_UNIT_INIT（零回归）
    expect = sum(t for d in ARMY_UNIT_INIT.values() for t in d.values())
    got = sum(u.troops for u in s.army_units)
    print(f"[兵额] 期望{sum(t for d in ARMY_UNIT_INIT.values() for t in d.values())} 实际{got} -> {'OK' if got==expect else 'FAIL'}")

    # 2) 防线聚合 = 总兵额
    s._derive_defense_lines()
    def_total = sum(v["garrison"] for v in s.defense_lines.values())
    print(f"[防线] Σgarrison={def_total} vs Σtroops={got} -> {'OK' if def_total==got else 'FAIL'}")

    # 3) 军费（粮饷两笔独立账、按军籍分档）
    ag, ag_by = s.calc_army_grain()
    ac, ac_by = s.calc_army_cash()
    print(f"[军费] 月军粮={ag:.1f}万石 月军饷={ac:.1f}万贯 (兵额人不变, 分档后允许微调)")

    # 4) 武库初值
    print(f"[武库] 枪刀={s.central_arsenal.stock['枪刀']} 火器={s.central_arsenal.stock['火器']}")

    # 5) 战力派生 / 火器代际
    gp = s.tech["gunpowder"]
    print(f"[火器] gunpowder={gp} -> {_firearm_tier(gp)} ; 总战力={_army_power_total(s.army_units, gp):.0f}")

    # 6) 整编（厢军->禁军）：河北路
    before = sum(u.troops for u in s.army_units if u.station=="河北路")
    r = reorganize_xiang_to_jin(s, "河北路", 1.0)
    after = sum(u.troops for u in s.army_units if u.station=="河北路")
    print(f"[整编] {r['msg']} 河北总兵额 {before}->{after} -> {'OK' if before==after else 'FAIL(守恒)'}")

    # 7) 跑一月结算（含粮荒/金军南下/靖康判定/训练衰减）
    log = run_monthly_settlement(s)
    print(f"[结算] 跑了一月, log条数={len(log)}, treasury={s.treasury}, granary={s.granary}, 实体数={len(s.army_units)}")

    # 8) 事件/评价不崩
    from core.evaluation import evaluate_game
    ev = evaluate_game(s)
    print(f"[评价] 维度={list(ev.keys())[:4]} OK")

    # 9) 存档往返
    from core.save_load import save_game, load_game
    save_game(s, 99)
    s2 = load_game(99)
    g2 = sum(u.troops for u in s2.army_units)
    print(f"[存档] 重载兵额={g2} vs 原={got} -> {'OK' if g2==got else 'FAIL'}")
    # 清理临时验证存档：删除前确认存在并 try/except 兜底（避免 shim/回收站环境误报）
    import glob
    for f in glob.glob("saves/*99*.json"):
        if os.path.exists(f):
            try:
                os.remove(f)
            except OSError:
                pass

    print("DONE")

if __name__ == "__main__":
    main()
