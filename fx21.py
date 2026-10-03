import io, sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
f="_dev_tools/game-dev/tests/test_transport_transit.py"
t=open(f,encoding="utf-8").read()
t=t.replace('''    res = transport.dispatch(s, frm=A, to=FAR, dim="timber", qty=300)
    assert res["ok"] and res["arrive_month"] > 10
    src_before = _have(s, A, "timber")''',
'''    dst_before = _have(s, FAR, "timber")   # 目的地原有量（配货而来，非 0）
    res = transport.dispatch(s, frm=A, to=FAR, dim="timber", qty=300)
    assert res["ok"] and res["arrive_month"] > 10
    src_before = _have(s, A, "timber")''')
t=t.replace('''    s2.month_index = int(b["arrive_month"])
    transport.arrive_due(s2)
    assert int((merchant_goods(s2, "两浙路") or {})["timber"]) == 300''',
'''    s2.month_index = int(b["arrive_month"])
    transport.arrive_due(s2)
    assert _have(s2, FAR, "timber") == dst_before + 300, "到货应叠加在原有量上"''')
open(f,"w",encoding="utf-8").write(t)
print("ok")
