import io, sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
f="_dev_tools/game-dev/tests/test_transport_transit.py"
t=open(f,encoding="utf-8").read()
t=t.replace("import pytest\n\n_GAME","_GAME")
t=t.replace("from core.material_holding import (                              # noqa: E402\n    MATERIAL_DIMS, merchant_goods, supply_merchant_materials,\n)",
            "from core.material_holding import (                              # noqa: E402\n    merchant_goods, supply_merchant_materials,\n)")
open(f,"w",encoding="utf-8").write(t)
print("ok")
