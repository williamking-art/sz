import io, sys, re
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
f="_dev_tools/game-dev/tests/test_b2r47_civil_building.py"
t=open(f,encoding="utf-8").read()
t=(t.replace('assert s.resources[d]["stock"] == qty - int(summary["material_used"][d])',
             'assert _mgoods(s, _pref(s)).get(d, 0) == qty - int(summary["material_used"][d])')
      .replace('assert s.resources[d]["stock"] == qty - int(s2["material_used"].get(d, 0))',
               'assert _mgoods(s, _pref(s)).get(d, 0) == qty - int(s2["material_used"].get(d, 0))')
      .replace('真扣 `state.resources[dim]["stock"]`，缺料时**分文不动**',
               '真扣**本路商人货栈** `pops["商人"]["goods"][dim]`（E-1），缺料时**分文不动**'))
open(f,"w",encoding="utf-8").write(t)
print("patched")
