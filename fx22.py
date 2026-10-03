import io, sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
for f in ["_dev_tools/game-dev/tests/test_transport_transit.py",
          "_dev_tools/game-dev/tests/test_material_trade_cross.py"]:
    t=open(f,encoding="utf-8").read()
    t=(t.replace('def _set_month(s, m):\n    s.month_index = int(m)',
                 'def _set_month(s, m):\n    """设定绝对月序（走真实字段 year/month）。"""\n'
                 '    s.year = 1101\n    s.month = 1 + (int(m) % 12)\n'
                 '    s._abs = int(m)')
      .replace('s.month_index = 10','_set_month(s, 10)')
      .replace('s.month_index = int(res["arrive_month"])','_set_month(s, int(res["arrive_month"]))')
      .replace('s2.month_index = int(b["arrive_month"])','s2.year=1101; s2.month=1+(int(b["arrive_month"])%12)')
      .replace('    s.month_index = 10\n',''))
    open(f,"w",encoding="utf-8").write(t)
print("ok")
