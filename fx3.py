import io, sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
files=["_dev_tools/game-dev/tests/test_b2r47_civil_building.py",
       "_dev_tools/game-dev/tests/test_construction_order_independence.py",
       "_dev_tools/game-dev/tests/test_b2r4_agri_supply.py"]
for f in files:
    t=open(f,encoding="utf-8").read()
    t=(t.replace("from core.material_holding import allocate_by_demand",
                "from core.material_holding import supply_merchant_materials")
         .replace("allocate_by_demand(s)","supply_merchant_materials(s)")
         .replace("`allocate_by_demand()` 把仓**分摊到各州府**",
                  "`supply_merchant_materials()` 把仓里的料**搬进商人货栈**")
         .replace("`allocate_by_demand`（分摊到各州府）",
                  "`supply_merchant_materials`（搬进商人货栈）")
         .replace("营造只从**本地州府仓**取料，故须 `allocate_by_demand()`",
                  "营造只从**本地商人货栈**取料，故须 `supply_merchant_materials()`"))
    open(f,"w",encoding="utf-8").write(t)
print("done")
