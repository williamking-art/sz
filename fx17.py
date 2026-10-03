import io, sys, re
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
f="_dev_tools/game-dev/tests/test_material_holding.py"
t=open(f,encoding="utf-8").read()
t=(t.replace('_set(s, R2, "timber"','_set(s, R1, "timber"')
      .replace('_set(s, R1, "timber", 0)','_set(s, R1, "timber", 0)')
      .replace('_set(s, R1, "iron", 10)','_set(s, R1, "iron", 10)'))
open(f,"w",encoding="utf-8").write(t)
print("ok")
