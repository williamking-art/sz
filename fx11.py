import io, sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
f="_dev_tools/game-dev/tests/test_b2r47_civil_building.py"
t=open(f,encoding="utf-8").read()
OLD1='''    for d, qty in res.items():
        if d in summary["material_used"]:
            assert _mgoods(s, _pref(s)).get(d, 0) == qty - int(summary["material_used"][d])'''
NEW1='''    for d in C.MATERIAL_DIMS:
        if d in summary["material_used"]:
            assert _mgoods(s, _pref(s)).get(d, 0) == qty_get(res, d) - int(summary["material_used"][d])'''
OLD2='''    for d, qty in res.items():
        assert _mgoods(s, _pref(s)).get(d, 0) == qty - int(s2["material_used"].get(d, 0))'''
NEW2='''    for d in C.MATERIAL_DIMS:
        assert _mgoods(s, _pref(s)).get(d, 0) == qty_get(res, d) - int(s2["material_used"].get(d, 0))'''
t=t.replace(OLD1,NEW1).replace(OLD2,NEW2)
t=t.replace('res = dict(_mgoods(s, _pref(s)))   # E-1：建材基准取本路商人货栈',
            'res = dict(_mgoods(s, _pref(s)))   # E-1：建材基准取本路商人货栈')
# 补 qty_get 辅助
t=t.replace('def _mgoods(s, pref):',
            'def qty_get(res, dim):\n    return int(res.get(dim, 0) or 0)\n\n\ndef _mgoods(s, pref):',1)
open(f,"w",encoding="utf-8").write(t)
print("ok")
