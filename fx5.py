import io, sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
for f in ["_dev_tools/game-dev/tests/test_projects_tech_review.py",
          "_dev_tools/game-dev/tests/test_econ_price_review.py",
          "_dev_tools/game-dev/tests/test_step_gap_fills.py"]:
    t=open(f,encoding="utf-8").read()
    t=(t.replace('assert s.resources[mdim]["stock"] == 0, "材料应按供给率同比例消耗"',
                  'assert _mg(s, r)[mdim] == 0, "材料应按供给率同比例消耗"')
         .replace('assert s.resources[mdim]["stock"] == 9_900, "材料未扣"',
                  'assert _mg(s, r)[mdim] == 9_900, "材料未扣"'))
    open(f,"w",encoding="utf-8").write(t)
print("asserts patched")
