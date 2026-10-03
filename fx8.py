import io, sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
f="_dev_tools/game-dev/tests/test_step_gap_fills.py"
t=open(f,encoding="utf-8").read()
HELPER='''

def _mg(s, route="京畿路"):
    """取某路**商人 POP `goods`**（E-1 后建材在这里）。"""
    return s.prefectures[route]["pops"]["商人"]["goods"]


def _stock_local(s, dim14, qty, route="京畿路"):
    """往**本地商人货栈**放建材（E-1）。"""
    from core.material_holding import to_material_dim
    mdim = to_material_dim(dim14)
    assert mdim, f"{dim14!r} 应能翻译为建材维度"
    _mg(s, route)[mdim] = int(qty)
    return mdim

'''
if "def _stock_local(" not in t:
    # 插到文件首个 def 之前
    i=t.index("\ndef ")
    t=t[:i]+HELPER+t[i:]
t=(t.replace('s.resources.setdefault("铁", {"stock": 10_000, "cap": 100_000})','mdim = _stock_local(s, "铁", 10_000)')
     .replace('assert s.resources["铁"]["stock"] == 9_900, "材料未扣"','assert _mg(s)[mdim] == 9_900, "材料未扣"'))
open(f,"w",encoding="utf-8").write(t)
print("ok")
