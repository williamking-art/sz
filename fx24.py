import io, sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
f="_dev_tools/game-dev/tests/test_material_trade_cross.py"
t=open(f,encoding="utf-8").read()
H='''def _set_month(s, a):
    """把**绝对月序** `a` 写成真实字段 `year`/`month`（1..12）。

    🔴 `abs_month_index = year*12 + month`，逆运算须精确；
    余 0 时退到前一年 12 月，保证 `month` 落在合法区间。
    """
    a = int(a)
    y, m = a // 12, a % 12
    if m == 0:
        y, m = y - 1, 12
    s.year = int(y)
    s.month = int(m)


def _prep(s, dim, qty_seller, qty_buyer, wealth_buyer):'''
t=t.replace("def _prep(s, dim, qty_seller, qty_buyer, wealth_buyer):", H, 1)
open(f,"w",encoding="utf-8").write(t)
print("ok", "def _set_month" in t)
