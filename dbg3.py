import sys,io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
sys.path.insert(0,r"D:\codebuddy\sz\game")
from core.game_state import GameState
from core.legacy_mechanic import init_legacies
from core.production_chain import settle_production_chain
from core.material_holding import supply_merchant_materials, merchant_goods
from core.material_trade import sell_material_across
s=GameState("史实"); init_legacies(s); settle_production_chain(s,[]); supply_merchant_materials(s)
s.month_index=10
merchant_goods(s,"京畿路")["timber"]=1000
merchant_goods(s,"两浙路")["timber"]=0
s.prefectures["京畿路"]["pops"]["商人"]["wealth"]=0.0
s.prefectures["两浙路"]["pops"]["商人"]["wealth"]=100000.0
r=sell_material_across(s,seller_route="京畿路",buyer_route="两浙路",dim="timber",qty=300,price=2.0)
print({k:v for k,v in r.items() if k!="batch"})
