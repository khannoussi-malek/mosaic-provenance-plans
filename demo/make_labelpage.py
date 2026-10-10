"""Build the label-check page: silver-flagged test docs plus possible misses, with evidence.

Usage: python3 make_labelpage.py TEMPLATE.html OUT.html
The template holds the page; this script inlines the cases as JSON (replacing __CASES__).
"""
import csv
import json
import sys
from pathlib import Path

import score as s


def entries_for(keys_found, keys, notes):
    return [{"key": k, "entry": name, "note": notes.get(name, "")} for k in sorted(keys_found) for name in keys[k]]


def case(d, kind, keys, rx, notes, tier):
    found = set()
    owners = []
    for g in d["gold_owners"]:
        hit = s.match(s.forward(g["name"]), rx, keys, tier=tier)
        found |= hit
        owners.append({"name": g["name"], "begin": g["beginyear"], "end": g["endyear"], "listed": bool(hit)})
    return {"id": d["id"], "kind": kind, "title": d["title"], "artist": d["artist"], "text": d["provenance_text"],
            "owners": owners, "entries": entries_for(found, keys, notes)}


def main():
    template, out = sys.argv[1:3]
    docs = json.loads(s.TESTSET.read_text())
    keys, rx = s.load_keys(s.REDFLAG)
    notes = {r["name"]: r["notes"] for r in csv.DictReader(open(s.REDFLAG))}
    cases = []
    for d in docs:
        if s.silver_label(d, keys, rx) == "flagged":
            cases.append(case(d, "flagged", keys, rx, notes, "fullname"))
        elif any(s.match(s.forward(g["name"]), rx, keys, tier="cased") for g in d["gold_owners"]):
            cases.append(case(d, "near", keys, rx, notes, "cased"))
    (s.HERE / "data" / "label_cases.json").write_text(json.dumps(cases, indent=1, ensure_ascii=False))
    props = s.HERE / "data" / "label_proposals.json"  # plain-language proposals; the page shows only cases that have one
    if props.exists():
        by_id = {p["id"]: p for p in json.loads(props.read_text())}
        cases = [dict(c, **by_id[c["id"]]) for c in cases if c["id"] in by_id]
    html = Path(template).read_text().replace("__CASES__", json.dumps(cases, ensure_ascii=False).replace("</", "<\\/"))
    Path(out).write_text(html)
    print(f"{sum(c['kind'] == 'flagged' for c in cases)} flagged + {sum(c['kind'] == 'near' for c in cases)} near-miss cases -> {out}")


if __name__ == "__main__":
    main()
