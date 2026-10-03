import io, sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
f="_dev_tools/game-dev/tests/test_material_holding.py"
t=open(f,encoding="utf-8").read()
# _two_merchants 改为同路两个不同 POP（原为跨路，现被 C-c 护栏拒绝）
t=t.replace('''def _two_merchants(s):
    return merchant_of(s, R1), merchant_of(s, R2)''',
'''def _two_merchants(s):
    """同路的**两个不同 POP**（买方士绅 / 卖方商人）。

    🔴 C-c 护栏：`trade_material` **拒绝跨州府**（跨路请用
    `core.material_trade.sell_material_across` 走真实在途），
    故同路成交用例必须用同路的不同 POP，否则是自成交。
    """
    return (s.prefectures[R1]["pops"]["士绅"],
            s.prefectures[R1]["pops"]["商人"])''')
open(f,"w",encoding="utf-8").write(t)
print("ok")
