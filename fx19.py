import io, sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
f="_dev_tools/game-dev/tests/test_material_holding.py"
t=open(f,encoding="utf-8").read()
t=t.replace("    material_holding_for_circuit, merchant_goods, merchant_of,\n",
            "    material_holding_for_circuit, merchant_goods,\n")
open(f,"w",encoding="utf-8").write(t)
print("ok")
