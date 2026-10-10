"""QR-6: recompute the first N test documents into an empty cache and compare with the original P1 answers.

Usage: MOSAIC_CACHE=<empty dir> python3 repro_check.py [N]
"""
import json
import os
import sys

import extract
import score as s

n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
assert "MOSAIC_CACHE" in os.environ, "set MOSAIC_CACHE to an empty directory"
docs = json.loads(s.TESTSET.read_text())[:n]
orig = {str(r["id"]): r for r in json.loads((s.HERE / "out" / "run_P1.json").read_text())}
same_text = same_events = 0
for d in docs:
    r = extract.extract("qwen3:8b", d)
    a, b = orig[str(d["id"])], r
    same_events += [(e["owner"], e.get("year")) for e in a["events"]] == [(e["owner"], e.get("year")) for e in b["events"]]
    same_text += a["events"] == b["events"] and a["error"] == b["error"]
    print(f"{d['id']}: identical={a['events'] == b['events']}", flush=True)
print(f"REPRO {n} docs: identical output {same_text}/{n}, identical owners+years {same_events}/{n}")
