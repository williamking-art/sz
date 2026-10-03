import io, sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
for f in ["_dev_tools/game-dev/tests/test_projects_tech_review.py",
          "_dev_tools/game-dev/tests/test_econ_price_review.py"]:
    t=open(f,encoding="utf-8").read().replace("_mg(s, r)[mdim]","_mg(s)[mdim]")
    open(f,"w",encoding="utf-8").write(t)
print("ok")
