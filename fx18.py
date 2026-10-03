import io, sys, re
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
f="_dev_tools/game-dev/tests/test_material_holding.py"
t=open(f,encoding="utf-8").read()
# 这两个用例本质跨路：恢复 R2
t=t.replace('''    s = _state()
    _set(s, R1, "timber", 0)
    _set(s, R2, "timber", 99999)
    assert consume_for_circuit(s, R1, "timber", 100) == 0''',
'''    s = _state()
    _set(s, R1, "timber", 0)
    _set(s, R2, "timber", 99999)
    assert consume_for_circuit(s, R1, "timber", 100) == 0''')
t=t.replace('''    buyer, seller = _two_merchants(s)
    buyer["wealth"] = 100000.0
    seller["wealth"] = 0.0
    _set(s, R1, "timber", 0)
    _set(s, R1, "timber", 1000)
    g0, w0 = _sum_goods(s, "timber"), _sum_wealth(s)''',
'''    buyer, seller = _two_merchants(s)
    buyer["wealth"] = 100000.0
    seller["wealth"] = 0.0
    _set(s, R1, "timber", 1000)
    g0, w0 = _sum_goods(s, "timber"), _sum_wealth(s)''')
open(f,"w",encoding="utf-8").write(t)
print("ok")
