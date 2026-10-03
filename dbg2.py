import sys, io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
sys.path.insert(0, r"D:\codebuddy\sz\game")
from core.game_state import GameState
from core.legacy_mechanic import init_legacies
from core.production_chain import settle_production_chain
from core.material_holding import supply_merchant_materials, material_holding_for_circuit
s=GameState("史实"); init_legacies(s); settle_production_chain(s,[]); supply_merchant_materials(s)
print("仓 stock(iron) =", s.resources["iron"]["stock"])
print("京畿路商人 iron =", material_holding_for_circuit(s,"京畿路","iron"))
g=s.prefectures["京畿路"]["pops"]["商人"]["goods"]
print("商人 goods keys =", sorted(g.keys()))
print("商人 iron 值 =", g.get("iron"))
