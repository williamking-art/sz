import io, sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
f="game/core/settlement_agri.py"
t=open(f,encoding="utf-8").read()
t=t.replace('    res = getattr(state, "resources", None)\n    land = getattr(state, "land", None)',
            '    land = getattr(state, "land", None)   # 建材已改走商人货栈（E-1），不再需要 res')
open(f,"w",encoding="utf-8").write(t)
print("ok", 'res = getattr(state, "resources", None)' in t)
