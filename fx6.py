import io, sys, re
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
HELPER = '''

def _mg(s, route="京畿路"):
    """取某路**商人 POP `goods`**（E-1 后建材在这里）。"""
    return s.prefectures[route]["pops"]["商人"]["goods"]
'''
for f in ["_dev_tools/game-dev/tests/test_projects_tech_review.py",
          "_dev_tools/game-dev/tests/test_econ_price_review.py"]:
    t=open(f,encoding="utf-8").read()
    if "def _mg(" not in t:
        t=t.replace("def _stock_local(", HELPER.strip("\n")+"\n\n\ndef _stock_local(",1)
    open(f,"w",encoding="utf-8").write(t)
    print(f,"helper ok")
