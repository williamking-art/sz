# -*- coding: utf-8 -*-
import json, os
d = json.load(open(os.path.join(os.path.dirname(__file__), "audit_dimension_replay.json"), encoding="utf-8"))
print("start_year", d["start_year"])
print("final", d["final"])
print("trajectory (year-month | granary | treasury | inner | price | ms | ref | msupply):")
for s in d["trajectory"]:
    print(f"{s['year']}-{s['month']:02d} | {s['granary']:>9.0f} | {s['treasury']:>11.0f} | "
          f"{s['inner']:>9.0f} | {s['grain_price']:5.2f} | {s['satisfaction']} | "
          f"{s['refugees']:>7.0f} | {s['money_supply']:>11.0f}")
