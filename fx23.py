import io, sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
f="_dev_tools/game-dev/tests/test_transport_transit.py"
t=open(f,encoding="utf-8").read()
t=t.replace('''def _set_month(s, m):
    """设定绝对月序（走真实字段 year/month）。"""
    s.year = 1101
    s.month = 1 + (int(m) % 12)
    s._abs = int(m)''',
'''def _set_month(s, a):
    """把**绝对月序** `a` 写成真实字段 `year`/`month`（1..12）。

    🔴 逆运算必须精确：`abs_month_index = year*12 + month`，
    故 `year = a // 12`、`month = a % 12`（余 0 时退到前一年 12 月，
    保证 `month` 落在游戏合法的 1..12）。
    """
    a = int(a)
    y, m = a // 12, a % 12
    if m == 0:
        y, m = y - 1, 12
    s.year = int(y)
    s.month = int(m)''')
open(f,"w",encoding="utf-8").write(t)

g="_dev_tools/game-dev/tests/test_material_trade_cross.py"
t2=open(g,encoding="utf-8").read()
t2=t2.replace('    s.month_index = 10\n','')
open(g,"w",encoding="utf-8").write(t2)
print("ok")
