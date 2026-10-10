"""How many NGA 1933-45 objects also have structured previous-owner rows (potential ground truth)?
Usage: python -I nga_structured.py <phase0/data dir>"""
import csv, sys
from pathlib import Path
csv.field_size_limit(10**9)
d = Path(sys.argv[1])
ids = {r["id"] for r in csv.DictReader(open(d / "nga_1933_45.csv", encoding="utf-8"))}
own, dated, overlap = set(), set(), set()
for r in csv.DictReader(open(d / "nga/objects_constituents.csv", encoding="utf-8")):
    if r["objectid"] in ids and r["role"] == "previous owner":
        own.add(r["objectid"])
        b, e = r["beginyear"], r["endyear"]
        if b or e:
            dated.add(r["objectid"])
            if int(b or 0) <= 1945 and int(e or 9999) >= 1933:
                overlap.add(r["objectid"])
print(f"1933-45 objects: {len(ids)}; with structured previous-owner rows: {len(own)}; "
      f"with dated owner rows: {len(dated)}; with an owner interval overlapping 1933-45: {len(overlap)}")
