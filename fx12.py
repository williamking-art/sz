import io, sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
f="_dev_tools/game-dev/tests/test_b2r47_civil_building.py"
t=open(f,encoding="utf-8").read()
t=t.replace("from core.material_holding import supply_merchant_materials          # noqa: E402",
            "from core.material_holding import (MATERIAL_DIMS,                    # noqa: E402\n                                supply_merchant_materials)")
t=t.replace("for d in C.MATERIAL_DIMS:","for d in MATERIAL_DIMS:")
open(f,"w",encoding="utf-8").write(t)
print("ok")
