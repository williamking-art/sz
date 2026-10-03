import io, sys, re
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
NEW = '''def _stock_local(s, dim14, qty, route="京畿路"):
    """往**本地商人货栈**放建材。

    🔴 E-1（用户 2026-10-02「建材也是商品啊」）：建材是**商品**，存量落在
    **商人 POP `goods`**（POP 挂载律），不再在仓里。
    施工侧（C-c）仍**只从本地取、取不到即缺料** ⇒ 物流仍有意义。
    """
    from core.material_holding import to_material_dim
    mdim = to_material_dim(dim14)
    assert mdim, f"{dim14!r} 应能翻译为建材维度"
    goods = s.prefectures[route]["pops"]["商人"]["goods"]
    goods[mdim] = int(qty)
    return mdim
'''
for f in ["_dev_tools/game-dev/tests/test_projects_tech_review.py",
          "_dev_tools/game-dev/tests/test_econ_price_review.py"]:
    t=open(f,encoding="utf-8").read()
    t=re.sub(r"def _stock_local\(s, dim14, qty, route=\"京畿路\"\):.*?\n    return mdim\n", NEW, t, flags=re.S)
    open(f,"w",encoding="utf-8").write(t)
    print(f, "->", "def _stock_local" in t)
