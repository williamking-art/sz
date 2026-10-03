import io, sys
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
f="_dev_tools/game-dev/tests/test_transport_transit.py"
t=open(f,encoding="utf-8").read()
t=(t.replace("from core.save_load import load_state, save_state",
             "from core.save_load import load_game, save_game")
      .replace("blob = save_state(s)\n    s2 = load_state(blob)",
             "assert save_game(s, slot=97)\n    s2 = load_game(slot=97)")
      .replace("    blob = save_state(s)\n    if isinstance(blob, dict):\n        blob.pop(\"material_transit\", None)\n    s2 = load_state(blob)",
             "    assert save_game(s, slot=98)\n    s2 = load_game(slot=98)"))
open(f,"w",encoding="utf-8").write(t)
print("ok", "save_state" in t)
