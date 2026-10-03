import io, sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
f="_dev_tools/game-dev/tests/test_b2r47_civil_building.py"
t=open(f,encoding="utf-8").read()
t=t.replace('def qty_get(res, dim):\n    return int(res.get(dim, 0) or 0)',
'''def qty_get(res, dim):
    return int(res.get(dim, 0) or 0)


def _mat_total(s, dim):
    """🔴 全域 Σ 建材（`apply_civil_construction` 遍历**所有路**，
    单路基准会错位，故必须按全域合计比对）。"""
    from core.material_holding import merchant_goods
    return sum(int((merchant_goods(s, r) or {}).get(dim, 0) or 0)
               for r in s.prefectures)''')
t=t.replace('''    for d in MATERIAL_DIMS:
        if d in summary["material_used"]:
            assert _mgoods(s, _pref(s)).get(d, 0) == qty_get(res, d) - int(summary["material_used"][d])''',
'''    for d in MATERIAL_DIMS:
        if d in summary["material_used"]:
            assert _mat_total(s, d) == qty_get(res, d) - int(summary["material_used"][d])''')
t=t.replace('''    for d in MATERIAL_DIMS:
        assert _mgoods(s, _pref(s)).get(d, 0) == qty_get(res, d) - int(s2["material_used"].get(d, 0))''',
'''    for d in MATERIAL_DIMS:
        assert _mat_total(s, d) == qty_get(res, d) - int(s2["material_used"].get(d, 0))''')
t=t.replace('res = dict(_mgoods(s, _pref(s)))   # E-1：建材基准取本路商人货栈',
            'res = {d: _mat_total(s, d) for d in MATERIAL_DIMS}   # E-1：全域 Σ 建材')
open(f,"w",encoding="utf-8").write(t)
print("ok")
