import io, sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
f="_dev_tools/game-dev/tests/test_b2r47_civil_building.py"
t=open(f,encoding="utf-8").read()
t=t.replace('res = {d: slot["stock"] for d, slot in s.resources.items() if isinstance(slot, dict)}',
            'res = dict(_mgoods(s, _pref(s)))   # E-1：建材基准取本路商人货栈')
open(f,"w",encoding="utf-8").write(t)
print("patched", t.count('res = dict(_mgoods'))
